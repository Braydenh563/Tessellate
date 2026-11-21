"""The person's word on a line of an answer (CHAT_PLAN B31 and B32).

"Wrong fact" and "Pin as true" sit on a cited line's peek, on the note's own
sentence the line was made from. Each is a derived fact the person wrote
(`DerivedFact`, kind "wrong" or "pinned", model "you"), so What it learned
lists it, its Delete is the undo, and decision 68's audit reads it beside
every claim it re-checks; each is also a correction (`learning.record`), so
"what has the app been getting wrong" has it.

From the next turn: a sentence marked wrong is not quoted, and no insight
that quotes it is volunteered; a pinned sentence is said as the person's own
word, with the day they pinned it, and no inference that quotes it is
volunteered beside it. A model is handed the same notes with the same
verdicts written into them (`for_model`), as context, never as the reply
(decision 75).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date

from tessellate.core import clock

WRONG = "wrong"
PINNED = "pinned"
VERDICTS = (WRONG, PINNED)
_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")


def norm(text: str) -> str:
    """A sentence as compared: spacing, case and end marks do not count."""
    return " ".join(str(text or "").split()).strip(" .!?;:,").lower()


def day_words(on: date) -> str:
    return f"{on.day} {_MONTHS[on.month - 1]}"


@dataclass(frozen=True)
class Known:
    """What the person said of sentences: `wrong` and `pinned` are keyed on
    (note id, `norm(sentence)`); a pin holds the day it was made."""

    wrong: frozenset = frozenset()
    pinned: dict = field(default_factory=dict)

    def is_wrong(self, note_id, text: str) -> bool:  # noqa: ANN001
        return (note_id, norm(text)) in self.wrong

    def pinned_on(self, note_id, text: str) -> date | None:  # noqa: ANN001
        return self.pinned.get((note_id, norm(text)))

    def quoted_in(self, text: str) -> bool:
        """Whether `text` (an insight's line) quotes a sentence ruled on."""
        said = norm(text)
        return any(sentence and sentence in said for _, sentence in (*self.wrong, *self.pinned))

    def __bool__(self) -> bool:
        return bool(self.wrong or self.pinned)


def known(session) -> Known:  # noqa: ANN001
    """The verdicts on notes the person can still open (`facts._visible`)."""
    from sqlalchemy import select

    from tessellate.ai import facts
    from tessellate.core.database import DerivedFact

    wrong, pinned = set(), {}
    for row in session.scalars(facts._visible(select(DerivedFact)).where(DerivedFact.kind.in_(VERDICTS))):
        key = (row.entry_id, norm(row.original_text or row.text))
        if row.kind == WRONG:
            wrong.add(key)
        else:
            pinned[key] = (row.computed_at.date() if row.computed_at else clock.today())
    return Known(frozenset(wrong - set(pinned)), pinned)


def mark(session, verdict: str, note_id: int, sentence: str, start: int, end: int, line: str = "") -> dict:  # noqa: ANN001
    """Write one verdict on the note's own sentence. The sentence must be in
    the note as it is now: a line quoting a note since edited is refused,
    since a verdict on words the note no longer holds would rest on nothing."""
    from tessellate.ai import learning
    from tessellate.core.database import DerivedFact, Entry

    if verdict not in VERDICTS:
        raise ValueError("That is not something a line can be marked.")
    entry = session.get(Entry, note_id)
    if entry is None or entry.is_deleted or entry.is_private:
        raise ValueError("That note could not be found.")
    content = entry.content or ""
    if not (0 <= start < end <= len(content)) or norm(content[start:end]) != norm(sentence):
        found = content.find(" ".join(sentence.split()))
        if found < 0:
            raise ValueError("That note no longer says this. Ask again to see it as it is now.")
        start, end = found, found + len(" ".join(sentence.split()))
    words = " ".join(content[start:end].split())
    row = DerivedFact(
        entry_id=note_id, kind=verdict, text=words, span_start=start, span_end=end, model="you", confidence=1.0,
        edited_by_user=True, original_text=words,
        payload=json.dumps({"line": " ".join(str(line or "").split())[:400], "source": f"{'marked wrong' if verdict == WRONG else 'pinned as true'} by you"}),
    )
    session.add(row)
    learning.record(
        session, kind="wrong_fact" if verdict == WRONG else "pin_fact",
        subject={"entry_id": note_id, "start": start, "end": end}, from_value=words if verdict == WRONG else None,
        to_value=words if verdict == PINNED else None, excerpt=line or words,
    )
    session.flush()
    return {"id": row.id, "verdict": verdict, "sentence": words}


def for_model(notes: list[dict], verdicts: Known, *, id_key: str = "id") -> list[dict]:
    """The notes a model reads, with the person's verdicts written in: a
    sentence marked wrong taken out, a pinned one said as theirs. Copies:
    the notes grounding reads stay as the notebook has them."""
    if not verdicts:
        return notes
    out = []
    for note in notes:
        content = str(note.get("content") or "")
        if str(note.get("kind") or "note").lower() not in ("note", ""):
            out.append(note)
            continue
        nid = note.get(id_key)
        changed = content
        for owner, sentence in verdicts.wrong:
            if owner == nid:
                changed = _replace(changed, sentence, "")
        for (owner, sentence), on in verdicts.pinned.items():
            if owner == nid:
                changed = _replace(changed, sentence, None, f" [pinned as true by the person, {day_words(on)}]")
        out.append({**note, "content": changed} if changed != content else note)
    return out


def without_wrong(text: str, note_id, verdicts: Known) -> str:  # noqa: ANN001
    """A note's text with every sentence the person marked wrong taken out:
    what filing reads (WORLD_CLASS I7), so a sentence ruled wrong on an
    evidence card no longer decides where its note, or a note like it, goes."""
    for owner, sentence in verdicts.wrong:
        if owner == note_id:
            text = _replace(text, sentence, "")
    return text


def _replace(content: str, sentence: str, with_text: str | None, after: str = "") -> str:
    """`content` with the sentence matching `sentence` (as `norm` reads it)
    replaced by `with_text`, or kept with `after` added (`with_text` None)."""
    import re

    words = [re.escape(w) for w in sentence.split()]
    if not words:
        return content
    pattern = re.compile(r"\s+".join(words) + r"[.!?]?", re.I)
    m = pattern.search(content)
    if not m:
        return content
    keep = m.group(0) if with_text is None else with_text
    return content[: m.start()] + keep + after + content[m.end():]
