"""Verify an agent answer against its sources before it is final (H2).

AGENT_SKILLS_REFORM, "Harness robustness", phase H2: a numeric or named claim
in the answer that no tool result, quoted note or the user's own words
contain is flagged the way an unsupported act is (`agent.unsupported_claims`
is the shape copied). No second model round: a small model asked "are you
sure?" agrees with whatever it said, and the check is the one thing in the
turn that cannot hallucinate, because it only ever looks for a string.

**Precision over recall, deliberately.** A false flag tells the user a true
answer may be wrong, which costs more trust than a missed one, so a claim is
only what can be checked mechanically: a number (a count, a time, a date, an
amount) and a capitalised name in the middle of a sentence. A sentence-initial
word, a month, a weekday and the app's own nouns are never names. A number is
backed by the same number anywhere in the sources, by the length of a list a
tool returned ("3 notes" from three results), or by a month the sources name.
`tests/fixtures/chat/source_check_cases.json` is the measure (twenty answers,
twelve true): see `tests/test_source_check.py`.
"""

from __future__ import annotations

import json
import re

from tessellate.ai import recognise

_MONTHS = (
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
)
_MONTH_ABBR = {m[:3]: i + 1 for i, m in enumerate(_MONTHS)}

#: Never a claim about the notebook: calendar words, the app's own nouns and
#: words a reply capitalises for emphasis or as a heading.
_NOT_NAMES = frozenset(
    {
        *_MONTHS,
        *(m[:3] for m in _MONTHS),
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
        "today", "tomorrow", "yesterday", "i", "i'm", "i've", "i'll", "i'd", "ok", "okay",
        "ai", "atlas", "memorymap", "notes", "note", "chat", "graph", "library",
        "settings", "timeline", "whiteboard", "documents", "document", "reminders",
        "reminder", "inbox", "ask", "agent", "skills", "skill", "tags", "tag",
        "categories", "category", "pinned", "favourites", "markdown", "am", "pm",
        "utc", "pdf", "url", "faq", "todo", "to-do", "dr", "mr", "mrs", "ms",
    }
)

#: A number may sit against its unit ("120kg", "10k", "5x5", "2h50"): it
#: starts after a non-word or after a digit and a letter, and ends where the
#: digits do (Brief 68: "120kg" and "10k" in a model's answer were never
#: checked, and "5x5" in a note backed no 5).
_STARTS = r"(?:(?<![\w.])|(?<=\d[a-zA-Z]))"
_NUMBER = re.compile(_STARTS + r"(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?(?:st|nd|rd|th)?(?![\d])")
_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")
_COMPOUND = re.compile(
    _STARTS + r"\d[\d,]*(?:\.\d+)?(?:[:/\-]\d[\d,]*(?:\.\d+)?)*(?:st|nd|rd|th)?(?![\d])"
)
#: Leaked bookkeeping (H3 strips it) and markdown list numbering are not claims.
_IGNORED = re.compile(
    r"(?m)^\s*(?:\d+[.)]|[-*+])\s+|\[\d+\]|\bnote (?:id\s*)?#?\d+\b|\bid[:=]?\s*\d+\b",
    re.IGNORECASE,
)
_SENTENCE_START = re.compile(r"(?:^|[.!?:;]\s+|\n\s*(?:[-*+]|\d+[.)])?\s*|\(\s*|[\"“]\s*)$")


#: A claim that is only figures: a day, a time, a date, a count.
_FIGURES = re.compile(r"^[\d:/\-.,]+(?:st|nd|rd|th)?$")


def _number_key(whole: str, fraction: str | None) -> str:
    whole = whole.replace(",", "").lstrip("0") or "0"
    fraction = (fraction or "").rstrip("0")
    return f"{whole}.{fraction}" if fraction else whole


class Sources:
    """Everything an answer may draw on this turn: lower-cased text and the
    numbers in it, with each tool result's list lengths."""

    def __init__(self, texts: list[str], question: str = ""):
        self.computed = recognise.asks_computed(question or "")
        self.text = "\n".join(texts).lower()
        self.words = set(re.findall(r"[a-z][a-z'\-]*", self.text))
        self.numbers = {_number_key(w, f) for w, f in _NUMBER.findall(self.text)}
        #: "2026-10-30T17:00:00" holds 30, 10 and 17 as their own figures.
        self.numbers.update(_number_key(part, None) for part in recognise.iso_figures(self.text))
        for word in self.words:
            month = _MONTH_ABBR.get(word[:3]) if word in _MONTHS or word in _MONTH_ABBR else None
            if month:
                self.numbers.add(str(month))
        for text in texts:
            self._list_lengths(text)

    def _list_lengths(self, text: str) -> None:
        try:
            value = json.loads(text)
        except (TypeError, ValueError):
            return
        stack = [value]
        while stack:
            item = stack.pop()
            if isinstance(item, list):
                self.numbers.add(str(len(item)))
                stack.extend(item)
            elif isinstance(item, dict):
                stack.extend(item.values())


def sources_from_messages(messages: list[dict]) -> Sources:
    """The user's words, the notes in the prompt and every tool result; never
    the system prompt (its numbers are the app's) nor the model's own replies
    (a claim cannot back itself)."""
    texts = [
        str(m.get("content") or "")
        for m in messages[1:]
        if m.get("role") in ("user", "tool")
    ]
    asked = next((str(m.get("content") or "") for m in reversed(messages) if m.get("role") == "user"), "")
    return Sources(texts, asked)


_APP_LINK = re.compile(r"\[[^\]\n]{1,120}\]\(#/[^)\s]*\)")


def unbacked_claims(answer: str, sources: Sources) -> list[str]:
    """Numbers and names in `answer` that `sources` does not contain, in order."""
    #: An app link ("[Open your notes](#/notes)") is the app's own offer, not
    #: a claim: "Open" was flagged as an unbacked name (owner, 2026-10-12).
    text = _IGNORED.sub(" ", _APP_LINK.sub(" ", answer).replace("**", "").replace("__", ""))
    found: list[str] = []
    # "10:15", "3/3" and "2026-10-06" are one claim of several numbers: said
    # as written, flagged when any part is not in the sources.
    for match in _COMPOUND.finditer(text):
        parts = [_number_key(w, f) for w, f in _NUMBER.findall(match.group(0))]
        if any(key not in ("0", "1") and key not in sources.numbers for key in parts):
            found.append(match.group(0))
    run: list[str] = []
    prev_end = -1

    def close() -> None:
        missing = [w for w in run if w.lower() not in sources.words]
        if missing:
            found.append(" ".join(run))
        run.clear()

    for match in _WORD.finditer(text):
        word = match.group(0).strip("'-")
        joined = text[prev_end:match.start()] == " "
        prev_end = match.end()
        if run and not joined:
            close()
        if not word[:1].isupper() or word.lower() in _NOT_NAMES or len(word) < 3:
            if run:
                close()
            continue
        if word.isupper() and len(word) <= 4:
            continue
        if not run and _SENTENCE_START.search(text[max(0, match.start() - 6):match.start()]):
            continue
        run.append(word)
    if run:
        close()
    return _without_computed(list(dict.fromkeys(found)), sources)


def _without_computed(found: list[str], sources: Sources) -> list[str]:
    """`found` less the claims that are only figures, when the question asked
    for a computed date or count."""
    if not sources.computed:
        return found
    return [c for c in found if not all(_FIGURES.match(part) for part in c.split())]


def heads_up(claims: list[str]) -> str:
    """The line appended under an answer, in the voice of the act heads-up."""
    named = ", ".join(claims[:4]) + (" and more" if len(claims) > 4 else "")
    return (
        f"\n\nHeads up: I could not find {named} in your notes or in anything I "
        "read this turn, so check that before relying on it."
    )
