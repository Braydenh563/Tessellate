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

import re
from datetime import date

from tessellate.ai import composer, composer_lists

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
    name = " ".join(w for w in rest.split() if w.lower() not in {"on", "for", "to", "at", "the", "my", "a", "do", "bring", "before"}) or "that"
    if not open_ and not done:
        out.lines.append(f"I found no checklist for {name} in your notes.")
        return True
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


def _did(out, rest: str, views: list, today: date) -> bool:  # noqa: ANN001
    words = rest.split()
    if len(words) < 2:
        return False
    verb = _stems(words[0])
    obj = _stems(" ".join(words[1:]))
    if not obj:
        return False
    best = None
    for view in sorted(views, key=lambda v: v.rank):
        for s in view.sentences:
            if not _holds(s, obj):
                continue
            if s.kind == "task":
                best = best or (view, s)
                if not verb or _holds(s, verb):
                    best = (view, s)
                    break
            elif verb and _holds(s, verb + obj):
                best = best or (view, s)
        else:
            continue
        break
    if best is None:
        out.lines.append(f"I found nothing in your notes that says you {rest}.")
        return True
    view, s = best
    if s.kind == "task":
        _verdict(out, view, s, words[0])
    else:
        day = view.written
        when = f" (your note of {composer_lists._day(day, today)})" if day else ""  # noqa: SLF001
        out.lines.append(f"Yes, your notes say so{when}: {s.text.strip()}")
        composer_lists._cite(out, view, s, s.text)  # noqa: SLF001
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


def _pair(out, q: str, views: list, today: date) -> bool:  # noqa: ANN001
    """"Compare the two lentil soup notes": both sides, side by side, or which
    side is missing (audit 1029 C36). Read in code, not by a pattern, so a long
    question costs nothing."""
    low = " ".join(q.lower().split())
    for lead in ("compare the two ", "compare my two ", "compare two "):
        if low.startswith(lead):
            low = low[len(lead):]
            break
    else:
        return False
    for tail in (" notes", " note", " ones"):
        if low.endswith(tail):
            low = low[: -len(tail)]
            break
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
    return True


def answer(out, asked: str, views: list, today: date) -> bool:  # noqa: ANN001
    """Say the slot's answer, or that no note holds it; False when `asked` is
    not a slot question this module reads."""
    q = composer_lists._q(asked)  # noqa: SLF001
    if q.lower().startswith("compare ") and _pair(out, q, views, today):
        return True
    if m := _SINCE.match(q):
        return _since(out, m.group(1), views, today)
    if m := _DID.match(q):
        return _did(out, m.group(1), views, today)
    if m := _NEED.match(q):
        return _left(out, m.group(1), views, today)
    if m := _LEFT.match(q):
        return _left(out, m.group(1), views, today)
    return False
