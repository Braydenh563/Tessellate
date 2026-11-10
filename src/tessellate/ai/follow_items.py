"""An instruction that follows a list or an act acts on what that answer showed
(INBOX 1730 F3, composer audit 2026-11-10).

"remove milk" after the shopping list is a line of that list, never the note
"Shopping" (`commands._delete` would match "milk" against note bodies and
propose the bin). The turn before is read from its answer text, the only state
a request carries (`composer_talk` does the same): a checklist note's lines, the
reminders table, the note just made, the reminder just set.

`read` gives either a sentence in the words the acts already parse (the
caller swaps it in for the question, so the usual cards, confirms and Undo
apply) or a line that asks which, when the words do not single out one item.
A destructive word that does not name one item never falls through to the
note-bin reader. Nothing here touches the notebook.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from tessellate.ai import follow_dates, task_acts

#: The reading of a turn: what to say instead of the question, and/or what to ask.
Reading = tuple[str | None, str | None]


@dataclass
class Shown:
    """What an answer put in front of the person."""

    kind: str  # "checklist", "reminders", "note" (just made) or "reminder" (just set)
    title: str = ""
    items: list[str] = field(default_factory=list)
    when: str = ""


_BOLD = re.compile(r"\*\*([^*\n]+)\*\*")
_BOX_LINE = re.compile(r"^\s*[-*+]\s+\[[ xX]\]\s+\S", re.MULTILINE)
_CREATED = re.compile(r"\bcreated [“\"]([^”\"]+)[”\"]", re.I)
_SET = re.compile(r"\bremind you (?P<when>[^:\n]+?): (?P<what>[^\n]+?)\.?\s*$", re.I | re.MULTILINE)


def _table_items(answer: str) -> list[str]:
    """The first column of a reminders table, header and rule left out."""
    rows = [ln.strip().strip("|").split("|") for ln in answer.splitlines() if ln.strip().startswith("|")]
    if not rows or rows[0][0].strip().lower() != "reminder":
        return []
    return [r[0].strip() for r in rows[2:] if r and r[0].strip()]


def shown(answer: str) -> Shown | None:
    """What `answer` showed, or None when it showed nothing an instruction can bind to."""
    answer = answer or ""
    if _table_items(answer):
        return Shown("reminders", items=_table_items(answer))
    bold = _BOLD.search(answer)
    if bold and _BOX_LINE.search(answer):
        return Shown("checklist", bold.group(1).strip(), task_acts.items_in(answer))
    made = _CREATED.search(answer)
    if made:
        return Shown("note", made.group(1).strip())
    got = _SET.search(answer)
    if got:
        return Shown("reminder", got.group("what").strip(), when=got.group("when").strip())
    return None


def _last_list(history: list[dict]) -> Shown | None:
    """The list or table the last answer showed, else the latest one within four turns."""
    for turn in reversed((history or [])[-4:]):
        found = shown(str(turn.get("answer") or ""))
        if found and found.kind in ("checklist", "reminders"):
            return found
    return None


# --- naming one item ----------------------------------------------------------------------------

_PRONOUN = frozenset({"it", "that", "this", "this one", "that one", "them", "those", "these", "one"})
_REMOVE = re.compile(
    r"^(?:please )?(?:remove|delete|take off|cross off|scratch|get rid of|bin|drop|cancel|scrap|ditch|clear)\s+(?P<what>.+?)\s*[.!]?$", re.I
)
_TAKE_OFF = re.compile(r"^(?:please )?take\s+(.+?)\s+off(?:\s+(?:of\s+)?(?:it|the list|my list|this list|that list))?$", re.I)
_NOT_AN_ITEM = re.compile(r"\b(?:notes?|tags?|categor(?:y|ies)|documents?|boards?|maps?|meetings?|everything|all|every)\b", re.I)


def _named(items: list[str]) -> str:
    quoted = [f"“{i}”" for i in items[:6]]
    return quoted[0] if len(quoted) == 1 else ", ".join(quoted[:-1]) + " or " + quoted[-1]


def _which(items: list[str], lead: str) -> str:
    return f"{lead} Which one do you mean: {_named(items)}? Say it again with its name."


def _pick(about: str, items: list[str]) -> tuple[str | None, str | None]:
    """(the one item named, None), or (None, the line that asks which)."""
    said = " ".join(about.lower().split())
    if said in _PRONOUN:
        return (items[0], None) if len(items) == 1 else (None, _which(items, "More than one line is showing."))
    place = task_acts.ordinal_of(about)
    if place:
        if 0 < place <= len(items) or place == -1:
            return items[place - 1 if place > 0 else -1], None
        return None, _which(items, f"That list has {len(items)} lines.")
    wanted = task_acts._stems(about)
    hits = [i for i in items if wanted and wanted <= task_acts._stems(i)]
    if len(hits) == 1:
        return hits[0], None
    if hits:
        return None, _which(hits, "More than one line fits.")
    return None, _which(items, f"I do not see “{about}” on that list.")


def _remove(question: str, history: list[dict]) -> Reading:
    said = _TAKE_OFF.sub(r"remove \1", " ".join(question.split()))
    found = _REMOVE.match(said)
    last = _last_list(history[-1:]) if history else None
    if not found or last is None:
        return None, None
    rest = task_acts._OFF_LIST.sub("", found.group("what").strip(), count=1)
    if _NOT_AN_ITEM.search(rest):
        return None, None
    about, said = task_acts._split_kind(rest)
    if not about or (said == "reminder" and last.kind != "reminders"):
        return None, None
    item, ask = _pick(about, last.items)
    if item is None:
        return None, ask
    if last.kind == "reminders":
        return f"cancel the reminder {item}", None
    return f"cancel the list item {item} on the {last.title} list", None


_TICK = re.compile(
    r"^(?:please )?(?:tick off|tick|check off|mark|complete|finish)\s+(?:the\s+)?(?P<what>[\w ]+?)(?:\s+(?:as\s+)?(?:done|complete|completed|off))?\s*[.!]?$", re.I
)


def _tick(question: str, history: list[dict]) -> Reading:
    """"mark the first one done" some turns after the list: the last answer showed none to count from."""
    found = _TICK.match(" ".join(question.split()))
    if not found or not history:
        return None, None
    if _last_list(history[-1:]) is not None or not task_acts.ordinal_of(found.group("what")):
        return None, None  # the list is right there: `task_acts.counted_from` counts it
    last = _last_list(history)
    if last is None:
        return None, None
    item, ask = _pick(found.group("what"), last.items)
    if item is None:
        return None, ask
    return (f"mark the reminder {item} done" if last.kind == "reminders" else f"tick {item} on the {last.title} list"), None


# --- adding to what was shown -------------------------------------------------------------------

_ADD = re.compile(r"^(?:please )?(?:add|put)\s+(?P<x>.+?)(?:\s+(?:to|on|onto|into|in)\s+(?:it|that|this|the list|this list|my list|the note|this note))?\s*[.!]?$", re.I)
_AND = re.compile(r"^(?:and|also|plus)\s+(?P<x>\w+(?: \w+){0,3})\s*[.!]?$", re.I)
_NOT_A_LINE = re.compile(r"\b(?:to|note|notes|tag|tags|reminder|reminders|event|meeting|task|tasks|category|board|calendar|bookmark)\b", re.I)
_QUESTION_WORD = re.compile(r"^(?:what|how|when|where|who|why|which|is|are|do|does|did|can|could|will|would|should|have|has|i|my|then|so)\b", re.I)


def _add(question: str, history: list[dict]) -> Reading:
    last = shown(str((history or [{}])[-1].get("answer") or "")) if history else None
    if last is None or last.kind not in ("checklist", "note"):
        return None, None
    text = " ".join(question.split())
    found = _ADD.match(text) or _AND.match(text)
    item = (found.group("x").strip() if found else "")
    if not item or _QUESTION_WORD.match(item) or _NOT_A_LINE.search(item) or text.endswith("?"):
        return None, None
    return f"add {item} to the {last.title} note", None


def _make_it(question: str, history: list[dict]) -> Reading:
    """"make it 6", "actually 9am": the reminder just set, at another time."""
    last = shown(str((history or [{}])[-1].get("answer") or "")) if history else None
    if last is None or last.kind != "reminder":
        return None, None
    found = re.match(
        r"^(?:actually,? |no,? |sorry,? )*(?:(?:make|change|set|move|push) (?:it|that|this)(?: to| for| at)? |(?:at )?)"
        r"(?P<t>\d{1,2}(?::\d\d)?\s*(?:am|pm)?|noon)\s*[.!]?$",
        " ".join(question.split()), re.I,
    )
    if not found:
        return None, None
    clock = found.group("t").replace(" ", "").lower()
    was = re.search(r"at (\d{1,2}(?::\d\d)?)\s*(am|pm)\b", last.when, re.I)
    if clock.isdigit() or re.fullmatch(r"\d{1,2}:\d\d", clock):
        if int(clock.split(":")[0]) > 12 or not was:
            return None, None
        clock += was.group(2).lower()
    day = re.sub(r"\s*\bat \d.*$", "", last.when, flags=re.I).strip()
    return f"move the reminder {last.title} to {day + ' ' if day else ''}at {clock}", None


def _rename(question: str, history: list[dict]) -> Reading:
    last = shown(str((history or [{}])[-1].get("answer") or "")) if history else None
    found = re.match(r"^rename (?:it|that|this)(?: note)? (?:to|as) (?P<x>.+?)\s*[.!]?$", " ".join(question.split()), re.I)
    if not found or last is None or last.kind not in ("note", "checklist"):
        return None, None
    return f"rename the {last.title} note to {found.group('x')}", None


def read(question: str, history: list[dict] | None, now: datetime | None = None) -> Reading:
    """(the sentence the question stands for, the line that asks which), either or neither.
    With `now`, a day counted from or moved off the one just shown is read too (`follow_dates`)."""
    history = history or []
    if not history or not (question or "").strip():
        return None, None
    for reader in (_remove, _tick, _make_it, _rename, _add):
        said, ask = reader(question, history)
        if said or ask:
            return said, ask
    if now is None:
        return None, None
    return follow_dates.read(question, history, now, shown(str(history[-1].get("answer") or "")))
