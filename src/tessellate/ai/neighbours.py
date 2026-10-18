"""Notes that belong to the same topic as a note the search found (CHAT_PLAN
decision 70, INBOX 812).

The keyword search wants every word of the question: "how's the gym going?"
finds the one note that also says "going" and misses the second gym note, the
one with the new weights. An overview, a comparison or a "what's left" is
about the topic as a whole, so a note that shares a *rare* tag with a note the
search found is read too. A tag many notes carry says little about any one of
them and brings nothing. Pure on purpose: the route gathers the rows, this
chooses (tests/test_neighbours_1018.py).
"""

from __future__ import annotations

from collections import Counter

#: A tag carried by more notes than this is a heading, not a topic.
HUB = 8
#: At most this many notes are added to what the search found.
LIMIT = 4
#: The kinds of question the digest answers about a topic as a whole.
WHOLE_KINDS = frozenset({"overview", "compare"})


def reads_whole(question: str) -> bool:
    """Whether `question` asks about a topic whole (an overview, a
    comparison) rather than for one fact."""
    from tessellate.ai import composer_digest

    return composer_digest.kind_of(question) in WHOLE_KINDS


def asks_left(question: str) -> bool:
    """Whether `question` asks what is still open ("what do I need to buy",
    "what's left"): answered from the notes that hold something open, which
    the question's own words rarely name."""
    from tessellate.ai import composer_digest

    return composer_digest.kind_of(question) == "left"


def pick(seed_ids: list[int], rows: list[tuple[int, list[str]]], limit: int = LIMIT, hub: int = HUB) -> list[int]:
    """Ids of the notes in `rows` (id, tags; newest first) that share a rare
    tag with any seed, the most tags shared first and, among equals, the order
    of `rows`. The seeds themselves are never returned."""
    seeds = set(seed_ids)
    carried = Counter(tag for _, tags in rows for tag in set(tags))
    topic = {tag for note_id, tags in rows if note_id in seeds for tag in tags if carried[tag] <= hub}
    if not topic:
        return []
    shared = [(len(topic & set(tags)), note_id) for note_id, tags in rows if note_id not in seeds]
    ranked = sorted((pair for pair in shared if pair[0]), key=lambda pair: -pair[0])
    return [note_id for _, note_id in ranked[:limit]]
