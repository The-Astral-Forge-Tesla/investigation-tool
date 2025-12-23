import re
from typing import Tuple

DISALLOWED_PATTERNS = [
    # criminality / intent
    r"\b(guilty|criminal|crime|felony|fraud|traffick\w*|rape|assault|abuse|murder)\b",
    r"\b(intended|intent|knowingly|conspired|cover[-\s]?up)\b",
    r"\b(proved|definitely|certainly)\b",
    # identity from images
    r"\b(identify|identification|this is|that is)\b.*\b(person|man|woman|face)\b",
    r"\b(face recognition|recognize(d)? (him|her|them)|match(ed)? (a )?face)\b",
]

def stopline_check(text: str) -> Tuple[bool, str]:
    """
    Returns (allowed, reason). If not allowed, reason explains.
    This is intentionally conservative: protects project survivability.
    """
    t = (text or "").strip()
    if not t:
        return True, ""

    for pat in DISALLOWED_PATTERNS:
        if re.search(pat, t, flags=re.IGNORECASE):
            return False, "This exceeds verifiable assertion boundaries. Relevant structured data is provided instead."
    return True, ""
