"""Relationship recognition with explanations (GRAPH_PLAN KG2, INBOX 528).

The auto-linker had one signal, embedding similarity, and so one reason
("similar in meaning"), and nothing at all with the embedding backend off.
A notebook says how its notes relate in more ways than their wording: two
notes that name the same rare person, two notes that both link to the same
third note, two notes that share a tag only a handful of notes carry. Each of
those is a **signal** here, with a sentence a person can check and a 0..1
confidence, and a pair's confidence is their noisy-or: independent pieces of
evidence that each might be wrong, any of which could be right.

Pure on purpose: `recognise` takes plain data, so it is tested and measured
without a database (`tests/test_relations_kg2.py`), and the route
(`routes_entries.link_suggestions`) only gathers the rows.

**Every signal's cost is bounded by a hub cap, not by the notebook.** Pairs
come from shared things (an entity, a neighbour, a tag), so a thing shared by
`n` notes makes `n²/2` pairs; past the cap it says little about any one pair
("both mention Monday") and costs the most, so it is skipped. The work is the
sum of `n²` over the things under the cap, measured at 2k and 10k notes in
the test file.

Written-close-in-time is support only: two notes typed in the same sitting
are often unrelated, so it raises a pair something else proposed and never
proposes one.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

#: A pair is offered at this combined confidence or more. A cosine at the
#: old bar (0.55) clears it alone, so the similarity-only behaviour is kept;
#: one shared entity only these two notes name (0.5) clears it; one shared
#: tag (0.35) does not, and needs a second piece of evidence.
MIN_CONFIDENCE = 0.5

#: Things shared by more notes than this make no pairs (see the docstring).
ENTITY_HUB = 30
NEIGHBOUR_HUB = 30
TAG_HUB = 10

#: Two notes written this close together get the time signal, as support.
TIME_WINDOW_MINUTES = 30
TIME_CONFIDENCE = 0.15

#: The time signal's ceiling under learning: support may grow, a little.
SIGNAL_CEILING = 1.5

#: The ceiling on each signal, so no one kind of evidence is certainty.
CAPS = {"similarity": 0.95, "entities": 0.9, "neighbours": 0.85, "tags": 0.7, "time": TIME_CONFIDENCE}


@dataclass(frozen=True)
class NoteFacts:
    label: str
    tags: frozenset[str] = frozenset()
    created_at: datetime | None = None


@dataclass
class Candidate:
    a: int
    b: int
    #: signal -> (confidence, the things it rests on)
    evidence: dict[str, tuple[float, list[str]]] = field(default_factory=dict)
    similarity: float | None = None

    @property
    def confidence(self) -> float:
        miss = 1.0
        for p, _ in self.evidence.values():
            miss *= 1.0 - p
        return 1.0 - miss

    def signals(self) -> list[dict]:
        rows = [
            {"signal": name, "reason": _reason(name, things), "confidence": round(p, 2)}
            for name, (p, things) in self.evidence.items()
        ]
        rows.sort(key=lambda row: -row["confidence"])
        return rows


def _named(things: list[str], quote: bool) -> str:
    shown = [f"“{t}”" if quote else t for t in things[:2]]
    more = len(things) - len(shown)
    text = " and ".join(shown)
    return f"{text} and {more} more" if more > 0 else text


def _reason(signal: str, things: list[str]) -> str:
    if signal == "similarity":
        return "similar in meaning"
    if signal == "entities":
        return f"both mention {_named(things, False)}"
    if signal == "neighbours":
        return f"both linked with {_named(things, True)}"
    if signal == "tags":
        return f"both tagged {_named(['#' + t for t in things], False)}"
    return things[0] if things else "written close together"


def _noisy_or(ps: list[float], cap: float) -> float:
    miss = 1.0
    for p in ps:
        miss *= 1.0 - p
    return min(cap, 1.0 - miss)


def _rarity(n: int, rare: float, few: float, some: float) -> float:
    """What sharing one thing held by `n` notes is worth: the rarer, the more."""
    return rare if n <= 2 else few if n <= 5 else some


def _collect_shared(
    notes: dict[int, NoteFacts],
    edges: list[tuple[int, int]],
    mentions: list[tuple[str, int]],
    banned: set[tuple[int, ...]],
) -> dict[str, dict[tuple[int, int], list[tuple[float, str]]]]:
    """Per signal, each pair of notes and the things (with weights) that tie them."""
    shared: dict[str, dict[tuple[int, int], list[tuple[float, str]]]] = {
        "entities": defaultdict(list), "neighbours": defaultdict(list), "tags": defaultdict(list),
    }

    def pairs_of(members: list[int], signal: str, weight: float, thing: str) -> None:
        members = sorted(set(members))
        table = shared[signal]
        for i, a in enumerate(members):
            for b in members[i + 1 :]:
                if (a, b) not in banned:
                    table[(a, b)].append((weight, thing))

    by_entity: dict[str, list[int]] = defaultdict(list)
    names: dict[str, str] = {}
    for name, note_id in mentions:
        if note_id in notes:
            folded = name.strip().casefold()
            names.setdefault(folded, name.strip())
            by_entity[folded].append(note_id)
    for folded, members in by_entity.items():
        n = len(set(members))
        if 2 <= n <= ENTITY_HUB:
            pairs_of(members, "entities", _rarity(n, 0.5, 0.35, 0.2), names[folded])

    neighbours: dict[int, set[int]] = defaultdict(set)
    for a, b in edges:
        if a in notes and b in notes and a != b:
            neighbours[a].add(b)
            neighbours[b].add(a)
    for hub, members in neighbours.items():
        n = len(members)
        if 2 <= n <= NEIGHBOUR_HUB:
            pairs_of(list(members), "neighbours", _rarity(n, 0.35, 0.25, 0.12), notes[hub].label)

    by_tag: dict[str, list[int]] = defaultdict(list)
    for note_id, facts in notes.items():
        for tag in facts.tags:
            by_tag[tag].append(note_id)
    for tag, members in by_tag.items():
        if 2 <= len(members) <= TAG_HUB:
            pairs_of(members, "tags", _rarity(len(members), 0.35, 0.25, 0.15), tag)
    return shared


def _cosine_pairs(
    similar: list[tuple[int, int, float]], notes: dict[int, NoteFacts], banned: set[tuple[int, ...]]
) -> dict[tuple[int, int], float]:
    """The first cosine score of each offerable pair of known notes."""
    cosine: dict[tuple[int, int], float] = {}
    for a, b, score in similar:
        key = (a, b) if a < b else (b, a)
        if a == b or key in banned or a not in notes or b not in notes or key in cosine:
            continue
        cosine[key] = score
    return cosine


def _written_apart(first, second) -> str | None:  # noqa: ANN001
    """Words for two notes written within `TIME_WINDOW_MINUTES` of each other, else None."""
    if not (first and second):
        return None
    minutes = abs((first - second).total_seconds()) / 60
    if minutes > TIME_WINDOW_MINUTES:
        return None
    return "written the same minute" if minutes < 1 else f"written {round(minutes)} minutes apart"


def recognise(
    notes: dict[int, NoteFacts],
    edges: list[tuple[int, int]],
    mentions: list[tuple[str, int]],
    similar: list[tuple[int, int, float]],
    exclude: set[frozenset[int]],
    weights: dict[str, float] | None = None,
) -> list[Candidate]:
    """Every pair with evidence at or over `MIN_CONFIDENCE`, best first.

    `edges` are the explicit connections (links and threads): they make the
    neighbour signal and are themselves excluded. `mentions` is
    `(entity name, note id)`. `similar` is cosine pairs already over the bar.
    `exclude` is pairs never to offer (linked, threaded, dismissed).
    `weights` scales each signal by what accepting and dismissing taught
    (`learning.signal_weights`, GRAPH_PLAN KG9); a missing signal is 1.0.
    """
    weights = weights or {}

    def worth(signal: str, p: float) -> float:
        return min(CAPS[signal], p * weights.get(signal, 1.0))

    #: Pairs are `(low, high)` tuples until the end: a frozenset and a
    #: Candidate per pair cost 2.4 s at 10k notes for pairs nearly all of
    #: which fall under the bar. Only the survivors become Candidates.
    banned = {tuple(sorted(pair)) for pair in exclude if len(pair) == 2}
    shared = _collect_shared(notes, edges, mentions, banned)

    miss: dict[tuple[int, int], float] = defaultdict(lambda: 1.0)
    for signal, table in shared.items():
        for key, hits in table.items():
            miss[key] *= 1.0 - worth(signal, _noisy_or([w for w, _ in hits], CAPS[signal]))
    cosine = _cosine_pairs(similar, notes, banned)
    for key, score in cosine.items():
        miss[key] *= 1.0 - worth("similarity", score)

    #: Time can only lift a pair already this close to the bar.
    time_p = min(CAPS["time"] * SIGNAL_CEILING, TIME_CONFIDENCE * weights.get("time", 1.0))
    lift = 1.0 - (1.0 - MIN_CONFIDENCE) / (1.0 - time_p)
    kept: list[Candidate] = []
    for key, missed in miss.items():
        a, b = key
        when = _written_apart(notes[a].created_at, notes[b].created_at) if 1.0 - missed >= lift else None
        if when:
            missed *= 1.0 - time_p
        if 1.0 - missed < MIN_CONFIDENCE:
            continue
        candidate = Candidate(a, b)
        for signal, table in shared.items():
            hits = table.get(key)
            if hits:
                hits.sort(key=lambda hit: (-hit[0], hit[1]))
                candidate.evidence[signal] = (worth(signal, _noisy_or([w for w, _ in hits], CAPS[signal])), [t for _, t in hits])
        if key in cosine:
            candidate.similarity = cosine[key]
            candidate.evidence["similarity"] = (worth("similarity", cosine[key]), [])
        if when:
            candidate.evidence["time"] = (time_p, [when])
        kept.append(candidate)
    kept.sort(key=lambda c: (-c.confidence, -len(c.evidence), c.a, c.b))
    return kept


def explain_pair(
    a: int,
    b: int,
    notes: dict[int, NoteFacts],
    neighbours: dict[int, set[int]],
    entity_notes: dict[str, set[int]],
) -> list[dict]:
    """Every structural reason two notes are related, for one pair (GRAPH_PLAN
    KG8: a path's hop says all of them, not only the link that made it).

    The same signals, weights and sentences as `recognise`, read for one pair
    from what the caller already holds: `neighbours` (links and threads),
    `entity_notes` (entity name -> the notes that name it, the whole notebook's
    count, which is what makes one rare). Similarity is left out: a path asks
    what the notebook says, not how two texts read.
    """
    candidate = Candidate(min(a, b), max(a, b))
    hits = [
        (_rarity(len(members), 0.5, 0.35, 0.2), name)
        for name, members in sorted(entity_notes.items())
        if a in members and b in members and 2 <= len(members) <= ENTITY_HUB
    ]
    if hits:
        candidate.evidence["entities"] = (_noisy_or([w for w, _ in hits], CAPS["entities"]), [t for _, t in hits])
    hits = [
        (_rarity(len(neighbours[hub]), 0.35, 0.25, 0.12), notes[hub].label)
        for hub in sorted(neighbours.get(a, set()) & neighbours.get(b, set()))
        if hub in notes and len(neighbours[hub]) <= NEIGHBOUR_HUB
    ]
    if hits:
        candidate.evidence["neighbours"] = (_noisy_or([w for w, _ in hits], CAPS["neighbours"]), [t for _, t in hits])
    tag_count: dict[str, int] = defaultdict(int)
    shared = notes[a].tags & notes[b].tags if a in notes and b in notes else frozenset()
    if shared:
        for facts in notes.values():
            for tag in facts.tags & shared:
                tag_count[tag] += 1
        hits = [(_rarity(tag_count[t], 0.35, 0.25, 0.15), t) for t in sorted(shared) if tag_count[t] <= TAG_HUB]
        if hits:
            candidate.evidence["tags"] = (_noisy_or([w for w, _ in hits], CAPS["tags"]), [t for _, t in hits])
    return candidate.signals()
