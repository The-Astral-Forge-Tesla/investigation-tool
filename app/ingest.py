import re
import hashlib
from collections import Counter
from pathlib import Path
from typing import Dict, Tuple

import pdfplumber
import pytesseract
from PIL import Image
import spacy
from tqdm import tqdm

from app.db import connect

# -----------------------------
# Model load (one-time)
# -----------------------------
try:
    NLP = spacy.load("en_core_web_sm")
except Exception:
    NLP = None

# -----------------------------
# Safety + performance defaults
# -----------------------------
MAX_FILE_SIZE_MB = 200
MAX_FILE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

TEXT_EXTS = {".txt", ".md", ".log"}
IMG_EXTS = {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{3}\)?[\s-]?)?\d{3}[\s-]?\d{4}\b")
URL_RE = re.compile(r"https?://\S+")

AIRCRAFT_REG_RE = re.compile(
    r"\b("
    r"(?:N\d{1,5}[A-Z]{0,2})"
    r"|(?:G-[A-Z]{4})"
    r"|(?:D-[A-Z]{4})"
    r"|(?:F-[A-Z]{4})"
    r"|(?:I-[A-Z]{4})"
    r"|(?:C-[A-Z]{3}[A-Z0-9])"
    r")\b"
)
IMO_RE = re.compile(r"\bIMO\s?\d{7}\b", re.IGNORECASE)


# -----------------------------
# Helpers
# -----------------------------
def normalize_text(s: str) -> str:
    s = (s or "").replace("\x00", " ")
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def norm_key(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def content_hash(text: str) -> str:
    """
    Generates a stable fingerprint for a page's text.
    If the extracted text is identical (or near identical after normalization),
    the hash will match and we can skip re-processing.
    """
    t = normalize_text(text)
    return hashlib.sha256(t.encode("utf-8", errors="ignore")).hexdigest()


def hash_exists(cur, h: str) -> bool:
    cur.execute("SELECT 1 FROM documents WHERE content_hash=? LIMIT 1", (h,))
    return cur.fetchone() is not None


# -----------------------------
# Main ingest entry point
# -----------------------------
def ingest_all(raw_dir: Path, db_path: Path):
    raw_dir = raw_dir.resolve()
    conn = connect(db_path)
    cur = conn.cursor()

    files = [p for p in raw_dir.rglob("*") if p.is_file()]
    if not files:
        print("No files found in data/raw. Add files and re-run.")
        conn.close()
        return

    # One transaction for speed
    cur.execute("BEGIN;")

    skipped = 0
    inserted = 0

    for file in tqdm(files, desc="Ingesting"):
        try:
            if file.is_symlink():
                continue
            if file.stat().st_size > MAX_FILE_BYTES:
                continue

            suffix = file.suffix.lower()

            if suffix == ".pdf":
                s, i = ingest_pdf(cur, file)
                skipped += s
                inserted += i
            elif suffix in IMG_EXTS:
                s, i = ingest_image(cur, file)
                skipped += s
                inserted += i
            elif suffix in TEXT_EXTS:
                s, i = ingest_text(cur, file)
                skipped += s
                inserted += i
            else:
                continue

        except Exception:
            # keep ingestion resilient (bad files shouldn't stop the run)
            continue

    conn.commit()
    conn.close()

    print(f"Ingestion complete. Inserted={inserted}, Skipped(existing)={skipped}")


# -----------------------------
# Ingest by type
# -----------------------------
def ingest_pdf(cur, file: Path) -> Tuple[int, int]:
    skipped = 0
    inserted = 0

    with pdfplumber.open(str(file)) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            text = normalize_text(text)
            if not text:
                continue

            h = content_hash(text)
            if hash_exists(cur, h):
                skipped += 1
                continue

            doc_id = insert_document(cur, file.name, i, text, h)
            extract_and_link(cur, doc_id, file.name, i, text)
            inserted += 1

    return skipped, inserted


def ingest_image(cur, file: Path) -> Tuple[int, int]:
    # quick skip tiny files (often icons/noise)
    if file.stat().st_size < 5000:
        return 1, 0

    text = pytesseract.image_to_string(Image.open(file)) or ""
    text = normalize_text(text)
    if not text:
        return 0, 0

    h = content_hash(text)
    if hash_exists(cur, h):
        return 1, 0

    doc_id = insert_document(cur, file.name, 1, text, h)
    extract_and_link(cur, doc_id, file.name, 1, text)
    return 0, 1


def ingest_text(cur, file: Path) -> Tuple[int, int]:
    text = normalize_text(file.read_text(errors="ignore"))
    if not text:
        return 0, 0

    h = content_hash(text)
    if hash_exists(cur, h):
        return 1, 0

    doc_id = insert_document(cur, file.name, 1, text, h)
    extract_and_link(cur, doc_id, file.name, 1, text)
    return 0, 1


# -----------------------------
# DB insert + extraction
# -----------------------------
def insert_document(cur, filename: str, page: int, content: str, h: str) -> int:
    cur.execute(
        "INSERT INTO documents(filename, page, content, content_hash) VALUES (?, ?, ?, ?)",
        (filename, int(page), content, h),
    )
    return int(cur.lastrowid)


def extract_and_link(cur, doc_id: int, filename: str, page: int, text: str):
    # --- Entities ---
    ent_counts: Counter[Tuple[str, str, str]] = Counter()  # (text, label, normalized)

    # Gate spaCy on garbage/small text (saves hours)
    if NLP is not None and len(text) >= 200:
        alpha_ratio = sum(c.isalpha() for c in text) / max(len(text), 1)
        if alpha_ratio >= 0.30:
            doc = NLP(text)
            for ent in doc.ents:
                t = ent.text.strip()
                if t:
                    ent_counts[(t, ent.label_, norm_key(t))] += 1

    for email in EMAIL_RE.findall(text):
        ent_counts[(email, "EMAIL", norm_key(email))] += 1

    for phone in PHONE_RE.findall(text):
        ent_counts[(phone, "PHONE", norm_key(phone))] += 1

    for url in URL_RE.findall(text):
        ent_counts[(url, "URL", norm_key(url))] += 1

    # Insert entities + link
    entity_ids: Dict[Tuple[str, str], int] = {}
    for (t, lab, norm), c in ent_counts.items():
        cur.execute(
            "INSERT OR IGNORE INTO entities(text, label, normalized) VALUES (?, ?, ?)",
            (t, lab, norm),
        )
        cur.execute("SELECT id FROM entities WHERE normalized=? AND label=?", (norm, lab))
        row = cur.fetchone()
        if not row:
            continue
        eid = int(row[0])
        entity_ids[(norm, lab)] = eid

        cur.execute(
            """
            INSERT INTO doc_entities(doc_id, entity_id, count)
            VALUES (?, ?, ?)
            ON CONFLICT(doc_id, entity_id) DO UPDATE SET count = count + excluded.count
            """,
            (doc_id, eid, int(c)),
        )

    # --- Assets ---
    asset_counts: Counter[Tuple[str, str, str]] = Counter()  # (type, value, norm)

    for reg in AIRCRAFT_REG_RE.findall(text):
        asset_counts[("AIRCRAFT_REG", reg, norm_key(reg))] += 1

    for imo in IMO_RE.findall(text):
        asset_counts[("IMO", imo, norm_key(imo))] += 1

    for (atype, aval, anorm), c in asset_counts.items():
        cur.execute(
            "INSERT OR IGNORE INTO assets(asset_type, asset_value, normalized) VALUES (?, ?, ?)",
            (atype, aval, anorm),
        )
        cur.execute("SELECT id FROM assets WHERE asset_type=? AND normalized=?", (atype, anorm))
        row = cur.fetchone()
        if not row:
            continue
        aid = int(row[0])

        cur.execute(
            """
            INSERT INTO doc_assets(doc_id, asset_id, count)
            VALUES (?, ?, ?)
            ON CONFLICT(doc_id, asset_id) DO UPDATE SET count = count + excluded.count
            """,
            (doc_id, aid, int(c)),
        )
