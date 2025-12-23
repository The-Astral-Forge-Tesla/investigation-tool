from __future__ import annotations
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional

from app.db import connect

@dataclass
class REEIngestReport:
    files_processed: int
    rows_loaded: int
    rows_inserted: int
    warnings: List[str]

def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())

def ingest_registry_folder(db_path: Path, registries_dir: Path) -> REEIngestReport:
    """
    Offline-first registry ingestion.
    CSV format requirements (minimum columns):
      registry_name,record_type,subject_type,subject_value,field_key,field_value,primary_source
    Optional:
      secondary_source
    Notes:
      - subject_type must be ENTITY or ASSET
      - subject_value is normalized into subject_norm
      - statement_type forced to FACT, confidence=1.0
    """
    warnings: List[str] = []
    files = sorted([p for p in registries_dir.glob("*.csv") if p.is_file()])
    if not files:
        return REEIngestReport(files_processed=0, rows_loaded=0, rows_inserted=0, warnings=["No CSV files found in data/registries/"])

    conn = connect(db_path)
    cur = conn.cursor()

    rows_loaded = 0
    rows_inserted = 0

    cur.execute("BEGIN;")

    for f in files:
        try:
            with f.open("r", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                required = {"registry_name","record_type","subject_type","subject_value","field_key","field_value","primary_source"}
                if not required.issubset(set(reader.fieldnames or [])):
                    warnings.append(f"{f.name}: missing required columns. Required: {sorted(required)}")
                    continue

                for row in reader:
                    rows_loaded += 1
                    registry_name = (row.get("registry_name") or "").strip()
                    record_type = (row.get("record_type") or "").strip()
                    subject_type = (row.get("subject_type") or "").strip().upper()
                    subject_value = (row.get("subject_value") or "").strip()
                    field_key = (row.get("field_key") or "").strip()
                    field_value = (row.get("field_value") or "").strip()
                    primary_source = (row.get("primary_source") or f.name).strip()
                    secondary_source = (row.get("secondary_source") or "").strip() or None

                    if subject_type not in ("ENTITY","ASSET"):
                        warnings.append(f"{f.name}: invalid subject_type '{subject_type}' (must be ENTITY or ASSET)")
                        continue
                    if not (registry_name and record_type and subject_value and field_key and field_value and primary_source):
                        continue

                    subject_norm = _norm(subject_value)

                    cur.execute(
                        """
                        INSERT OR IGNORE INTO registry_records(
                          registry_name, record_type, subject_type, subject_norm,
                          field_key, field_value, statement_type, confidence,
                          primary_source, secondary_source
                        )
                        VALUES (?, ?, ?, ?, ?, ?, 'FACT', 1.0, ?, ?)
                        """,
                        (registry_name, record_type, subject_type, subject_norm, field_key, field_value, primary_source, secondary_source),
                    )
                    rows_inserted += cur.rowcount

        except Exception as e:
            warnings.append(f"{f.name}: failed to read ({e})")

    conn.commit()
    conn.close()

    return REEIngestReport(files_processed=len(files), rows_loaded=rows_loaded, rows_inserted=rows_inserted, warnings=warnings)

def lookup_registry_records(db_path: Path, subject_type: str, subject_value: str, limit: int = 200) -> List[Dict[str, Any]]:
    conn = connect(db_path)
    cur = conn.cursor()
    subject_type = subject_type.strip().upper()
    subject_norm = _norm(subject_value)

    cur.execute(
        """
        SELECT registry_name, record_type, field_key, field_value, primary_source, secondary_source
        FROM registry_records
        WHERE subject_type=? AND subject_norm=?
        LIMIT ?
        """,
        (subject_type, subject_norm, int(limit)),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "registry_name": r[0],
            "record_type": r[1],
            "field_key": r[2],
            "field_value": r[3],
            "primary_source": r[4],
            "secondary_source": r[5],
        }
        for r in rows
    ]
