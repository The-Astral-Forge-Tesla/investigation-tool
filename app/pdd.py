from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List, Tuple
from pathlib import Path
import math

from app.db import connect
from app.fil import FILStatement, StatementType, SourceRef
from app.assertion import enforce_assertion_boundaries

@dataclass
class PDDResult:
    statements: List[FILStatement]

def _safe_log(x: float) -> float:
    return math.log(x) if x > 0 else -999.0

def _approx_p_value_from_overlap(N: int, a: int, b: int, k: int) -> float:
    """
    Very conservative approximation: overlap density score mapped to pseudo p-value.
    Not claiming statistical proof—just "how many coincidences" framing.
    """
    if N <= 0:
        return 1.0
    expected = (a * b) / max(N, 1)
    if expected <= 0:
        return 0.5 if k > 0 else 1.0

    # ratio of observed to expected
    ratio = k / expected if expected > 0 else 999.0
    # squash to (0,1] (smaller => less likely random)
    p = 1.0 / (1.0 + max(0.0, ratio - 1.0) * 2.5)
    return max(0.0001, min(1.0, p))

def analyze_overlap_randomness(
    db_path: Path,
    entity_a: str,
    entity_b: str,
    scope: str = "EVENTS"  # EVENTS or DOCS
) -> PDDResult:
    """
    Answers: "How many independent coincidences would need to exist for this to be random?"
    It does NOT accuse. It provides overlap counts and a conservative improbability framing.
    """
    conn = connect(db_path)
    cur = conn.cursor()

    # Resolve normalized
    cur.execute("SELECT normalized FROM entities WHERE text=? LIMIT 1", (entity_a,))
    ra = cur.fetchone()
    cur.execute("SELECT normalized FROM entities WHERE text=? LIMIT 1", (entity_b,))
    rb = cur.fetchone()

    if not ra or not rb:
        conn.close()
        return PDDResult(statements=enforce_assertion_boundaries([
            FILStatement(
                statement_type=StatementType.FACT,
                confidence_score=1.0,
                text="One or both entities were not found in the dataset. Ingest data first or check spelling.",
                primary_sources=[],
            )
        ]))

    na, nb = ra[0], rb[0]

    stmts: List[FILStatement] = []

    if scope.upper() == "DOCS":
        cur.execute("SELECT COUNT(*) FROM documents")
        N = int((cur.fetchone() or [0])[0])

        cur.execute(
            """
            SELECT COUNT(DISTINCT d.id)
            FROM documents d
            JOIN doc_entities de ON de.doc_id = d.id
            JOIN entities e ON e.id = de.entity_id
            WHERE e.normalized=? AND e.label IN ('PERSON','ORG')
            """,
            (na,),
        )
        a = int((cur.fetchone() or [0])[0])

        cur.execute(
            """
            SELECT COUNT(DISTINCT d.id)
            FROM documents d
            JOIN doc_entities de ON de.doc_id = d.id
            JOIN entities e ON e.id = de.entity_id
            WHERE e.normalized=? AND e.label IN ('PERSON','ORG')
            """,
            (nb,),
        )
        b = int((cur.fetchone() or [0])[0])

        cur.execute(
            """
            SELECT COUNT(DISTINCT d.id)
            FROM documents d
            JOIN doc_entities de1 ON de1.doc_id = d.id
            JOIN entities e1 ON e1.id = de1.entity_id
            JOIN doc_entities de2 ON de2.doc_id = d.id
            JOIN entities e2 ON e2.id = de2.entity_id
            WHERE e1.normalized=? AND e2.normalized=?
              AND e1.label IN ('PERSON','ORG') AND e2.label IN ('PERSON','ORG')
            """,
            (na, nb),
        )
        k = int((cur.fetchone() or [0])[0])

        p = _approx_p_value_from_overlap(N, a, b, k)

        stmts.append(
            FILStatement(
                statement_type=StatementType.FACT,
                confidence_score=1.0,
                text=f"Document overlap counts (scope=DOCS): total_docs={N}, docs_with_A={a}, docs_with_B={b}, docs_with_both={k}.",
                primary_sources=[],
                metadata={"N": N, "a": a, "b": b, "k": k, "scope": "DOCS"},
            )
        )
        stmts.append(
            FILStatement(
                statement_type=StatementType.INFERENCE,
                confidence_score=0.7,
                text="Overlap density can be used to assess how many independent coincidences would need to exist for repeated co-occurrence to be random. This is a probabilistic framing, not a claim of intent or wrongdoing.",
                primary_sources=[],
                metadata={"approx_p_value": p},
            )
        )
        stmts.append(
            FILStatement(
                statement_type=StatementType.IMPLICATION,
                confidence_score=0.9,
                text=f"Approximate randomness score (conservative): p≈{p:.4f}. Smaller values indicate that repeated overlap is less consistent with random coincidence under a simplistic independence assumption.",
                primary_sources=[],
                metadata={"approx_p_value": p},
            )
        )

    else:
        # EVENTS
        cur.execute("SELECT COUNT(*) FROM events")
        N = int((cur.fetchone() or [0])[0])

        cur.execute(
            """
            SELECT COUNT(DISTINCT ev.id)
            FROM events ev
            JOIN event_entities ee ON ee.event_id = ev.id
            JOIN entities e ON e.id = ee.entity_id
            WHERE e.normalized=? AND e.label IN ('PERSON','ORG')
            """,
            (na,),
        )
        a = int((cur.fetchone() or [0])[0])

        cur.execute(
            """
            SELECT COUNT(DISTINCT ev.id)
            FROM events ev
            JOIN event_entities ee ON ee.event_id = ev.id
            JOIN entities e ON e.id = ee.entity_id
            WHERE e.normalized=? AND e.label IN ('PERSON','ORG')
            """,
            (nb,),
        )
        b = int((cur.fetchone() or [0])[0])

        cur.execute(
            """
            SELECT COUNT(DISTINCT ev.id)
            FROM events ev
            JOIN event_entities ee1 ON ee1.event_id = ev.id
            JOIN entities e1 ON e1.id = ee1.entity_id
            JOIN event_entities ee2 ON ee2.event_id = ev.id
            JOIN entities e2 ON e2.id = ee2.entity_id
            WHERE e1.normalized=? AND e2.normalized=?
              AND e1.label IN ('PERSON','ORG') AND e2.label IN ('PERSON','ORG')
            """,
            (na, nb),
        )
        k = int((cur.fetchone() or [0])[0])

        p = _approx_p_value_from_overlap(N, a, b, k)

        stmts.append(
            FILStatement(
                statement_type=StatementType.FACT,
                confidence_score=1.0,
                text=f"Event overlap counts (scope=EVENTS): total_events={N}, events_with_A={a}, events_with_B={b}, events_with_both={k}.",
                primary_sources=[],
                metadata={"N": N, "a": a, "b": b, "k": k, "scope": "EVENTS"},
            )
        )
        stmts.append(
            FILStatement(
                statement_type=StatementType.INFERENCE,
                confidence_score=0.7,
                text="Repeated overlap in derived events can be used to evaluate how many independent coincidences would be required for a pattern to be accidental. This is a probabilistic framing, not an accusation.",
                primary_sources=[],
                metadata={"approx_p_value": p},
            )
        )
        stmts.append(
            FILStatement(
                statement_type=StatementType.IMPLICATION,
                confidence_score=0.9,
                text=f"Approximate randomness score (conservative): p≈{p:.4f}. Smaller values suggest overlap is less consistent with random coincidence under simplistic assumptions.",
                primary_sources=[],
                metadata={"approx_p_value": p},
            )
        )

    conn.close()
    return PDDResult(statements=enforce_assertion_boundaries(stmts))
