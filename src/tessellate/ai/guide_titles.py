"""A Guide question that is a topic's own title names that topic outright (L195).

The keyword reading sent 51 of 246 titles to a neighbour or to nothing
("Asking and chatting" read as small talk), so a title is checked first, with
or without "Tell me about" in front.
"""

from __future__ import annotations

import re

from tessellate.ai.help_topics_more import TOPIC_META

_TITLE_ASK = re.compile(
    r"^\s*(?:(?:tell me|what is|what are|what's|how do (?:i|you) use|how does|explain|about)\s+(?:about\s+)?)?(.+?)\s*[?.!]*\s*$",
    re.I,
)


def topic(question: str, topics: list[dict]) -> list[dict]:
    """The topic whose own title the question is ("Managing tags", "Tell me about managing tags"), or []."""
    wanted = _TITLE_ASK.match(question or "")
    if not wanted:
        return []
    keys = {wanted.group(1).lower(), wanted.group(1).lower().removeprefix("the ")}
    return [t for t in topics if TOPIC_META.get(t["id"], {}).get("title", "").lower().removeprefix("the ") in keys][:1]
