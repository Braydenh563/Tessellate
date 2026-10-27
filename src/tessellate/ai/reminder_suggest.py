"""A chat message that reads as a dated intention, offered as a reminder.

"I need to call the dentist on Friday" is a reminder the person has said
aloud without asking for one. The chat shows a "Make this a reminder" chip
under the reply (CHAT_PLAN decision 79); one press creates it. Rules only,
no model (decision 75: with a model up the composer hands facts, so the chip
is never the model's job), and it offers, never creates.

It stays quiet when the person is asking (a question mark, a question word,
"do I have to"), when it is over (past tense, "I didn't need to"), when no
time is said, and when the chat already acts on the words ("remind me to ...",
`commands._reminder`, through `reminder_parser.reminder_head`), so one message never gets both a reminder and an offer.
"""

from __future__ import annotations

import re
from datetime import datetime

from tessellate.ai import reminder_parser

_MAX = 400

#: First-person intention, or a nudge to oneself. Past forms ("needed to",
#: "had to", "went to") do not match: each alternative ends on a word boundary
#: and is the present or future form.
_INTENT = re.compile(
    r"\b(?:"
    r"(?:i|we)\s*(?:'ll|will|need to|have to|must|should|ought to|want to|plan to|promised to|got to|gotta|gonna"
    r"|(?:'m|am|'re|are) going to|(?:have|'ve) got to)"
    r"|don'?t forget to|do not forget to|remember to|need to remember to|(?:i|we) need to remember to"
    r")\b",
    re.IGNORECASE,
)
_NEGATED = re.compile(r"\b(?:didn'?t|did not|don'?t|do not|won'?t|will not|never|no need|not going to|doesn'?t)\b", re.IGNORECASE)
_FORGET = re.compile(r"\b(?:don'?t|do not) forget\b", re.IGNORECASE)
_QUESTION_FIRST = re.compile(
    r"^(?:what|who|where|when|how|why|which|whether|do|does|did|can|could|should|would|will|is|are|am|shall|may|have|has)\b",
    re.IGNORECASE,
)
_PAST = re.compile(r"\b(?:yesterday|last (?:week|month|year|night|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|ago)\b", re.IGNORECASE)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def _reads_as_intention(sentence: str) -> bool:
    if sentence.endswith("?") or _QUESTION_FIRST.match(sentence) or _PAST.search(sentence):
        return False
    if not _INTENT.search(sentence):
        return False
    return not _NEGATED.search(_FORGET.sub("", sentence))


def suggest(text: str, now: datetime) -> dict | None:
    """`{"text", "due_at", "priority", ...}` for the first sentence of `text`
    that states a dated intention to come, else None. `now` is the person's
    clock, as everywhere a time is read."""
    said = " ".join((text or "").replace("’", "'").split())[:_MAX]
    for sentence in _sentences(said):
        if not _reads_as_intention(sentence) or reminder_parser.reminder_head(sentence)[1] is not None:
            continue
        #: The task is what follows the intention: "I should email Priya
        #: tomorrow" is "Email Priya", whatever the verb that carried it.
        task = _INTENT.sub(" ", sentence, count=1)
        parsed = reminder_parser.read_by_rule(" ".join(task.split()), now)
        if parsed is None or parsed["due_at"] <= now.replace(tzinfo=parsed["due_at"].tzinfo):
            continue
        return parsed
    return None
