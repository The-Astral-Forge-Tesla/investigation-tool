from __future__ import annotations
from dataclasses import dataclass, asdict
from enum import Enum
from typing import List, Optional, Dict, Any

class StatementType(str, Enum):
    FACT = "FACT"
    INFERENCE = "INFERENCE"
    IMPLICATION = "IMPLICATION"

@dataclass(frozen=True)
class SourceRef:
    filename: str
    page: int
    snippet: str

    def to_dict(self) -> Dict[str, Any]:
        return {"filename": self.filename, "page": self.page, "snippet": self.snippet}

@dataclass
class FILStatement:
    statement_type: StatementType
    confidence_score: float
    text: str
    primary_sources: List[SourceRef]
    secondary_sources: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["statement_type"] = self.statement_type.value
        d["primary_sources"] = [s.to_dict() for s in self.primary_sources]
        return d
