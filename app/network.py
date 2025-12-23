from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Tuple, Any
from pathlib import Path

from app.db import connect
from app.fil import FILStatement, StatementType, SourceRef
from app.assertion import enforce_assertion_boundaries

@dataclass
class NetworkSummary:
    statements: List[FILStatement]

def build_network_exposure(
    db_path: Path,
    focus_entity_text: str | None = None,
    max_assets: int = 10,
    max_events: int = 50
) -> NetworkSummary:
    """
    Exposes structure without accusations.
    - Assets ↔ Entities
    - Entities ↔ Events
    - Overlaps over time (based on derived events)
    """
    conn = connect(db_path)
    cur = conn.cursor()

    # resolve focus entity -> normalized
    focus_norm = None
    if focus_entity_text:
        cur.execute("SELECT normalized FROM entities WHERE text=? LIMIT 1", (focus_entity_text,))
        row = cur.fetchone()
        if row:
            focus_norm = row[0]

    # Pull assets and entity overlaps via events
    # Strategy: find events with focus entity (if provided), then summarize overlaps
    statements: List[FILStatement] = []

    if focus_norm:
        cur.execute(
            """
            SELECT ev.id, ev.date_text, ev.location_text, ev.filename, ev.page
            FROM events ev
            JOIN event_entities ee ON ee.event_id = ev.id
            JOIN entities e ON e.id = ee.entity_id
            WHERE e.normalized = ? AND e.label IN ('PERSON','ORG')
            ORDER BY ev.id DESC
            LIMIT ?
            """,
            (focus_norm, int(max_events)),
        )
    else:
        cur.execute(
            """
            SELECT id, date_text, location_text, filename, page
            FROM events
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(max_events),),
        )

    events = cur.fetchall()

    # Summarize overlaps per event: count unique entities + assets
    for (ev_id, dtext, ltext, fname, page) in events:
        cur.execute(
            """
            SELECT COUNT(DISTINCT e.id)
            FROM event_entities ee
            JOIN entities e ON e.id = ee.entity_id
            WHERE ee.event_id=? AND e.label IN ('PERSON','ORG')
            """,
            (int(ev_id),),
        )
        ent_count = int((cur.fetchone() or [0])[0])

        cur.execute(
            """
            SELECT COUNT(DISTINCT a.id)
            FROM event_assets ea
            JOIN assets a ON a.id = ea.asset_id
            WHERE ea.event_id=?
            """,
            (int(ev_id),),
        )
        asset_count = int((cur.fetchone() or [0])[0])

        src = SourceRef(filename=fname, page=int(page), snippet=f"Derived event: date={dtext}, location={ltext}")

        # FACT: what exists in documents (event derivation is still document-anchored)
        statements.append(
            FILStatement(
                statement_type=StatementType.FACT,
                confidence_score=0.85,
                text=f"Event structure detected on {fname} page {int(page)}: date='{dtext}' location='{ltext}', with {ent_count} linked entities and {asset_count} linked assets.",
                primary_sources=[src],
                secondary_sources=None,
                metadata={"event_id": int(ev_id)},
            )
        )

    # Aggregate: entities ↔ assets overlaps across selected events
    # Top overlaps: which assets appear across multiple events
    cur.execute(
        """
        SELECT a.asset_type, a.asset_value, COUNT(DISTINCT ev.id) AS event_count
        FROM assets a
        JOIN event_assets ea ON ea.asset_id = a.id
        JOIN events ev ON ev.id = ea.event_id
        GROUP BY a.id
        HAVING event_count >= 2
        ORDER BY event_count DESC
        LIMIT ?
        """,
        (int(max_assets),),
    )
    asset_overlaps = cur.fetchall()

    if asset_overlaps:
        # INFERENCE: "overlap density suggests reuse pattern" (careful language)
        statements.append(
            FILStatement(
                statement_type=StatementType.INFERENCE,
                confidence_score=0.65,
                text="Repeated asset reuse across multiple distinct events is consistent with centralized control or operational reuse patterns. This is a pattern-based inference, not a claim of intent.",
                primary_sources=[],
                secondary_sources=None,
                metadata={"top_asset_overlaps": [{"asset_type": t, "asset_value": v, "event_count": int(c)} for (t, v, c) in asset_overlaps]},
            )
        )

        # IMPLICATION: structure without naming faces
        statements.append(
            FILStatement(
                statement_type=StatementType.IMPLICATION,
                confidence_score=0.9,
                text="The same assets appear across multiple events in the dataset. This indicates structural overlap across documents and time, without asserting identity, intent, or wrongdoing.",
                primary_sources=[],
                secondary_sources=None,
                metadata={"top_asset_overlaps": [{"asset_type": t, "asset_value": v, "event_count": int(c)} for (t, v, c) in asset_overlaps]},
            )
        )

    conn.close()
    return NetworkSummary(statements=enforce_assertion_boundaries(statements))
