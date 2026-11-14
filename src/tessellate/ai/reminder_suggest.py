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
from datetime import datetime, timedelta

from tessellate.ai import recognise, reminder_parser

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
#: A nudge with no "I": "must book the venue", "need to call", a bare to-do marker at the
#: head of a sentence (G10). "must have been" is a guess about the past, not a task.
_BARE_HEAD = re.compile(
    r"^(?:must(?!\s+(?:have|be|not)\b)|need to(?!\s+know\b)|have to|to-?do\s*:|todo\s*:)\s*",
    re.IGNORECASE,
)
#: A command to oneself with a time in it ("call mum on sunday", "take the bins out tonight").
_IMPERATIVE = re.compile(
    r"^(?:call|ring|phone|text|email|message|buy|get|book|pay|send|submit|renew|take|bring|pick up|drop off|order|"
    r"cancel|schedule|return|water|finish|write|clean|fix|check|visit|post|print|pack|prepare|register|sign|"
    r"reply|file|collect|charge|back up|feed|cook|wash|tidy|organise|organize|plan|apply|update|review)\b",
    re.IGNORECASE,
)
#: A dated fact is a thing to be there for: "exam on 24 november at 9am", "the plumber is coming thursday".
_EVENT = re.compile(
    r"\b(?:is|are) (?:coming|arriving|visiting|due|on|at|starting)\b|\b(?:arrives|starts|ends|opens|closes)\b|^(?:the |my |our )?"
    r"(?:exam|test|interview|appointment|meeting|flight|deadline|party|wedding|concert|lesson|class|dentist|doctor)\b",
    re.IGNORECASE,
)
_PAST = re.compile(
    r"\b(?:i|we)\s+(?:(?!need\b)\w+ed|went|saw|had|was|got|did|made|took|met|paid|sent|bought)\b|\b(?:was|were|had|did)\b",
    re.IGNORECASE,
)
#: What the date reader leaves behind once it takes the date out.
#: The hanging word alone; the separators before it are checked in code, so a
#: long blank run is never rescanned from every start (CodeQL 2134).
_DANGLING = re.compile(r"\b(?:before|by|until|till|on|at|from|for|between|in|this|next)$", re.IGNORECASE)
_SEPARATORS = " \t\n\r\f\v,;:"
_NEGATED = re.compile(r"\b(?:didn'?t|did not|don'?t|do not|won'?t|will not|never|no need|not going to|doesn'?t)\b", re.IGNORECASE)
_FORGET = re.compile(r"\b(?:don'?t|do not) forget\b", re.IGNORECASE)
_QUESTION_FIRST = re.compile(
    r"^(?:what|who|where|when|how|why|which|whether|do|does|did|can|could|should|would|will|is|are|am|shall|may|have|has)\b",
    re.IGNORECASE,
)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def _reads_as_intention(sentence: str) -> bool:
    if sentence.endswith("?") or _QUESTION_FIRST.match(sentence):
        return False
    if _PAST.search(sentence):
        return False
    if not (_INTENT.search(sentence) or _BARE_HEAD.match(sentence)):
        return False
    return not _NEGATED.search(_FORGET.sub("", sentence))


def _tidy(text: str) -> str:
    """The reminder's words without a preposition the date left hanging."""
    out = text.strip()
    while True:
        hang = _DANGLING.search(out)
        if hang is None or hang.start() == 0 or out[hang.start() - 1] not in _SEPARATORS:
            return out
        out = out[: hang.start()].rstrip(_SEPARATORS)


def _read(sentence: str, now: datetime) -> dict | None:
    """The reminder a sentence states: an intention (with or without "I"),
    a command with a time, or a dated fact."""
    bare = _BARE_HEAD.match(sentence)
    if bare or _INTENT.search(sentence):
        task = _BARE_HEAD.sub(" ", sentence, count=1) if bare else _INTENT.sub(" ", sentence, count=1)
        parsed = reminder_parser.read_by_rule(" ".join(task.split()), now)
        if parsed is None and _FORGET.search(sentence):
            #: "Don't forget to buy milk": an explicit nudge with no time is
            #: offered for tomorrow 9am, marked as a guess for the chip to say.
            words = reminder_parser.worded(" ".join(task.split()))
            due = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
            return {"text": words, "due_at": due, "priority": "normal", "guess": True}
        return parsed
    parsed = reminder_parser.read_by_rule(sentence, now)
    if parsed is None:
        return None
    if _IMPERATIVE.match(sentence):
        return parsed
    if _EVENT.search(sentence):
        #: A fact reads as itself: the words before its time, not the parser's remains.
        phrases = recognise.find(sentence)
        #: "is coming thursday": the recogniser takes "coming thursday" as the date, but "coming" is the fact's verb.
        cut = phrases[0][0] + (len("coming") if phrases[0][2].lower().startswith("coming ") else 0) if phrases else len(sentence)
        parsed["text"] = reminder_parser.worded(sentence[:cut])
        return parsed
    return None


def suggest(text: str, now: datetime) -> dict | None:
    """`{"text", "due_at", "priority", ...}` for the first sentence of `text`
    that states a dated intention to come, else None. `now` is the person's
    clock, as everywhere a time is read."""
    said = " ".join((text or "").replace("’", "'").split())[:_MAX]
    for sentence in _sentences(said):
        if reminder_parser.reminder_head(sentence)[1] is not None:
            continue
        if sentence.endswith("?") or _QUESTION_FIRST.match(sentence) or _PAST.search(sentence):
            continue
        if not _reads_as_intention(sentence) and not (_IMPERATIVE.match(sentence) or _EVENT.search(sentence)):
            continue
        #: The task is what follows the intention: "I should email Priya
        #: tomorrow" is "Email Priya", whatever the verb that carried it.
        parsed = _read(sentence, now)
        if parsed is not None:
            parsed["text"] = _tidy(parsed["text"]) or parsed["text"]
        #: A time already gone ("yesterday", "a week ago") is the recogniser's
        #: to read (tests/test_one_reader.py): a due time not ahead is no offer.
        if parsed is None or parsed["due_at"] <= now.replace(tzinfo=parsed["due_at"].tzinfo):
            continue
        return parsed
    return None
