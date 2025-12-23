import re
from pathlib import Path
from typing import List, Tuple, Dict, Any

from app.db import connect

def sanitize_fts_query(q: str) -> str:
    q = (q or "").strip()
    q = q.replace("\x00", " ")
    q = re.sub(r"\s+", " ", q)
    q = re.sub(r'[^\w\s"*\-]', " ", q)
    q = re.sub(r"\s+", " ", q).strip()
    if not q:
        return ""
    if '"' in q:
        return q
    parts = q.split()
    if len(parts) <= 1:
        return q
    return " AND ".join(parts)

def keyword_search(db_path: Path, query: str, limit: int = 200) -> List[Tuple[str, int, str]]:
    q = sanitize_fts_query(query)
    if not q:
        return []
    conn = connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT d.filename, d.page,
               snippet(documents_fts, 0, '[', ']', '...', 20) AS snip
        FROM documents_fts
        JOIN documents d ON documents_fts.rowid = d.id
        WHERE documents_fts MATCH ?
        LIMIT ?
        """,
        (q, int(limit)),
    )
    rows = cur.fetchall()
    conn.close()
    return [(r[0], int(r[1]), r[2]) for r in rows]

def list_top_entities(db_path: Path, label: str, limit: int = 200):
    conn = connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT e.text, e.label, SUM(de.count) as total_count
        FROM entities e
        JOIN doc_entities de ON de.entity_id = e.id
        WHERE e.label = ?
        GROUP BY e.id
        ORDER BY total_count DESC
        LIMIT ?
        """,
        (label, int(limit)),
    )
    rows = cur.fetchall()
    conn.close()
    return [(r[0], r[1], int(r[2])) for r in rows]

def search_entity_mentions(db_path: Path, entity_text: str, label: str, limit: int = 300):
    conn = connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT d.filename, d.page, d.content
        FROM entities e
        JOIN doc_entities de ON de.entity_id = e.id
        JOIN documents d ON d.id = de.doc_id
        WHERE e.text = ? AND e.label = ?
        LIMIT ?
        """,
        (entity_text, label, int(limit)),
    )
    rows = cur.fetchall()
    conn.close()
    return [(r[0], int(r[1]), r[2]) for r in rows]

def list_top_assets(db_path: Path, asset_type: str, limit: int = 200):
    conn = connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT a.asset_value, a.asset_type, SUM(da.count) as total_count
        FROM assets a
        JOIN doc_assets da ON da.asset_id = a.id
        WHERE a.asset_type = ?
        GROUP BY a.id
        ORDER BY total_count DESC
        LIMIT ?
        """,
        (asset_type, int(limit)),
    )
    rows = cur.fetchall()
    conn.close()
    return [(r[0], r[1], int(r[2])) for r in rows]

def search_asset_mentions(db_path: Path, asset_value: str, asset_type: str, limit: int = 300):
    conn = connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT d.filename, d.page, d.content
        FROM assets a
        JOIN doc_assets da ON da.asset_id = a.id
        JOIN documents d ON d.id = da.doc_id
        WHERE a.asset_value = ? AND a.asset_type = ?
        LIMIT ?
        """,
        (asset_value, asset_type, int(limit)),
    )
    rows = cur.fetchall()
    conn.close()
    return [(r[0], int(r[1]), r[2]) for r in rows]

def list_events(db_path: Path, limit: int = 200):
    conn = connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, date_text, location_text, filename, page
        FROM events
        ORDER BY id DESC
        LIMIT ?
        """,
        (int(limit),),
    )
    rows = cur.fetchall()
    conn.close()
    return [(int(r[0]), r[1], r[2], r[3], int(r[4])) for r in rows]

def get_event_detail(db_path: Path, event_id: int) -> Dict[str, Any]:
    conn = connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT date_text, location_text, filename, page FROM events WHERE id=?", (int(event_id),))
    row = cur.fetchone()
    if not row:
        conn.close()
        return {}

    date_text, loc_text, filename, page = row

    cur.execute(
        """
        SELECT e.text, e.label
        FROM event_entities ee
        JOIN entities e ON e.id = ee.entity_id
        WHERE ee.event_id=?
        """,
        (int(event_id),),
    )
    ents = [(r[0], r[1]) for r in cur.fetchall()]

    cur.execute(
        """
        SELECT a.asset_value, a.asset_type
        FROM event_assets ea
        JOIN assets a ON a.id = ea.asset_id
        WHERE ea.event_id=?
        """,
        (int(event_id),),
    )
    assets = [(r[0], r[1]) for r in cur.fetchall()]

    conn.close()
    return {
        "event_id": int(event_id),
        "date_text": date_text,
        "location_text": loc_text,
        "filename": filename,
        "page": int(page),
        "entities": ents,
        "assets": assets,
    }
