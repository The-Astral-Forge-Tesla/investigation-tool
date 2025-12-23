from __future__ import annotations
from typing import List
from app.fil import FILStatement, StatementType
from app.stopline import stopline_check

def enforce_assertion_boundaries(stmts: List[FILStatement]) -> List[FILStatement]:
    """
    Ensures outputs never become accusations.
    - Blocks disallowed claims (Stop-Line Guard)
    - Forces conservative typing + confidence clamping
    """
    safe: List[FILStatement] = []

    for s in stmts:
        # clamp confidence
        conf = float(s.confidence_score)
        conf = 0.0 if conf < 0 else 1.0 if conf > 1 else conf
        s.confidence_score = conf  # type: ignore[attr-defined]

        allowed, reason = stopline_check(s.text)
        if not allowed:
            # downgrade to an IMPLICATION that refuses the claim and points to structure
            safe.append(
                FILStatement(
                    statement_type=StatementType.IMPLICATION,
                    confidence_score=1.0,
                    text=reason,
                    primary_sources=s.primary_sources,
                    secondary_sources=s.secondary_sources,
                    metadata={"blocked_original": s.text, "rule": "STOPLINE_GUARD"},
                )
            )
            continue

        # Additional boundary: FACT must be document anchored
        if s.statement_type == StatementType.FACT and (not s.primary_sources):
            # no source = cannot be FACT
            s.statement_type = StatementType.INFERENCE  # type: ignore[attr-defined]
            s.confidence_score = min(s.confidence_score, 0.6)  # type: ignore[attr-defined]
            s.metadata = {**(s.metadata or {}), "downgraded": "FACT_WITHOUT_SOURCES"}  # type: ignore[attr-defined]

        safe.append(s)

    return safe
