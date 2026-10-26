"""The AI-only text buttons, done by plain rule when no model runs (owner-1026b
K3, INBOX 1357): naming a draft and splitting a text into notes.

Both take only what the text already holds, in the order it holds it: a title
is its own first words, a split is its own headings and paragraphs. Nothing is
reworded, so nothing here needs a model, and the preview and the draft's undo
still let the person read it before it counts.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from tessellate.search import query as query_understanding

#: `composer_voice.TITLE_WORDS`, repeated here so importing this module does
#: not load the composer; `title_for` itself is imported where it is used.
TITLE_WORDS = 7
#: A part this short is a scrap ("Notes:", "TODO"), not a note: it joins its neighbour.
SCRAP_WORDS = 4

_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(\S.*?)(?:\s+#+)?\s*$")
_RULE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")
_MARKS = re.compile(r"^(?:\s*(?:[-*+>]|\d+[.)]|\[[ xX]\]|#{1,6}))+\s*")


@dataclass
class Part:
    title: str
    content: str


def _count(text: str) -> int:
    return len(re.findall(r"\w+", text))


def _clean_line(line: str) -> str:
    text = _MARKS.sub("", line.strip())
    return re.sub(r"[*_`~]+", "", text).strip()


def _trim(words: list[str]) -> str:
    from tessellate.ai import composer_voice

    stop = query_understanding.STOPWORDS | composer_voice.TITLE_DANGLING
    words = words[:TITLE_WORDS]
    while words and (words[-1].lower().strip(",;:") in stop or words[-1].endswith((",", ";", ":"))):
        words.pop()
    title = " ".join(words).strip(" ,;:-.!?")
    return title[:1].upper() + title[1:] if title else ""


def draft_title(draft: str) -> str:
    """A title from the draft's own words, or "" when there is nothing to name.

    In order: its first sentence (`composer_voice.title_for`, a lead-in such as
    "Remember to" off, seven words at most); else its first line with the
    markdown marks off; else its most repeated words. A draft that opens with a
    heading is named from what follows it, and by the heading when nothing does.
    """
    from tessellate.ai import composer_voice

    lines = (draft or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    heading = ""
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        found = _HEADING.match(line)
        if found:
            heading = found.group(1).strip()
            lines = lines[i + 1 :]
        break
    body = "\n".join(lines).strip()
    title = composer_voice.title_for(_without_marks(body)) if body else ""
    if not title:
        for line in lines:
            first = _clean_line(line)
            words = first.split()
            if words and len(first) >= 3 and not _RULE.match(line):
                title = _trim(words)
                if title:
                    break
    if not title:
        title = _top_terms(body)
    if not title and heading:
        title = _trim(heading.split())
    return title if len(title) >= 3 else ""


def _without_marks(body: str) -> str:
    """Bullets, quote marks and bold stripped line by line, so the first
    sentence reads as prose rather than as a list item or a quotation."""
    return "\n".join(_clean_line(line) if _MARKS.match(line) or "*" in line else line for line in body.split("\n"))


def _top_terms(text: str) -> str:
    stop = query_understanding.STOPWORDS
    seen: dict[str, int] = {}
    counts: Counter = Counter()
    for i, word in enumerate(re.findall(r"[A-Za-z][A-Za-z'-]{3,}", text)):
        key = word.lower()
        if key in stop:
            continue
        counts[key] += 1
        seen.setdefault(key, i)
    if not counts:
        return ""
    top = sorted(counts, key=lambda k: (-counts[k], seen[k]))[:3]
    top.sort(key=lambda k: seen[k])
    return " ".join(top).capitalize()


def _blocks(lines: list[str]) -> list[list[str]]:
    """Blank-line blocks, a rule line counting as a blank and a code fence
    holding its own blank lines."""
    blocks: list[list[str]] = []
    current: list[str] = []
    fenced = False
    for line in lines:
        if _FENCE.match(line):
            fenced = not fenced
        if not fenced and (not line.strip() or _RULE.match(line)):
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(line)
    if current:
        blocks.append(current)
    return blocks


def _headings(lines: list[str]) -> list[int]:
    out, fenced = [], False
    for i, line in enumerate(lines):
        if _FENCE.match(line):
            fenced = not fenced
        elif not fenced and _HEADING.match(line):
            out.append(i)
    return out


def _strip_rules(lines: list[str]) -> list[str]:
    out, fenced = [], False
    for line in lines:
        if _FENCE.match(line):
            fenced = not fenced
        if fenced or not _RULE.match(line):
            out.append(line)
    return out


def _merge(chunks: list[str], lo: int) -> None:
    chunks[lo : lo + 2] = [chunks[lo] + "\n\n" + chunks[lo + 1]]


def split_notes(text: str, limit: int) -> list[Part]:
    """One part per heading, or per paragraph when the text has fewer than two
    headings. A section keeps its heading as its first line (a note's title in
    this app is its leading heading); scraps join the part beside them; more
    parts than `limit` are merged, shortest pair first, never dropped."""
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    marks = _headings(lines)
    chunks: list[str] = []
    if len(marks) >= 2:
        edges = [0, *marks, len(lines)] if marks[0] > 0 else [*marks, len(lines)]
        chunks = ["\n".join(_strip_rules(lines[a:b])).strip() for a, b in zip(edges, edges[1:])]
    else:
        bare_heading = False
        for block in _blocks(lines):
            body = "\n".join(block)
            if bare_heading:
                chunks[-1] += "\n\n" + body
                bare_heading = False
                continue
            chunks.append(body)
            bare_heading = len(block) == 1 and bool(_HEADING.match(block[0]))
    chunks = [c for c in chunks if c.strip()]
    i = 0
    while len(chunks) > 1 and i < len(chunks):
        if _count(chunks[i]) < SCRAP_WORDS:
            _merge(chunks, i if i + 1 < len(chunks) else i - 1)
            i = max(i - 1, 0)
        else:
            i += 1
    while len(chunks) > max(limit, 1):
        k = min(range(len(chunks) - 1), key=lambda j: _count(chunks[j]) + _count(chunks[j + 1]))
        _merge(chunks, k)
    return [_part(c) for c in chunks]


def _part(chunk: str) -> Part:
    from tessellate.ai import composer_voice

    found = _HEADING.match(chunk.split("\n", 1)[0])
    title = found.group(1) if found else composer_voice.title_for(_without_marks(chunk))
    return Part(title=title, content=chunk)
