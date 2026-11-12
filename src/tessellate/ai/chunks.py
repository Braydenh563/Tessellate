"""A note's paragraphs as character spans (WORLD_CLASS_PLAN section 14 item 3).

Its own module, not inside `embeddings`: the composer cites a quote by its
paragraph (`grounding.paragraph_ordinal`) and answers with no model, and
importing `embeddings` for this brought the model manager, the database models
and SQLAlchemy with it, 0.6 to 1.8 s on the first answer (engine probe P8).
`embeddings` re-exports every name here, so the stored chunk rows and the
citations still read one split.
"""

from __future__ import annotations

import re

#: A paragraph shorter than this joins the next one: a heading, a one-line
#: list item or a sign-off is not a subject on its own, and a vector of three
#: words matches every question that shares one of them.
CHUNK_MIN_WORDS = 12
#: A paragraph longer than this is cut at a sentence end. Small embedding
#: models read about 256 to 512 tokens and quietly drop the rest, so a
#: 600-word paragraph embedded whole is its first half.
CHUNK_MAX_WORDS = 160
#: The most chunks one note stores. A book pasted into a note would otherwise
#: be hundreds of embeds inside one save; past this the note vector covers the
#: rest, which is what every note had before chunks existed.
CHUNK_MAX_PER_NOTE = 32

_PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n+")
#: The stop is matched, not looked behind: CodeQL ignores a lookbehind and reads a bare `\s+` as polynomial;
#: only `m.end()` is used, which is the same either way.
_SENTENCE_END = re.compile(r"[.!?]\s+")
_CHUNK_WORD = re.compile(r"[^\W_]+", re.UNICODE)


def _word_count(text: str) -> int:
    return len(_CHUNK_WORD.findall(text))


def _blocks_with_offsets(text: str) -> list[tuple[int, int]]:
    """`(start, end)` of every non-blank paragraph, trimmed of outer space."""
    spans: list[tuple[int, int]] = []
    position = 0
    for match in [*_PARAGRAPH_BREAK.finditer(text), None]:
        end = match.start() if match else len(text)
        piece = text[position:end]
        if piece.strip():
            lead = len(piece) - len(piece.lstrip())
            trail = len(piece) - len(piece.rstrip())
            spans.append((position + lead, end - trail))
        if match:
            position = match.end()
    return spans


def _split_long(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Cut one over-long paragraph at sentence ends, about `CHUNK_MAX_WORDS` each."""
    body = text[start:end]
    cuts = [0] + [m.end() for m in _SENTENCE_END.finditer(body)] + [len(body)]
    out: list[tuple[int, int]] = []
    piece_start, words = 0, 0
    for left, right in zip(cuts, cuts[1:]):
        words += _word_count(body[left:right])
        if words >= CHUNK_MAX_WORDS:
            out.append((piece_start, right))
            piece_start, words = right, 0
    if piece_start < len(body):
        if out and _word_count(body[piece_start:]) < CHUNK_MIN_WORDS:
            out[-1] = (out[-1][0], len(body))
        else:
            out.append((piece_start, len(body)))
    spans = []
    for left, right in out:
        piece = body[left:right]
        lead = len(piece) - len(piece.lstrip())
        trail = len(piece) - len(piece.rstrip())
        spans.append((start + left + lead, start + right - trail))
    return [span for span in spans if span[1] > span[0]]


def paragraph_chunks(text: str) -> list[tuple[int, int]]:
    """The paragraphs of a note as `(start, end)` character spans, in order.

    Blank lines separate paragraphs, as they do in every Markdown note; a
    short paragraph joins the one after it (a heading reads as part of what it
    heads), a long one is cut at sentence ends. A note that comes out as one
    chunk returns one span, and the caller stores nothing for it: that chunk
    *is* the note, and its vector already exists.
    """
    text = text or ""
    spans: list[tuple[int, int]] = []
    pending: tuple[int, int] | None = None
    for start, end in _blocks_with_offsets(text):
        if pending is not None:
            start = pending[0]
            pending = None
        words = _word_count(text[start:end])
        if words < CHUNK_MIN_WORDS:
            pending = (start, end)
            continue
        if words > CHUNK_MAX_WORDS:
            spans.extend(_split_long(text, start, end))
        else:
            spans.append((start, end))
    if pending is not None:
        if spans:
            spans[-1] = (spans[-1][0], pending[1])
        else:
            spans.append(pending)
    return spans[:CHUNK_MAX_PER_NOTE]
