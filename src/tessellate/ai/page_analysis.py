"""A web page read without a model: key points, key terms and its sections.

The 22-10 bug doc: "Analyse a page in the web panel: key points, section list
with jump links." The reader (`search/websearch.fetch_readable`) gives a page
as blocks (`heading`, `p`, `li`); this reads them the way the composer reads
notes. Nothing is written here: a key point is a sentence of the page, whole,
chosen by how many of the page's most repeated words it carries, and shown in
the page's order; a key term is a word the page repeats; a section is a heading.

Deterministic and pure: the same blocks give the same analysis.
"""

from __future__ import annotations

import re
from collections import Counter

MAX_POINTS = 5
MAX_TERMS = 8
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9“\"'(])")
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]{2,}")
_BOILERPLATE = re.compile(r"\b(?:cookies?|subscribe|sign up|sign in|log in|privacy policy|terms of (?:use|service)|all rights reserved|newsletter|advertisement)\b", re.I)
_STOP = frozenset(
    """the and for are but not you all any can had her was one our out has have his how its may new now see two way who did get him
    let put say she too use that this with from they will would there their what when which about after again also been before being
    between both could does done each even every few first into just like made make many more most much must only other over said same
    should since some such than then them these those through under very were where while your because still being than""".split()
)


def _stem(word: str) -> str:
    word = word.lower()
    for tail in ("ies", "es", "s"):
        if len(word) > len(tail) + 3 and word.endswith(tail):
            return word[: -len(tail)] + ("y" if tail == "ies" else "")
    return word


def _plain(text: str) -> str:
    """A page's sentence as text: no markup, links or code that could be read as such."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return " ".join(re.sub(r"[`<>]|\*{1,2}", "", text).split())


def _count(text: str, weight: int, counts: Counter, surface: dict[str, Counter]) -> None:
    for word in _WORD.findall(text):
        if word.lower() in _STOP:
            continue
        stem = _stem(word)
        counts[stem] += weight
        surface.setdefault(stem, Counter())[word.lower()] += 1


def _scan(blocks: list[dict]) -> tuple[list[dict], list[tuple[int, str, bool]], Counter, dict[str, Counter]]:
    """Headings, the sentences worth ranking (block index, text, first in its
    block), and the weighted stem counts with their surface forms."""
    sections: list[dict] = []
    units: list[tuple[int, str, bool]] = []
    counts: Counter = Counter()
    surface: dict[str, Counter] = {}
    for i, block in enumerate(blocks or []):
        text = _plain(str(block.get("text") or ""))
        if not text:
            continue
        heading = block.get("type") == "heading"
        if heading:
            sections.append({"title": text[:120], "level": int(block.get("level") or 2), "index": i})
        _count(text, 2 if heading else 1, counts, surface)
        if heading:
            continue
        for n, sentence in enumerate(s.strip() for s in _SENTENCE.split(text)):
            if 7 <= len(sentence.split()) <= 45 and 40 <= len(sentence) <= 280 and not _BOILERPLATE.search(sentence):
                units.append((i, sentence, n == 0))
    return sections, units, counts, surface


def _stems(sentence: str, *, stop: bool) -> set[str]:
    return {_stem(w) for w in _WORD.findall(sentence) if not (stop and w.lower() in _STOP)}


def _choose(units: list[tuple[int, str, bool]], counts: Counter) -> list[str]:
    """The top sentences by weighted stems, spread out, in page order."""
    #: A word that appears once says nothing about the page.
    weights = {stem: n for stem, n in counts.items() if n >= 2}
    scored = []
    for order, (_block, sentence, first) in enumerate(units):
        stems = _stems(sentence, stop=True)
        score = sum(weights.get(s, 0) for s in stems) / (len(stems) ** 0.5 or 1)
        scored.append((score * (1.25 if first else 1.0), order, sentence))
    chosen: list[tuple[int, str]] = []
    for _score, order, sentence in sorted(scored, key=lambda t: (-t[0], t[1])):
        if len(chosen) >= MAX_POINTS:
            break
        words = _stems(sentence, stop=False)
        if any(len(words & _stems(other, stop=False)) / max(len(words), 1) > 0.7 for _, other in chosen):
            continue
        chosen.append((order, sentence))
    return [s for _, s in sorted(chosen)]


def analyse(blocks: list[dict]) -> dict:
    """`{"key_points": [...], "terms": [...], "sections": [{"title", "level", "index"}]}`."""
    sections, units, counts, surface = _scan(blocks)
    points = _choose(units, counts) if units else []
    return {"key_points": points, "terms": _terms(counts, surface), "sections": sections}


def _terms(counts: Counter, surface: dict[str, Counter]) -> list[str]:
    ranked = [stem for stem, n in counts.most_common() if n >= 2][:MAX_TERMS]
    return [surface[stem].most_common(1)[0][0] for stem in ranked]
