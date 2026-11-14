"""The model's `[Sn]` sentence marks, taken out of the answer and kept as
grounding (L-chat-59; CHAT_PLAN "the handoff protocol" step 3).

`composer.brief` writes each sentence it chose after an id, `[S1]`, `[S2]`,
and the prompt asks the model to write the id after a sentence of its own
that uses one. The person never sees an id: `MarkScrubber` takes them out of
the stream, holding back a delta's tail that could still become one (as
`fence.AnswerScrubber` does for fence markers), and remembers the words just
before each, so `rows` can name the answer sentence that cited it once the
answer is whole.
"""

from __future__ import annotations

import re

from tessellate.ai.grounding import split_sentences
from tessellate.ai.composer_read import NoteView, Sentence

#: A mark as the model writes it, with the one space before it. A 1.5B model
#: also writes `(S1)`, taken only for an id the brief gave, and echoes the
#: prompt's bare `[S]`, which is taken out and names nothing.
_MARK = re.compile(r"[ \t]?(?:\[S(\d{0,3})\]|\(S(\d{1,3})\))")
#: What may still turn into a mark at the end of a delta.
_PARTIAL = re.compile(r"[ \t]?[\[(](?:S\d{0,3})?$")
#: The answer's words before a mark, kept to find its sentence afterwards.
TAIL_CHARS = 48


class MarkScrubber:
    """Takes `[Sn]` marks out of a streamed answer and records each one."""

    def __init__(self, marks: dict[str, dict]) -> None:
        self.marks = marks
        self.said = ""
        self.cites: list[tuple[str, str]] = []
        self._held = ""

    def feed(self, delta: str) -> str:
        if not self.marks:
            return delta or ""
        text = self._held + (delta or "")
        self._held = ""
        out: list[str] = []
        last = 0
        for m in _MARK.finditer(text):
            mark = f"S{m.group(1) or m.group(2) or ''}"
            if m.group(2) and mark not in self.marks:
                continue
            out.append(text[last : m.start()])
            self.said += text[last : m.start()]
            if mark in self.marks:
                self.cites.append((self.said[-TAIL_CHARS:].strip(), mark))
            last = m.end()
        rest = text[last:]
        partial = _PARTIAL.search(rest)
        if partial:
            self._held = rest[partial.start() :]
            rest = rest[: partial.start()]
        out.append(rest)
        self.said += rest
        return "".join(out)

    def flush(self) -> str:
        held, self._held = self._held, ""
        self.said += held
        return held


def rows(answer: str, scrubber: MarkScrubber | None) -> list[dict]:
    """One grounding row per answer sentence that cited a mark: the sentence
    and the note of the brief sentence it named."""
    if scrubber is None or not scrubber.cites:
        return []
    sentences = split_sentences(answer)
    out: list[dict] = []
    for tail, mark in scrubber.cites:
        #: The words since the last sentence end, so a short cited sentence is
        #: not looked for with the end of the one before it.
        key = re.split(r"(?<=[.!?])\s+", tail)[-1][-24:].strip()
        sentence = next((s for s in sentences if key and key in s), None)
        if sentence is None:
            continue
        row = {"sentence": sentence, "note_id": scrubber.marks[mark]["note_id"], "cited": mark}
        if not any(r["sentence"] == sentence and r["note_id"] == row["note_id"] for r in out):
            out.append(row)
    return out


def pack(notes: list[dict], views: dict, by_note: dict, whole: float) -> tuple[list[dict], dict, int, int, int]:
    """`composer.brief`'s notes as the model reads them, each chosen sentence
    after its `[Sn]` id (CHAT_PLAN handoff step 3), with the ids, how many
    notes were shortened, and the characters before and after. A note the cut
    would barely shorten (`whole` of its length) goes whole."""
    out: list[dict] = []
    shortened = before = after = 0
    marks: dict[str, dict] = {}
    for i, note in enumerate(notes):
        content = str(note.get("content") or "")
        before += len(content)
        view = views.get(i)
        text = _brief_text(view, content, by_note) if view else None
        if text is None or len(text) >= whole * len(content.strip()):
            out.append(note)
            after += len(content)
            continue
        had = len(marks)
        text = _brief_text(view, content, by_note, marks)
        out.append({**note, "content": text, "briefed": True, **({"marked": True} if len(marks) > had else {})})
        after += len(text)
        shortened += 1
    if len({mark["note_id"] for mark in marks.values()}) < 2:
        #: One note's sentences need no ids: every sentence of the answer can
        #: only be grounded in that note, and the ids and the line asking for
        #: them cost the brief its measured saving on short notes.
        out, marks = _unmarked(out, notes, views, by_note), {}
    return out, marks, shortened, before, after


def _raw(content: str, s: Sentence) -> str:
    """The sentence as the note has it: the offsets, not the cleaned text, so a
    model reads (and the grounding pass later matches) the person's words."""
    return " ".join(content[s.start : s.end].split())


def _unmarked(out: list[dict], notes: list[dict], views: dict, by_note: dict) -> list[dict]:
    """The brief's notes again, without `[Sn]` ids."""
    plain = []
    for i, note in enumerate(out):
        if note.get("marked"):
            note = {k: v for k, v in note.items() if k != "marked"}
            note["content"] = _brief_text(views[i], str(notes[i].get("content") or ""), by_note)
        plain.append(note)
    return plain


def _brief_text(view: NoteView, content: str, by_note: dict[int, list[Sentence]], marks: dict | None = None) -> str:
    """One note's part of the brief: its name, then the sentences kept.

    With `marks`, each sentence the composer chose (not the first-sentence
    stand-in of a note it chose none from) is written after its `[Sn]` id,
    and the id's note and span are added to `marks`."""
    if view.id in by_note:
        picked = sorted(by_note[view.id], key=lambda s: s.order)
    else:
        picked = view.sentences[:1]
    parts: list[str] = []
    #: An untitled note is named by its first words; when its first sentence
    #: is kept, the name would only say those words twice.
    opens_with_name = bool(picked) and picked[0].order == 0 and _raw(content, picked[0]).startswith(view.title.rstrip("…"))
    if view.title and not opens_with_name:
        parts.append(view.title)
    last = -1
    chosen = marks is not None and view.id in by_note
    for s in picked:
        if parts and s.order != last + 1:
            parts.append("…")
        if chosen:
            mark = f"S{len(marks) + 1}"
            marks[mark] = {"note_id": view.id, "start": s.start, "end": s.end}
            parts.append(f"[{mark}] {_raw(content, s)}")
        else:
            parts.append(_raw(content, s))
        last = s.order
    if last < len(view.sentences) - 1:
        parts.append("…")
    return " ".join(parts)


def with_cited(answer: str, grounding: list[dict], scrubber, allowed: set[int]) -> list[dict]:  # noqa: ANN001
    """The rows the model's own `[Sn]` marks name, beside the similarity rows,
    in answer order; a mark is the model's word for which sentence it used,
    so it counts even where the words drifted."""
    have = {(row["sentence"], row["note_id"]) for row in grounding}
    cited = [row for row in rows(answer, scrubber) if row["note_id"] in allowed and (row["sentence"], row["note_id"]) not in have]
    if not cited:
        return grounding
    return sorted([*grounding, *cited], key=lambda row: answer.find(row["sentence"]))
