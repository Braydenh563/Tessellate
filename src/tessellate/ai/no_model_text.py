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
#: A part this short is a scrap ("Notes:", a bare marker word), not a note: it joins its neighbour.
SCRAP_WORDS = 4

# Prefixes only, each bounded: the rest of the line is trimmed in Python, so
# no two unbounded runs of whitespace meet (CodeQL: a line of tabs went
# polynomial through `\s+(\S.*?)(?:\s+#+)?\s*$`).
_HEADING_LEAD = re.compile(r"[ \t]{0,3}#{1,6}[ \t]+")
_RULE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")
_MARK = re.compile(r"[-*+>]|\d{1,9}[.)]|\[[ xX]\]|#{1,6}")


@dataclass
class Part:
    title: str
    content: str


def _heading(line: str) -> str | None:
    """A Markdown heading's text, closing hashes dropped, or None."""
    lead = _HEADING_LEAD.match(line)
    if not lead:
        return None
    text = line[lead.end() :].rstrip()
    bare = text.rstrip("#")
    if bare != text and bare.strip() and bare[-1] in " \t":
        text = bare.rstrip()
    return text or None


def _marks_end(line: str) -> int:
    """Where a line's leading list, quote, task and heading marks end (0 when it has none)."""
    at, end = 0, 0
    while True:
        while at < len(line) and line[at] in " \t":
            at += 1
        mark = _MARK.match(line, at)
        if not mark:
            return end
        at = end = mark.end()


def _count(text: str) -> int:
    return len(re.findall(r"\w+", text))


def _clean_line(line: str) -> str:
    stripped = line.strip()
    text = stripped[_marks_end(stripped) :].lstrip()
    return re.sub(r"[*_`~]+", "", text).strip()


def _trim(words: list[str]) -> str:
    from tessellate.ai import composer_voice

    stop = query_understanding.STOPWORDS | composer_voice.TITLE_DANGLING
    words = words[:TITLE_WORDS]
    while words and (words[-1].lower().strip(",;:") in stop or words[-1].endswith((",", ";", ":"))):
        words.pop()
    title = " ".join(words).strip(" ,;:-.!?")
    return title[:1].upper() + title[1:] if title else ""


def _split_heading(draft: str) -> tuple[str, list[str]]:
    """(the leading heading's text or "", the lines after it)."""
    lines = (draft or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        found = _heading(line)
        return (found, lines[i + 1 :]) if found else ("", lines)
    return "", lines


def _first_line_title(lines: list[str]) -> str:
    for line in lines:
        first = _clean_line(line)
        if first and len(first) >= 3 and not _RULE.match(line):
            title = _trim(first.split())
            if title:
                return title
    return ""


def draft_title(draft: str) -> str:
    """A title from the draft's own words, or "" when there is nothing to name.

    In order: its first sentence (`composer_voice.title_for`, a lead-in such as
    "Remember to" off, seven words at most); else its first line with the
    markdown marks off; else its most repeated words. A draft that opens with a
    heading is named from what follows it, and by the heading when nothing does.
    """
    from tessellate.ai import composer_voice

    heading, lines = _split_heading(draft)
    lines = _outside_fences(lines)
    body = "\n".join(lines).strip()
    title = (
        (not heading and _label_title(lines))
        or (composer_voice.title_for(_without_marks(body)) if body else "")
        or _first_line_title(lines)
        or _top_terms(body)
        or (_trim(heading.split()) if heading else "")
    )
    return title if len(title) >= 3 else ""


def _outside_fences(lines: list[str]) -> list[str]:
    """The lines with every fenced code block (and its fence lines) taken
    out: the fence's language word ("python") and the code are not the
    draft's words, so neither can name it."""
    out, fenced = [], False
    for line in lines:
        if _FENCE.match(line):
            fenced = not fenced
        elif not fenced:
            out.append(line)
    return out


#: A first line this short, with no sentence or list mark, that has more
#: written below it is the person's own label for the note ("Trip to
#: Lisbon"), the way the notebook itself reads a note's first line.
LABEL_WORDS = 6


def _label_title(lines: list[str]) -> str:
    rows = [line for line in lines if line.strip()]
    if len(rows) < 2:
        return ""
    first = rows[0].strip()
    if _marks_end(first) or _RULE.match(first) or first.endswith((".", "!", "?", ",", ";")) or "://" in first:
        return ""
    words = first.rstrip(":").split()
    return _trim(words) if 1 <= len(words) <= LABEL_WORDS else ""


def _without_marks(body: str) -> str:
    """Bullets, quote marks and bold stripped line by line, so the first
    sentence reads as prose rather than as a list item or a quotation."""
    return "\n".join(_clean_line(line) if _marks_end(line) or "*" in line else line for line in body.split("\n"))


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
        elif not fenced and _heading(line):
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


def _paragraph_chunks(lines: list[str]) -> list[str]:
    """Blank-line blocks; a block that is only a heading leads the next one."""
    chunks: list[str] = []
    bare_heading = False
    for block in _blocks(lines):
        body = "\n".join(block)
        if bare_heading:
            chunks[-1] += "\n\n" + body
        else:
            chunks.append(body)
        bare_heading = not bare_heading and len(block) == 1 and bool(_heading(block[0]))
    return chunks


def _section_chunks(lines: list[str], marks: list[int]) -> list[str]:
    edges = [0, *marks, len(lines)] if marks[0] > 0 else [*marks, len(lines)]
    return ["\n".join(_strip_rules(lines[a:b])).strip() for a, b in zip(edges, edges[1:])]


def _join_scraps(chunks: list[str]) -> None:
    i = 0
    while len(chunks) > 1 and i < len(chunks):
        if _count(chunks[i]) < SCRAP_WORDS:
            _merge(chunks, i if i + 1 < len(chunks) else i - 1)
            i = max(i - 1, 0)
        else:
            i += 1


#: A single paragraph this long, in this many sentences, may hold more than one subject.
SUBJECT_WORDS = 30
SUBJECT_SENTENCES = 3
#: A group of sentences this short is not a note: it stays with its neighbour.
SUBJECT_MIN_WORDS = 8
#: Sentence openers that turn to something else ("Now I am...", "Later...").
_SHIFTS = frozenset(
    "now next then later also meanwhile anyway afterwards afterward tomorrow tonight yesterday today separately finally".split()
)
#: Matched on a right-stripped heading, with no leading `\s*`: that prefix made the
#: search polynomial on a heading of many tabs (CodeQL 2002).
_EMOTICON = re.compile(r"[:;=][-^]?[)(DPpOo]+$")


def _subject_stems(sentence: str) -> set[str]:
    from tessellate.ai import tagging

    stop = query_understanding.STOPWORDS
    words = [w for w in re.findall(r"[a-z][a-z'-]+", sentence.lower()) if len(w) >= 4 and w not in stop]
    return tagging.stems([w.removesuffix("s") for w in words])


def _by_subject(body: str) -> list[str]:
    """One long paragraph cut where the subject changes: a sentence opening on
    a turn ("Now", "Later") or sharing no content word with the group so far
    starts a new group. Sentences come from the composer's splitter and stay
    as written; a short or single-subject paragraph comes back whole."""
    from tessellate.ai import composer_tidy

    if "\n" in body.strip() or _count(body) < SUBJECT_WORDS:
        return [body]
    sentences = composer_tidy.sentences(body)
    if len(sentences) < SUBJECT_SENTENCES:
        return [body]
    groups = [[sentences[0]]]
    seen = _subject_stems(sentences[0])
    for sentence in sentences[1:]:
        stems = _subject_stems(sentence)
        opener = re.sub(r"\W", "", sentence.split()[0].lower())
        if opener in _SHIFTS or not (stems & seen):
            groups.append([sentence])
            seen = stems
        else:
            groups[-1].append(sentence)
            seen |= stems
    texts = [" ".join(g) for g in groups]
    i = 0
    while len(texts) > 1 and i < len(texts):
        if _count(texts[i]) < SUBJECT_MIN_WORDS:
            lo = i if i + 1 < len(texts) else i - 1
            texts[lo : lo + 2] = [texts[lo] + " " + texts[lo + 1]]
            i = max(i - 1, 0)
        else:
            i += 1
    return texts


def _expand(chunk: str) -> list[str]:
    """A chunk as one or more chunks; a leading heading stays on the first."""
    first, _, rest = chunk.partition("\n")
    if _heading(first) and rest.strip():
        pieces = _by_subject(rest.strip())
        return [first + "\n\n" + pieces[0], *pieces[1:]]
    return _by_subject(chunk) if not _heading(first) else [chunk]


def split_notes(text: str, limit: int) -> list[Part]:
    """One part per heading, or per paragraph when the text has fewer than two
    headings; a long single paragraph is cut further at its subject changes.
    A heading that titles a part is the part's title and leaves its body;
    scraps join the part beside them; more parts than `limit` are merged,
    shortest pair first, never dropped."""
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    marks = _headings(lines)
    chunks = _section_chunks(lines, marks) if len(marks) >= 2 else _paragraph_chunks(lines)
    chunks = [c for c in chunks if c.strip()]
    _join_scraps(chunks)
    chunks = [piece for c in chunks for piece in _expand(c)]
    while len(chunks) > max(limit, 1):
        k = min(range(len(chunks) - 1), key=lambda j: _count(chunks[j]) + _count(chunks[j + 1]))
        _merge(chunks, k)
    return [_part(c) for c in chunks]


def _plain_title(heading: str) -> str:
    """A heading as a title: the shouting and the trailing emoticon off."""
    bare = heading.rstrip()
    found = _EMOTICON.search(bare)
    if found:
        bare = bare[: found.start()]
    return bare.rstrip(" \t!?.") or heading


def _part(chunk: str) -> Part:
    from tessellate.ai import composer_voice

    first, _, rest = chunk.partition("\n")
    found = _heading(first)
    if found:
        body = rest.strip()
        return Part(title=_plain_title(found), content=body or chunk)
    label = _label_title(_outside_fences(chunk.split("\n")))
    return Part(title=label or _tidy_title(composer_voice.title_for(_without_marks(chunk))), content=chunk)


def _tidy_title(title: str) -> str:
    """A turn-of-subject opener ("Now") and a dangling number off the title."""
    words = title.split()
    if len(words) > 3 and re.sub(r"\W", "", words[0].lower()) in _SHIFTS:
        words = words[1:]
    if len(words) > 2 and words[-1].isdigit():
        words = words[:-1]
    return _trim(words) if words else title
