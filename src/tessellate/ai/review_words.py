"""The words that ask for a review of the week or the day, a leaf module.

"Weekly review", "how was my week", "summarise my week", "daily review",
"summarise my day" (composer audit 2, G4). `review_digest` writes the review;
the Guide reads these words to hand the question to Chat. Kept apart so the
Guide imports no composer code to tell one from the other."""

from __future__ import annotations

import re

_LEAD = r"^\W*(?:(?:please|pls|can you|could you)\s+)*(?:(?:give me|do|run|show me|start|open|get)\s+)?(?:(?:a|an|the|my|our)\s+)*"
_SUM = r"(?:summari[sz]e|sum up|recap|review|summary of|rundown of|overview of)\s+(?:of\s+)?(?:(?:my|our|the)\s+)?"
_WEEK = re.compile(
    _LEAD + r"(?:(?:weekly|week'?s?)\s+(?:review|recap|digest|summary|roundup)|week in review|review of (?:my |the )?week"
    r"|" + _SUM + r"(?:this\s+)?week|how (?:was|did) (?:my |our |the )?(?:this\s+)?week(?: go| been)?)\W*$",
    re.I,
)
_DAY = re.compile(
    _LEAD + r"(?:(?:daily|day'?s?)\s+(?:review|recap|digest|summary|roundup)|day in review|review of (?:my |the )?day"
    r"|" + _SUM + r"(?:day|today)|how (?:was|did) (?:my |our |the )?(?:day|today)(?: go| been)?)\W*$",
    re.I,
)


def kind(text: str) -> str | None:
    """"week" or "day" when `text` asks for that review, else None."""
    said = " ".join((text or "").split())
    if not said or len(said) > 80:
        return None
    return "week" if _WEEK.match(said) else "day" if _DAY.match(said) else None
