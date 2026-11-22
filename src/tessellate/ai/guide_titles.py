"""A Guide question that is a topic's own title names that topic outright (L195).

The keyword reading sent 51 of 246 titles to a neighbour or to nothing
("Asking and chatting" read as small talk), so a title is checked first, with
or without "Tell me about" in front.
"""

from __future__ import annotations

import re

from tessellate.ai.help_topics_more import TOPIC_META

#: The ask's lead, anchored and bounded: the title after it is cut with str ops, so no
#: lazy group meets an optional tail (CodeQL polynomial regex: "(.+?)\s*[?.!]*\s*$").
_TITLE_LEAD = re.compile(r"(?:tell me|what is|what are|what's|how do (?:i|you) use|how does|explain|about) (?:about )?", re.I)


def asked_title(question: str) -> str:
    """The title a question asks for: the words after "Tell me about" and the like, trimmed of end marks."""
    text = " ".join((question or "")[:300].split())
    lead = _TITLE_LEAD.match(text)
    return text[lead.end() :].rstrip("?.! ").lower() if lead else text.rstrip("?.! ").lower()


def topic(question: str, topics: list[dict]) -> list[dict]:
    """The topic whose own title the question is ("Managing tags", "Tell me about managing tags"), or []."""
    title = asked_title(question)
    if not title:
        return []
    keys = {title, title.removeprefix("the ")}
    return [t for t in topics if TOPIC_META.get(t["id"], {}).get("title", "").lower().removeprefix("the ") in keys][:1]
