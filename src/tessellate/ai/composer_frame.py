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


_MARKS = re.compile(r"(?m)^\s*(?:#{1,6}\s+|[-*+]\s+(?:\[[ xX]\]\s+)?|\d+[.)]\s+)|\*\*|__|`")


def plain_snippet(content: str | None, limit: int = 60) -> str:
    """A note's opening as one plain line for a lead: heading, list and
    checkbox marks off, cut at a word or a sentence end, never mid-word and
    never with a space before the closing quote (audit 1030 Z44)."""
    text = " ".join(_MARKS.sub("", str(content or "")).split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    stop = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if stop >= limit // 2:
        return cut[: stop + 1]
    return cut[: cut.rfind(" ")].rstrip(" ,;:-") + "…" if " " in cut else cut + "…"


def note_words(content: str | None) -> int:
    """How many words a note has: its tokens that hold a letter or a digit, so
    a list dash is not one, and not its title line, which names the note
    rather than says anything in it. The one counter for "how long is this
    note", "which is longer" and "your longest note" (audit 1030 Z10)."""
    body = re.sub(r"\A\s*#{1,6}[ \t][^\n]*", "", str(content or ""))
    return sum(1 for token in body.split() if any(c.isalnum() for c in token))


def _lower(text: str) -> str:
    """"Movie review" as "movie review"; "League of Legends" and "Gym
    Routine Overview" keep their capitals: a later capital marks a name."""
    words = text.split()
    if len(words) > 1 and any(w[:1].isupper() for w in words[1:3]):
        return text
    if words and any(c.isupper() for c in words[0][1:]):
        return text  # "IaaS", "iPhone": a capital inside the word is its shape
    return text[:1].lower() + text[1:] if text[1:2].islower() else text


#: What a note's first line is when it is a name: a heading's or bold
#: marks, the colon after "Ice Breakers:", a split "Follow- Up" (INBOX 1420).
_MARK = re.compile(r"[*_`]")
_SPLIT_HYPHEN = re.compile(r"(?<=[A-Za-z])- (?=[A-Z][a-z])")
_ARTICLE = re.compile(r"(?:the|a|an)\b", re.I)
#: "Here are some refined, non-corny pickup ... starters that work ...": the
#: words that present a list, and where the thing presented ends.
_PRESENTING = re.compile(r"^(?:here(?:'s| is| are)|these are|this is|below are)\s+(?:some|a few|a list of|my|a|an)?\s*", re.I)
_PRESENTED_END = re.compile(r"(?<!\s)\s+(?:that|which|who|to|for|i|you|we)\b|:", re.I)
#: Where a long first sentence can end on a whole clause: "I had work today
#: and a friend was sad | so I stayed with her".
_CLAUSE_BREAK = re.compile(r"\s+(?:so|but|because|then|and then|which|and)\s+", re.I)
#: "My uni days this week are Tuesday and Thursday": a sentence about
#: something is named by its subject, "the note on your uni days this week".
_SUBJECT_VERB = re.compile(r"^((?:[\w'-]+\s+){0,5}?[\w'-]+)\s+(?:is|are|was|were|means|refers to)\b", re.I)
_EMOTICON_END = re.compile(r"\s*(?:[:;=][-']?[()DPpOo/|\\]+|<3)\s*$")
#: The longest first clause a name may quote whole.
_NAME_WORDS = 7
_QUOTE_WORDS = 12


def _plain(text: str) -> str:
    return _SPLIT_HYPHEN.sub("-", _MARK.sub("", text)).strip()


def _title_of(content: str) -> str:
    """A first line that names the note ("# Trains", "**The Complete Social
    Skills Guide**", "Ice Breakers:" over its list), or ""."""
    lines = content.splitlines()
    if len(lines) < 2 or not "".join(lines[1:]).strip():
        return ""
    first = lines[0].strip()
    marked = bool(re.match(r"#{1,6}\s|(\*\*|__)\S.*\1:?$", first))
    if not marked and _PREFIX.match(_plain(first)):
        #: "Pros: more time" opens a section; it does not name the note (C8).
        return ""
    name = _plain(re.sub(r"^#{1,6}\s+", "", first)).rstrip(".").rstrip(":").strip()
    return name if name and len(name.split()) <= (10 if marked else 6) else ""


def _titled(title: str) -> str:
    """"the Trains"; "The Complete Social Skills Guide" keeps its own article."""
    return title if _ARTICLE.match(title) else f"the {title}"


def _whole_clause(clause: str) -> str:
    """The clause, or the whole part of it before a break, short enough to
    name a note; "" when no whole part is short enough (never a cut)."""
    words = clause.split()
    if len(words) <= _QUOTE_WORDS:
        return clause
    for found in reversed(list(_CLAUSE_BREAK.finditer(clause))):
        head = clause[: found.start()].strip()
        if 3 <= len(head.split()) <= _QUOTE_WORDS:
            return head
    return ""


#: How many words of a title-less note's first clause name it (C8).
_CLIP_WORDS = 7


def _clipped(note: dict) -> str:
    """A title-less note by its first clause, cut at a word with an ellipsis:
    "the note that starts “I just missed the bus to uni…”", never by its
    day alone or "an untitled note" (audit 1029 C8, INBOX 1420)."""
    first = _first_line(str(note.get("content") or "").strip())
    clause = re.split(r"(?<=\w)[,;.!?](?:\s|$)", first, maxsplit=1)[0].strip()
    words = clause.split()
    if not words:
        return "a note with no words yet"
    said = " ".join(words[:_CLIP_WORDS]).rstrip(",;:")
    return f"the note that starts “{said}{'…' if len(words) > _CLIP_WORDS else ''}”"


#: A verb that makes a short line a sentence, after its first word (the
#: first is the imperative's or the dropped "I"'s, read by own_title's guards).
_FINITE = re.compile(r"\s(?:is|are|was|were|has|had|starts|started|begins|began|ends|ended|opens|closes|"
                     r"comes|came|goes|went|looks|sent|wants|needs|says|said|gets|got|takes|took)\b")


#: Labels that open a section of a note and never name the note: "Your
#: attendees note", "your pros note", "your key idea note" (C8).
SECTION_LABELS = frozenset("""
idea ideas pros cons attendees decisions decision actions notes note summary todo tasks takeaways takeaway questions
thoughts update status agenda outcome outcomes result results quote tip tips reading points
""".split()) | {"key idea", "key ideas", "action items", "next steps", "key points", "to do"}


def note_title(content: object, *, size: int = 80) -> str:
    """**The one reader of a note's name from its text** (second eye F13: eight
    readers named one note eight ways): `study.title_of`, which takes the text
    or a note dict. "" for a note with no words; a caller that wants
    "Untitled" says so itself."""
    from tessellate.ai import study

    return study.title_of(content.get("content") if isinstance(content, dict) else content, size=size)


def note_label(note: dict) -> str:
    """The label a title-less note opens with when it names the note
    ("Trip planning: flights to Lisbon" is the trip planning note); "" for
    a section's label ("Pros:", "Attendees:"), the note's own category, or
    a label too long to be a name."""
    head = _PREFIX.match(_first_line(str(note.get("content") or "").strip()))
    label = re.sub(r"\s+", " ", head.group(1).strip()) if head else ""
    key = label.lower()
    if not label or len(label.split()) > 5 or key in SECTION_LABELS or key == str(note.get("category") or "").strip().lower():
        return ""
    return label


def lower_name(text: str) -> str:
    """A name in running text: "Trip planning" as "trip planning", "League of Legends" as written."""
    return _lower(text)


def own_title(content: str) -> str:
    """A one-line note that is only a name ("Atlas retro meeting"): short,
    no sentence marks, not an instruction and not the person's own "I";
    "" otherwise."""
    line = _first_line(content.strip())
    #: "Gym: squats at 80 kg" is a label and its detail, never a title.
    if "\n" in content.strip() or not line or re.search(r"[,;:.!?]", line) or len(line.split()) > 6:
        return ""
    if _FINITE.search(line):
        #: "Intro to Cloud Computing starts Monday" says something: a
        #: sentence, never a name ("the Intro to ... starts Monday names it").
        return ""
    return "" if _IMPERATIVE.match(line) or re.match(r"i\b", line, re.I) else line


def _presented(body: str) -> str:
    """"Here are some refined, non-corny pickup and conversation starters
    that work ..." as "your non-corny pickup and conversation starters"."""
    rest = _PRESENTING.sub("", body, count=1)
    end = _PRESENTED_END.search(rest)
    thing = (rest[: end.start()] if end else rest).strip(" ,;")
    thing = thing.rsplit(",", 1)[-1].strip()
    return f"your {thing}" if 1 <= len(thing.split()) <= _NAME_WORDS else ""


def short_name(note: dict, lower=_lower) -> str:  # noqa: ANN001
    """A note as a list names it: its title, its own label, or what it is
    about; quoted when it is an instruction ("go to the gym at 9pm") or a
    sentence of the person's own; never a phrase cut mid-thought (1420)."""
    content = str(note.get("content") or "").strip()
    title = _title_of(content) or own_title(content)
    if title:
        return _titled(title)
    label = note_label(note)
    if label:
        return f"the {lower(label)} note"
    first = _first_line(content)
    head = _PREFIX.match(first)
    if head and head.group(1).strip().lower() in SECTION_LABELS:
        #: "Pros: more time", "Idea: a bike route": a section's label is
        #: never the note's name ("your pros note", C8).
        return _clipped(note)
    body = head.group(2) if head else first
    return _named_by_subject(body, lower) or _named_by_clause(body, note, lower)


def _first_line(content: str) -> str:
    """The note's first line, plain, without a heading's marks or a closing emoticon."""
    first = _plain(content.splitlines()[0]).rstrip(".") if content else ""
    #: A heading's own marks are not part of its name: "the # Trains" (1324).
    first = re.sub(r"^#{1,6}\s+", "", first)
    return _EMOTICON_END.sub("", first).rstrip(".")


def _named_by_subject(body: str, lower) -> str:  # noqa: ANN001
    """What the note presents, or the subject its first sentence defines; "" with neither."""
    if _PRESENTING.match(body):
        presented = _presented(body)
        if presented:
            return presented
    sentence = re.sub(r",\s*however,", "", re.split(r"(?<=[.!?])\s", body, maxsplit=1)[0])
    about = _SUBJECT_VERB.match(sentence)
    #: "What your notes leave out is ...": a wh-clause is a question's shape,
    #: never a subject to name the note by ("the note on what your notes
    #: currently leave out", INBOX 1420); the sentence is quoted instead.
    if about and not re.match(r"(?:i|it|this|that|there|here|they|we|he|she|you|what|how|why|which|who|where|when|whether)\b", about.group(1), re.I):
        return "the note on " + re.sub(r"\bmy\b", "your", lower(about.group(1)), flags=re.I)
    return ""


def _named_by_clause(body: str, note: dict, lower) -> str:  # noqa: ANN001
    """The note's first clause: quoted when an instruction or the person's own sentence, else as a phrase."""
    clause = re.split(r"[,;.!?]", body, maxsplit=1)[0].strip()
    if _IMPERATIVE.match(clause):
        return "“" + lower(clause) + "”"
    if re.match(r"i\b", clause, re.I):
        #: The person's own sentence is quoted whole, never cut into a
        #: different meaning ("I had work today and a friend").
        whole = _whole_clause(clause)
        return "“" + whole + "”" if whole else _clipped(note)
    clause = _DOING.sub("", clause).strip() or clause
    if _FINITE.search(clause):
        #: A sentence is quoted, never worn as a name ("Intro to Cloud
        #: Computing starts Monday names it in full").
        return _clipped(note)
    if len(clause.split()) > _NAME_WORDS:
        whole = _whole_clause(clause)
        if not whole or len(whole.split()) > _NAME_WORDS:
            return _clipped(note)
        clause = whole
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
    """"You linked the Trains to the Lisbon note.", its own sentence, so the
    group's line does not run on through a third "and" (INBOX 1420)."""
    if not group.links:
        return ""
    a, b = group.links[0]
    return f"You linked {short_name(by_id[a], lower)} to {short_name(by_id[b], lower)}."


def group_line(group: Group, notes: list[dict], topic: str, lower=_lower) -> str:  # noqa: ANN001
    """One line saying why a group answers the question and how its notes go
    together: "Your gym notes go together: the Gym Routine Overview and
    “go to the gym at 9pm on Tuesday”, both tagged #gym."."""
    by_id = {n["id"]: n for n in notes}
    names = _names(group.ids, by_id, lower)
    if group.band == "loose":
        return f"More loosely related to {topic}: {names}."
    linked = _link_said(group, by_id, lower)
    theme = f"your {group.name} notes" if group.name else "two of your notes" if len(group.ids) == 2 else "some of your notes"
    joined = "" if group.joined_by == "linked" else group.joined_by
    if group.band == "closest" and topic == group.name:
        #: "Closest to conversation, your conversation notes" said it twice.
        line = f"closest of all are {theme}: {names}" + (f", {joined}" if joined else "")
    elif group.joined_by.startswith("share "):
        line = f"{theme} {group.joined_by}: {names}"
    else:
        line = f"{theme} go together: {names}" + (f", {joined}" if joined else "")
    if group.band == "closest" and topic != group.name:
        line = f"Closest to {topic}, {line}"
    line = line[:1].upper() + line[1:] + "."
    return f"{line} {linked}" if linked else line


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
