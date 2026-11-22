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

from tessellate.core.lazyre import lazy_compile
from collections import Counter
from dataclasses import dataclass, field

from tessellate.ai import composer_threads, realise
from tessellate.core import cjk

#: A group leads as "the closest" only when its notes score this far above
#: every note outside it; nearer than that, no group is closer than another.
CLOSEST_MARGIN = 0.1
#: Fewer notes than this read fine as a list: no frame.
FRAME_MIN = 4
_STOP = frozenset(
    "what whats have has had i i've ive me my mine saved save about the a an any anything do does did "
    "is are was were tell show list give all of on in for to with from notes note written wrote you your "
    "know there so far else say said more other another also can could would should please how what's "
    "which who when where why find get we our us it its that this these those if or and but not no yes "
    "much many some really just still ever already yet".split()
)
_PREFIX = lazy_compile(r"^([^:.!?\n]{2,40}):\s+(\S.*)$", re.S)
_IMPERATIVE = lazy_compile(r"^(?:go|buy|call|book|get|ask|read|pay|send|bring|try|do|check|remember)\b", re.I)


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
    #: Loose notes the question's own category holds: counted, not "loosely related".
    in_topic: bool = False
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


_MARKS = lazy_compile(r"(?m)^\s*(?:#{1,6}\s+|[-*+]\s+(?:\[[ xX]\]\s+)?|\d+[.)]\s+)|\*\*|__|`")


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


#: `[^\W_]` is exactly `str.isalnum` (letters and digits, not the underscore); a
#: compiled search per token is a quarter faster than `any(c.isalnum() ...)`.
_HAS_ALNUM = lazy_compile(r"[^\W_]").search


def note_words(content: str | None) -> int:
    """How many words a note has: its tokens that hold a letter or a digit, so
    a list dash is not one, and not its title line, which names the note
    rather than says anything in it. The one counter for "how long is this
    note", "which is longer" and "your longest note" (audit 1030 Z10)."""
    body = re.sub(r"\A\s*#{1,6}[ \t][^\n]*", "", str(content or ""))
    #: A script with no spaces counts by character, as every other count does (N15).
    if cjk.has(body):
        return cjk.word_count(body)
    return sum(1 for token in body.split() if _HAS_ALNUM(token))


_SAID_IN_A_FRAME = []


def bind_lower(said) -> None:  # noqa: ANN001
    """The digest hands in how a name is said after other words: lower case
    only where its first word is a plain dictionary word, so "Myers
    chapters" and "Lisbon trip" keep their capital (composer-1031). This
    module imports no composer, so it is given, not imported."""
    _SAID_IN_A_FRAME[:] = [said]


def _lower(text: str) -> str:
    """"Movie review" as "movie review"; "League of Legends" and "Gym
    Routine Overview" keep their capitals: a later capital marks a name."""
    if _SAID_IN_A_FRAME:
        return _SAID_IN_A_FRAME[0](text)
    return _plain_lower(text)


def _plain_lower(text: str) -> str:
    words = text.split()
    if len(words) > 1 and any(w[:1].isupper() for w in words[1:3]):
        return text
    if words and any(c.isupper() for c in words[0][1:]):
        return text  # "IaaS", "iPhone": a capital inside the word is its shape
    return text[:1].lower() + text[1:] if text[1:2].islower() else text


#: What a note's first line is when it is a name: a heading's or bold
#: marks, the colon after "Ice Breakers:", a split "Follow- Up" (INBOX 1420).
_MARK = lazy_compile(r"[*_`]")
_SPLIT_HYPHEN = lazy_compile(r"(?<=[A-Za-z])- (?=[A-Z][a-z])")
_ARTICLE = lazy_compile(r"(?:the|a|an)\b", re.I)
#: Searched on right-stripped text with no leading `\s*`: `\s*(face)\s*$`
#: re-scanned every whitespace run from each start, quadratic on a line of
#: tabs (CodeQL, polynomial regex). One helper for every reader.
_EMOTICON_END = lazy_compile(r"(?:[:;=][-']?[()DPpOo/|\\]+|<3)$")


def strip_end_emoticon(text: str) -> str:
    """`text` without a closing emoticon and the space before it ("done :)")."""
    face = _EMOTICON_END.search(text.rstrip())
    return text[: face.start()].rstrip() if face else text


def _plain(text: str) -> str:
    return _SPLIT_HYPHEN.sub("-", _MARK.sub("", text)).strip()


def _list_item(line: str) -> bool:
    """"- eggs", "2) milk", "[x] bread": the first of a list, by string steps:
    CodeQL reads `\\d+[.)]` as backtracking on a run of digits."""
    rest = line.lstrip("0123456789")
    if len(rest) < len(line) and rest[:1] in (".", ")"):
        return rest[1:2].isspace()
    return (line[:1] in "-*+•" and line[1:2].isspace()) or (line[:1] == "[" and line[1:2] in " xX" and line[2:3] == "]" and line[3:4].isspace())


def _opens_section(line: str) -> bool:
    """`_PREFIX.match(line)` by string steps: "Pros: more time". The label
    before the first colon is 2 to 40 characters with no sentence stop, and
    words follow the colon after a space."""
    label, colon, rest = line.partition(":")
    return bool(colon and 2 <= len(label) <= 40 and not any(c in label for c in ".!?\n") and rest[:1].isspace() and rest.strip())


def _marked(first: str) -> bool:
    """A heading or a bold line. Bold is checked by its ends, not by a
    backreference regex, which backtracks on a long line of markers (CodeQL
    polynomial ReDoS)."""
    shut = first[:-1] if first.endswith(":") else first
    return bool(re.match(r"#{1,6}\s", first)) or (
        first[:2] in ("**", "__") and len(shut) > 4 and not first[2].isspace() and shut.endswith(first[:2])
    )


def _title_of(content: str) -> str:
    """A first line that names the note ("# Trains", "**The Complete Social
    Skills Guide**", "Ice Breakers:" over its list), or ""."""
    lines = content.splitlines()
    if len(lines) < 2 or not "".join(lines[1:]).strip():
        return ""
    first = lines[0].strip()
    marked = _marked(first)
    if not marked and _list_item(first):
        #: "[x] Milk" and "- eggs" are the first of a list, not its name.
        return ""
    if not marked and _opens_section(_plain(first)):
        #: "Pros: more time" opens a section; it does not name the note (C8).
        return ""
    name = _plain(re.sub(r"^#{1,6}\s+", "", first)).rstrip(".").rstrip(":").strip()
    if not marked and (_said_line(name) or re.search(r"[,;!?]", name)):
        #: "Went to the gym today" over its details is what the person did,
        #: never the note's name (1515); "Legs day" is a name.
        return ""
    return name if name and len(name.split()) <= (10 if marked else 6) else ""


def title_line(content: str) -> str:
    """**The one reader of a note's own name for every answer shape** (INBOX
    1515: the frame, the sections and the lists each read it their own way):
    a heading, a bold line, a short plain first line over the note's body, or
    a one-line note that is only a name; "" for a note that has none."""
    return _title_of(content) or own_title(content)


def _titled(title: str) -> str:
    """A note's own name as it is: "Cloud computing", never "the Cloud
    computing" (composer-1031); "The Complete Social Skills Guide" keeps its
    own article; a lower-case one is "your trains note"."""
    return title if _ARTICLE.match(title) or title[:1].isupper() or title[:1].isdigit() else f"your {title} note"
#: How many words of a title-less note's first clause name it (C8, R3-15).
_CLIP_WORDS = 6


#: A stop after one of these is part of the word, not the end of a clause.
_ABBREVIATIONS = frozenset("dr mr mrs ms st vs etc approx cf prof jr sr no".split())
#: A list, task or heading mark at the start of a line: not part of its words.
_LINE_MARK = lazy_compile(r"(?:#{1,6}[ \t]+|[-*+][ \t]+|\d{1,3}[.)][ \t]+)?(?:\[[ xX]\][ \t]+)?")


def _clause_end(first: str) -> int:
    """Where the first clause of a line ends: at a semicolon or sentence stop
    followed by a space, but not after an abbreviation ("Dr. Smith") or a
    single initial ("J. Smith"). A comma does not end it: "Here are some
    refined, non-corny lines" is not named "Here are some refined" (1420)."""
    for found in re.finditer(r"(?<=\w)[;.!?](?=\s|$)", first):
        word = first[: found.start()].rsplit(None, 1)[-1].lower()
        if found.group() == "." and (word in _ABBREVIATIONS or len(word) == 1 or "." in word):
            continue
        return found.start()
    return len(first)


def clipped_words(note: dict) -> str:
    """The first clause of a title-less note, six words at most, cut with an
    ellipsis, unquoted ("Dentist said to floss more and…"); "" for a note
    with no words. The chip and the link text quote it themselves."""
    first = _first_line(str(note.get("content") or "").strip())
    first = _LINE_MARK.sub("", first, count=1).strip()
    words = first[: _clause_end(first)].split()
    said = " ".join(words[:_CLIP_WORDS]).rstrip(",;:")
    return said + ("…" if len(words) > _CLIP_WORDS else "") if said else ""


#: Words of when that were the note's own day. A summary is read on other
#: days than the notes were written, so it never says them (INBOX 1461).
_OWN_DAY = lazy_compile(r"\b(?:today|yesterday|tonight|this (?:morning|afternoon|evening)|last night)\b", re.I)


def without_own_day(name: str) -> str:
    """`name` without the note's own "today" ("Pottery: trimmed my first bowl"),
    unchanged when nothing else would be left."""
    return " ".join(_OWN_DAY.sub("", name).split()).replace(" ”", "”").replace("“ ", "“") or name


def link_text(note: dict) -> str:
    """A note's name as the text of a link to it: the heading when it has one, else `name_of`'s quoted first line
    (a lower-case "hi" is “hi”, never "your hi note" inside brackets)."""
    explicit = _title_of(str(note.get("content") or "").strip())
    return explicit or name_of(note)


def _order_title(content: str) -> str:
    """A one-line note that is an order in a few capitalised words ("Call
    plumber", "Renew passport") is named as it is written, plain, as every
    other title (owner answer Q3, W10 B36). Not `own_title`: that one says a
    note is only a name, which an order is not."""
    line = _first_line(content.strip())
    if "\n" in content.strip() or not line or len(line.split()) > 4 or not line[:1].isupper():
        return ""
    if re.search(r"[,;:.!?、。！？；：，]", line) or NON_LATIN.search(line) or _FINITE.search(line) or _WHEN_IN_LINE.search(line):
        return ""
    return line if _IMPERATIVE.match(line) else ""


def name_of(note: dict) -> str:
    """**The one name for a note, on every surface** (R3-15): its own title
    when it has one ("Trains", `_titled`), else its first clause, six words
    at most, in quotes (“Dentist said to floss more and…”), in a list, a
    sentence, a link's text and the Open chip. The day is the caller's muted
    second field, never part of the name."""
    content = str(note.get("content") or "").strip()
    title = _title_of(content)
    if title:
        return _titled(title)
    #: A one-line note that is only a name: as written when it starts with a capital, else quoted like any
    #: title-less note ("milk", not "your milk note"; owner 2026-11-10).
    own = own_title(content)
    if own and (own[:1].isupper() or own[:1].isdigit() or _ARTICLE.match(own)):
        return own
    if (order := _order_title(content)):
        return order
    return f"“{clipped_words(note) or 'An empty note'}”"


#: A verb that makes a short line a sentence, after its first word (the
#: first is the imperative's or the dropped "I"'s, read by own_title's guards).
_FINITE = lazy_compile(r"\s(?:is|are|was|were|has|had|starts|started|begins|began|ends|ended|opens|closes|"
                     r"comes|came|goes|went|looks|sent|wants|needs|says|said|gets|got|takes|took|likes|liked|loves|loved|hates|hated|prefers|"
                     #: A regular past with its place or time after it: "Group
                     #: project meeting moved to Friday" says something (1461).
                     r"[a-z]{3,}ed\s+(?:to|on|at|in|for|from|until|till|back|up|off|out|by)\b)\b", re.I)


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


NON_LATIN = lazy_compile(r"[\u0400-\u052f\u0590-\u06ff\u0900-\u097f\u0e00-\u0e7f\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")


#: A time or a day inside a line makes it a plan, never a name ("Pottery class
#: on Thursday at 6pm"): the note says something, so it is quoted (1515).
_WHEN_IN_LINE = lazy_compile(
    r"\b\d{1,2}(?::\d\d)?\s?(?:am|pm)\b|\b(?:on|at|by|every|next|this)\s+(?:mon|tues?|wed(?:nes)?|thu(?:rs)?|fri|sat(?:ur)?|sun)(?:day)?\b"
    r"|\b(?:on|by)\s+\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", re.I)


def _said_line(line: str) -> bool:
    """A line that says something (a verb, an order, a first-person start,
    what the person did) and so cannot name a note."""
    return bool(_FINITE.search(line) or _IMPERATIVE.match(line) or re.match(r"i\b", line, re.I) or _DIARY_VERB.match(line))


def own_title(content: str) -> str:
    """A one-line note that is only a name ("Atlas retro meeting"): short,
    no sentence marks, not an instruction and not the person's own "I";
    "" otherwise."""
    line = _first_line(content.strip())
    #: "Gym: squats at 80 kg" is a label and its detail, never a title.
    if "\n" in content.strip() or not line or re.search(r"[,;:.!?、。！？；：，]", line) or len(line.split()) > 6:
        return ""
    #: A line in a script with no spaces or stops of the kind this reads
    #: ("今日は雨が降っていたので、...") cannot be judged a name: it is the
    #: note's words, quoted whole, never "only a title" (audit 1031 C10).
    if NON_LATIN.search(line):
        return ""
    if _FINITE.search(line) or _WHEN_IN_LINE.search(line):
        #: "Intro to Cloud Computing starts Monday" says something: a
        #: sentence, never a name ("the Intro to ... starts Monday names it").
        return ""
    return "" if _said_line(line) else line
#: A diary line with its "I" dropped opens on a verb in the past: "had
#: design class today", "went to the gym", "finished my assignment".
_DIARY_VERB = lazy_compile(
    r"^(?:had|went|met|got|made|did|saw|took|ate|bought|came|felt|found|gave|heard|kept|left|lost|paid|ran|sent|"
    r"slept|spent|told|wore|won|wrote|began|brought|caught|drove|flew|forgot|knew|rode|sat|sold|spoke|swam|"
    r"taught|woke|built|held|"
    #: Regular pasts that tell what the person did before a bare noun
    #: ("Booked flights to Lisbon", "Cooked dinner for Sam"): verbs, never a
    #: dish's or a subject's adjective ("grilled", "advanced", "mixed").
    r"(?:book|cook|visit|watch|play|clean|fix|order|paint|plant|walk|pack|email|text|submitt|join|cancel|"
    r"cancell|renew|return|sign|post|print|upload|install|attend|complet|hand|pass|miss|help|call|finish|"
    r"start|plann|organis|organiz|schedul|rebook|repair|replac|wash|vacuum|feed)ed(?=\s+[A-Za-z])|"
    #: A regular past only before a thing's article or a place's word:
    #: "advanced calculus" and "grilled cheese recipe" stay names.
    r"[a-z]{2,}ed(?<!need)(?<!feed)(?<!seed)(?<!speed)(?=\s+(?:a|an|the|my|our|some|to|at|for|with|on|in|into|up|out|over|back)\b))"
    r"\s+(?:(?:to|at|for|with|on|in|into|up|out|over|back)\s+)?",
    re.I,
)


#: A first line that is only pictures ("![](/media/cat.png)"): no words to
#: name the note by, never its markdown (INBOX 1512).
_ONLY_PICTURES = lazy_compile(r"(?:!\[[^\]\n]{0,300}\]\([^)\s]{0,1000}\)\s*)+")


def short_name(note: dict, lower=_lower) -> str:  # noqa: ANN001
    """A note as a list names it: its title, or `name_of` for a title-less
    one (R3-15: one name, not a second way per surface)."""
    content = str(note.get("content") or "").strip()
    if note.get("_by_day"):
        return composer_threads.note_from(note)
    if _ONLY_PICTURES.fullmatch(content.split("\n", 1)[0].strip()):
        return composer_threads.picture_name(note)
    return name_of(note)


def _first_line(content: str) -> str:
    """The note's first line, plain, without a heading's marks or a closing emoticon."""
    first = _plain(content.splitlines()[0]).rstrip(".") if content else ""
    #: A heading's own marks are not part of its name: "the # Trains" (1324).
    first = re.sub(r"^#{1,6}\s+", "", first)
    return strip_end_emoticon(first).rstrip(".")
#: A group names at most this many of its notes; the rest are counted
#: ("A, B and four more"), since each is told on its own line below (INBOX
#: 1461: a line of ten names was a list, not a summary).
NAMED_MAX = 3


def _names(ids: list[int], by_id: dict[int, dict], lower) -> str:  # noqa: ANN001
    #: Two notes of the same words are named once.
    said = list(dict.fromkeys(short_name(by_id[i], lower) for i in ids))
    if len(said) > NAMED_MAX:
        rest = len(said) - 2
        said = [*said[:2], f"{realise.count_word(rest)} more"]
    if len(said) <= 2:
        return " and ".join(said)
    return ", ".join(said[:-1]) + " and " + said[-1]


def reason_said(reason: str) -> str:
    """A link's reason as one clause, in the second person or quoted as the
    person's own (`composer_threads.reason_said`, INBOX 1512)."""
    return composer_threads.reason_said(reason)


def _link_said(group: Group, by_id: dict[int, dict], lower, i: int = 0) -> str:  # noqa: ANN001
    """The group's link as its own sentence, so the group's line does not run
    on through a third "and" (INBOX 1420); back to "them" when the group is
    just the pair the line named, a wording of its own each group (1512)."""
    if not group.links:
        return ""
    a, b = group.links[0]
    reason = (by_id[a].get("link_reasons") or {}).get(b) or (by_id[b].get("link_reasons") or {}).get(a)
    back = len(group.ids) == 2 and {a, b} == set(group.ids)
    #: A reason the two notes' own words already say is not said again (INBOX 1767 c).
    reason = "" if composer_threads.restated(reason or "", by_id[a], by_id[b]) else reason
    return composer_threads.link_said(short_name(by_id[a], lower), short_name(by_id[b], lower), reason or "", i, back)


def _shared_line(group: Group, theme: str, by_id: dict[int, dict], lower) -> str:  # noqa: ANN001
    """"your gym notes share the tag #gym: A and B": only the notes that carry
    the tag share it; the others are in the group through a link (audit 1031 C14)."""
    holders = [i for i in group.ids if group.name in _tag_list(by_id[i])]
    others = [i for i in group.ids if i not in holders]
    if len(group.ids) > NAMED_MAX:
        #: A big group says what joins it and how many are linked in, not a
        #: run of titles: each note is told on its own line below (INBOX 1665 b).
        more = f", and {realise.count_word(len(others))} more {'is' if len(others) == 1 else 'are'} linked to {'it' if len(holders) == 1 else 'them'}"
        return f"{theme} {group.joined_by}{more if holders and others else ''}"
    line = f"{theme} {group.joined_by}: {_names(holders or group.ids, by_id, lower)}"
    if holders and others:
        line += f"; {_names(others, by_id, lower)} {'is' if len(others) == 1 else 'are'} linked to {'it' if len(holders) == 1 else 'them'}"
    return line


def _group_clause(group: Group, topic: str, theme: str, by_id: dict[int, dict], lower, i: int = 0) -> str:  # noqa: ANN001
    """The group's line before its capital and stop, worded by its place `i`."""
    names = _names(group.ids, by_id, lower)
    joined = "" if group.joined_by == "linked" else group.joined_by
    tail = f", {joined}" if joined else ""
    if group.band == "closest" and topic == group.name:
        #: "Closest to conversation, your conversation notes" said it twice.
        return f"closest of all are {theme}: {names}{tail}"
    if group.joined_by.startswith("share "):
        line = _shared_line(group, theme, by_id, lower)
    else:
        line = composer_threads.group_said(theme, names, tail, 0 if group.band == "closest" else i)
    return f"Closest to {topic}, {line}" if group.band == "closest" else line


def echoed(group: Group, notes: list[dict], told: str) -> set[int]:
    """The group's notes its line names by a quote of all their words that the
    lines told after it quote again (INBOX 1515: "the note that starts
    “Climbing gym membership renewed for a year”" then "You wrote “Climbing
    gym membership renewed for a year”"); such a note is named by its day."""
    by_id = {n["id"]: n for n in notes}
    said = _flat_quote(told)
    found = set()
    for i in group.ids:
        quote = re.search(r"“([^”…]+)”", short_name(by_id[i]))
        if quote and len(quote.group(1).split()) >= 2 and _flat_quote(quote.group(1)) in said:
            found.add(i)
    return found


def _flat_quote(text: str) -> str:
    return " ".join(_plain(text).lower().replace("’", "'").split()).rstrip(".")


def group_line(group: Group, notes: list[dict], topic: str, lower=_lower, i: int = 0, by_day: frozenset | set = frozenset()) -> str:  # noqa: ANN001
    """One line saying why a group answers the question and how its notes go
    together: "Your gym notes go together: the Gym Routine Overview and
    “go to the gym at 9pm on Tuesday”, both tagged #gym."."""
    by_id = {n["id"]: ({**n, "_by_day": True} if n["id"] in by_day else n) for n in notes}
    if group.band == "loose":
        #: No names: each of these notes is told on its own line below, and a
        #: name here said it twice (INBOX 1665 f).
        return f"More from {topic}." if group.in_topic else f"More loosely related to {topic}."
    linked = _link_said(group, by_id, lower, i)
    theme = f"your {group.name} notes" if group.name else "two of your notes" if len(group.ids) == 2 else "some of your notes"
    line = _group_clause(group, topic, theme, by_id, lower, i)
    line = line[:1].upper() + line[1:] + "."
    return f"{line} {linked}" if linked else line


_MEDIA = lazy_compile(r"!\[[^\]\n]{0,300}\]\([^)\n]{0,1000}\)|\[Pictures in this note, as this app read them:")


def thread_name(group: Group, by_id: dict[int, dict]) -> str:
    """What a group is about, for the lead (INBOX 1512): its tag, or the word
    its notes and their link's reason share ("sketches"), or ""."""
    if group.name:
        return group.name
    texts = [_MEDIA.sub(" ", str(by_id[i].get("content") or "")) for i in group.ids]
    texts += [str(r) for i in group.ids for r in (by_id[i].get("link_reasons") or {}).values()]
    return composer_threads.thread_word(texts)


def lead_line(groups: list[Group], notes: list[dict], seed: int = 0) -> str:
    """"They fall into three threads: gaming, art and gym.", or "" for fewer
    than two named threads."""
    by_id = {n["id"]: n for n in notes}
    return composer_threads.lead_said([thread_name(g, by_id) for g in groups if g.band != "loose"], seed)


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
    terms = [str(t) for t in info["terms"]]
    if category.lower() in {t.lower() for t in terms}:
        return f"Filed under {category}"
    #: A filler word of the question ("say") is not what the note has.
    real = [t for t in terms if t.lower() not in _STOP] or terms
    return f"Has the word “{real[0]}”"


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
