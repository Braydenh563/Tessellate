"""How the notes an answer shows stand to the question and to each other
(INBOX 1310, the owner: "it just lists every entry, it has no frame of
reference for how related each shown matching record is or why it was shown
and how the shown notes link if they do").

Three facts, each from what the search and the notebook already hold, never
a guess:

- **Themes**: notes that share a tag, or that the person linked, go together;
  a tag every shown note carries joins nothing.
- **Relevance bands**: the group whose notes score clearly above the rest is
  the closest; other groups are also related; a note on its own is said as
  "more loosely".
- **Reasons**: one short line per Matching records card, why it was shown
  ("Matches hobbies by meaning, and shares #gaming with the gaming mouse").

With a model up these are facts handed to it; with no model the composer
says them (CHAT_PLAN decision 75). No import of the composer here: the
digest hands in what it needs, so this module joins no import cycle.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

#: A group leads as "the closest" only when its notes score this far above
#: every note outside it; nearer than that, no group is closer than another.
CLOSEST_MARGIN = 0.1
#: Fewer notes than this read fine as a list: no frame.
FRAME_MIN = 4
_STOP = frozenset(
    "what whats have has had i i've ive me my mine saved save about the a an any anything do does did "
    "is are was were tell show list give all of on in for to with from notes note written wrote you your "
    "know there so far".split()
)
_PREFIX = re.compile(r"^([^:.!?\n]{2,40}):\s+(\S.*)$", re.S)
_DOING = re.compile(r"^(?:i'?m |i was |been )?(?:(?:thinking|looking|planning|hoping|considering|saving|trying)\s+(?:of|about|at|for|to|on)?\s*)+(?:buying|getting|doing|trying|playing|making)?\s*", re.I)
_IMPERATIVE = re.compile(r"^(?:go|buy|call|book|get|ask|read|pay|send|bring|try|do|check|remember)\b", re.I)


@dataclass
class Group:
    """Notes said together: a theme of two or more, or the loose ones."""

    ids: list[int]
    #: The tag that names the theme ("gym"), or "" for linked or loose notes.
    name: str = ""
    #: What joins them, as words: "both tagged #gym", "share #gaming",
    #: "linked"; "" for the loose notes.
    joined_by: str = ""
    score: float = 0.0
    band: str = "also"
    links: list[tuple[int, int]] = field(default_factory=list)


def _tag_list(note: dict) -> list[str]:
    return [str(t).lower().lstrip("#").strip() for t in (note.get("tags") or []) if str(t).strip()]


def _tags(note: dict) -> set[str]:
    return set(_tag_list(note))


def _score(note: dict) -> float:
    info = note.get("match_info") or {}
    if info.get("type") in ("connected", "connected_2hop"):
        return 0.4
    score = info.get("score")
    return float(score) if isinstance(score, (int, float)) else 1.0


def _links(notes: list[dict]) -> list[tuple[int, int]]:
    ids = {n["id"] for n in notes}
    pairs = {tuple(sorted((n["id"], other))) for n in notes for other in (n.get("linked_to") or []) if other in ids and other != n["id"]}
    return sorted(pairs)


def _components(ids: list[int], pairs: list[tuple[int, int]]) -> list[list[int]]:
    parent = {i: i for i in ids}

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b in pairs:
        parent[root(a)] = root(b)
    out: dict[int, list[int]] = {}
    for i in ids:
        out.setdefault(root(i), []).append(i)
    return list(out.values())


def _tag_pairs(notes: list[dict]) -> tuple[list[tuple[int, int]], set[str]]:
    """Pairs of notes sharing a tag that does not sit on every note."""
    tags = {n["id"]: _tags(n) for n in notes}
    common = set.intersection(*tags.values()) if len(tags) > 1 else set()
    holders: dict[str, list[int]] = {}
    for n in notes:
        for t in tags[n["id"]] - common:
            holders.setdefault(t, []).append(n["id"])
    pairs = [(held[0], other) for held in holders.values() if len(held) > 1 for other in held[1:]]
    return pairs, common


def _joined(members: list[dict], links: list[tuple[int, int]], common: set[str]) -> tuple[str, str]:
    """A theme's name and what joins it, in words."""
    #: In the order written, so a tie names the tag the person put first.
    counts = Counter(t for n in members for t in _tag_list(n) if t not in common)
    shared = [(t, c) for t, c in counts.most_common() if c > 1]
    if not shared:
        return "", "linked"
    tag, count = shared[0]
    if count == len(members):
        said = f"both tagged #{tag}" if count == 2 else f"all tagged #{tag}"
    else:
        said = f"share #{tag}"
    return tag, said


def themes(notes: list[dict]) -> list[Group]:
    """The notes as groups, closest first; a note joined to no other is a
    group of one, after the rest."""
    if not notes:
        return []
    by_id = {n["id"]: n for n in notes}
    links = _links(notes)
    tag_pairs, common = _tag_pairs(notes)
    groups = []
    for ids in _components(list(by_id), links + tag_pairs):
        members = [by_id[i] for i in ids]
        name, joined = _joined(members, links, common) if len(ids) > 1 else ("", "")
        inside = [p for p in links if p[0] in ids and p[1] in ids]
        groups.append(Group(ids, name, joined, sum(_score(m) for m in members) / len(members), links=inside))
    order = {n["id"]: i for i, n in enumerate(notes)}
    groups.sort(key=lambda g: (len(g.ids) == 1, -round(g.score, 2), -len(g.ids), order[g.ids[0]]))
    return groups


def groups(notes: list[dict]) -> list[Group]:
    """The groups an answer is said in, each with its band, or [] when a
    frame would not help (too few notes, or no two of them go together)."""
    found = themes(notes)
    multi = [g for g in found if len(g.ids) > 1]
    if len(notes) < FRAME_MIN or not multi:
        return []
    #: Named in the order they are told: the notes' own order.
    loose = [n["id"] for n in notes if any(g.ids == [n["id"]] for g in found)]
    best = multi[0]
    rest = [_score(n) for n in notes if n["id"] not in best.ids]
    if rest and best.score >= max(rest) + CLOSEST_MARGIN:
        best.band = "closest"
    out = list(multi)
    if loose:
        out.append(Group(loose, band="loose", score=min(_score(n) for n in notes if n["id"] in loose)))
    return out


def _lower(text: str) -> str:
    """"Movie review" as "movie review"; "League of Legends" and "Gym
    Routine Overview" keep their capitals: a later capital marks a name."""
    words = text.split()
    if len(words) > 1 and any(w[:1].isupper() for w in words[1:3]):
        return text
    return text[:1].lower() + text[1:] if text[1:2].islower() else text


def short_name(note: dict, lower=_lower) -> str:  # noqa: ANN001
    """A note as a list names it: its title, its own label, or what it is
    about; quoted when it is an instruction ("go to the gym at 9pm")."""
    content = str(note.get("content") or "").strip()
    first = content.splitlines()[0].strip().rstrip(".") if content else ""
    head = _PREFIX.match(first)
    category = str(note.get("category") or "").lower()
    if head and len(head.group(1).split()) <= 5 and head.group(1).strip().lower() != category:
        return f"the {lower(head.group(1).strip())} note"
    if not head and "\n" in content and len(first.split()) <= 6:
        return f"the {first}"
    body = head.group(2) if head else first
    clause = re.split(r"[,;.!?]", body, maxsplit=1)[0].strip()
    if _IMPERATIVE.match(clause):
        return "“" + lower(clause) + "”"
    clause = _DOING.sub("", clause).strip() or clause
    words = clause.split()
    clause = " ".join(words[:7])
    if not re.match(r"(?:the|a|an|my|your)\b", clause, re.I):
        clause = lower(clause)
    return re.sub(r"^my\b", "your", clause, flags=re.I)


def _names(ids: list[int], by_id: dict[int, dict], lower) -> str:  # noqa: ANN001
    #: Two notes of the same words are named once.
    said = list(dict.fromkeys(short_name(by_id[i], lower) for i in ids))
    if len(said) <= 2:
        return " and ".join(said)
    return ", ".join(said[:-1]) + " and " + said[-1]


def _link_said(group: Group, by_id: dict[int, dict], lower) -> str:  # noqa: ANN001
    if not group.links:
        return ""
    a, b = group.links[0]
    return f"you linked {short_name(by_id[a], lower)} to {short_name(by_id[b], lower)}"


def group_line(group: Group, notes: list[dict], topic: str, lower=_lower) -> str:  # noqa: ANN001
    """One line saying why a group answers the question and how its notes go
    together: "Your gym notes go together: the Gym Routine Overview and
    “go to the gym at 9pm on Tuesday”, both tagged #gym."."""
    by_id = {n["id"]: n for n in notes}
    names = _names(group.ids, by_id, lower)
    if group.band == "loose":
        alone = "a note of its own" if len(group.ids) == 1 else "each a note of its own"
        return f"Also under {topic}, more loosely: {names}, {alone}."
    linked = _link_said(group, by_id, lower)
    theme = f"your {group.name} notes" if group.name else "two of your notes" if len(group.ids) == 2 else "some of your notes"
    joined = "" if group.joined_by == "linked" else group.joined_by
    if group.joined_by.startswith("share "):
        line = f"{theme} {group.joined_by}: {names}"
    else:
        line = f"{theme} go together: {names}" + (f", {joined}" if joined else "")
    if linked:
        line += f", and {linked}"
    lead = f"Closest to {topic}, " if group.band == "closest" else ""
    line = lead + line
    return line[:1].upper() + line[1:] + "."


def topic_words(question: str) -> str:
    """The words a question is about ("hobbies"), for a reason line."""
    words = [w for w in re.findall(r"[a-z][a-z'-]*", question.lower()) if w not in _STOP]
    return " ".join(words[:3])


_BASE_BY_MODE = {
    "dated": "Written in the time you asked about",
    "recent": "One of your newest notes",
    "attached": "You attached it",
}


def _by_meaning(note: dict, info: dict, about: str, by_id: dict) -> str:  # noqa: ARG001
    score = float(info["score"])
    how = "closely " if score >= 0.75 else "loosely " if score < 0.45 else ""
    words = f" and by the word “{info['terms'][0]}”" if info.get("type") == "hybrid" and info.get("terms") else ""
    return f"Matches {about} {how}by meaning{words}"


def _by_word(note: dict, info: dict, about: str, by_id: dict) -> str:  # noqa: ARG001
    category = str(note.get("category") or "")
    if category.lower() in {str(t).lower() for t in info["terms"]}:
        return f"Filed under {category}"
    return f"Has the word “{info['terms'][0]}”"


def _by_link(note: dict, info: dict, about: str, by_id: dict) -> str:  # noqa: ARG001
    via = [by_id[i] for i in (note.get("linked_to") or []) if i in by_id]
    step = "Linked to" if info.get("type") == "connected" else "Two links from"
    target = short_name(via[0]) if via else "a note that matched"
    return f"{step} {target}" + (f" ({info['reason']})" if info.get("reason") else "")


def _sayer(info: dict):  # noqa: ANN202
    kind = info.get("type")
    if kind in ("semantic", "hybrid") and isinstance(info.get("score"), (int, float)):
        return _by_meaning
    if kind == "keyword" and info.get("terms"):
        return _by_word
    return _by_link if kind in ("connected", "connected_2hop") else None


def _base(note: dict, topic: str, by_id: dict[int, dict], mode: str) -> str:
    """Why the search brought this note, as words."""
    info = note.get("match_info") or {}
    say = _sayer(info)
    if say:
        return say(note, info, topic or "your question", by_id)
    fallback = f"Matches {topic}" if topic else "Found by your search"
    return _BASE_BY_MODE.get(mode.split(" + ")[0] if mode else "", fallback)


def _relation(note: dict, before: list[dict], by_id: dict[int, dict], common: set[str]) -> str:
    """How this note stands to a note shown above it: a link, then a tag."""
    linked = [i for i in (note.get("linked_to") or []) if i in by_id and i != note["id"]]
    if linked:
        return f"linked to {short_name(by_id[linked[0]])}"
    mine = _tags(note) - common
    for other in before:
        shared = sorted(mine & _tags(other))
        if shared:
            return f"shares #{shared[0]} with {short_name(other)}"
    return ""


def reasons(question: str, notes: list[dict], mode: str = "") -> dict[str, str]:
    """Each shown note's reason, keyed by str(id), for its Matching records
    card: why the search brought it, then how it stands to the others."""
    by_id = {n["id"]: n for n in notes}
    topic = topic_words(question)
    _, common = _tag_pairs(notes)
    out: dict[str, str] = {}
    for n, note in enumerate(notes):
        base = _base(note, topic, by_id, mode)
        rel = "" if base.startswith(("Linked", "Two links")) else _relation(note, notes[:n], by_id, common)
        out[str(note["id"])] = f"{base}, and {rel}" if rel else base
    return out
