"""Backlinks with their sentence, and the mentions that are not links yet.

One scanner for documents (`routes_documents._backlinks`) and notes
(`routes_mentions`, GRAPH_PLAN KG1), so "a mention" is defined once. Moved
whole from routes_documents; the names lost their underscore when they
became shared.
"""

from __future__ import annotations

import re
from functools import lru_cache

from tessellate.entry.manager import WIKI_LINK, wiki_target

#: How far either side of a hit the context may reach before it gives up
#: looking for a sentence boundary. A backlink row is two lines in a 280px
#: sidebar; more than this is a paragraph nobody reads in a panel.
BACKLINK_CONTEXT_CHARS = 180
#: Hits shown per source. A note that names this document eight times has said
#: one thing, not eight.
BACKLINK_HITS_PER_SOURCE = 3
#: Sources scanned and rows returned. A local notebook is small; an imported
#: vault is not, and this runs on every document open.
BACKLINK_SOURCES_MAX = 400
BACKLINK_ROWS_MAX = 60
#: A title shorter than this is never searched for as an *unlinked* mention:
#: "AI", "Q3" or "t" would match a third of the notebook and every row would
#: be noise (audit 1029 N1: the title "t" had 58 incoming rows). A linked
#: mention is an exact `[[name]]` and is found at any length, which is why the
#: guard sits on one half and not the other. One floor for the backlinks
#: panel, the Referenced-by rows, Connections and the counts.
MENTION_MIN_TITLE_CHARS = 3

#: The markdown a line opens with, dropped from the front of a context line so
#: a backlink from a bullet list does not read as "- - the sentence".
_CONTEXT_LEAD = re.compile(r"(?:[#>]+\s*|[-*+]\s+|\d{1,3}[.)]\s+)+")


def sentence_around(text: str, start: int, end: int) -> tuple[str, int, int]:
    """The sentence a hit sits in, and where the hit is inside that sentence.

    Returns `(context, hit_start, hit_end)` with the offsets relative to the
    context, so the browser can mark the hit without searching the string
    again: searching it again is how the second occurrence of a word gets
    marked instead of the first.
    """
    floor = max(0, start - BACKLINK_CONTEXT_CHARS)
    left = floor
    index = start - 1
    while index >= floor:
        char = text[index]
        if char == "\n":
            left = index + 1
            break
        if char in ".!?" and (index + 1 >= len(text) or text[index + 1] in " \n"):
            left = index + 1
            break
        index -= 1

    ceiling = min(len(text), end + BACKLINK_CONTEXT_CHARS)
    right = ceiling
    index = end
    while index < ceiling:
        char = text[index]
        if char == "\n":
            right = index
            break
        if char in ".!?" and (index + 1 >= len(text) or text[index + 1] in " \n"):
            right = index + 1
            break
        index += 1

    context = text[left:right]
    hit_start, hit_end = start - left, end - left

    # Tidy the left edge, but never past the hit itself: a document whose only
    # mention is inside its own heading would otherwise lose the hit with the
    # `#`.
    drop = len(context) - len(context.lstrip())
    lead = _CONTEXT_LEAD.match(context[drop:])
    if lead and drop + lead.end() <= hit_start:
        drop += lead.end()
    context = context[drop:]
    hit_start -= drop
    hit_end -= drop
    trimmed = context.rstrip()
    hit_end = min(hit_end, len(trimmed)) if hit_end > len(trimmed) else hit_end
    context = trimmed

    # An ellipsis only where the text really was cut mid-sentence, not where a
    # sentence or a line ended on its own.
    if left > 0 and left == floor:
        context = "…" + context
        hit_start += 1
        hit_end += 1
    if right < len(text) and right == ceiling:
        context = context + "…"
    return context, hit_start, hit_end


@lru_cache(maxsize=512)
def mention_pattern(label: str) -> re.Pattern[str]:
    """The one whole-word, case-folded matcher for "this text names `label`".

    `(?<![\\w\\[])` and `(?![\\w\\]])` keep "Roadmap" out of "Roadmaps" and out
    of `[[Roadmap]]` (a link is its own, stronger fact, found by `[[...]]`).
    """
    return re.compile(rf"(?<![\w\[]){re.escape(label)}(?![\w\]])", re.IGNORECASE)


def names_label(content: str | None, label: str) -> bool:
    """Whether `content` holds `label` as a whole word, and `label` is long
    enough to be a name rather than a letter (`MENTION_MIN_TITLE_CHARS`)."""
    label = label.strip()
    return len(label) >= MENTION_MIN_TITLE_CHARS and mention_pattern(label).search(content or "") is not None


def backlink_spans(content: str, title: str) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """`(linked, unlinked)` spans of this title in one source's text.

    A source with a real link is never listed under unlinked mentions as
    well: the panel's second list means "not connected yet", and a note that
    appears in both says the opposite of what each list is for.
    """
    wanted = title.lower()
    wiki: list[tuple[int, int]] = []
    linked: list[tuple[int, int]] = []
    for match in WIKI_LINK.finditer(content):
        wiki.append(match.span())
        if wiki_target(match.group(1)).lower() == wanted:
            linked.append(match.span())
    if linked or len(title) < MENTION_MIN_TITLE_CHARS:
        return linked, []
    # The wiki-overlap check below is what keeps it out of
    # `[[Roadmap for 2027]]`, which no lookaround can see.
    pattern = mention_pattern(title)
    unlinked = [
        match.span()
        for match in pattern.finditer(content)
        if not any(start < match.end() and match.start() < end for start, end in wiki)
    ]
    return linked, unlinked


def backlink_rows(
    kind: str, source_id: int, label: str, content: str, spans: list[tuple[int, int]]
) -> list[dict]:
    rows = []
    for start, end in spans[:BACKLINK_HITS_PER_SOURCE]:
        context, hit_start, hit_end = sentence_around(content, start, end)
        rows.append(
            {
                "kind": kind,
                "id": source_id,
                "title": label,
                "context": context,
                "hit_start": hit_start,
                "hit_end": hit_end,
                # Offsets in the *source's* text, which is what the "Link"
                # action rewrites. Checked against the title again before any
                # write: a source edited in another tab must not have a
                # sentence of it replaced from a stale offset.
                "start": start,
                "end": end,
            }
        )
    return rows
