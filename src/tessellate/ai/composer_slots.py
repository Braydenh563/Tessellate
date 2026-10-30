"""Slot-first answers (audit 1029 C22, C23, C33; INBOX 1357).

A question has a slot, and the item that answers it must hold it: a ticked or
unticked task for "did I pay X", an open task for "what is left on X", a
dated line that says the thing for "how long since I called mum". When no item
holds the slot the answer says so; it never offers a near item (the first
list, the first to-do) as if it were the answer. No model, and the same with
one on. Every pattern here is anchored with one `.+` at the end and the rest
is read in code, so it stays linear (`tests/test_composer_regex_linear_1029.py`).
"""

from __future__ import annotations

import functools
import re
from collections.abc import Callable
from datetime import date
from typing import NamedTuple

from tessellate.ai import composer, composer_lists, recognise
from tessellate.ai import when as when_words

_DID = re.compile(r"^(?:did|have|has)\s+(?:i|we)\s+(?:already\s+|yet\s+|ever\s+)?(.+)$", re.I)
_LEFT = re.compile(r"^what(?:'s|\s+is|\s+else\s+is|\s+is\s+still)?\s+(?:still\s+)?(?:left|remaining|outstanding|open)\s*(.*)$", re.I)
_NEED = re.compile(r"^what\s+(?:else\s+)?(?:do|should)\s+i\s+(?:still\s+)?(?:need|have)\s+to\s+(.+)$", re.I)
_SINCE = re.compile(r"^how\s+long\s+(?:has\s+it\s+been\s+)?since\s+(?:i|we)\s+(?:last\s+)?(.+)$", re.I)
#: Words that carry no subject: the framing of the request itself.
_FILLER = frozenset({
    "the", "a", "an", "my", "our", "on", "for", "to", "of", "in", "at", "with", "list", "lists", "note", "notes", "item", "items",
    "task", "tasks", "checklist", "todo", "still", "do", "i", "we", "it", "that", "this", "yet", "already", "ever", "last",
})
_MARKERS = (" for ", " before ", " to ", " on ", " at ")


def _stems(text: str) -> list[str]:
    seen: list[str] = []
    for w in composer._words(text):  # noqa: SLF001  # the composer's own stemmer, so question and note read alike
        if w not in _FILLER and w not in seen:
            seen.append(w)
    return seen


def _holds(sentence, stems: list[str]) -> bool:  # noqa: ANN001
    have = set(composer._words(sentence.text))  # noqa: SLF001
    return bool(stems) and all(s in have for s in stems)


def _list_subject(rest: str) -> list[str]:
    """The stems of what a "left" question names: "on the Lisbon packing
    list" -> lisbon, pack; "to do for Atlas" -> atlas (the verb before the
    marker is the asking, not the subject)."""
    rest = " " + " ".join(rest.lower().split()) + " "
    cut = [rest.find(m) for m in _MARKERS if rest.find(m) >= 0]
    if cut and not rest.strip().startswith(("on ", "for ", "at ")):
        rest = rest[min(cut):]
    return _stems(rest)


def _title_holds(view, stems: list[str]) -> bool:  # noqa: ANN001
    return bool(stems) and all(s in view.title_words for s in stems)


def _tasks(views: list, stems: list[str]) -> tuple[list, list]:
    """`(open, done)` task sentences of the best note the stems name: one
    whose title holds every stem first, then one filed or worded so
    (`composer._notes_named_by`, the reader "still open" questions share)."""
    named = composer._notes_named_by(views, set(stems))  # noqa: SLF001
    for view in sorted(named, key=lambda v: (not _title_holds(v, stems), v.rank)):
        tasks = [s for s in view.sentences if s.kind == "task"]
        if tasks:
            return [(view, t) for t in tasks if not t.done], [(view, t) for t in tasks if t.done]
    return [], []


def _left(out, rest: str, views: list, today: date) -> bool:  # noqa: ANN001
    stems = _list_subject(rest)
    if not stems:
        return False
    open_, done = _tasks(views, stems)
    #: No list the subject names ("what do I need to buy" names a verb, not a
    #: list): the composer's own readers answer, as they did before the slots.
    if not open_ and not done:
        return False
    view = open_[0][0] if open_ else done[0][0]
    title = composer_lists._title(view)  # noqa: SLF001
    if not open_:
        out.lines.append(f"Nothing is left on {title}: all {len(done)} items are ticked.")
        return True
    out.lines.append(f"{len(open_)} still to do on {title}:")
    for v, task in open_[:12]:
        text = re.sub(r"^\s*[-*]\s*\[ \]\s*", "", task.text).strip()
        out.lines.append(f"- {text}")
        composer_lists._cite(out, v, task, text)  # noqa: SLF001
    return True


def _verdict(out, view, task, verb_said: str) -> None:  # noqa: ANN001
    text = re.sub(r"^\s*[-*]\s*\[[ xX]\]\s*", "", task.text).strip()
    if task.done:
        line = f"Yes, “{text}” is ticked off in {composer_lists._title(view)}."  # noqa: SLF001
    else:
        line = f"Not yet: “{text}” is still open in {composer_lists._title(view)}."
    out.lines.append(line)
    composer_lists._cite(out, view, task, line)  # noqa: SLF001


def _first_did(views: list, verb, obj):  # noqa: ANN001
    """The (view, sentence) that says the doing: a task that holds the object
    and the verb at once, else the first task or prose that holds the object."""
    best = None
    for view in sorted(views, key=lambda v: v.rank):
        for s in view.sentences:
            if not _holds(s, obj):
                continue
            if s.kind == "task":
                best = best or (view, s)
                if not verb or _holds(s, verb):
                    return view, s
            elif not verb or _holds(s, verb + obj):
                best = best or (view, s)
    return best


def _say_did(out, view, s, verb_word: str, today: date) -> None:  # noqa: ANN001
    if s.kind == "task":
        _verdict(out, view, s, verb_word)
        return
    day = view.written
    when = f" (your note of {composer_lists._day(day, today)})" if day else ""  # noqa: SLF001
    out.lines.append(f"Yes, your notes say so{when}: {s.text.strip()}")
    composer_lists._cite(out, view, s, s.text)  # noqa: SLF001


#: "Did I like the ramen place": the note rarely says "like"; it says "8/10,
#: the broth was great". A taste verb is answered by what the note says of
#: the thing, verdict left to the person (2026-10-30 sweep).
_TASTE = frozenset({"like", "enjoy", "love", "hate", "rate", "mind"})


def _say_taste(out, view, s, today: date) -> None:  # noqa: ANN001
    day = view.written
    when = f" of {composer_lists._day(day, today)}" if day else ""  # noqa: SLF001
    text = re.sub(r"^\s*[-*]\s*(?:\[[ xX]\]\s*)?", "", s.text).strip()
    out.lines.append(f"Your note{when} says: {text}")
    composer_lists._cite(out, view, s, s.text)  # noqa: SLF001


def _did(out, rest: str, views: list, today: date) -> bool:  # noqa: ANN001
    words = rest.split()
    if len(words) < 2:
        return False
    verb = _stems(words[0])
    obj = _stems(" ".join(words[1:]))
    if not obj:
        return False
    if words[0] in _TASTE and (best := _first_did(views, None, obj)):
        _say_taste(out, *best, today)
        return True
    best = _first_did(views, verb, obj)
    if best is None:
        out.lines.append(f"I found nothing in your notes that says you {rest}.")
        return True
    _say_did(out, *best, words[0], today)
    return True


def _when_said(view, sentence, today: date) -> date | None:  # noqa: ANN001
    for day, at in composer._days_named(view, today, "past"):  # noqa: SLF001
        if sentence.start <= at < sentence.end:
            return day
    return view.written


def _since(out, rest: str, views: list, today: date) -> bool:  # noqa: ANN001
    words = rest.split()
    if len(words) < 2:
        return False
    verb, obj = _stems(words[0]), _stems(" ".join(words[1:]))
    if not (verb and obj):
        return False
    found = []
    for view in views:
        for s in view.sentences:
            if s.kind == "task" and not s.done:
                continue
            if _holds(s, verb + obj):
                day = _when_said(view, s, today)
                if day and day <= today:
                    found.append((day, view, s))
    if not found:
        out.lines.append(f"Your notes do not say when you {rest}, so I cannot work out how long it has been.")
        return True
    day, view, s = max(found, key=lambda f: f[0])
    n = (today - day).days
    ago = "today" if n == 0 else "yesterday" if n == 1 else f"{n} days ago"
    line = f"It was {composer_lists._day(day, today)}, {ago}."  # noqa: SLF001
    out.lines.append(line)
    composer_lists._cite(out, view, s, line)  # noqa: SLF001
    return True


#: "compare the two X notes", "what changed between the two X notes",
#: "the difference between my two X notes" (2026-10-30 sweep).
_PAIR_LEAD = re.compile(
    r"^(?:compare|what(?:'s| is| are)? (?:changed|different|the differences?) between|(?:the )?differences? between) (?:the |my )?two "
)


def _pair_subject(q: str) -> str | None:
    """What the two notes are about in "compare the two X notes", else None."""
    lead = _PAIR_LEAD.match(" ".join(q.lower().split()))
    if not lead:
        return None
    low = lead.string[lead.end():]
    for tail in (" notes", " note", " ones"):
        if low.endswith(tail):
            return low[: -len(tail)]
    return low


def _say_side_by_side(out, named: list, low: str) -> None:  # noqa: ANN001
    out.lines.append(f"Your two {low} notes, side by side:")
    for view in named[:2]:
        first = next((x for x in view.sentences if x.kind in ("prose", "item", "task")), None)
        line = f"- {composer_lists._title(view)}: {first.text.strip() if first else 'empty'}"  # noqa: SLF001
        out.lines.append(line)
        if first is not None:
            composer_lists._cite(out, view, first, line)  # noqa: SLF001
    sizes = [len(str(v.note.get("content") or "").split()) for v in named[:2]]
    if sizes[0] != sizes[1]:
        longer = named[0] if sizes[0] > sizes[1] else named[1]
        out.lines.append(f"{composer_lists._title(longer)} is the longer, {max(sizes)} words to {min(sizes)}.")  # noqa: SLF001


def _pair(out, q: str, views: list, today: date) -> bool:  # noqa: ANN001
    """"Compare the two lentil soup notes": both sides, side by side, or which
    side is missing (audit 1029 C36). Read in code, not by a pattern, so a long
    question costs nothing."""
    low = _pair_subject(q)
    if low is None:
        return False
    stems = _stems(low)
    if not stems:
        return False
    named = composer._notes_named_by(views, set(stems))  # noqa: SLF001
    named = sorted(named, key=lambda v: (not _title_holds(v, stems), v.rank))
    if not named:
        return False
    if len(named) == 1:
        view = named[0]
        out.lines.append(f"You have only one {low} note, {composer_lists._title(view)}, so there is nothing to compare it with.")  # noqa: SLF001
        return True
    _say_side_by_side(out, named, low)
    return True


# --- value slots (audit 1029 C21): one table, one reader -----------------------------------
#
# "What temperature do I bake at", "when is the race", "how many km did I run
# on Sunday" each ask for a VALUE: a number with a unit, a date. The sentence
# that answers must hold it; a sentence that only names the subject ("I bake
# sourdough on Sundays") is not the answer. A slot kind is one row: how its
# question is read (`ask`) and how its value is read out of a sentence
# (`read`). Adding a kind adds a row, never a branch in `_value`.


class Ask(NamedTuple):
    """What a value question names: the subject words, a unit, a weekday."""

    subject: list[str]
    unit: str | None = None
    day: str | None = None


class Slot(NamedTuple):
    kind: str
    ask: Callable[[list[str]], Ask | None]
    read: Callable[[str, str | None], str | None]
    #: What is missing when no sentence holds it ("a temperature"); `{unit}`
    #: is the question's own unit word.
    noun: str
    #: The ordinary readers already word a value they find (a day is worked
    #: out against the note's own date, "tomorrow" in a July note is not
    #: tomorrow): the slot only speaks to say that no sentence holds one.
    plain: bool = False


_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_AUX = frozenset({"do", "did", "does", "should", "shall", "must", "can", "could", "will", "would", "have", "has"})
_SELF = frozenset({"i", "we"})
_DONE = frozenset({"did", "have", "has"})
#: Words that frame the question and are not the thing it is about.
_CUES = frozenset({"temperature", "temp", "degrees", "date", "day", "many", "much", "time", "when", "what", "which", "at", "to", "of"})
#: A superlative asks which note is first or next, the ranker's question.
_RANKED = frozenset({"next", "first", "last", "latest", "newest", "upcoming", "previous", "earliest"})
#: Past forms the stemmer does not fold ("ran" is "run"), so a question that
#: says the verb meets the note that says it in the past.
_IRREGULAR = {
    "ran": "run", "wrote": "write", "ate": "eat", "swam": "swim", "rode": "ride", "drove": "drive", "bought": "buy",
    "went": "go", "flew": "fly", "took": "take", "made": "make", "baked": "bake", "cycled": "cycle", "walked": "walk",
}
#: Unit aliases by the unit a question names; the first is how the note's own
#: figure is read back to the person.
_UNITS = {
    "km": ("km", "kms", "kilometre", "kilometres", "kilometer", "kilometers"),
    "miles": ("miles", "mile", "mi"),
    "minutes": ("minutes", "minute", "mins", "min"),
    "hours": ("hours", "hour", "hrs", "hr"),
    "pages": ("pages", "page", "pp"),
    "kg": ("kg", "kgs", "kilo", "kilos", "kilogram", "kilograms"),
    "steps": ("steps", "step"),
    "calories": ("calories", "calorie", "kcal", "cal"),
    "litres": ("litres", "litre", "liters", "liter", "l"),
    "cups": ("cups", "cup"),
    "reps": ("reps", "rep"),
    "words": ("words", "word"),
    "glasses": ("glasses", "glass"),
}
_UNIT_OF = {alias: unit for unit, aliases in _UNITS.items() for alias in aliases}


def _flat(words: list[str], drop=()) -> list[str]:  # noqa: ANN001
    return [w for w in words if w not in drop]


def _ask_temperature(t: list[str]) -> Ask | None:
    """"what temperature do I bake at", "how hot do I bake the bread": a
    temperature asked of something I do."""
    if t[:2] == ["at", "what"]:
        t = t[1:]
    if t[:2] == ["how", "hot"]:
        t = ["what", "temperature", *t[2:]]
    if len(t) < 5 or t[0] != "what" or t[1] not in ("temperature", "temp") or t[2] not in _AUX or t[3] not in _SELF:
        return None
    return Ask(_flat(t[4:], ("at",)))


def _ask_date(t: list[str]) -> Ask | None:
    """"when is the race", "when do I fly", "what is the beta date": a day.
    "When did I buy the kindle" is not one: a done thing is dated by the
    note that tells it, which the when-answer says (the gold's day lead)."""
    if len(t) >= 3 and t[0] == "when" and t[1] not in _DONE and (t[1] in _AUX or t[1] in ("is", "are", "am")):
        subject = _flat(t[2:], _SELF)
    elif len(t) >= 3 and t[0] == "what" and ("date" in t[1:6] or "day" in t[1:6]):
        if any(w in t for w in ("today", "tomorrow", "yesterday", "week", "month", "year")):
            return None
        subject = _flat(t[1:], ("is", "are", "the", "my", "date", "day", "of", "on", "for"))
    else:
        return None
    return Ask(subject) if subject and not _RANKED & set(subject) else None


def _ask_quantity(t: list[str]) -> Ask | None:
    """"how many km did I run on Sunday": a count of a unit I did."""
    if len(t) < 6 or t[0] != "how" or t[1] not in ("many", "much") or t[2] not in _UNIT_OF or t[3] not in _AUX or t[4] not in _SELF:
        return None
    day = next((w for w in t[5:] if w in _WEEKDAYS), None)
    rest = _flat(t[5:], (*_WEEKDAYS, "on", "in", "during", "last", "this", "today", "yesterday", "week", "weekend"))
    return Ask(rest, _UNIT_OF[t[2]], day) if rest else None


@functools.cache
def _temperature_pattern() -> re.Pattern[str]:
    return re.compile(r"(?<![\w.])\d{2,3}(?:[.,]\d)?\s?(?:[°º]\s?[CFcf]?|(?i:degrees?|deg)\b|[CF]\b)|(?i:gas\s+mark\s+\d)")


@functools.cache
def _quantity_pattern(unit: str) -> re.Pattern[str]:
    aliases = "|".join(sorted(_UNITS.get(unit, (unit,)), key=len, reverse=True))
    return re.compile(rf"(?<![\w.,])\d+(?:[.,]\d+)?\s?(?i:{aliases})\b")


def _read_temperature(text: str, unit: str | None) -> str | None:
    found = _temperature_pattern().search(text)
    return found.group(0).strip() if found else None


def _read_quantity(text: str, unit: str | None) -> str | None:
    found = _quantity_pattern(_UNIT_OF.get(unit or "", unit or "")).search(text) if unit else None
    return found.group(0).strip() if found else None


def _read_date(text: str, unit: str | None) -> str | None:
    """The first time phrase that names a day: a date, not a bare "May"."""
    for _start, _end, phrase in when_words.find(text):
        if recognise.names_a_day(phrase):
            return phrase
    return None


#: The table. A new kind is a row here.
SLOTS = (
    Slot("temperature", _ask_temperature, _read_temperature, "temperature"),
    Slot("date", _ask_date, _read_date, "date", plain=True),
    Slot("quantity", _ask_quantity, _read_quantity, "number of {unit}"),
)


def read_value(kind: str, text: str, unit: str | None = None) -> str | None:
    """The value of slot `kind` in `text` ("230C", "12 km", "14 November"), or None."""
    slot = next((s for s in SLOTS if s.kind == kind), None)
    return slot.read(text, unit) if slot else None


def _norm(text: str) -> list[str]:
    return [_IRREGULAR.get(w, w) for w in composer._words(text)]  # noqa: SLF001


def _subject_stems(subject: list[str]) -> list[str]:
    seen: list[str] = []
    for w in _norm(" ".join(subject)):
        if w not in _FILLER and w not in _CUES and w not in _AUX and w not in seen:
            seen.append(w)
    return seen


def _score(view, sentence, stems: list[str]) -> int:  # noqa: ANN001
    """How much of the subject a sentence and its note's title and filing hold:
    twice for the sentence's own words, once for the heading's."""
    have = set(_norm(sentence.text))
    head = set(view.title_words) | set(view.filed_words)
    return sum(2 * composer._holds(s, have) + composer._holds(s, head) for s in stems)  # noqa: SLF001


def _weekday_fits(ask: Ask, view, sentence) -> int:  # noqa: ANN001
    """1 when the sentence names the weekday asked, -1 when it names another
    (so "On Saturday I ran 5 km" is not Sunday's answer), else 0."""
    if not ask.day:
        return 0
    named = {w for w in re.split(r"\W+", sentence.text.lower()) if w in _WEEKDAYS}
    if named:
        return 1 if ask.day in named else -1
    return 1 if view.written and _WEEKDAYS[view.written.weekday()] == ask.day else 0


def _value(out, slot: Slot, ask: Ask, views: list, today: date) -> bool:  # noqa: ANN001
    """The sentence of the notes that names the subject AND holds the slot's
    value; else the plain statement that none does, with the nearest note."""
    stems = _subject_stems(ask.subject)
    if not stems:
        return False
    held, near = [], []
    for view in views:
        for s in view.sentences:
            if s.kind in ("picture", "picture_text"):
                continue
            score = _score(view, s, stems)
            if not score:
                continue
            near.append((score, -view.rank, view, s))
            value = slot.read(s.text, ask.unit)
            fit = _weekday_fits(ask, view, s)
            if value and fit >= 0:
                held.append((score, fit, -view.rank, view, s, value))
    if held and slot.plain:
        return False
    if held:
        _score_, _fit, _rank, view, s, value = max(held, key=lambda h: h[:3])
        line = f"Your notes say {value}, in {composer_lists._title(view)}: {s.text.strip()}"  # noqa: SLF001
        out.lines.append(line)
        composer_lists._cite(out, view, s, line)  # noqa: SLF001
        return True
    subject = " ".join(_flat(ask.subject, _AUX | _SELF)) or stems[0]
    missing = slot.noun.format(unit=ask.unit or "")
    if not near:
        out.lines.append(f"I found no note about {subject}, so I have no {missing} to give.")
        return True
    _score_, _rank, view, s = max(near, key=lambda n: n[:2])
    line = f"Your notes do not say a {missing} for {subject}. The nearest is {composer_lists._title(view)}: {s.text.strip()}"  # noqa: SLF001
    out.lines.append(line)
    composer_lists._cite(out, view, s, line)  # noqa: SLF001
    return True


# --- how often, how old (audit 1029 C23) ----------------------------------------------------

#: What a note says when it gives a thing's start ("started on", "since",
#: "bought", "born"); the date in that sentence is the start date.
_START = frozenset({"start", "begin", "begun", "since", "born", "buy", "make", "create", "plant", "adopt", "found", "open", "join", "install", "build", "brew", "from"})
_ABOUT = frozenset({"write", "wrote", "written", "note", "post", "journal", "log", "about", "on", "mention", "talk", "think"})


def _filed_under(views: list, stems: list[str]) -> list:
    """The notes TITLED or TAGGED with every stem (the filing says what a note
    is about; a passing mention does not)."""
    return sorted((v for v in views if all(s in v.title_words or s in v.filed_words for s in stems)), key=lambda v: v.rank)


def _often(out, rest: list[str], views: list, today: date) -> bool:  # noqa: ANN001
    """"How often do I write about baking": the notes titled or tagged baking,
    counted, with the gap between them; a mention in another note is not one."""
    if rest[0] in ("mention", "mentioned"):
        return False  # a count of mentions: `composer_lists` counts them
    stems = _stems(" ".join(w for w in rest if w not in _ABOUT))
    if not stems:
        return False
    subject = " ".join(w for w in rest if w not in _ABOUT and w not in _FILLER)
    filed = _filed_under(views, stems)
    if not filed:
        if rest[0] not in _ABOUT:
            #: "how often do I water the garden" with no log filed under it:
            #: a sentence says how often ("Water every second day"), the
            #: ordinary answer's to find (2026-10-30 sweep).
            return False
        return _only_mentioned(out, views, stems, subject)
    out.lines.append(_often_line(filed, subject, today) + ":")
    for v in filed[:6]:
        first = next((x for x in v.sentences if x.kind in ("prose", "item", "task")), None)
        entry = f"- {composer_lists._title(v)}"  # noqa: SLF001
        out.lines.append(entry)
        if first is not None:
            composer_lists._cite(out, v, first, entry)  # noqa: SLF001
    return True


def _only_mentioned(out, views: list, stems: list[str], subject: str) -> bool:  # noqa: ANN001
    """No note is filed under the subject: say how many mention it, or False."""
    said = [v for v in views if all(composer._holds(s, set(v.words)) for s in stems)]  # noqa: SLF001
    if not said:
        return False
    out.lines.append(f"No note is titled or tagged {subject}; {composer_lists._plural(len(said), 'note')} only {'mentions' if len(said) == 1 else 'mention'} it in passing.")  # noqa: SLF001
    return True


def _often_line(filed: list, subject: str, today: date) -> str:
    """How many notes are filed under the subject, from when to when and how far apart."""
    days = sorted(v.written for v in filed if v.written)
    line = f"You have {composer_lists._plural(len(filed), 'note')} titled or tagged {subject}"  # noqa: SLF001
    if len(days) >= 2 and days[-1] > days[0]:
        gap = round((days[-1] - days[0]).days / (len(days) - 1))
        line += f", from {composer_lists._day(days[0], today)} to {composer_lists._day(days[-1], today)}"  # noqa: SLF001
        line += f", about one every {composer_lists._plural(max(gap, 1), 'day')}"  # noqa: SLF001
    return line


def _start_day(view, today: date) -> tuple[date, object] | None:  # noqa: ANN001
    """`(day, sentence)` of the earliest past day a sentence of the note gives
    as a start ("Started on 1 September")."""
    found = []
    for s in view.sentences:
        if not _START & set(_norm(s.text)):
            continue
        for day, at in composer._days_named(view, today, "past"):  # noqa: SLF001
            if s.start <= at < s.end:
                found.append((day, s))
    return min(found, key=lambda f: f[0]) if found else None


def _old(out, rest: list[str], views: list, today: date) -> bool:  # noqa: ANN001
    """"How old is my sourdough starter": today less the start date the note
    gives; when it gives none, that is said."""
    stems = _stems(" ".join(rest))
    if not stems:
        return False
    named = composer._notes_named_by(views, set(stems))  # noqa: SLF001
    named = sorted(named, key=lambda v: (not _title_holds(v, stems), v.rank))
    if not named:
        return False
    subject = " ".join(w for w in rest if w not in _FILLER)
    for view in named:
        if got := _start_day(view, today):
            day, s = got
            n = (today - day).days
            line = f"Your {subject} is {composer_lists._plural(n, 'day')} old, started on {composer_lists._day(day, today)}"  # noqa: SLF001
            line += f", about {n // 30} months." if n >= 60 else "."
            out.lines.append(line)
            composer_lists._cite(out, view, s, line)  # noqa: SLF001
            return True
    view = named[0]
    first = next((x for x in view.sentences if x.kind in ("prose", "item", "task")), None)
    line = f"Your notes do not say when your {subject} was started, so I cannot work out its age. The nearest is {composer_lists._title(view)}."  # noqa: SLF001
    out.lines.append(line)
    if first is not None:
        composer_lists._cite(out, view, first, line)  # noqa: SLF001
    return True


def answer(out, asked: str, views: list, today: date) -> bool:  # noqa: ANN001
    """Say the slot's answer, or that no note holds it; False when `asked` is
    not a slot question this module reads."""
    q = composer_lists._q(asked)  # noqa: SLF001
    if _PAIR_LEAD.match(" ".join(q.lower().split())) and _pair(out, q, views, today):
        return True
    tokens = q.lower().replace("'s ", " is ").split()
    shaped = _by_words(out, tokens, views, today)
    if shaped is not None:
        return shaped
    for pattern, say in ((_SINCE, _since), (_DID, _did), (_NEED, _left), (_LEFT, _left)):
        if m := pattern.match(q):
            return say(out, m.group(1), views, today)
    return False


def _by_words(out, tokens: list[str], views: list, today: date) -> bool | None:  # noqa: ANN001
    """A value slot's answer (True, or False when the slot cannot say), how
    often or how old; None when the words ask none of these."""
    if tokens and tokens[0] in ("what", "when", "how", "at"):
        for slot in SLOTS:
            if (ask := slot.ask(tokens)) is not None:
                return _value(out, slot, ask, views, today)
    if len(tokens) > 4 and tokens[0] == "how" and tokens[1] == "often" and tokens[2] in _AUX and tokens[3] in _SELF and _often(out, tokens[4:], views, today):
        return True
    if len(tokens) > 3 and tokens[:2] == ["how", "old"] and tokens[2] in ("is", "are", "was") and _old(out, tokens[3:], views, today):
        return True
    return None
