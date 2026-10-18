"""What a topic question's notes hold, read for the overview answer (INBOX 787).

The owner, on the composed answer: "the composer is still pretty barebone, has
no life to it and I may as well just ignore it and use the matching records".
Asked "games notes" or "what did I write about uni", it quoted one or two
sentences and stopped. A person asked the same thing would say how many notes
there are and when they were written, what most of them are about, the notes
grouped by that, each with its day and one short line, and what links them.

This module is the reading half, on plain data and with no wording: which
questions ask for an overview (`topic`), which of the notes found are about
the topic (`members`), the threads that group them (`themes`), the names that
link them (`shared_names`) and the line of a note that best stands for it
(`best_line`). `composer._overview` says it, every clause a quote, a measured
count or day, a word of the question, or a word of the notes (`term`).
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Iterable

#: The frames that ask about a subject as a whole. "games notes", "ideas for
#: projects", "what did I write about uni", "summarise my uni notes", "what do
#: I know about X", "tell me about my X", "who is Jake".
_ASKS = (
    re.compile(
        r"^\s*(?:what|which)\s+(?:did|have)\s+i\s+(?:write|written|note|noted|say|said|jot|jotted|save|saved|got|keep|kept|store|stored|record|recorded|log|logged|collect|collected)(?:\s+down)?\s+(?:about|on)\s+(?:my\s+)?(?P<t>.+?)\s*\??$",
        re.I,
    ),
    re.compile(r"^\s*what\s+do\s+i\s+(?:know|have)(?:\s+written)?\s+(?:about|on)\s+(?P<t>.+?)\s*\??$", re.I),
    re.compile(r"^\s*(?:summari[sz]e|sum\s+up|go\s+over|tell\s+me\s+about|show\s+me)\s+(?:all\s+)?my\s+(?P<t>.+?)\s*\??$", re.I),
    #: The owner's own words (decision 70: "What have I saved about courses
    #: & study?") and their kin: a topic asked about as a whole, so it is
    #: counted from every note on it, not the five a search ranked first.
    re.compile(r"^\s*tell\s+me\s+about\s+(?:my\s+)?(?P<t>.+?)\s*\??$", re.I),
    re.compile(r"^\s*(?:what(?:'s|\s+is)\s+there|is\s+there\s+anything)\s+(?:about|on)\s+(?:my\s+)?(?P<t>.+?)\s*\??$", re.I),
    re.compile(r"^\s*(?:what\s+are\s+)?(?:my\s+|some\s+|any\s+)?(?P<t>ideas\s+(?:for|about)\s+.+?)\s*\??$", re.I),
    re.compile(r"^\s*(?:all\s+)?(?:my\s+|the\s+)?(?P<t>[\w'][\w' -]{1,40}?)\s+notes\s*\??$", re.I),
    #: "what is there about X" (decision 64): the overview, not one quoted line.
    re.compile(
        r"^\s*(?:what(?:'s|\s+is|s)\s+there|(?:is\s+there\s+)?anything|what\s+have\s+i\s+got)\s+(?:in\s+my\s+notes\s+)?(?:about|on)\s+(?:my\s+)?(?P<t>.+?)\s*\??$",
        re.I,
    ),
    re.compile(r"^\s*(?:who\s+is|who's)\s+(?P<t>[A-Z][\w'-]+)\s*\??$"),
    re.compile(r"^\s*what\s+(?:did|does|has)\s+(?P<t>[A-Z][\w'-]+)\s+(?:say|said|want|think|thinks?|tell\s+me)\b.{0,30}?\??$"),
    re.compile(r"^\s*how\s+many\s+(?:of\s+my\s+)?notes\s+(?:are\s+|do\s+i\s+have\s+)?(?:about|on|mention(?:ing)?)\s+(?P<t>.+?)\s*\??$", re.I),
    re.compile(r"^\s*what\s+are\s+my\s+(?P<t>[\w' -]{2,40}?)\s*\??$", re.I),
)
#: "What am I working on": the notes that say so, newest last.
DOING = "working on"
_DOING = re.compile(r"^\s*what\s+am\s+i\s+(?:working\s+on|doing|up\s+to|busy\s+with)(?:\s+(?:at\s+the\s+moment|now|right\s+now|these\s+days|lately))?\s*\??$", re.I)
#: A subject that is itself an asking frame is no subject ("my notes").
_NOT_TOPIC = re.compile(r"^(?:my|all|the|recent|latest|new|old|last|these|those|other|some|any|what|which)$", re.I)
_TRAILING_NOTES = re.compile(r"\s+notes?$", re.I)
#: "what are my notes about sourdough" is about sourdough: the subject was
#: once "notes about sourdough" ("There are two notes on notes about ...").
_LEADING_NOTES = re.compile(r"^(?:notes?|entries|entry)\s+(?:about|on|for|of|abt|re|regarding)\s+", re.I)


def topic(question: str) -> str | None:
    """The subject a question asks about as a whole, as typed, or None."""
    text = " ".join((question or "").split())
    if _DOING.match(text):
        return DOING
    for pattern in _ASKS:
        found = pattern.match(text)
        if found:
            subject = _LEADING_NOTES.sub("", _TRAILING_NOTES.sub("", found.group("t"))).strip(" ?.,")
            subject = re.sub(r"^(?:the|a|an)\s+", "", subject, flags=re.I)
            if subject and not _NOT_TOPIC.match(subject):
                return subject
    return None


def _holding(views: list, stems: set[str], holds: Callable, field: str, every: bool) -> list:
    """The notes whose `field` ("filed", "words" or "title") holds every
    (or any) stem of the subject."""
    def bag(v) -> set[str]:
        return {"filed": v.filed_words, "title": v.title_words, "words": v.words | v.filed_words}[field]

    test = all if every else any
    return [v for v in views if test(holds(stem, bag(v)) for stem in stems)]


def members(stems: set[str], views: list, holds: Callable[[str, set[str]], bool], head: str = "") -> list:
    """The notes about the topic: filed under it (a tag or the category) when
    two or more are, with any note named for it; else the notes
    holding every word of it; else those holding its first word (`head`).
    Fewer than two is no overview."""
    if stems == {DOING}:
        return [v for v in views if re.search(r"\bworking on\b", str(v.note.get("content") or ""), re.I)]
    filed = _holding(views, stems, holds, "filed", every=False) if stems else []
    if len(filed) >= 2:
        named = _holding(views, stems, holds, "title", every=True)
        return [v for v in views if v in filed or v in named]
    every = _holding(views, stems, holds, "words", every=True) if stems else []
    if len(every) >= 2:
        return every
    found = _holding(views, _wider(stems, every, head), holds, "words", every=False)
    return found if len(found) >= 2 else []


def _wider(stems: set[str], every: list, head: str) -> set[str]:
    """When fewer than two notes hold the whole subject: none, its words one
    at a time; one, its first word alone ("League of Legends" is in the notes
    that say "League"), else nothing, since that note is the answer, not one
    of several sharing a word of it ("binary search trees")."""
    if not every:
        return stems
    return {head} if len(every) == 1 and len(stems) > 1 and head else set()


#: A capitalised word after a lower-case one: a name, never a sentence's
#: first word ("League" in "for our League team", "COMP1511" in "for COMP1511").
_NAMED = re.compile(r"(?<=[a-z,] )([A-Z][A-Za-z]{2,}(?: [A-Z][A-Za-z]+)*|[A-Z]{2,}\d{2,})\b")
_ANY_CASE_CODE = re.compile(r"\b([A-Z]{2,}\d{2,})\b")
#: Capitalised words that name no thread: days, months, the person.
_PLAIN = frozenset(
    "monday tuesday wednesday thursday friday saturday sunday january february march april may june july "
    "august september october november december today tomorrow yesterday notes note idea ideas the this".split()
)


def _names(text: str) -> set[str]:
    return {m for m in _NAMED.findall(text) if m.lower() not in _PLAIN and m.lower() not in _NOT_TOPICS} | set(_ANY_CASE_CODE.findall(text))


#: Words that start a heading without being its topic: function words and
#: the verbs a note opens with ("Ask one more question", "Buy snacks"). A
#: thread named "Ask" reads as a sentence start, not a subject.
_NOT_TOPICS = frozenset(
    "ask tell call ring text email message book buy pay send check collect pick get see meet renew cancel finish start "
    "fix write read try make take bring find keep let use go do have has had are was were will would should could can "
    "may might must not remember note notes todo idea ideas plan plans list lists add put set give look want need "
    "think try also then there here what when where which who why how but and for with from into over about after "
    "before just still some any all each every more most one two three first next last new".split()
)


def _head_word(view) -> str:
    first = str(view.note.get("content") or "").lstrip("# ").split("\n", 1)[0].split()
    word = first[0].strip(":,.") if first else ""
    if word.lower() in _NOT_TOPICS:
        return ""
    return word if re.fullmatch(r"[A-Z][A-Za-z]{2,}", word) else ""


def names_by_note(views: list, known: list | None = None) -> dict[int, dict[str, str]]:
    """Each note's names, keyed by lower case, as first written: a name any
    note (of `known`, else of `views`) writes after a lower-case word counts
    in every note that has it."""
    seen: dict[str, str] = {}
    pool = known or views
    for view in pool:
        for name in _names(str(view.note.get("content") or "")):
            seen.setdefault(name.lower(), name)
    #: A heading's first word two or more notes start with ("League notes",
    #: "League stats") names their thread too.
    heads = Counter(_head_word(view) for view in pool)
    for word, n in heads.items():
        if word and n >= 2 and word.lower() not in _PLAIN:
            seen.setdefault(word.lower(), word)
    out: dict[int, dict[str, str]] = {}
    for view in views:
        body = str(view.note.get("content") or "")
        out[view.id] = {key: name for key, name in seen.items() if re.search(rf"\b{re.escape(name)}\b", body)}
    return out


#: At most this many threads, each of at least this many notes.
MAX_THEMES = 2
THEME_NOTES = 2


def themes(views: list, skip: set[str], stem: Callable[[str], str], known: list | None = None) -> list[tuple[str, list]]:
    """The threads through the notes, biggest first: a name two or more of
    them share, each note under the first thread that holds it. `skip` is
    the topic's own stems (a thread of "games" under "games" says nothing);
    `known` is every note found, which teaches a name ("our League team")
    the notes' headings only start with."""
    names = names_by_note(views, known)
    left = list(views)
    found: list[tuple[str, list]] = []
    while len(found) < MAX_THEMES:
        counts = Counter(key for v in left for key in names[v.id] if stem(key) not in skip)
        best = [key for key, n in counts.most_common() if n >= THEME_NOTES]
        if not best:
            break
        key = best[0]
        held = [v for v in left if key in names[v.id]]
        label = next(names[v.id][key] for v in held)
        found.append((label, held))
        left = [v for v in left if v not in held]
    return found


def shared_names(views: list, skip: set[str], known: list | None = None, least: int = 2) -> list[tuple[str, int]]:
    """Names in `least` or more of the notes that are no thread already: what
    links notes the threads did not group ("Jake is in two of them")."""
    names = names_by_note(views, known)
    counts = Counter(key for v in views for key in names[v.id])
    labels = {key: name for v in views for key, name in names[v.id].items()}
    return [(labels[key], n) for key, n in counts.most_common() if n >= least and key not in skip]


#: A line of a note is short enough to stand for it under this many words,
#: and two lines together under this many.
LINE_WORDS = 24
PAIR_WORDS = 30
_ENDS = re.compile(r"[.!?…:;\"”’)\]]\s*$")


def _prose_line(units: list, stems: set[str]) -> list:
    """The note's sentence holding the subject, else its first; a heading
    line with no full stop is said with the sentence after it, or skipped
    when the two run long."""
    prose = [s for s in units if s.kind in ("prose", "item", "task") and len(s.text.split()) <= LINE_WORDS]
    if not prose:
        return units[:1]
    pick = next((s for s in prose if stems & set(s.words)), prose[0])
    at = prose.index(pick)
    after = prose[at + 1] if at + 1 < len(prose) else None
    if after is not None and len(pick.text.split()) + len(after.text.split()) <= PAIR_WORDS:
        return [pick, after]
    if after is not None and not _ENDS.search(pick.text):
        return [after]
    return [pick]


def best_line(sentences: Iterable, stems: set[str], text_stems: set[str] | None = None) -> list:
    """The units that stand for a note in one bullet: a picture's reading
    (what it shows, then the line of its words that matches `text_stems`,
    else its first line), else `_prose_line`."""
    units = list(sentences)
    shows = [s for s in units if s.kind == "picture"]
    reads = [s for s in units if s.kind == "picture_text"]
    if shows or reads:
        want = stems if text_stems is None else text_stems
        match = [s for s in reads if want & set(s.words)]
        return [*shows[:1], *(match or reads)[:1]]
    return _list_line(units) or _prose_line(units, stems)


def _list_line(units: list) -> list:
    """A list note's entries, when it is mostly a short list."""
    items = [s for s in units if s.kind in ("item", "task")]
    if 2 <= len(items) <= LIST_ITEMS and len(items) * 2 > len(units) and all(_phrase(s.text) for s in items):
        return items
    return []


#: A list said as one sentence ("a list of four: A, B, C and D") holds at
#: most this many entries, each a phrase of at most this many words.
LIST_ITEMS = 6
LIST_ITEM_WORDS = 16


def _phrase(text: str) -> bool:
    return len(text.split()) <= LIST_ITEM_WORDS and not re.search(r"[.!?;]\s+\S", text)
