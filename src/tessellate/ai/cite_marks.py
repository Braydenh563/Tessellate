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
