"""Topics inside an island, named (GRAPH_PLAN KG6, INBOX 528).

`paths.clusters` is connected components on purpose (its docstring says why:
exactly true, checkable by clicking). That decision stands. A topic is a
second, labelled layer over it: a judgement, said to be one, that a big
island is two or three subjects joined by a bridge.

**Detection: weighted label propagation, in id order.** Each note takes the
label its neighbours vote for most, a vote weighted by how strong the edge is
(`1 / Step.weight`, so a link counts four times a shared tag, as on a path)
times one plus the neighbours the two ends share. That second factor is what
stops a lone bridge pulling one subject into the next: an edge inside a
subject sits in triangles, a bridge does not. A note keeps its label on a tie
and otherwise the smallest label wins, so the answer is the same every time.
Cost is the edges times the rounds plus one set intersection per edge.

**Naming: what the topic shares more than the notebook does.** A term (a
tag, an entity, a title word) scores its share of the topic's notes times its
inverse document frequency over the notebook; a term every note has scores
nothing. Tags win ties over entities and entities over words, because a tag
is a name somebody chose. A topic nothing names that way is named, in turn,
by the best term two of its notes share at any share, then by its most
linked note's title ("Around Kiln notes"); only a topic of private or
untitled notes is "Topic 3" (the owner, 2026-10-11: a chip reading "Topic 2"
says nothing). Never an invented word; a local model's summary is a
separate, on-demand step.
"""

from __future__ import annotations

import math
from collections import defaultdict

from tessellate.entry.paths import Connections, degree

#: A topic smaller than this is a pair and a hanger-on, not a subject.
MIN_TOPIC_NOTES = 3
#: Label propagation settles in a handful of rounds; this is the ceiling.
ROUNDS = 20
#: How many terms a topic lists beside its name.
TERMS_SHOWN = 5
#: A term must be on this share of a topic's notes to name it.
MIN_TERM_SHARE = 0.3

_KIND_ORDER = {"tag": 0, "entity": 1, "word": 2}


def detect(index: Connections) -> dict[int, int]:
    """Note id -> topic label (a member's id), for every note in the index."""
    near = {node: set(index.neighbours(node)) for node in index.entries}
    weight: dict[int, dict[int, float]] = defaultdict(dict)
    for node, steps in index.edges.items():
        for other, step in steps.items():
            if other == node or other not in near or node not in near:
                continue
            shared = len(near[node] & near[other])
            weight[node][other] = (1.0 / max(step.weight, 1e-9)) * (1.0 + shared)
    labels = {node: node for node in index.entries}
    order = sorted(index.entries)
    for _ in range(ROUNDS):
        changed = False
        for node in order:
            votes: dict[int, float] = defaultdict(float)
            for other, w in weight.get(node, {}).items():
                votes[labels[other]] += w
            if not votes:
                continue
            best = max(votes.values())
            if votes.get(labels[node], 0.0) >= best - 1e-9:
                continue
            labels[node] = min(label for label, v in votes.items() if v >= best - 1e-9)
            changed = True
        if not changed:
            break
    return labels


def _display(kind: str, term: str) -> str:
    return f"#{term}" if kind == "tag" else term


def _score_terms(members: list[int], terms_of: dict, document_frequency: dict, total: int) -> tuple[list, list]:
    """A topic's terms, scored `(-score, kind order, term, kind, notes)`: the
    ones shared widely enough, sorted, and the weaker ones kept for a fallback name."""
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for node in members:
        for term in terms_of.get(node, ()):
            counts[term] += 1
    scored = []
    weak = []
    for (kind, term), notes in counts.items():
        if notes < 2:
            continue
        score = (notes / len(members)) * math.log(total / document_frequency[(kind, term)])
        if score <= 0:
            continue
        row = (-score, _KIND_ORDER.get(kind, 3), term, kind, notes)
        (weak if notes / len(members) < MIN_TERM_SHARE else scored).append(row)
    scored.sort()
    return scored, weak


def build(
    index: Connections,
    terms_of: dict[int, set[tuple[str, str]]],
    titles: dict[int, str] | None = None,
) -> list[dict]:
    """The topics of `MIN_TOPIC_NOTES` or more, largest first, each named.

    `terms_of` is note id -> `{(kind, term)}`, kind one of tag, entity, word;
    a note missing from it (a private one) lends nothing to a name. `titles`
    is note id -> the title a person reads, for a topic no term names.
    """
    labels = detect(index)
    groups: dict[int, list[int]] = defaultdict(list)
    for node, label in labels.items():
        groups[label].append(node)
    kept = sorted(
        (sorted(members) for members in groups.values() if len(members) >= MIN_TOPIC_NOTES),
        key=lambda members: (-len(members), members[0]),
    )
    total = max(1, len(index.entries))
    document_frequency: dict[tuple[str, str], int] = defaultdict(int)
    for terms in terms_of.values():
        for term in terms:
            document_frequency[term] += 1

    out: list[dict] = []
    for position, members in enumerate(kept):
        scored, weak = _score_terms(members, terms_of, document_frequency, total)
        terms = [
            {"term": _display(kind, term), "kind": kind, "notes": notes}
            for _, _, term, kind, notes in scored[:TERMS_SHOWN]
        ]
        out.append({
            "id": position,
            "size": len(members),
            "name": terms[0]["term"] if terms else _fallback_name(index, members, weak, titles or {}, position),
            "terms": terms,
            "ids": members,
            "core_id": max(members, key=lambda node: (degree(index, node), -node)),
        })
    return out


#: A title that names a topic is cut to this many characters.
TITLE_NAME_CHARS = 40


def _fallback_name(index: Connections, members: list[int], weak: list, titles: dict, position: int) -> str:
    """A topic no term names at `MIN_TERM_SHARE`: the best term two of its
    notes share, then its most linked note's title, then "Topic N". The
    caller leaves a private note out of `titles`, so it never lends one."""
    if weak:
        _, _, term, kind, _ = min(weak)
        return _display(kind, term)
    for node in sorted(members, key=lambda n: (-degree(index, n), n)):
        title = (titles.get(node) or "").strip()
        if title:
            if len(title) > TITLE_NAME_CHARS:
                title = title[: TITLE_NAME_CHARS - 1].rstrip() + "\u2026"
            return f"Around {title}"
    return f"Topic {position + 1}"


def terms_sentence(size: int, terms: list[str]) -> str:
    """A topic's summary with no model: how many notes, and what they share.
    Never an invented word: with nothing shared it says what a topic is."""
    named = [t for t in terms if t][:3]
    if not named:
        return f"{size} notes that link to each other more than to the rest."
    joined = named[0] if len(named) == 1 else ", ".join(named[:-1]) + f" and {named[-1]}"
    return f"{size} notes about {joined}."


def extractive_sentence(size: int, terms: list[str], first, last, leads: list[str]) -> str:
    """`terms_sentence` plus what the notes themselves say, with no model:
    the date span and the opening lines of the most-linked notes. Every word
    is one the notes or their dates hold (K8: the composer summarises)."""
    parts = [terms_sentence(size, terms)]
    if first and last:
        a, b = first.date().isoformat(), last.date().isoformat()
        parts.append(f"Written {a}." if a == b else f"Written {a} to {b}.")
    named = [lead for lead in leads if lead][:2]
    if named:
        parts.append("Most linked: " + "; ".join(f"\u201c{lead}\u201d" for lead in named) + ".")
    return " ".join(parts)


#: How much of each note the model reads for a summary, and how many notes:
#: a topic's titles and opening lines say what it is about; its bodies are a
#: long prompt for a small model to get lost in.
SUMMARY_NOTES = 12
SUMMARY_CHARS = 160
SUMMARY_SYSTEM = (
    "You say what a group of someone's notes is about, in one plain sentence "
    "of under 30 words, from their titles and opening lines. No preamble, no "
    "quotes, no list, and nothing the notes do not say."
)


#: A stored name follows its topic while at least half of the two sets'
#: union is shared (INBOX 547). Topics are recomputed from the links on every
#: change, so a topic has no lasting id; its notes are the only identity it
#: has, and a topic that gained or lost a note or two is still the one that
#: was named.
NAME_MATCH = 0.5
#: How many renamed topics are remembered; the oldest go first.
NAMES_KEPT = 200


def overlap(a: set[int], b: set[int]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def apply_names(found: list[dict], stored: list[dict]) -> list[dict]:
    """`found` with the names the person gave, best match first, each stored
    name used once. Copies: `found` is a cached value shared by requests."""
    out = [dict(topic) for topic in found]
    pairs = []
    for s_index, saved in enumerate(stored or []):
        ids = set(saved.get("ids") or [])
        for t_index, topic in enumerate(out):
            score = overlap(ids, set(topic["ids"]))
            if score >= NAME_MATCH:
                pairs.append((-score, s_index, t_index))
    used_saved: set[int] = set()
    for _, s_index, t_index in sorted(pairs):
        topic = out[t_index]
        if s_index in used_saved or topic.get("named"):
            continue
        used_saved.add(s_index)
        topic["found_name"] = topic["name"]
        topic["name"] = stored[s_index]["name"]
        topic["named"] = True
    return out


def store_name(stored: list[dict], ids: list[int], name: str) -> list[dict]:
    """The stored names with this topic's set to `name`, or forgotten when
    `name` is empty (the found name comes back)."""
    wanted = set(ids)
    kept = [s for s in stored or [] if overlap(set(s.get("ids") or []), wanted) < NAME_MATCH]
    if name:
        kept.append({"ids": sorted(wanted), "name": name})
    return kept[-NAMES_KEPT:]
