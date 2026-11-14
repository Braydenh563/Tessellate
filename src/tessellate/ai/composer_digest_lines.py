"""The digest's facts, lines and overview, moved whole out of composer_digest.py (audit K24): the notes' facts and subjects, the dated lines, the overview and the ranked sentence helpers. Imports only composer_digest_sentences; composer_digest.py keeps the answer kinds and the polish pass."""

from __future__ import annotations

import calendar
import functools
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from tessellate.ai import (
    composer,
    composer_aliases,
    composer_ask,
    composer_brief,
    composer_frame,
    composer_likeness,
    composer_overview,
    composer_read,
    composer_slots, composer_stale,
    composer_story,
    composer_threads,
    composer_verbuse,
    factgraph,
    realise,
    recognise as recogniser, recognise_questions,
    verdicts,
    when as when_words,
)
from tessellate.ai.composer_lists import clean
from typing import NamedTuple
from tessellate.ai.composer_digest_sentences import (
    _FUNCTION_WORDS, _a_name, _as_you, _starts_a_title,
    CONTEXT_TAGS, FACETS, Fact, LINES, PHRASES, VOICES, _ACTION, _ASKING, _ASKS_WORDS, _BASE,
    _CALENDAR_WORD, _CUES, _CURRENT, _Capitals, _DAYS_PLURAL, _DAY_NAMES, _FRAME_WORDS, _GAPS,
    _KNOWN, _LEAD_VERBS, _NAMES, _NOUN_AFTER, _Out, _PREFIX, _REGISTER, _RELATIVE, _SEED, _STILL_TO,
    _STRONG_CUES, _SUBJECT_STEMS, _TIMED, _TIME_LABEL, _TODAY, _TURN, _VERBS, _VIEWS, _VOICE, _WORK,
    _bare_gap, _clause_list, _day, _dictionary, _did, _fragment, _fresh, _gap, _lead_day,
    _note_called, _pin, _second_person, _span, _spans, _stems, _title_capitals, _title_only,
    _titled_names, _unlinked, _vary, _verb_led, _your_note,
)
__all__ = ["_CJK_ENDS", "_CJK_STOP", "_LATEST_ASK", "_NAMES_A_THING", "_WHEN_NOW", "_WHEN_LAST", "_AM_DOING", "_LAST_ONE"]  # read by the digest halves that import them

#: The note's own asides, dropped when its words are said back (the owner,
#: 2026-10-11: "You just bought a new gaming mouse ... haha" is "you bought a
#: gaming mouse"): laughter, emoji, and "just" or "literally" before a verb
#: in the past ("just bought"), never "just two left", which is "only".
_LAUGHED = re.compile(r"(?<![\s,])[\s,]*\b(?:(?:ha|he){2,}h?|lo+l+|lmf?a+o+|rofl|xd+)\b[.!]*", re.I)
_EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]+")
#: A typed face is an emoji too (INBOX 1483: "so it was chill :D,¹"), never
#: a time ("10:30") or a link ("https://"): it stands alone between spaces.
_FACE = re.compile(r"\s+(?:[:;=][-']?[)(DPpOo3/\\|\]\[]+|<3+|\^_?\^)(?=$|\s|[.,!?])")
_JUST = re.compile(
    r"\b(?:just|literally|finally just)\s+(?=(?:\w+ed|bought|got|went|made|found|sold|paid|spent|won|lost|had|took|saw|met|"
    r"left|came|ran|did|began|set|put|read|heard|told|gave|sent|built|broke|fell|felt|kept|wrote)\b)",
    re.I,
)


def _unfilled(text: str) -> str:
    text = _FACE.sub("", _EMOJI.sub("", _LAUGHED.sub("", text)))
    return re.sub(r"\s{2,}", " ", _JUST.sub("", text)).strip()


def _tidy(text: str, written: date | None = None) -> str:
    text = _unfilled(_unlinked(text))
    if written is not None:
        text = _pin(text, written)
    else:
        #: With no day to pin it to, "next week" is stale by now and goes;
        #: "the 14th of next month" is the date itself and stays.
        text = _RELATIVE.sub(lambda m: m.group(0) if re.search(r"\bof\s*$", text[:m.start()]) else "", text)
    #: A hashtag is filing, not something the person said: trailing ones go
    #: ("quicksort is n log n. #uni"), one inside a sentence keeps its word.
    text = re.sub(r"(?:\s*#[A-Za-z][\w-]*)+\s*$", "", text)
    text = re.sub(r"(?<![\w&/])#([A-Za-z][\w-]*)", r"\1", text)
    text = re.sub(r"\s+([,.;])", r"\1", text)
    return text.strip().rstrip(".!").strip()


def _context_note(view: composer.NoteView) -> bool:
    tags = {str(t).lower().strip("#") for t in (view.note.get("tags") or [])}
    return bool(tags & CONTEXT_TAGS)


def _context_facts(view: composer.NoteView) -> list[Fact]:
    """A joke or a quote is one piece (decision 67): its question and its
    punchline are never two facts. A list of them ("Jokes I like" with a joke a bullet) is one piece a
    bullet: run together, one joke's punchline ran into the next one's question (L-chat-19)."""
    if len(view.sentences) > 1 and all(s.kind == "item" for s in view.sentences):
        return [Fact(view, s, "Joke", s.text.strip().rstrip("."), "") for s in view.sentences]
    whole = " ".join(s.text.strip() for s in view.sentences)
    head = _PREFIX.match(whole)
    label = head.group(1).strip() if head else "Joke"
    body = head.group(2) if head else whole
    return [Fact(view, view.sentences[0], label, body.strip().rstrip("."), "")] if view.sentences else []


def _picture_shows(subject: str, caption: str, what: str) -> str:
    """"The picture in X shows a green fox"; a caption with its own verb is
    quoted whole, not spliced after "shows" (INBOX 1599)."""
    whole, said = composer_threads.caption_form(caption)
    return f"{subject} is described as “{said}”" if whole else f"{subject} shows {_fragment(what, set())}"


def _picture_fact(view: composer.NoteView, shown: list, read: list) -> Fact:
    """A picture is one fact, what it shows and the words in it, the words
    quoted as read (INBOX 787: never run into the caption)."""
    #: A note that is mostly its picture ("League stats" and a screenshot):
    #: the words in it are what the note says.
    mostly = sum(1 for s in view.sentences if s.kind not in ("picture", "picture_text")) <= 1
    what = composer_threads.caption_said(shown[0].text.strip()) if shown else ""
    words = realise.join_items([f"“{r.text.strip()}”" for r in read[:3]]) if (_ASKS_WORDS.get() or not shown or mostly) else ""
    #: Said as what it shows, past the captioner's frame, never as the
    #: person's words ("Your note says “A picture of ...”", "a picture of a
    #: photo depicts", INBOX 787, 1496, 1512): a note that is its picture by
    #: its name, a picture beside words as "its picture".
    name = _your_note(view)
    subject = "its picture" if not mostly else name if name.startswith("your picture") else f"the picture in {name}"
    body = _picture_shows(subject, shown[0].text.strip(), what) if what else ""
    if words:
        body = f"{body}, reading {words}" if body else f"{subject} reads {words}"
    return Fact(view, (shown or read)[0], "", body, "")


class _Split(NamedTuple):
    label: str
    body: str
    #: The label is the sentence's own (a heading or a time), not inferred.
    own: bool
    #: A "Heading: ..." was matched, even one too long to be a label.
    headed: bool
    #: The label is a heading, which a note's first sentence hands the note.
    titled: bool = False


#: "It's in four phases: the Opener, ..." is a sentence leading into its
#: list, not a heading: never "Your It's in four phases note" (INBOX 1420).
_CLAUSE_HEAD = re.compile(r"(?:it|this|that|there|they|we|i|he|she|you)(?:'s|'re|'m|’s| is| are| was| were| has| have| had)\b", re.I)


def _split_label(text: str) -> _Split:
    """A sentence's own heading ("Study plan: ...") and the rest. "Watched
    Dune Part Two: 7 out of 10" names what was done, not a heading: the
    sentence stays whole ("you watched Dune Part Two")."""
    head = _PREFIX.match(text)
    if head and (_WORK.match(head.group(1)) or _CLAUSE_HEAD.match(head.group(1))):
        head = None
    if head and len(head.group(1).split()) <= 5:
        return _Split(head.group(1).strip(), head.group(2), True, True, True)
    timed = _TIME_LABEL.match(text)
    if timed:
        return _Split(timed.group(1)[:1].upper() + timed.group(1)[1:], timed.group(2), True, bool(head))
    return _Split("", text, False, bool(head))


def _node_split(view: composer.NoteView, sentence: composer.Sentence) -> _Split | None:
    """A map's node or a board's card is its own text, whole: "IaaS: renting
    servers" is one node, not the heading "IaaS" over a sentence (the owner's
    "**Service models:**" over a mind map). None for anything else."""
    if view.kind in ("map", "board") and sentence.kind == "item":
        return _Split("", sentence.text.strip().rstrip(".!"), False, False)
    return None


_CONDITION = re.compile(r"(?:^|,\s*)(?:if|when|whenever|once|unless|in case)\b[^,]*$", re.I)


def _action_of(body: str) -> tuple[str, str]:
    """The to-do a sentence ends with, split from what it says: (action, body)."""
    acted = _ACTION.search(body)
    if acted and acted.start(1) > 0 and _CONDITION.search(body[: acted.start()].rstrip(" ,;")):
        #: "If she mentions a trip, ask what the best part was" is advice:
        #: split, it left "For example, if she mentions a trip." (INBOX 1420).
        return "", body
    if acted and acted.start(1) > 0:
        return acted.group(1).strip(), body[: acted.start()].rstrip(" ,;")
    if acted and acted.start(1) == 0 and re.search(r"\b(on|by|before) (mon|tues|wednes|thurs|fri|satur|sun)day\b", body, re.I):
        return body, body
    return "", body


def _pieces_of(body: str) -> list[tuple[str, str]]:
    still = _STILL_TO.search(body)
    if still and still.start() > 0 and re.search(r",\s*$", body[: still.start()]):
        #: "Hotel is booked, flights still to book": two facts, and the
        #: second is a to-do.
        return [(body[: still.start()].rstrip(" ,"), ""), (f"{still.group(2).lower()} the {still.group(1).lower()}", "Still to do")]
    return [(body, "")]


def _cue_for(piece: str, fixed: str, label: str, own: bool, note_label: str, parts: bool = True) -> str:
    """The label a fact goes under. A weak cue ("How it went") only tells the
    parts of one note apart: a note that is one event heads itself, and the
    label read as the outcome of the note before it (INBOX 1668)."""
    strong = next((name for name, cue in _CUES[:_STRONG_CUES] if cue.search(piece)), "")
    weak = next((name for name, cue in _CUES if cue.search(piece)), "") if parts else ""
    return fixed or (label if own else "") or strong or note_label or weak


def _said_piece(piece: str, cue: str, written: date | None, pinned, last: bool, asked: bool = False) -> str:  # noqa: ANN001
    #: A listed question is a line to ask someone ("I like your jacket,
    #: where is it from?"): its "I" and its "this week" are the asker's,
    #: never "you like your jacket" or "the week of 20 July" (INBOX 1420).
    said = _tidy(piece, None) if asked else _tidy(_second_person(piece, written), written)
    if cue == "Your schedule":
        said = re.sub(r"\b(?:are|is) (on|every)\b", r"\1", said)
    if cue == "What you want":
        said = re.sub(r"^you (?:want|need) (?:it|one|them) ", "", said)
    if said and pinned and last:
        said = PHRASES["pinned"].format(said=said.rstrip("."), day=verdicts.day_words(pinned))
    return said


def _only_the_subject(body: str, own: bool, subject: set[str] | None) -> bool:
    """A short sentence that is only the asked-about words restates the
    question, so it says nothing."""
    if not subject or own or len(body.split()) > 7:
        return False
    content = {composer._stem(w) for w in composer._words(body)} - _FRAME_WORDS()
    return bool(content) and all(any(composer._holds(st, {w}) for st in subject) for w in content)


def _labelled_list(split: _Split) -> bool:
    """"Q1: run a 10k, read 12 books" is a list under its label, and its last
    item is one of the list, not a to-do split off it (audit 1030 C)."""
    parts = [p for p in re.split(r",(?!\d)\s*", split.body) if p.strip()]
    return bool(split.label) and len(parts) >= 2 and all(len(p.split()) <= 5 for p in parts)


def _sentence_facts(view: composer.NoteView, s, split: _Split, note_label: str, subject: set[str] | None, pinned) -> list[Fact]:  # noqa: ANN001
    """The facts one sentence gives: its to-do split off, and a sentence of
    two halves ("booked, flights still to book") said as two."""
    if _only_the_subject(split.body, split.own, subject):
        return []
    action, body = ("", split.body) if _labelled_list(split) else _action_of(split.body)
    pieces = _pieces_of(body)
    out: list[Fact] = []
    for n, (piece, fixed) in enumerate(pieces):
        if not split.own and len(piece.split()) <= 6 and _RELATIVE.search(piece):
            #: "Uni starts back next week.": true on the day it was
            #: written, and misleading said now with no day.
            continue
        cue = _cue_for(piece, fixed, split.label, split.own, note_label, len(pieces) > 1 or len(view.sentences) > 1)
        asked = s.kind == "item" and str(s.text).rstrip().endswith("?")
        said = _said_piece(piece, cue, view.written, pinned, n == len(pieces) - 1, asked)
        if said:
            heading = bool(cue and ((split.own and split.headed and cue == split.label) or cue == note_label))
            out.append(Fact(view, s, cue, said, _tidy(action, view.written) if n == 0 else "", heading=heading))
    return out


def _picture_of(view: composer.NoteView) -> Fact | None:
    shown = [s for s in view.sentences if s.kind == "picture"]
    read = [s for s in view.sentences if s.kind == "picture_text"]
    return _picture_fact(view, shown, read) if shown or read else None


_DAY_HEADING = re.compile(
    r"^(?:[A-Za-z]+:\s*)?(?:(?:mon|tues|wednes|thurs|fri|satur|sun)day,?\s+)?(?:\d{1,2}\s+[A-Za-z]{3,9}|[A-Za-z]{3,9}\s+\d{1,2})(?:,?\s+\d{4})?\.?$",
    re.I,
)


def _left_out(view: composer.NoteView, s, known) -> bool:  # noqa: ANN001
    """A picture's sentences are said as one fact; one the person marked wrong is not said."""
    if s.kind in ("picture", "picture_text") or bool(known and known.is_wrong(view.id, s.text)):
        return True
    #: "Diary: Saturday 24 October." is the note's day, not something it says
    #: (audit 1031 C13); a note that is only that line still says it.
    return len(view.sentences) > 1 and bool(_DAY_HEADING.match(s.text.strip()))


_IT_IS = re.compile(r"^it(?:'s|’s| is)\s+", re.I)


def _its_title(view: composer.NoteView, text: str, i: int) -> str:
    """A titled note's first "It's in four phases" said with what "it" is:
    "your Complete Social Skills Guide is in four phases" (INBOX 1420)."""
    if i or not view.titled or not view.title or not _IT_IS.match(text):
        return text
    name = re.sub(r"^(?:the|a|an|my|your)\s+", "", view.title, flags=re.I)
    return f"your {name} is " + text[_IT_IS.match(text).end():]


def _facts(view: composer.NoteView, names: set[str], subject: set[str] | None = None) -> list[Fact]:
    """A note as labelled facts. A note that names its own heading ("Study
    plan: ...") gives its facts that label, unless a fact says plainly what
    it is (a booking, a choice); otherwise each fact is labelled by what it
    says (a day of the week, a price, a verdict). A sentence that only
    names the topic ("Looking at a new gaming mouse") is the note's frame,
    not a fact, and the answer's opening already says it."""
    if _context_note(view) or _joke_shaped(view):
        return _context_facts(view)
    picture = _picture_of(view)
    out: list[Fact] = []
    note_label = ""
    #: Verdicts are on notes: a document's id is another table's.
    known = _KNOWN.get() if composer_read.source_kind(view.note) == "note" else None
    for i, s in enumerate(view.sentences):
        if _left_out(view, s, known):
            continue
        pinned = known.pinned_on(view.id, s.text) if known else None
        split = _node_split(view, s) or _split_label(_its_title(view, s.text.strip().rstrip(".!"), i))
        if i == 0 and split.titled:
            note_label = split.label
        out += _sentence_facts(view, s, split, note_label, subject, pinned)
    return _with_picture(out, picture)


def _with_picture(out: list[Fact], picture: Fact | None) -> list[Fact]:
    """The picture said after the note's first sentence ("You bought a new
    gaming mouse ... Its picture shows ..."), or first when the note is its
    picture (INBOX 1512)."""
    if picture is None:
        return out
    if not out:
        return [picture]
    first = out[0].sentence.key
    at = next((n for n, f in enumerate(out) if f.sentence.key != first), len(out))
    return [*out[:at], picture, *out[at:]]


def _subject_facts(members: list[composer.NoteView], names: set[str], subject: set[str], kind: str = "overview") -> list[Fact]:
    """The members' facts. A note the subject is only mentioned in (not its
    title, its category or its tags) gives the sentences that mention it, not
    its opening ones: "what do I know about sourdough" does not end on a
    sister's birthday (audit 1031 C22). Only an overview of several notes: a
    question for one fact ("where am I flying") reads the whole note."""
    out: list[Fact] = []
    narrow = kind == "overview" and len(members) > 1
    for v in members:
        held = _facts(v, names, subject)
        about = v.title_words | v.filed_words | {composer._stem(str(t).lower()) for t in v.note.get("tags") or []}
        if narrow and subject and held and not any(composer._holds(st, about) for st in subject):
            said = [f for f in held if any(composer._holds(st, set(f.sentence.words)) for st in subject)]
            held = said or held
        out += held
    return out


#: "when did I start learning Spanish": the start asks for a day, it is not a
#: word the note must hold (a streak note says "42 days in a row").
_BEGINNING = _stems("start begin first")


def _subject(question: str) -> list[str]:
    stems = [st for st in (composer._stem(t) for t in composer.subject_terms(clean(question))) if st not in _ASKING()]
    return [st for st in stems if st not in _BEGINNING()] if _WHEN_DID.match(clean(question)) else stems


def _pool(v: composer.NoteView) -> set[str]:
    """Every word a note holds: its text, its title and where it is filed."""
    return v.words | v.title_words | v.filed_words


def _in_named(named: list[composer.NoteView], stems: list[str]) -> list[composer.NoteView]:
    """"python in Pets": the category's notes that hold the subject, when
    the subject is more than the category's own name (B9's chip)."""
    rest = [st for st in stems if not composer._holds(st, set(composer._words(str(named[0].note.get("category") or ""))))]
    held = [v for v in named if rest and any(composer._holds(st, _pool(v)) for st in rest)]
    return held or named


def _named_in(q: str, views: list[composer.NoteView]) -> list[composer.NoteView]:
    """The notes whose category the (lower-cased) question names."""
    return [v for v in views if str(v.note.get("category") or "").strip() and str(v.note.get("category")).lower() in q and not _used_as_verb(q, str(v.note.get("category")).lower())]


#: "where does Tom work", "do I run": the category's word after an auxiliary,
#: at most two words on, is the verb of the question, not the category (audit 1031 C1).
_AUX_BEFORE = r"(?:does|do|did|doesn't|didn't|don't|can|could|will|would|should|to|might|must)\s+(?:\w+\s+){0,2}"


def _used_as_verb(q: str, category: str) -> bool:
    return " " not in category and bool(re.search(rf"\b{_AUX_BEFORE}{re.escape(category)}(?:\s+\w+){{0,2}}\s*[?.!]*$", q.strip()))


def _unanswerable(stems: list[str], views: list[composer.NoteView]) -> bool:
    """"the weather on Mars": a subject word no note holds is a question
    the notes cannot answer, and the composer says which word is missing."""
    everywhere = set().union(*(_pool(v) for v in views))
    return any(st not in _VERBS() and not composer._holds(st, everywhere) for st in stems)


def _said_as_typed(view: composer.NoteView, said: re.Pattern, stems: set[str]) -> bool:
    """Whether a note says the plural noun as typed. A title that names the
    activity ("Shopping") is "shops" as typed; "Booked flights" is not "books" (R3-9)."""
    note = view.note
    text = " ".join(str(note.get(k) or "") for k in ("content", "title", "category")) + " " + " ".join(map(str, note.get("tags") or []))
    return bool(said.search(text)) or any(w.lower().endswith("ing") and composer._stem(w.lower()) in stems for w in re.findall(r"[A-Za-z]+", view.title))  # noqa: SLF001


def _typed_first(members: list[composer.NoteView], question: str) -> list[composer.NoteView]:
    """"books" is the notes that say "book" or "books", before the ones that
    only say "booked" (the stemmer folds all three; audit 1031 C8). Only a
    plural noun asks this, and only when some member says it as typed."""
    plural = [t for t in composer.subject_terms(clean(question)) if len(t) > 3 and t.endswith("s") and not t.endswith(("ss", "us", "is"))]
    if not plural or len(members) < 2:
        return members
    said = re.compile(r"\b(?:" + "|".join(re.escape(w) for t in plural for w in (t, t[:-1])) + r")\b", re.I)
    stems = {composer._stem(t) for t in plural}  # noqa: SLF001
    typed = [v for v in members if _said_as_typed(v, said, stems)]
    return typed or members


def _acting(members: list[composer.NoteView], question: str) -> list[composer.NoteView]:
    """"When did I bake banana bread" is the note with a sentence that says the
    whole doing, not the recipe that shares its words across sentences (audit
    1031 C16); the members stay when no sentence says it all."""
    if len(members) < 2 or not _WHEN_DID.match(clean(question)):
        return members
    stems = [st for st in _subject(question) if st not in _VERBS()] + [st for st in _subject(question) if st in _VERBS()]
    if len(stems) < 2:
        return members
    said = [v for v in members if any(all(composer._holds(st, set(s.words)) for st in stems) for s in v.sentences)]
    return said or members


def _members(question: str, views: list[composer.NoteView]) -> list[composer.NoteView]:
    """The notes the question is about: a category it names, else the notes
    that hold most of its words (in the text, the title or the tags)."""
    q = clean(question).lower()
    stems = _subject(question)
    named = _named_in(q, views)
    if named:
        return _in_named(named, stems)
    if not stems:
        return []
    #: A doing word ("buy", "get") says what is wanted, not which note: "what
    #: should I buy for my sister" is about the sister, not the note that has
    #: "buy a capo" in it. A note must hold a word that names something (when
    #: the question has one); the doing words then count with the rest.
    scored = _scored_members(stems, views)
    aside = composer_likeness.set_aside([v for _, v in scored], question)
    scored = [(h, v) for h, v in scored if v.id not in aside] or scored
    scored = composer_verbuse.drop(list(composer.subject_terms(clean(question))), scored, lambda v: str(v.note.get("content") or ""))
    if not scored or _unanswerable(stems, views):
        return []
    best = max(h for h, _ in scored)
    need = best if best >= 2 else 1
    return _acting(_typed_first([v for h, v in scored if h >= need], question), question)


@functools.lru_cache(maxsize=1)
def _NEIGHBOURS() -> frozenset[str]:  # noqa: N802
    """The stems whose synonym group is a set of different things of one kind, not one thing said twice."""
    return frozenset(composer._stem(w) for w in ("cat", "dog", "bird", "fish", "kitten", "puppy", "pet", "animal", "boiler", "heater", "radiator"))  # noqa: SLF001


def _spelled(named: list[str], views: list[composer.NoteView]) -> list[composer.NoteView]:
    """The notes that write a naming word itself, for the groups of neighbours only: "shop" and "buy" are one thing."""
    return [v for v in views if any(st in _pool(v) for st in named)] if any(st in _NEIGHBOURS() for st in named) else []


def _scored_members(stems: list[str], views: list[composer.NoteView]) -> list[tuple[int, composer.NoteView]]:
    """Each note holding a naming word of the question, with how many of its words it holds."""
    named = [st for st in stems if st not in _VERBS()] or stems
    #: A synonym is a neighbour, not the thing: with notes that write the word itself, a note that only
    #: shares a synonym group with it ("cat" and "fish", "boiler" and "radiator") is not about it (W7 B6).
    spelled = _spelled(named, views)
    return [
        (hits, v) for v in spelled or views
        if any(composer._holds(st, _pool(v)) for st in named) and (hits := sum(1 for st in stems if composer._holds(st, _pool(v))))
    ]


def _shared_tags(members: list[composer.NoteView]) -> list[str]:
    """The tags most of the notes carry, commonest first (a joke's or quote's own tag is not a topic)."""
    tags: dict[str, int] = {}
    for v in members:
        for t in {str(t).lower().strip("#") for t in (v.note.get("tags") or [])}:
            tags[t] = tags.get(t, 0) + 1
    return [t for t, n in sorted(tags.items(), key=lambda kv: -kv[1]) if n >= max(2, len(members) * 3 // 4) and t not in CONTEXT_TAGS]


def _named_category(q: str, members: list[composer.NoteView]) -> str:
    """The first member's category that the question names, or empty. "&" and
    "and" are one word: "courses and study" names "Courses & Study" (INBOX 1665)."""
    def plain(text: str) -> str:
        return " ".join(re.sub(r"\s*&\s*", " and ", text.lower()).split())

    asked = plain(q)
    return next((str(v.note.get("category")) for v in members if v.note.get("category") and plain(str(v.note["category"])) in asked), "")


#: "the plan for December", "my gifts for Mum": a thing for something, both
#: halves the topic (composer-subject-1029.md item 2: "about December" lost
#: the plan). The determiner is needed: "what did I buy for Mum" is about Mum.
_OWNED_FOR = re.compile(r"\b(the|my|our)\s+([a-z][\w'-]*)\s+for\s+(.+?)\s*\??$", re.I)


def _topic_owned(q: str) -> str:
    found = _OWNED_FOR.search(q)
    if not found or found[2].lower() in composer_ask._ASKING_WORDS:  # noqa: SLF001
        return ""
    rest = recogniser.without_windows(found[3]).strip(" ,")
    if not rest:
        return ""
    owner = "your" if found[1].lower() == "my" else found[1].lower()
    rest = re.sub(r"^(?:my|the)\s+", "", rest)
    return f"{owner} {found[2]} for {rest}"


def _topic_typed(typed: "re.Match[str] | None") -> str:
    """The subject after "about/on/for", as typed, without a time window."""
    if not typed:
        return ""
    #: "for next month" is a time, not a topic (1324).
    #: "my" goes; "the" stays, said as typed: "three notes about the Lisbon trip", not "about Lisbon trip".
    said = re.sub(r"^my\s+", "", recogniser.without_windows(typed.group(1))).strip(" ,")
    #: Fillers and asides off its end, and the person's "my" said back as "your" ("eating your homework", INBOX 1705).
    return re.sub(r"\bmy\b", "your", composer_ask._TRAILERS.sub("", said)).strip(" ,")  # noqa: SLF001


def _topic_sides(q: str) -> str:
    """"compare the Porto and Lisbon notes": about Porto and Lisbon, as typed,
    not "porto lisbon" (1324)."""
    sides = composer.compare_sides(q)
    return " and ".join(re.sub(r"^(?:my|the|our)\s+", "", side, flags=re.I) for side in sides) if sides else ""


def _always_capital(word: str, text: str) -> bool:
    """Every time the notes write `word` it has a capital, and more than once."""
    found = re.findall(rf"\b{re.escape(word)}\b", text, re.I)
    return len(found) > 1 and all(w[:1].isupper() for w in found)


def _as_written(topic: str, members: list[composer.NoteView]) -> str:
    """The topic with each name in the capitals the notes write it in:
    "lisbon" typed small is "Lisbon" (C1: "two notes about lisbon")."""
    #: A name: a word not in the dictionary ("lisbon") or one a title writes
    #: with a capital ("atlas"); "social" in "Complete Social Skills" is neither.
    text = " ".join(f"{v.title} " + " ".join(s.text for s in v.sentences) for v in members)
    #: Or a dictionary word the notes write as a place ("moving to Lisbon"):
    #: "what about lisbon" is answered as a topic, so it no longer takes the
    #: who shape's capital (audit 1029 C15 residue).
    placed = {w.lower() for w in re.findall(r"\b(?:to|in|from|at|near|visit|visiting|visited)\s+([A-Z][a-z'-]+)", text)}
    #: A dictionary word capitalised inside a sentence ("Learn Portuguese
    #: before Lisbon") is a name too when the notes never write it small;
    #: `cased` checks that last part (2026-10-30: "three notes about lisbon").
    names = {w for w in _NAMES.get() if w not in _dictionary() or w in placed or _always_capital(w, text)} | _title_capitals() | _titled_names()
    whole = re.search(rf"\b{re.escape(topic)}\b", text, re.I) if " " in topic.strip() else None
    if whole and topic.islower() and re.search(r"\s[A-Z]", whole.group(0)) and any(w in names for w in topic.split()):
        #: "project atlas" is "Project Atlas", as the notes write it.
        return whole.group(0)

    def cased(m: re.Match) -> str:
        word = m.group(0)
        if not word.islower() or word not in names or re.search(rf"\b{re.escape(word)}\b", text):
            #: A word the notes also write small ("social") is not a name.
            return word
        found = re.search(rf"\b{re.escape(word)}\b", text, re.I)
        return found.group(0) if found and found.group(0)[:1].isupper() else word

    return re.sub(r"[A-Za-z][\w'-]*", cased, topic)


def _topic(question: str, members: list[composer.NoteView]) -> str:
    """What the notes are about, in the person's word (a name in the notes'
    capitals): the tag they share, or the subject as typed."""
    return _as_written(_topic_said(question, members), members)


def _topic_said(question: str, members: list[composer.NoteView]) -> str:
    q = clean(question)
    shared = _shared_tags(members)
    typed = re.search(r"\b(?:about|on|for|regarding|in)\s+(.+?)\s*[?.!]*$", q, re.I)
    category = _named_category(q, members)
    if category and shared:
        #: "social connections", tagged social: the category as typed, not
        #: its first word (INBOX 1301 D5); "Courses & Study" tagged uni: uni.
        return category.lower() if shared[0] in category.lower().split() else shared[0]
    said = (not typed and _topic_sides(q)) or _topic_owned(q) or _topic_typed(typed)
    if said:
        return said
    terms = composer.subject_terms(q)
    if shared and (not terms or shared[0] in " ".join(terms)):
        return shared[0]
    return " ".join(terms) or (shared[0] if shared else "this")


#: How many lines the More fold holds past the short answer; the rest stay
#: "N more on the right".
MORE_LINES = 8


def _group_by_label(facts: list[Fact], skip: set[tuple] | None, by_day: date | None) -> tuple[dict[str, list[Fact]], set[str]]:
    """The facts under their labels in the order met, and the labels that are days."""
    groups: dict[str, list[Fact]] = {}
    spans: dict[str, set[int]] = {}
    days: set[str] = set()
    for f in facts:
        spans.setdefault(f.label, set()).add(f.view.id)
    for f in facts:
        if skip and f.sentence.key in skip:
            continue
        label = f.label
        if by_day and (not label or len(spans[label]) > 1) and f.view.written:
            #: Facts with no label of their own, or one label over several
            #: notes ("Gym: ..." twice), read best by their day.
            label = _day(f.view.written, by_day)
            days.add(label)
        groups.setdefault(label or PHRASES["also"], []).append(f)
    return groups, days


def _told_by_day(bodies: list[str], tail: str) -> str | None:
    """A day's note in its own shorthand ("squats 80 kg for 5") said as what
    the person did that day (the owner, 2026-10-11: every paragraph gets the
    first one's treatment), or None when a body cannot be said so."""
    told = [_day_clause(b) for b in bodies]
    if not all(told):
        return None
    #: "..., going on Mondays", not "..., and you were going on Mondays".
    return told[0] + "".join(
        ", " + c.removeprefix("you were ") if c.startswith("you were going ") else ", and " + c for c in told[1:]
    ) + tail


#: A note's shorthand opening on a past verb ("trimmed your first bowl"), which
#: a date in front needs a subject for.
_VERB_FIRST = re.compile(r"^(?!(?:\w*eed|\w{0,3}ed)\b)[a-z]{3,}ed\b")


def _own_subject(body: str) -> str:
    return "you " + body if _VERB_FIRST.match(body) else body


def _recent(written: date | None, today: date | None) -> str:
    """A day of the last fortnight as a person says it (INBOX 1310, the
    owner: "saying dates and time words in sentences"): "yesterday, ",
    "on Thursday, ", "last Friday, ", "a week ago, on 12 October, ",
    "earlier this month, on 3 October, "; "" for an older day."""
    if not written or not today or not _TIMED.get():
        return ""
    ago = (today - written).days
    weekday = _DAY_NAMES[written.weekday()]
    if ago < 0 or ago > 31:
        return ""
    if ago <= 1:
        return ("today, ", "yesterday, ")[ago]
    if ago <= 6:
        return f"on {weekday}, " if written.weekday() < today.weekday() else f"last {weekday}, "
    if ago <= 13 and written.weekday() < today.weekday():
        return f"last {weekday}, "
    if ago == 7:
        return f"a week ago, on {_day(written, today)}, "
    return f"earlier this month, on {_day(written, today)}, " if written.month == today.month else ""


#: A day's shorthand that opens on a thing ("golf practice after work"), not
#: on the person, a place ("at Mia's barbecue") or a time.
#: A day said first by `_when_gone` ("back in July, ...", "three weeks
#: ago, on 8 October, ...", "yesterday, ...") leads a clause, never a fragment.
_SHORTHAND = re.compile(
    r"^(?!(?:you|your|at|in|on|with|after|before|from|for|during|to|by|this|last|next|the day|back in|yesterday,|"
    r"[\w-]+ (?:days?|weeks?|months?|years?) ago)\b)[a-z]", re.I)


_HERE_ARE = re.compile(r"^here(?:'s| is| are)\s+((?:some|a few|a list of|a|an)\s+)?", re.I)
_WH_SUBJECT = re.compile(r"(?:what|how|why|which|who|where)\b", re.I)


#: A date a sentence says itself ("ran 6 km on 25 October"): the day the note
#: was written must not lead it.
_OWN_DATE = re.compile(
    rf"\b\d{{1,2}}(?:st|nd|rd|th)? (?i:{'|'.join(composer_ask._MONTHS)})\b"  # noqa: SLF001
    #: Month first needs the capital: "we may 5 of us go" is not a date.
    rf"|\b(?:{'|'.join(m.capitalize() for m in composer_ask._MONTHS)}) \d{{1,2}}\b"  # noqa: SLF001
)


def _dated_lead(label: str, i: int, by_day: date | None, written: date | None, before: date | None) -> str:
    """The line's lead: the time since the line before, a recent day, or its date."""
    if not _TIMED.get():
        return ""
    gap = (written - before).days if i and before and written else 0
    #: The time since the line before reads first; a run's first line, or
    #: one the same days as the last, says a recent day as a person would.
    recent = _recent(written, by_day) if not gap or (by_day and written and (by_day - written).days <= 7) else ""
    if recent or gap >= 2:
        return recent or _gap_on(gap, label)
    return _lead_day(written, by_day, capital=False) if written and by_day else f"on {label}, "


def _cleaned_body(line_body: str, label: str) -> str:
    """The note's words with its own date, a pasted "however" and a "here are" opener taken out."""
    #: A note that opens on its own day ("on 21 September, you have work")
    #: already has it in the lead: kept, it read "on 21 September, on 21
    #: September, you have work", and the present tense went unshifted.
    #: Only when the lead says it (`_dated_lead`, a question about time).
    if _TIMED.get():
        line_body = re.sub(rf"^on {re.escape(label)}(?: \([^)]*\))?,?\s*", "", line_body, flags=re.I) or line_body
    #: A pasted summary's "however" answers text that is not there (1420).
    line_body = re.sub(r",\s*however,", "", line_body)
    #: "Here are some refined ... starters" is what was saved, not said.
    return _HERE_ARE.sub(lambda m: "you saved " + (m.group(1) or ""), line_body, count=1)


#: A note's own plural "we" and "our": said by the writer, so kept as reported speech.
_WE = re.compile(r"(?:we|we're|we've|we'd|we'll|our|us)\b", re.I)
#: Verbs a note opens a line with when it tells what to do ("Bake at 230C",
#: "feed the starter"): the person's note-to-self, never what they did.
_IMPERATIVES = frozenset("""
bake keep mix stir add cook heat boil simmer chop slice cut preheat rest let leave serve fold knead whisk pour season taste
rinse drain soak toast roast fry grill steam blend squat press lift stretch
""".split()) | _LEAD_VERBS


#: A weekday the app pinned to its date ("Saturday 3 October"): inside a
#: quotation it is the note's own words, so the date goes outside it.
_PINNED_DAY = re.compile(rf"\b((?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day) (\d{{1,2}} (?:{'|'.join(composer_ask._MONTHS)})(?: \d{{4}})?)\b")  # noqa: SLF001


def _unpinned(said: str) -> tuple[str, str]:
    """`said` with each pinned weekday back as the note wrote it, and the
    asides that give the dates: ("Saturday long run", ", the Saturday being 3 October")."""
    pins = _PINNED_DAY.findall(said)
    if not pins:
        return said, ""
    plain = _PINNED_DAY.sub(r"\1", said)
    return plain, ", " + " and ".join(f"the {day} being {date}" for day, date in dict.fromkeys(pins))


def _wrote(body: str, i: int) -> str:
    """`body`, words of the note with no subject of their own, after a verb
    of writing that does not change who they are about (audit 1030 Z1, Z2):
    "we talked about" is the writer's "we", so it is reported; "slept badly"
    is what the writer did; "Bake at 230C" is a note-to-self, quoted; a noun
    phrase is simply what was noted. Never a raw fragment after "you
    jotted down"."""
    first = (re.match(r"[A-Za-z][\w'-]*", body) or [""])[0]
    if _WE.match(body):
        return _REPORTS[i % len(_REPORTS)] + body[:1].lower() + body[1:]
    if first and (_did(first) or _past_verb(first)):
        return _as_you(body)
    if _CALENDAR_WORD.match(first.capitalize()) or (first.lower() in _IMPERATIVES and not (len(body.split()) >= 2 and body.split()[1].lower() in _NOUN_AFTER)):
        #: Quoted as written, capital and all: it is the note's sentence.
        said = _DAY_NAME.sub(lambda m: m.group(0).capitalize(), body[:1].upper() + body[1:].rstrip("."))
        said, pinned = _unpinned(said)
        return f"{_QUOTED_AS[i % len(_QUOTED_AS)]} “{composer_story.clipped(said, 30)}”{pinned}"
    #: A noun phrase is what the note says, not a speech act ("You jotted
    #: down Dentist appointment on 4 November": audit 1031 C32). The quote
    #: is the note, so no unnamed "Your note says" (INBOX 1512).
    return f"{_QUOTED_AS[i % len(_QUOTED_AS)]} “{composer_story.clipped(body[:1].upper() + body[1:].rstrip('.'), 30)}”"


#: A note's own words quoted whole, with the one plain verb (fable-composer-1110 F7: a rotation of verbs read as a table).
_QUOTED_AS = ("you wrote",)


def _past_verb(word: str) -> bool:
    """An irregular past ("slept", "ate", "met") a diary line opens with."""

    factgraph._tables()  # noqa: SLF001
    return word.lower() in factgraph._PAST  # noqa: SLF001


_SENTENCE_BREAK = re.compile(r"[.!?] [A-Z]")
#: A line with "my" or "I" in it is reported ("Sara is your sister"), so only the rest is quoted whole.
_FIRST_PERSON = re.compile(r"\b(?:my|me|mine|your|yours|i|i'm|i've|we|our)\b", re.I)
_LIST_HEADING = re.compile(r"your .+? note lists \w+ (?:items|questions to ask)\b", re.I)


def _said_as_written(line_body: str, i: int, written: date | None = None) -> str:
    """The body as reported speech: shorthand noted, a statement about something else written, else retold."""
    #: "What your notes leave out is how ...": a clause of its own, its verb late.
    if _LIST_HEADING.match(line_body) or composer_threads.said_whole(line_body):
        #: A list's heading is not speech ("You mentioned that questions to ask: ...", C32).
        return line_body
    asked_clause = bool(_WH_SUBJECT.match(line_body) and _FINITE.search(line_body))
    if _OBLIGED.match(line_body):
        #: "you wrote down need to cut eating out" (audit 1029 C13): a need
        #: is said as one, not as an object of "wrote down".
        return f"you {line_body[0].lower() + line_body[1:]}"
    if _SHORTHAND.match(line_body) and not _FINITE.search(line_body.split(",")[0]) and not asked_clause:
        #: "golf practice after work, hit a bucket ...": shorthand with no
        #: verb is what the person wrote down, never a dated fragment.
        return _wrote(line_body, i)
    if _SHORTHAND.match(line_body) and not _CLAUSE_HEAD.match(line_body):
        #: "by 20 July, Cloud computing is the delivery of ...": a statement
        #: about something else is what the person wrote (INBOX 1420). Two sentences are not one
        #: "that" clause ("you mentioned that Boiler service due in December. Engineer is ..."): quoted (R3-11).
        if _SENTENCE_BREAK.search(line_body) and not _FIRST_PERSON.search(line_body):
            return _wrote(line_body, i)
        return _REPORTS[i % len(_REPORTS)] + _fragment(line_body, _NAMES.get())
    return _reported(line_body, i, written)


def _dated_line(line_body: str, label: str, i: int, by_day: date | None, written: date | None, before: date | None) -> tuple[str, str]:
    """A day's line is said as that day, not under it (the owner,
    2026-10-11: no label lines), the time since the last one first."""
    lead = _dated_lead(label, i, by_day, written, before)
    lead, reported = composer_stale.dated(lead, _cleaned_body(line_body, label), written, by_day, lambda b: _said_as_written(b, i, written), _backshift)
    if _OWN_DATE.search(reported) and lead.lower().startswith(("today, ", "yesterday, ")):
        #: "Today, you ran 6 km on 25 October" reads as a run today (round 1 D9).
        lead = ""
    line_body = lead + reported
    line_body = line_body[:1].upper() + line_body[1:]
    return line_body, line_body + _relate(line_body, by_day)


def _heading_line(label: str, held: list[Fact], bodies: list[str], i: int, by_day: date | None, tail: str, before: date | None, same: bool = False) -> tuple[str, str]:
    line_body = _prose(label, held, bodies, i, by_day, same) + tail
    written = held[0].view.written
    #: A note told by its day after an earlier one says the time
    #: between (gold Q2: "a week later, you tried the Viper").
    on_day = _lead_day(written, by_day or written) if written and _TIMED.get() else ""
    if on_day and before and (written - before).days >= 2 and line_body.startswith(on_day):
        lead = _gap_on((written - before).days, _day(written, by_day or written))
        line_body = lead[0].upper() + lead[1:] + _reported(line_body[len(on_day):], i, written)
    return line_body, line_body + _relate(line_body, by_day)


def _said_body(f: Fact, label: str) -> str:
    """A fact's words as a line says them; a note that is only its title
    is named, never said as if spoken ("you noted atlas retro meeting", C2)."""
    if _title_only(f.view) and f.body.strip().rstrip(".") == f.view.title.strip():
        return f"you started {_note_called(f.view.title)}"
    #: Under that day's own label the day is said once, by the label; with
    #: no label said (a question not about time) the day stays (INBOX 1461:
    #: "had design class today" lost its day).
    body = re.sub(rf"(?:^|\s)on {re.escape(label)}(?: \([^)]*\))?,?", "", f.body).strip() if _TIMED.get() else f.body
    return _fragment(_named_pronoun(body, f.view), _NAMES.get())


_PRONOUN_START = re.compile(r"(she|he|her|his)\b(?P<rest>.*)", re.I | re.S)
_PERSON_TITLE = re.compile(r"[A-Z][a-z]+(?: [A-Z][a-z]+)?")


def _kind_of_note(title: str, view) -> bool:  # noqa: ANN001
    """A note named for what it holds ("Jokes", "Recipes"), not for a person: its "he" is a character in a joke,
    never the title (W7b B34: "Jokes was outstanding in his field")."""
    low = title.lower()
    known = _dictionary()
    return _context_note(view) or _joke_shaped(view) or bool(known and low.endswith("s") and low in known and not _a_name(low, known))


def _joke_shaped(view) -> bool:  # noqa: ANN001
    """A note that opens on a question and answers it in its next sentence ("Why did the scarecrow win an award?
    He was outstanding in his field.") is one piece, the way a tagged joke is (decision 67), tagged or not."""
    sentences = view.sentences
    return len(sentences) == 2 and sentences[0].text.strip().endswith("?") and not sentences[1].text.strip().endswith("?")


def _named_pronoun(body: str, view) -> str:  # noqa: ANN001
    """"She likes gardening" lifted out of the note titled "Mum" says nothing on its own: the pronoun is the
    note's name ("Mum likes gardening", "Mum's birthday is 4 July"; R3-25). Only a one- or two-word name."""
    title = (view.title or "").strip() if getattr(view, "titled", False) else ""
    found = _PRONOUN_START.match(body or "")
    if not found or not _PERSON_TITLE.fullmatch(title) or _kind_of_note(title, view):
        return body
    return title + ("'s" if found.group(1).lower() in ("her", "his") else "") + found.group("rest")


def _bodies_of(held: list[Fact], label: str) -> tuple[list[str], str]:
    """A line's distinct sentences, and the pinned note ending it, if any."""
    bodies = list(dict.fromkeys(_said_body(f, label) for f in held))
    #: A line made of pinned sentences says so once, at its end (B32).
    pins = [m.group(0) for b in bodies for m in [_PINNED.search(b)] if m]
    return [_PINNED.sub("", b) for b in bodies], (pins[-1] if pins else "")


def _all_headings(held: list[Fact], label: str) -> bool:
    return all(f.heading and f.label == label for f in held)


def _days_apart(before: date | None, written: date | None) -> int:
    return (written - before).days if before and written else 0


def _line_of(label: str, held: list[Fact], i: int, weave: bool, by_day: date | None, days: set[str], before: date | None, same: bool = False) -> tuple[str, str, bool]:
    """One line's words: (said, the body its row cites, said as prose)."""
    bodies, tail = _bodies_of(held, label)
    line_body = _join(bodies, weave) + tail
    said = line_body + (_relate(line_body, by_day) if weave else "")
    written = held[0].view.written
    #: How this line stands to the one before (INBOX 870): the time
    #: between them, said as a clause, when they are days apart.
    #: Only before a clause of the person's own ("you tried ..."): "a
    #: week later, tram 28, pasteis de Belem" joins nothing.
    heading = weave and _all_headings(held, label)
    mine = bool(re.match(r"you\b|you're\b|your\b", line_body))
    on_day = weave and label in days
    told = _told_by_day(bodies, tail) if on_day and not mine else None
    if told:
        line_body, mine = told, True
    if on_day:
        #: Not only a clause of the person's own: "at Mia's barbecue ..." is
        #: dated too, never a "**9 August:**" label line (2026-10-11).
        heading = True
        line_body = _own_subject(line_body)
        line_body, said = _dated_line(line_body, label, i, by_day, written, before)
    elif heading:
        line_body, said = _heading_line(label, held, bodies, i, by_day, tail, before, same)
    elif weave and mine and i and _days_apart(before, written) >= 2 and _TIMED.get():
        #: "A week later" names its day too (the owner, 2026-10-11).
        said = _gap_on(_days_apart(before, written), _day(written, by_day or written)) + _reported(line_body, i, written)
    return said, line_body, bool(heading)


def _line_row(line_body: str, held: list[Fact]) -> dict:
    row = _row(line_body, held[0])
    #: Every sentence the line was made from (B31, B32): a verdict on
    #: the line is a verdict on each of them.
    parts = list({(f.view.id, f.sentence.start): f for f in held}.values())
    if len(parts) > 1:
        row["parts"] = [{"note_id": f.view.note.get("source_id", f.view.id), "source": f.sentence.text, "start": f.sentence.start, "end": f.sentence.end} for f in parts]
    return row


ALSO_ITEMS = 3


def _also_held(held: list[Fact]) -> list[Fact]:
    """What "Also" carries: the few facts that speak to the question, in the
    note's order, not the rest of the note (audit 1030 Z15)."""
    if len(held) <= ALSO_ITEMS:
        return held
    stems = _SUBJECT_STEMS.get()
    ranked = sorted(range(len(held)), key=lambda i: (-sum(w in stems for w in composer._words(held[i].body)), i))
    return [held[i] for i in sorted(ranked[:ALSO_ITEMS])]


def _one_note_lines(groups: dict[str, list[Fact]]) -> list[tuple[str, list[Fact]]]:
    """The groups as lines, the unlabelled ones a line a note: a sentence
    never holds more than one note's words (audit 1031 C5: the words of three
    notes were glued into one sentence with commas)."""
    items: list[tuple[str, list[Fact]]] = []
    for label, held in groups.items():
        if len({f.view.id for f in held}) > 1:
            by_note: dict[int, list[Fact]] = {}
            for f in held:
                by_note.setdefault(f.view.id, []).append(f)
            items += [(label, run) for h in by_note.values() for run in _contiguous(h)]
        else:
            items += [(label, run) for run in _contiguous(held)]
    return items


def _contiguous(held: list[Fact]) -> list[list[Fact]]:
    """`held` cut where the note has a sentence between two of them: a quote
    is the note's words verbatim and unbroken, never two sentences with a
    third left out between them (bt-compcomp-1109 item 4)."""
    runs: list[list[Fact]] = [[held[0]]] if held else []
    for f in held[1:]:
        last = runs[-1][-1]
        gap = str(f.view.note.get("content") or "")[last.sentence.end:f.sentence.start] if f.view.id == last.view.id else ""
        if f.sentence.start >= last.sentence.end and re.search(r"\w", gap):
            runs.append([f])
        else:
            runs[-1].append(f)
    return runs


#: Words a clause cannot end on: a line cut after one was cut mid-sentence
#: (INBOX 1649: an "Also:" item ended "... hub-finish-ui and").
_DANGLING = frozenset("and or but nor so then the a an to of with for in on at by as from into that which who if when while because than".split())


def asks_for_a_topic(question: str) -> bool:
    """False for a request or an act ("I want to edit my pasta note", "can I
    open the pasta note"): "so far this is your only note on it" claims a
    topic's coverage, and a request has no topic (INBOX 1649)."""
    from tessellate.ai import intent

    return not re.match(rf"\s*{intent._REQUEST_FRAME}\b", question or "", re.IGNORECASE)


def _sentence_ends(held: list[Fact]) -> frozenset[str]:
    """The last word of each sentence a line is made from, as the person
    wrote it ("I didnt lock in 😔" ends on "in")."""
    ends = set()
    for f in held:
        words = [w for w in (re.sub(r"[^\w']+$", "", t) for t in f.sentence.text.split()) if w]
        if words:
            ends.add(words[-1].lower())
    return frozenset(ends)


def whole_clause(text: str, whole_ends: frozenset[str] = frozenset()) -> str:
    """The text without a dangling tail ("... the footer and" is "... the
    footer"), cut back to its last whole clause; "" when under three words
    are left, so the caller drops the item rather than quote a fragment. A
    last word that a whole sentence of the note ends on (`whole_ends`) is not
    dangling: "lock in" is the person's own phrase, not a cut one (INBOX 1665)."""
    said = text.rstrip()
    ended = said.rstrip(" ,;:-").rsplit(None, 1)
    if said.endswith((".", "!", "?", ")", "\"", "\u201d", "`")) or not ended or ended[-1].lower().strip(",;:") not in _DANGLING:
        return text
    if ended[-1].lower().strip(",;:") in whole_ends:
        return text
    words = said.rstrip(" ,;:-").split()
    while words and words[-1].lower().strip(",;:") in _DANGLING:
        words.pop()
    kept = " ".join(words).rstrip(" ,;:-")
    return kept if len(kept.split()) >= 3 else ""


def _capitalised_items(said: str) -> str:
    return "; ".join(c[:1].upper() + c[1:] for c in said.split("; "))


def _as_the_note_began(said: str, held: list[Fact]) -> str:
    """A noun phrase said after its own "**Agenda:**" label keeps the capital the note wrote it with:
    "Orchard project budget" is a name, and nothing joins it to a verb frame (W7b B33)."""
    first = re.match(r"[a-z][\w'-]*", said or "")
    if not first or len(held) != 1:
        return said
    word = first.group(0)
    body = _unlinked(held[0].body or "")
    if not body.startswith(word[:1].upper() + word[1:]) or _verb_led(body) or _did(word) or word in _FUNCTION_WORDS or _starts_a_title(body, False):
        return said
    #: Only a noun phrase (a capital word, then a small one) is restored; a clause is left as lowered.
    return body[:1] + said[1:] if re.match(r"[A-Za-z][\w'-]*\s+[a-z]", body) else said


def _lines(out: _Out, facts: list[Fact], limit: int, skip: set[tuple] | None = None, by_day: date | None = None, more: bool = False, weave: bool = False) -> int:
    """Facts grouped under their labels, oldest note first, one line a label;
    the line carries its first note for its one citation mark."""
    groups, days = _group_by_label(facts, skip, by_day)
    shown = 0
    seen_days: list[date] = []
    last = None
    for i, (label, held) in enumerate(_one_note_lines(groups)[: limit + (MORE_LINES if more else 0)]):
        held = _also_held(held) if label == PHRASES["also"] else held
        written = held[0].view.written
        #: The time since the latest note told above that came before this
        #: one (gold Q2: "a week later, you tried the Viper", though the line
        #: above it was made from the same later note).
        before = max((d for d in seen_days if written and d < written), default=None)
        said, line_body, heading = _line_of(label, held, i, weave, by_day, days, before, last == held[0].view.id)
        last = held[0].view.id
        if written:
            seen_days.append(written)
        #: Each item of "Also" starts a capital: "phone $35" after "Groceries about $80 a week;" did not (review 1).
        said = _capitalised_items(said) if label == PHRASES["also"] else said
        if not (said := whole_clause(said, _sentence_ends(held))):
            continue
        listed = _clause_list(said)
        (out.lines if i < limit else out.more).append(
            (f"**{label}:**\n{listed}" if listed and not heading else listed or (f"{said}." if heading else f"**{label}:** {_as_the_note_began(said, held)}.")))
        out.rows.append(_line_row(line_body, held))
        shown += 1
    return shown


def _next_gap(days: int) -> str:
    """The gap lead for this line: the next wording round, never the one the
    line before used, and never the same words twice in an answer."""
    said = VOICES.get(_VOICE.get(), {}).get("gap") or _BASE["gap"]
    options = said if isinstance(said, tuple) else (said,)
    used = _GAPS.get()
    start = _SEED.get() + _TURN.get() + len(used)
    leads = [_Capitals(options[(start + k) % len(options)]).format(gap=_gap(days)) for k in range(len(options))]
    lead = next((x for x in leads if x not in used and not (used and _shape(x) == _shape(used[-1]))), leads[0])
    _GAPS.set(used + (lead,))
    return lead


def _shape(lead: str) -> str:
    """How a gap lead is worded, whatever the gap ("after X," / "X later,")."""
    return "after" if lead.lower().startswith("after ") else lead.rstrip(", ").rsplit(" ", 1)[-1]


def _gap_on(days: int, day: str) -> str:
    """"A week later, on 4 August, "; "three weeks on" takes "by", not a
    second "on"."""
    lead = _next_gap(days)
    return lead + ("by " if lead.endswith(" on, ") else "on ") + f"{day}, "


#: **A dated line reports what the note said then** (B85; BACKLOG INBOX 1299,
#: the owner: "it probably should have said instead 'A week on, by 9 August,
#: you mentioned that you had just recently begun playing League of
#: Legends'"). A clause in the present, or one pinned to its note's own day
#: ("just", "recently"), is true of that day, not of today: after "by 9
#: August," it is said as reported speech, one tense back. A plain past
#: ("you bought a headset") is already the day's and stays as it is.
_NOW_WORDS = re.compile(r"\b(?:just|recently|currently|now|at the moment|these days|so far|lately)\b", re.I)
_PRESENT = re.compile(r"\byou(?:'re|'ve| are| have| am| can| will| don't| do not| need| want| feel| think| like| love| hate| know)\b", re.I)
_BACKSHIFT = (
    (re.compile(r"\byou're\b"), "you were"), (re.compile(r"\byou are\b"), "you were"),
    (re.compile(r"\byou've\b"), "you had"), (re.compile(r"\byou have\b"), "you had"),
    (re.compile(r"\byou can\b"), "you could"), (re.compile(r"\byou will\b"), "you would"),
    (re.compile(r"\byou don't\b"), "you didn't"), (re.compile(r"\byou do not\b"), "you did not"),
    (re.compile(r"\byou (need|want|feel|think|like|love|hate|know)\b"),
     lambda m: "you " + {"need": "needed", "want": "wanted", "feel": "felt", "think": "thought", "like": "liked",
                         "love": "loved", "hate": "hated", "know": "knew"}[m.group(1)]),
    #: "..., it is $129 right now" told later: "and it was $129 at the time".
    (re.compile(r", it(?:'s| is)\b"), ", and it was"), (re.compile(r"\bright now\b"), "at the time"),
)
_PAST_PARTICIPLE = {
    "began": "begun", "went": "gone", "saw": "seen", "took": "taken", "did": "done", "wrote": "written",
    "ate": "eaten", "gave": "given", "came": "come", "ran": "run", "drove": "driven", "rode": "ridden",
    "swam": "swum", "sang": "sung", "drank": "drunk", "spoke": "spoken", "broke": "broken", "chose": "chosen",
    "forgot": "forgotten", "knew": "known", "grew": "grown", "threw": "thrown", "flew": "flown", "fell": "fallen",
    "became": "become", "wore": "worn", "hid": "hidden", "woke": "woken", "froze": "frozen", "stole": "stolen",
}
_HAD_PAST = re.compile(r"^you((?: (?:just|recently|only|finally|already|also|actually))*) ([a-z]+ed|" + "|".join(_PAST_PARTICIPLE) + r"|bought|felt|made|found|left|met|paid|sent|spent|told|thought|heard|kept|lost|read|said|sat|slept|stood|taught|won|built|got|put|set|cut|hit|quit)\b")
#: A clause whose own verb is a plain present the backshift does not turn
#: ("you interrupt", "you get"), not "you're", "you have", "you want".
_HABIT = re.compile(
    r"^you (?!(?:are|have|can|will|don't|do|need|want|feel|think|like|love|hate|know|am|were|was|had|did|just|recently|"
    r"currently|now|still|also|only|finally|already|actually)\b)(?![a-z]+ed\b)[a-z]+\b(?!')",
)
_REPORTS = ("you mentioned that ", "you wrote that ", "you noted that ", "you said that ", "you recorded that ",
            "you put down that ", "you jotted down that ", "your note said that ")


def _reported(body: str, i: int, written: date | None = None) -> str:
    """`body`, a clause of the person's own under a dated lead, as reported
    speech when it is in the present or pinned to its note's day; as it is
    otherwise. The reporting verb turns with the line (`i`)."""
    if not re.match(r"you\b", body) or not (_NOW_WORDS.search(body) or _PRESENT.search(body)):
        return body
    if _HABIT.match(body) or _fresh(written):
        #: "you interrupt when you're nervous": a habit, true then and now,
        #: is reported as it was written; shifting only its "you're" gave
        #: "you interrupt when you were nervous" (INBOX 1301 D5).
        return _REPORTS[i % len(_REPORTS)] + body
    said = body
    past = _HAD_PAST.match(said)
    if past and not _PRESENT.match(said):
        verb = past.group(2)
        said = f"you had{past.group(1)} {_PAST_PARTICIPLE.get(verb, verb)}" + said[past.end():]
    #: The note's later sentences were written that day too ("You need to
    #: finish your IT assignment, which is due on Friday"): shifted alike.
    head, *rest = re.split(r"(?<=[.!?]) (?=You\b)", said)
    said = " ".join([_backshift(head)] + ["Y" + _backshift("y" + more[1:])[1:] for more in rest])
    return _REPORTS[i % len(_REPORTS)] + said


def _backshift(said: str) -> str:
    for pattern, repl in _BACKSHIFT:
        said = pattern.sub(repl, said)
    return recogniser.as_of_then(said)


_PINNED = re.compile(r" \(you pinned this as true, [^)]+\)")

#: What a note's heading names, and how a paragraph opens on it (the owner,
#: 2026-10-11: "In your first psych lecture you learned that ...").
_HEARD = re.compile(r"\b(lecture|class|seminar|talk|tutorial|lesson|workshop|webinar|podcast|course)\b", re.I)
_DID = re.compile(r"\b(lab|practical|session|workout|training|game|match|meeting|appointment|trip|visit|shift|run|ride|swim)\b", re.I)
_PLANNED = re.compile(r"\b(plan|routine|schedule|goals?|budget|timetable|system)\b", re.I)
_ORDINALS = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth")
#: A note-to-self ("Read chapters 1 to 3 before next week"), said as the
#: task the person set: what to do, and to what.
_TASK = re.compile(r"^(read|watch|finish|review|revise|redo|practise|practice|learn|write|do|study|listen to)\s+(.+?)(\s+(?:before|by|until|for|on)\s+.+)?$", re.I)
_DOING = re.compile(r"^(?:ask|call|email|text|book|buy|order|check|remember to|pay|send|bring|look up|try|go|get|sort|plan|start)\b", re.I)
_PLACE_NOUN = re.compile(r"^(library|gym|pool|office|park|bus|train|cafe|range|studio|lab|track|beach)\b", re.I)


_LIFT = re.compile(r"^(squats?|bench(?: press(?:es)?)?|deadlifts?|rows?|overhead press(?:es)?|presses|curls?|lunges?)\s+(up to\s+)?(\d.+)$", re.I)
_LIFTED = {"squat": "squatted", "bench": "benched", "deadlift": "deadlifted", "row": "rowed", "overhead": "overhead pressed", "press": "pressed", "curl": "curled", "lunge": "lunged"}
#: "Back in July, ..." is a day said first (INBOX 1483), not how a back felt.
_BODY_PART = re.compile(r"^(?!back in\b)(knees?|back|shoulders?|legs?|arms?|ankles?|hips?|wrists?|neck|feet|foot|hamstrings?|calves|elbows?)\b", re.I)
_PLANNED_FOR = re.compile(r"^\s*(\S+(?:\s+\S+)*?)\s+(planned|booked|set|moved|pencilled in)\s+(for|to)\s+(.+)$", re.I)
#: A day's shorthand is a line or two; `_PLANNED_FOR` retries `(.+)$` at every "planned for" and each try runs to
#: the line end, so it is only offered a body this short (review 1109: 50,000 characters took 0.4 s).
PLANNED_MAX = 1000
_WEEKDAY_WORD = re.compile(r"\b(Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day\b")


def _day_clause(body: str) -> str | None:
    """A day's shorthand as the person's own clause, or None when it is not
    one of the shapes read here: a plan ("Lisbon trip planned for May"), a
    lift log ("squats 80 kg for 5, bench 60 kg for 5"), how a body part felt,
    and "going Monday and Friday"."""
    planned = _PLANNED_FOR.match(body) if len(body) <= PLANNED_MAX else None
    if planned:
        thing = _fragment(planned.group(1), _NAMES.get())
        return f"you {planned.group(2).lower()} the {thing} {planned.group(3).lower()} {planned.group(4)}"
    if _BODY_PART.match(body):
        return f"your {body[0].lower() + body[1:]}"
    going = re.match(r"^going\s+((?:on\s+)?(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day\b.*)$", body)
    if going:
        days = _WEEKDAY_WORD.sub(lambda m: m.group(0) + "s", going.group(1).removeprefix("on "))
        return f"you were going on {days}"
    lifts = [_LIFT.match(p.strip()) for p in re.split(r",(?!\d)\s*(?:and\s+)?|\s+and\s+", body) if p.strip()]
    if lifts and all(lifts):
        said = []
        for n, m in enumerate(lifts):
            stem = m.group(1).lower().split()[0].rstrip("s") if not m.group(1).lower().startswith("press") else "press"
            if m.group(2):
                said.append(("your " if n == 0 else "") + f"{stem} was up to {m.group(3)}")
            else:
                said.append(("you " if n == 0 else "") + f"{_LIFTED.get(stem, stem)} {m.group(3)}")
        return realise.join_items(said)
    return None


def _pick(key: str, i: int) -> str:
    """One wording of `key`, turned by the paragraph so neighbours differ."""
    said = VOICES.get(_VOICE.get(), {}).get(key) or _BASE[key]
    return said[(_SEED.get() + _TURN.get() + i) % len(said)] if isinstance(said, tuple) else said


def _heading_said(label: str) -> str:
    """"Psych lecture 1" as "first psych lecture"; "Data Structures lab" kept
    in its own capitals where they are a name."""
    numbered = re.match(r"^(.*?\S)\s+(\d{1,2})$", label.strip())
    if numbered and 1 <= int(numbered.group(2)) <= len(_ORDINALS):
        return f"{_ORDINALS[int(numbered.group(2)) - 1]} {_fragment(numbered.group(1), _NAMES.get())}"
    #: "League of Legends", "Gym Routine Overview": a later capital marks a
    #: name, kept whole (INBOX 1310: "Your league of Legends note").
    if any(w[:1].isupper() for w in label.split()[1:3]):
        return label.strip()
    return _fragment(label.strip(), _NAMES.get())


def _said_in_a_frame(text: str) -> str:
    """A name or a clause put after other words, lower case only where its
    first word is a plain dictionary word (`composer_frame.bind_lower`)."""
    if any(w[:1].isupper() for w in text.split()[1:3]):
        return text
    return _fragment(text.strip(), _NAMES.get())


def _past(body: str) -> str:
    """A note's present said from later: "you're still shaky" was then."""
    body = re.sub(r"\byou're\b", "you were", body)
    body = re.sub(r"\byou are\b", "you were", body)
    body = re.sub(r", it(?:'s| is)\b", ", and it was", body)
    body = re.sub(r"\bright now\b", "at the time", body)
    return re.sub(r"\byou were going to\b", "you planned to", body)


_FINITE = re.compile(r"\b(?:is|was|are|were|has|had|have|will|can|felt|looks?|seems?)\b", re.I)


_CLAUSE_SPLICE = re.compile(r", (?=(?:the|my|your|it|his|her|their)\b[^,]*\b(?:was|is|were|are)\b)", re.I)


def _noted_sentence(body: str, first: bool) -> str:
    """A sentence under a note's heading, never read as a list (INBOX 1310):
    "Your movie review note says Dune Part Two was stunning", "Your League of
    Legends note says your mains are ...", "Your Pokemon image note is your
    favourite card scan"; "" for a body that is a list."""
    finite = bool(_FINITE.search(body))
    if re.match(r"you\b", body, re.I) or not (finite or re.match(r"your\b", body, re.I)):
        return ""
    #: "Dune was stunning, the sound was huge": two clauses, one "and".
    body = _CLAUSE_SPLICE.sub(", and ", body)
    if not first:
        return "it says " + body
    return ("says " if finite else "is ") + body


_LABELLED = re.compile(r"[A-Z][^:.!?\n]{0,60}:\s+\S")


def _clause_of_frame(body: str, frame: str, i: int, first: bool) -> str:
    """The clause a body gets from the frame alone, once no task or doing claimed it."""
    if frame == "heard":
        return f"{_pick('learned', i)} {body}"
    #: "Wedding table 4: Anna, Tom and Sara" is a label and its value: said as written, its commas kept (R3-12).
    if frame in ("planned", "noted") and _LABELLED.match(body):
        return _wrote(body, i)
    if frame in ("planned", "noted") and re.search(r",\s*(?:he|she|it|they|we|i)\b", body, re.I):
        #: "nothing, he's my boss" is one remark, not a list to join with "and" (R9-4).
        return ("has " if first else "it has ") + body
    if frame in ("planned", "noted"):
        items = [("the " + p if _PLACE_NOUN.match(p) else p) for p in re.split(r",(?!\d)\s*(?:and\s+)?", body) if p]
        return ("has " if first else "it has ") + realise.join_items(items)
    return _wrote(body, i)


_OBLIGED = re.compile(r"(?:need|needs|needed|want|wants|wanted|have|has|got|should|must|ought|hope|hopes|forgot)\s+to\b", re.I)


def _clause(body: str, frame: str, i: int, first: bool) -> str:
    """One fact as a clause of the paragraph: a statement heard is what was
    learned, a note-to-self is the task set, a plain noun is what the plan
    has, and the person's own "you ..." stays theirs."""
    body = re.sub(r", not (a|an|the) ", r" rather than \1 ", body)
    if body.lower().startswith("still "):
        return f"you were {body}"
    said = _noted_sentence(body, first) if frame == "noted" else ""
    if said:
        return said
    if re.match(r"(?:you|your)\b", body, re.I):
        return _past(body)
    if body.lower().startswith("going to "):
        return f"{_pick('meant', i)} {body[9:]}"
    if _OBLIGED.match(body):
        #: "you wrote down need to cut eating out", "it has need to cut ..."
        #: (audit 1029 C13): a need is a clause of its own, not an object.
        return f"you {body[0].lower() + body[1:]}"
    task = _TASK.match(body)
    if task:
        verb, obj, when = task.group(1).lower(), task.group(2), task.group(3) or ""
        return _pick("set_task", i).format(obj=obj, verb=verb) + when
    if _DOING.match(body) and _verb_led(body):
        return f"{_pick('meant', i)} {body[0].lower() + body[1:]}"
    return _clause_of_frame(body, frame, i, first)


def _prose_opening(label: str, named: str, written: date | None, today: date | None, filed: bool = False, view=None) -> tuple[str, str]:  # noqa: ANN001
    """How a heading-labelled paragraph opens: (frame, opening words)."""
    if not _TIMED.get():
        written = None
    on = f" on {_day(written, today or written)}" if written else ""
    if _PLANNED.search(label):
        return "planned", f"Your {named}"
    if _DID.search(label):
        return "did", f"At the {named}{on}"
    if _HEARD.search(label):
        return "heard", f"In your {named}" + (f", on {_day(written, today or written)}," if written else "")
    if re.match(r"(?:the|a|an|this|my|your)\b", named, re.I) or filed:
        #: "Your the split follows this structure note" (owner, 2026-10-12):
        #: a heading that is a sentence cannot stand between "Your" and "note".
        #: Named by its title or first clause, never "Your note of 27 July" (1441).
        name = _your_note(view) if view is not None else "your note"
        return "noted", name[:1].upper() + name[1:]
    if view is not None and not getattr(view, "titled", False):
        #: A title-less note is named once, by its first line, never by its label (owner 2026-11-10).
        name = _your_note(view)
        return "noted", name[:1].upper() + name[1:]
    return "noted", f"Your {named} note"


def _label_names(label: str, view) -> bool:  # noqa: ANN001
    """Whether a line's label is the note's own name: a title-less note's
    first "Psych lecture 1: ..." names it; a section ("Attendees:", "Pros:")
    or a label inside a titled note does not."""
    key = re.sub(r"\s+", " ", label.strip().lower())
    if key in composer_frame.SECTION_LABELS:
        return False
    if getattr(view, "titled", False):
        return key == re.sub(r"\s+", " ", (view.title or "").strip().lower())
    sentences = getattr(view, "sentences", None) or []
    return not sentences or sentences[0].text.strip().lower().startswith(key)


def _section_items(bodies: list[str]) -> str:
    if any(_FINITE.search(b) for b in bodies) or len(bodies) == 1 and len(bodies[0].split()) > 8:
        return _join(bodies, True)
    if any(re.search(r",\s*(?:he|she|it|they|we|i)\b", b, re.I) for b in bodies):
        #: "nothing, he's my boss" is one remark, not a list to join with "and" (R9-4).
        return "; ".join(b.strip().rstrip(".") for b in bodies)
    pieces = [p for b in bodies for p in re.split(r",(?!\d)\s*(?:and\s+)?", b) if p]
    # "Anna, Tom and Sara" is already a list: split on its commas and joined again it read "Anna and Tom and Sara" (R3-12).
    if any(re.search(r"\band\b", p) for p in pieces):
        return "; ".join(b.strip().rstrip(".") for b in bodies)
    return realise.join_items(pieces)


def _noted_section(head: str, items: str, view, today: date | None) -> str:  # noqa: ANN001
    """A title-less note that is one labelled thought: "On 22 October, you noted an idea: ..."."""
    article = "" if head.endswith("s") or head[:1].isupper() else ("an " if head[:1] in "aeiou" else "a ")
    written = view.written
    lead = _recent(written, today) or (_lead_day(written, today, capital=False) if written and _TIMED.get() else "")
    return f"{lead}you noted {article}{head}: {items}"


def _section_line(label: str, view, bodies: list[str], today: date | None, same: bool) -> str:  # noqa: ANN001
    """A section of one note said as that note's part, never as a note of
    its own (C8, INBOX 1301 D5): "Your Project Atlas kickoff meeting note
    has attendees: Sara, Tom and Priya." then "It also has decisions: ...";
    a title-less note that is one labelled thought ("Idea: a bike route")
    is what the person noted: "On 22 October, you noted an idea: ..."."""
    head = _fragment(label.strip(), _NAMES.get())
    items = _section_items(bodies)
    first = view.sentences[0].text.strip().lower() if view.sentences else ""
    if composer_threads.label_is_sentence(label):
        #: Its own words, said as the note's (INBOX 1512).
        #: A title-less note's name is its own first words, so "“harbor standup: Mia says…” says Mia says…" would say them twice.
        line = (f"{_your_note(view) + (' also says' if same else ' says')} " if view.titled else "") + f"{composer_threads.voiced(head)}: {items}"
    elif not view.titled and first.startswith(label.strip().lower()):
        line = _noted_section(head, items, view, today)
    elif re.search(r"\s\d+$", label.strip()):
        # A label that ends in a number ("Wedding table 4") is the note's own words:
        # "has a wedding table 4:" invented an article and rewrote its commas (R3-12).
        said = f"“{label.strip()}: {items}”"
        line = f"you wrote {said}" if not view.titled else f"{_your_note(view) + (' also says' if same else ' says')} {said}"
    elif same:
        #: Not "It also has": a line can open an answer paragraph, and "it" is then no one (R9-6).
        line = f"{_your_note(view)} also has {composer_threads.with_article(head)}: {items}"
    else:
        line = f"{_your_note(view)} has {composer_threads.with_article(head)}: {items}"
    return line[0].upper() + line[1:]


def _opened(label: str, frame: str, opening: str, first: str) -> str:
    """The line's start. A title-less note named by its first words does not say them twice
    ("“harbor standup: Mia says…” says Mia says…"): the label and what follows are the note's own line."""
    if frame == "noted" and opening.startswith("“") and first.startswith("says "):
        return f"{label.strip()}: {first.removeprefix('says ')}"
    return f"{opening} {first}".lstrip()


def _prose(label: str, held: list, bodies: list[str], i: int, today: date | None, same: bool = False) -> str:
    """A heading-labelled line said as a paragraph that understands its note
    (the owner, 2026-10-11): "In your first psych lecture you learned that
    memory is reconstructive rather than a recording, and you gave yourself
    chapters 1 to 3 of the Myers textbook to read before 27 July". A
    section's label is said as the note's part (`_section_line`)."""
    if not _label_names(label, held[0].view):
        return _section_line(label, held[0].view, bodies, today, same)
    named = _heading_said(label)
    written = held[0].view.written
    #: "Hobbies: ..." filed under Hobbies names nothing the filing does not
    #: (INBOX 1310: "Your hobbies note has thinking of buying").
    filed = label.lower() == str((getattr(held[0].view, "note", None) or {}).get("category") or "").lower()
    frame, opening = _prose_opening(label, named, written, today, filed, held[0].view)
    clauses = [_clause(b, frame, i + n, n == 0) for n, b in enumerate(bodies)]
    if frame in ("planned", "noted") and re.match(r"you\b", clauses[0]):
        #: The person's own doing needs no heading: its day says when.
        recent = _recent(written, today).rstrip(", ")
        opening = (recent[:1].upper() + recent[1:] + "," if recent else _lead_day(written, today).rstrip()) if written else f"In your {named} note,"
        if written and not _TIMED.get():
            opening = ""
    line = _opened(label, frame, opening, clauses[0])
    for clause in clauses[1:]:
        line += (", though " if clause.startswith("you were still") else ", and ") + clause
    return line[0].upper() + line[1:]


#: The joins inside a line (INBOX 870): "; still shaky on big O" reads as
#: a list; ", though you're still shaky on big O" reads as a thought.
_STILL_VERB = re.compile(r"^still (need|have|want|haven't|hasn't|don't|to)\b", re.I)


#: A body with no subject of its own: a lower-case "-ing" word first (typed
#: case matters, so no `re.I`), or one to three words that do not open on a
#: pronoun. Two patterns, not one with an inline flag group: CodeQL read
#: the inline `(?-i:` form as an unmatchable `$`.
_GERUND_OPEN = re.compile(r"[a-z]+ing\b")
_SHORT_FRAGMENT = re.compile(r"(?!(?:you|i|we|he|she|they|it)\b)\w+(?:\s+\w+){0,2}$", re.I)


def _is_fragment(body: str) -> bool:
    return bool(_GERUND_OPEN.match(body) or _SHORT_FRAGMENT.match(body))


def _join(bodies: list[str], sentences: bool = False) -> str:
    """A line's bodies as one line. Woven into an overview (`sentences`),
    two facts are two sentences, never a ";" run (INBOX 1301 D5)."""
    out = bodies[0] if bodies else ""
    for body in bodies[1:]:
        if sentences and _is_fragment(body):
            #: "slicing everything but it was fun", "straighter this time":
            #: no subject of its own, so it rides on the sentence before.
            out += ", " + body
        elif sentences and not body.lower().startswith(("still ", "going to ")):
            out += ". " + body[:1].upper() + body[1:]
        elif _STILL_VERB.match(body):
            out += ", but you " + body
        elif body.lower().startswith("still "):
            out += ", though you're " + body
        elif body.lower().startswith("going to "):
            out += ", and you're " + body
        elif out.rstrip().endswith(("?", "!")) or _a_sentence(out) or _a_sentence(body):
            #: "That's fascinating; What drew you to it?; you've always ..."
            #: ran sentences together (INBOX 1420): a sentence ends.
            out = out.rstrip() + ("" if out.rstrip().endswith(("?", "!", ".")) else ".") + " " + body[:1].upper() + body[1:]
        else:
            out += "; " + body
    return out


_SUBJECT_START = re.compile(r"^(?:i|you|we|he|she|they|it|that|this|there|what|how|why|who|when|where)(?:'\w+|’\w+)?\b", re.I)


def _a_sentence(body: str) -> bool:
    """A body that is a whole sentence (a subject and its verb, or a
    question), not a list entry: joined by a stop, never a ";"."""
    body = body.strip()
    return body.endswith("?") or bool(_SUBJECT_START.match(body) and (_FINITE.search(body) or re.match(r"\w+(?:'|’)\w+", body)))


_MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december")
#: Not "back in July", a month gone by (INBOX 1483).
_FOR_MONTH = re.compile(r"\b(?<![Bb]ack )(?:for|in|by|until) (" + "|".join(m.capitalize() for m in _MONTHS) + r")\b")


#: What a price is per: two prices on different periods ("$1,200 a month",
#: "$80 a week") have no gap between them.
_PER = re.compile(r"(?:\ba|\bper|\beach|\bevery|/)\s*(day|week|month|year|hour|night)\b", re.I)
#: A gap is the budget against what was spent, the ask against the offer:
#: it needs one word of each side.
#: Two things weighed against each other in one line ("The Logitech is about
#: $230 and the Razer is $200"): each is named and priced, so the gap between
#: them is true, which a budget and an unrelated amount are not.
_RIVAL_PRICES = re.compile(r"\b[A-Z][\w-]{0,30}(?: [\w-]{1,30}){0,6} is (?:about )?\$\d{1,9}[\d.,]{0,9} and (?:the )?[A-Z][\w-]{0,30}(?: [\w-]{1,30}){0,6} is (?:about )?\$\d")
_PLANNED_PRICE = re.compile(r"\b(?:budget|limit|target|goal|estimate|quote|quoted|asking|listing|listed|planned)\b", re.I)
_ACTUAL_PRICE = re.compile(r"\b(?:spent|spend|paid|cost|actual|offer|negotiated|saved|came to)\b", re.I)


def _price_gap(body: str) -> str:
    """The gap between two prices of one thing, a budget and what it came to
    (INBOX 870); not between rent and groceries (audit 1030 Z6): the two
    share a period, and one is the plan and the other the outcome."""
    prices = re.findall(r"\$\s?(\d+(?:\.\d+)?)", body)
    if len(prices) != 2 or prices[0] == prices[1]:
        return ""
    periods = {m.group(1).lower() for m in _PER.finditer(body)}
    if len(periods) > 1 or (periods and len(_PER.findall(body)) == 1) or not ((_PLANNED_PRICE.search(body) and _ACTUAL_PRICE.search(body)) or _RIVAL_PRICES.search(body)):
        return ""
    gap = abs(float(prices[0]) - float(prices[1]))
    return PHRASES["price_gap"].format(gap=("about " if "about $" in body else "") + f"${gap:g}")


def _relate(body: str, today: date | None) -> str:
    """A clause the line's own note does not say (INBOX 870): the gap
    between two prices, or how far off a month it is planned for."""
    if gap := _price_gap(body):
        return gap
    month = _FOR_MONTH.search(body)
    #: Said of a month still to come: a past-tense sentence ("Finished Piranesi
    #: in September", "Met at the conference in June") is behind, not ahead
    #: (audit 1030 Z5).
    if month and today and not _told_in_past(body):
        ahead = (_MONTHS.index(month.group(1).lower()) + 1 - today.month) % 12
        if ahead >= 2:
            return _vary("months_away").format(away=f"{realise.count_word(ahead)} months")
    return ""


_BE_PAST = frozenset({"was", "were", "had", "did"})
#: Participles that look ahead ("a trip planned for May", "booked for June"):
#: past in form, not in what they tell, so a month after them is still to come.
_AHEAD_PARTICIPLES = frozenset({"planned", "scheduled", "booked", "arranged", "expected"})


def _told_in_past(body: str) -> bool:
    """Whether `body` says something that happened ("you met", "finished")."""
    return any(
        (_did(w) or _past_verb(w)) and w.lower() not in _BE_PAST and w.lower() not in _AHEAD_PARTICIPLES
        for w in re.findall(r"[A-Za-z']+", body)
    )


def _pattern(members: list[composer.NoteView], today: date) -> str:
    """One closing sentence the notes on the right cannot show (INBOX 870):
    how the notes sit in time: stale, one burst, or a steady habit."""
    days = sorted(v.written for v in members if v.written)
    #: Jokes and quotes are kept, not kept up: "may have moved on" is no
    #: thing to say of them.
    if len(days) < 2 or any(_context_note(v) for v in members):
        return ""
    age = (today - days[-1]).days
    span = (days[-1] - days[0]).days
    #: How the notes sit in time is said only when time was asked, and how
    #: stale they are only when the question is about now (INBOX 1441).
    if age >= 21:
        return _vary("stale").format(age=_gap(age)) if _CURRENT.get() else ""
    if not _TIMED.get():
        return ""
    ago = "today" if age <= 0 else f"{_gap(age)} ago"
    if span <= 9:
        #: "Both came within a day", never "All two came" (2026-10-30).
        all_of = "Both" if len(days) == 2 else f"All {realise.count_word(len(days))}"
        return _vary("burst").format(all_of=all_of, span=_gap(max(span, 1)), ago=ago)
    if len(days) >= 3:
        every = _bare_gap(_gap(max(1, round(span / (len(days) - 1)))))
        return _vary("cadence").format(every=every, ago=ago)
    return _vary("fresh").format(ago=ago)


def _row(said: str, fact: Fact) -> dict:
    return {
        "sentence": said,
        "note_id": fact.view.note.get("source_id", fact.view.id),
        "source": fact.sentence.text,
        #: Where in the note, so the mark's peek shows the note's own
        #: sentence under the rewritten line (B5).
        "start": fact.sentence.start,
        "end": fact.sentence.end,
        "score": 1.0,
        "digest": True,
        #: The source's kind, so a closing line reads a document's id in its
        #: own table (INBOX 1357).
        "kind": getattr(fact.view, "kind", "note"),
    }


#: A note that is weighing a purchase, not one with a price in it (audit 1031 C20).
_PLAN_ASK = re.compile(r"\b(?:plan|plans|planning|itinerary)\b", re.I)
_WEIGHING = re.compile(r"\blooking at an? new\b|\bleaning towards\b|\bdeciding between\b", re.I)


def _missing(members: list[composer.NoteView], asked: str | None = None) -> str:
    """What a topic the person asked about lacks. Only a topic the question
    itself names has gaps worth saying: rent in a budget note is no
    "purchase" and a dentist note holding "essay" no "study" (audit 1031
    C20). `asked` None is the open category, where the notes are the topic."""
    text = " ".join(s.text for v in members for s in v.sentences)
    for name, topic, facets in FACETS:
        #: The question names the topic, asks for a plan ("what's the plan
        #: for Lisbon": a plan has the gaps its topic lists), or (a purchase
        #: only) the notes say they are weighing one: "what is there about a
        #: gaming mouse" holds a note that is looking at a new one, and its
        #: gap is where to buy it.
        if asked is not None and not topic.search(asked) and not _PLAN_ASK.search(asked) and not (name == "purchase" and _WEIGHING.search(text)):
            continue
        if len(topic.findall(text)) >= 2 or (len(members) == 1 and topic.search(text)):
            absent = [name for name, cue in facets if not cue.search(text)]
            if absent:
                return PHRASES["nothing_yet"].format(facets=" or ".join(absent[:2]))
            return ""
    return ""


#: A question about what is open or due, where any to-do is on topic.
_ABOUT_TASKS = re.compile(r"\b(?:to ?do|left|remaining|outstanding|need|should|must|due|deadline|homework|tasks?|remind\w*)\b", re.I)


_ABOUT_TIME = re.compile(r"\b(?:when|what (?:day|time|date))\b", re.I)


def _on_topic(action: str, asked: str) -> bool:
    """Whether a to-do is what the question is about: it asks what is open or
    due, or asks when something happens that the to-do names ("when is the
    tutor meeting" offers "ask the tutor on Thursday"). A definition
    ("what is the Krebs cycle") offers nothing, even beside a to-do on it."""
    if _ABOUT_TASKS.search(asked):
        return True
    if not _ABOUT_TIME.search(asked):
        return False
    words = {composer._stem(w) for w in re.findall(r"[a-z]{4,}", action.lower())}
    return bool(words & {composer._stem(w) for w in re.findall(r"[a-z]{4,}", asked.lower())})


def _answered(out: _Out, facts: list[Fact]) -> list[Fact]:
    """The facts from the notes the answer cites. An offer is a next step on
    what was just said, so a to-do from a note that is not in the answer
    ("Remind you to buy a capo?" under an answer about a sister, audit 1029
    C4) is never a candidate. With no rows yet, every fact stands."""
    cited = {r["note_id"] for r in out.rows}
    if not cited:
        return facts
    return [f for f in facts if f.view.note.get("source_id", f.view.id) in cited]


def _open_actions(facts: list[Fact]) -> list[str]:
    """The to-dos the facts hold that are still to do: a checklist line a later
    note records as done is not (second eye F15)."""
    views = _VIEWS.get()
    return [
        _asked_about(_still_ahead(a, f.view.written), f.body)
        for f in facts
        if (a := _task_of(f)) and _on_subject(f.view, f.body) and not composer_slots.recorded_later(views, f.view, f.sentence)
    ]


def _offer(facts: list[Fact], asked: str | None = None) -> dict | None:
    """One thing to do next, from the notes' own to-dos: the one with a day
    first ("ask the tutor on Thursday"), then something still to book. With
    `asked`, only a to-do the question is about (`_on_topic`)."""
    #: A day in a to-do is the note's day ("ask the tutor on Thursday",
    #: written 4 August, was 6 August): one gone by is not offered for this
    #: Thursday (the owner, 2026-10-11: relative time resolved everywhere).
    actions = _open_actions(facts)
    if asked is not None:
        actions = [a for a in actions if _on_topic(a, asked)]
    actions.sort(key=lambda a: not any(s.kind in ("date", "datetime") for s in _spans(a, None)))
    if not actions:
        for f in facts:
            still = _STILL_TO.search(f.sentence.text)
            if still and (asked is None or _on_topic(f"{still.group(2)} {still.group(1)}", asked)):
                actions.append(f"{still.group(2).lower()} the {still.group(1).lower()}")
    #: "Remind you to passport?", "Remind you to tom to draft ...": an offer
    #: is only for a to-do that starts with a verb (C3).
    actions = [a for a in actions if _verb_led(a)]
    if not actions:
        return None
    action = realise.shift_person(actions[0])
    action = _fragment(action, _NAMES.get())
    return {"kind": "reminder", "label": PHRASES["remind"].format(action=action), "text": action[0].upper() + action[1:]}


#: With the date a weekday is pinned to, when it carries one ("on Thursday 6
#: August", `_pin_weekdays`): the two go together.
_ON_DAY = re.compile(r"(?<!\s)\s+on\s+((?:mon|tues|wednes|thurs|fri|satur|sun)day)\b(?:\s\d{1,2}\s[A-Za-z]+(?:\s\d{4})?)?", re.I)
#: What makes an instruction a task rather than advice: a thing or person
#: it is about ("the tutor", "my passport", "Daniel") or a day or number.
_SPECIFIC_CASED = re.compile(r"(?<=\s)[A-Z][a-z]+")


def _task_of(f: Fact) -> str:
    """The to-do a fact states, or "". An open checkbox is one; an
    instruction in prose is one only when it names what it is about: "ask
    the tutor on Thursday" is a task, "ask follow-up questions that reflect
    genuine interest" (a guide's advice) is not (INBOX 1301 D5: it was
    offered as a reminder)."""
    if f.sentence.kind == "task":
        return "" if f.sentence.done else f.body
    if not f.action:
        return ""
    rest = f.action.split(" ", 1)[1] if " " in f.action else ""
    #: A day is the recogniser's to read (tests/test_one_reader.py).
    specific = re.search(r"\b(?:the|my|your|our|this|next)\b|\d", rest, re.I) or recogniser.looks_dated(rest)
    return f.action if specific or _SPECIFIC_CASED.search(" " + rest) else ""


def _still_ahead(action: str, written: date | None) -> str:
    """`action` without its day when that day, read from the day the note
    was written, has gone by."""
    m = _ON_DAY.search(action)
    today = _TODAY.get()
    if not m or not written or not today:
        return action
    found = when_words.span(m.group(1).lower(), written, "future")
    if found and found[0] < today:
        return (action[: m.start()] + action[m.end():]).strip()
    return action


_STUCK = re.compile(r"\b(?:shaky|stuck|confused|unsure|lost) (?:on|with|about) ([^,;.]+)", re.I)


def _asked_about(action: str, body: str) -> str:
    """"ask the tutor", from a line "still shaky on big O", is "ask the
    tutor about big O": what to ask is in the note beside it."""
    stuck = _STUCK.search(body)
    if not stuck or not re.match(r"ask\b", action, re.I) or " about " in action:
        return action
    m = _ON_DAY.search(action)
    at = m.start() if m else len(action)
    return f"{action[:at]} about {stuck.group(1).strip()}{action[at:]}"


def _count(n: int, noun: str = "note") -> str:
    return realise.count_noun(n, noun)


#: A note's event with a relative time ("Uni starts back next week"): said
#: from today, with its tense, rather than dropped as stale (the owner,
#: 2026-10-11: "seeing the context for uni, classes, next week (in comparison
#: to the current datetime and the datetime that note was written)").
_EVENT = re.compile(
    r"^(?P<subj>[A-Za-z][\w&' -]{1,40}?) (?P<verb>starts?|begins?|opens?|ends?|finish(?:es)?|is|are|goes|go)"
    r"(?P<adv> back| again| up)? (?P<when>[a-z ]+?)\.?$",
    re.I,
)
#: The relative times an event is said from today with: the recogniser
#: must read the whole of `when` as one day or span, opening with one of these.
_EVENT_WHEN = ("next ", "this ", "tomorrow")


def _event(text: str, written: date | None):  # noqa: ANN202
    """`_EVENT`'s match when its time is one relative day or span the
    recogniser reads ("next week", "tomorrow", "next friday"), else None."""
    m = _EVENT.match(text)
    if m is None or written is None:
        return None
    when = m.group("when")
    whole = [s for s in _spans(when, written) if s.kind in ("date", "range") and s.start == 0 and s.end == len(when)]
    return m if whole and when.lower().startswith(_EVENT_WHEN) else None
_BACK_AT = {"uni", "university", "school", "college", "work", "the gym", "training", "classes", "class"}
_PAST = {"start": "started", "starts": "started", "begin": "began", "begins": "began", "open": "opened", "opens": "opened",
         "end": "ended", "ends": "ended", "finish": "finished", "finishes": "finished", "is": "was", "are": "were",
         "go": "went", "goes": "went"}


def _when_now(when: str, written: date, today: date) -> tuple[str, bool]:
    """A note's "next week" said from today, and whether it is still ahead.
    The day it meant is the app's one resolver's (`when.span`, which also
    draws a note card's "Mentions" chip), anchored on the day it was written;
    only the saying is here: still "next week" the week it was written, the
    week of its Monday once that week has gone, in the past tense."""
    found = when_words.span(when.lower(), written, "future")
    if found is None:
        return when, True
    start, _end, unit = found
    if unit == "day":
        gap = (start - today).days
        return ({0: "today", 1: "tomorrow"}.get(gap) or f"on {_day(start, today)}"), gap >= 0
    if unit == "month":
        ahead = (start.year, start.month) >= (today.year, today.month)
        same = (start.year, start.month) == (today.year, today.month)
        return ("this month" if same else f"in {composer_ask._MONTHS[start.month - 1]}"), ahead
    weeks = (start - (today - timedelta(days=today.weekday()))).days // 7
    return ({0: "this week", 1: "next week"}.get(weeks) or f"the week of {_day(start, today)}"), weeks >= 0


def _event_clause(m: re.Match, written: date, today: date) -> tuple[str, bool]:
    """The event said from today, and whether it is still ahead."""
    when, ahead = _when_now(m.group("when"), written, today)
    subj, verb, adv = m.group("subj").strip(), m.group("verb").lower(), (m.group("adv") or "")
    place = subj.lower()
    if place in _BACK_AT and adv.strip() == "back" and verb.startswith(("start", "begin", "go")):
        return (f"you're back at {place} {when}" if ahead else f"you went back to {place} {when}"), ahead
    name = subj if subj[:1].isupper() and subj.split()[0].lower() not in ("the", "a", "my") else subj[:1].lower() + subj[1:]
    return f"{name} {verb if ahead else _PAST.get(verb, verb)}{adv} {when}", ahead


def _woven(own: list[Fact]) -> tuple[list[str], list[str]]:
    """The note's other facts as (said as the person's own, said after)."""
    told, trailing = [], []
    for f in own:
        body = _fragment(f.body, _NAMES.get())
        timed = f.label if _TIME_LABEL.match(f.label + " x") else ""
        if timed and timed.lower() not in body.lower():
            body = f"{body} {timed.lower()}"
        (told if re.match(r"you\b|you're\b|your\b", body) else trailing).append(body)
    return told, trailing


def _narrated_line(clause: str, told: list[str], trailing: list[str], ahead: bool) -> str:
    line = clause[0].upper() + clause[1:]
    if told:
        line += f", and {_vary('told')} {realise.join_items(told)}"
    if trailing and not ahead:
        line += f", with {realise.join_items(trailing)}"
    line += "."
    if trailing and ahead:
        weekly = " each week" if _DAYS_PLURAL.search(" ".join(trailing)) and "every" not in " ".join(trailing) else ""
        line += " " + _vary("told_future").format(np=realise.join_items(trailing) + weekly)
    return line


def _narrate(out: _Out, view, facts: list[Fact], today: date) -> set:  # noqa: ANN001
    """One note told as what happened, when it has an event with a relative
    time: the event from today ("you're back at uni next week"; months on,
    "you went back to uni the week of 24 July"), then its facts woven in
    with a reporting verb, one citation for the line. The keys of the
    sentences said, for `_lines` to skip; empty when the note has no event."""
    event = next((s for s in view.sentences if s.kind == "prose" and _event(s.text.strip(), view.written)), None)
    if event is None or not view.written:
        return set()
    clause, ahead = _event_clause(_event(event.text.strip(), view.written), view.written, today)
    own = sorted((f for f in facts if f.view.id == view.id and f.sentence.key != event.key), key=lambda f: f.sentence.start)[:3]
    line = _narrated_line(clause, *_woven(own), ahead)
    out.lines.append(line)
    said = [event, *(f.sentence for f in own)]
    row = {
        "sentence": line.rstrip("."), "note_id": view.note.get("source_id", view.id), "source": event.text,
        "start": event.start, "end": event.end, "score": 1.0, "digest": True,
    }
    if len(said) > 1:
        row["parts"] = [{"note_id": row["note_id"], "source": s.text, "start": s.start, "end": s.end} for s in said]
    out.rows.append(row)
    return {s.key for s in said}


_HAS_SUBJECT = re.compile(r"(?:you|we|i|they|he|she|it|you're|we're|i'm|they're)\b", re.I)


def _opening_line(members, facts: list[Fact], today: date, topic: str) -> tuple[str, list[Fact]]:  # noqa: ANN001
    """The opening of an overview, and the facts still to say. It answers in
    the person's terms (INBOX 870): where they have got to, or how much is
    still open, not only how many notes."""
    opening = PHRASES["overview"].format(count=_count(composer_overview.pooled(len(members))), topic=topic, span=_span(members, today))
    landed = next((f for f in facts if f.label == "Where you landed"), None)
    left = [f for f in facts if f.label == "Still to do"]
    if landed:
        said = _fragment(landed.body, _NAMES.get())
        key = "landed_said" if _HAS_SUBJECT.match(said) else "landed"
        if _WE.match(said):
            #: A note's "we" is the writer's and someone else's: reported, not
            #: spliced after "you're" or run on from the count (audit 1030 Z1).
            key, said = "landed_we", said[:1].lower() + said[1:]
        elif key == "landed_said" and not re.match(r"I\b", said):
            said = said[:1].lower() + said[1:]
        opening = _vary(key).format(opening=opening.rstrip("."), landed=said)
        #: Said once, up front, as the answer; not again as a line.
        return opening, [f for f in facts if f is not landed]
    if left:
        opening = _vary("open_count").format(opening=opening.rstrip("."), left="one thing" if len(left) == 1 else f"{realise.count_word(len(left))} things")
    return opening, facts


#: **A note in an overview is its gist** (INBOX 1301 D5, the owner: "the
#: responses for how they are written, how they sound, how they are
#: formatted ... are very poor"). A long guide was said as every sentence,
#: list item and quoted example it holds, glued with ";" ("not cheesy:;",
#: "Follow- Up Questions:;", '"..."; "..."'), then its "Phase 1: ..." lines as
#: notes of their own. A note is now at most two sentences: what it is, then
#: its shape (its sections) or what is still to do on it, or a second line.
#: Quoted examples are the note's material, never the person's facts.
_QUOTED = re.compile(r'^["\u201c\u2018\']')
_NUMBERED = re.compile(r"^(.*?\S)\s+(\d{1,2})$")
#: A body that opens on an instruction ("Count to two before answering"):
#: the person's advice to themselves, said as theirs.
_ADVICE = re.compile(
    r"^(?:invite|count|find|listen|stop|start|try|keep|remember to|focus|message|suggest|take|say|be|don't|do not|use|make|"
    r"give|practise|practice|slow down|breathe|smile|wait|ask|call|email|text|book|buy|order|check|pay|send|bring|look up|"
    r"go|get|sort|plan|write|read|watch|finish)\b",
    re.I,
)
GIST_ITEMS = 3


def _part_name(text: str) -> str:
    """"The Opener (Ice Breakers)" as "the Opener": a section's name in a list."""
    name = re.sub(r"\s*\([^)]*\)", "", text).strip().rstrip(".:")
    return re.sub(r"^The\b", "the", name)


def _plural(word: str) -> str:
    word = word.lower()
    return word + ("es" if re.search(r"(s|x|ch|sh)$", word) else "s")


def _parts_said(names: list[str], kind: str) -> str:
    count = realise.count_word(len(names))
    said = realise.join_items(names) if len(names) <= 6 else f"{names[0]} to {names[-1]}"
    if kind:
        return PHRASES["in_parts"].format(count=count, kind=_plural(kind), names=said)
    return PHRASES["has_parts"].format(count=count, names=said)


def _numbered_sections(own: list[Fact]) -> tuple[list[Fact], str]:
    """"Phase 1: The Opener", "Phase 2: ...": the heads and the shape, when
    two or more numbers of one kind head the note's sentences. "Psych
    lecture 1: ..." said twice is one lecture's note, not a note in sections."""
    numbered = [(f, m) for f in own if f.heading and f.label and (m := _NUMBERED.match(f.label))]
    kinds = Counter(m.group(1).lower() for m in {m.group(0).lower(): m for _, m in numbered}.values())
    if not kinds or kinds.most_common(1)[0][1] < 2:
        return [], ""
    kind = kinds.most_common(1)[0][0]
    heads = [f for f, m in numbered if m.group(1).lower() == kind]
    return heads, _parts_said([_part_name(f.body) for f in heads], kind)


def _heading_sections(view: composer.NoteView) -> str:
    """The shape of a note in markdown sections, two or more, or ""."""
    content = str(view.note.get("content") or "")
    _, start = composer_read._title(content)
    heads = [h for line in content[start:].splitlines() if (h := composer_read._heading_text(line)) is not None]
    if len(heads) < 2:
        return ""
    labelled = [_split_label(h) for h in heads]
    named = [_NUMBERED.match(x.label) for x in labelled if x.own]
    if len(named) == len(heads) and all(named) and len({m.group(1).lower() for m in named}) == 1:
        return _parts_said([_part_name(x.body) for x in labelled], named[0].group(1))
    return _parts_said([_part_name(h) for h in heads], "")


def _sections(view: composer.NoteView, own: list[Fact]) -> tuple[list[Fact], str]:
    """A note's sections, as the facts that name them and its shape said
    ("it's in four phases: the Opener, ..."), or ([], "") when it has none."""
    heads, shape = _numbered_sections(own)
    return (heads, shape) if shape else ([], _heading_sections(view))


def _sub_head(body: str) -> bool:
    """"Follow- Up Questions:", "Ideas:": a list's own heading, not a fact."""
    return body.rstrip().endswith(":") and len(body.split()) <= 4


def _named_as(view: composer.NoteView, body: str) -> str:
    """"A step by step way to ..." under the title "Complete Social Skills
    Guide" is what the note is: "you saved your Complete Social Skills
    Guide, a step by step way to ..."."""
    title = (view.title or "").strip()
    if not view.titled or not title or len(title.split()) > 6 or re.match(r"(?:the|a|an|my|your)\b", title, re.I):
        return body
    if not re.match(r"(?:a|an)\s", body, re.I):
        return body
    if _FINITE.search(body):
        #: "A sourdough starter is flour and water ...": a sentence, not what
        #: the note is; the note is named, then its words (C2).
        return f"{_note_called(title)} says {_fragment(body, _NAMES.get())}"
    return f"you saved your {title}, {body[0].lower() + body[1:]}"


def _listed(facts: list[Fact]) -> str:
    #: "and one more" names nothing; a single item left over is said (R3-13).
    shown = facts[:GIST_ITEMS + 1] if len(facts) == GIST_ITEMS + 1 else facts[:GIST_ITEMS]
    items = [_fragment(f.body.rstrip("."), _NAMES.get()) for f in shown]
    if len(facts) > len(shown):
        items.append(f"{realise.count_word(len(facts) - len(shown))} more")
    return realise.join_items(items)


@dataclass
class _Sorted:
    """A note's facts by what they are, for its gist."""

    plain: list[Fact] = field(default_factory=list)
    tasks: list[Fact] = field(default_factory=list)
    items: list[Fact] = field(default_factory=list)
    labelled: int = 0


def _sorted(own: list[Fact], heads: list[Fact]) -> _Sorted:
    out = _Sorted()
    for f in own:
        if f in heads or _QUOTED.match(f.body) or _sub_head(f.body):
            continue
        if f.sentence.kind == "task":
            if not f.sentence.done:
                out.tasks.append(f)
        elif f.sentence.kind == "item":
            out.items.append(f)
        elif f.label:
            out.labelled += 1
        else:
            out.plain.append(f)
    _subject_sentence_first(out, own)
    return out


def _subject_sentence_first(out: _Sorted, own: list[Fact]) -> None:
    """A note that holds the subject in one sentence is told by that sentence, not by its first ("Skipped meditation", R9-2)."""
    stems = _SUBJECT_STEMS.get()
    held = [f for f in out.plain if any(composer._holds(st, set(f.sentence.words)) for st in stems)]
    if held and not any(composer._holds(st, own[0].view.title_words | own[0].view.filed_words) for st in stems if own):
        out.plain = held + [f for f in out.plain if f not in held]


def _on_subject(view: composer.NoteView, text: str) -> bool:
    """Whether `text`, an item of `view`, is about what the question asked:
    its note is named for the subject, or it says a word of it. With no
    subject (an overview of a category) everything is."""
    stems = _SUBJECT_STEMS.get()
    #: A note filed under the subject ("Social connections") is on it whole.
    if not stems or any(composer._holds(st, view.title_words | view.filed_words) for st in stems):
        return True
    return bool(stems & {composer._stem(w) for w in re.findall(r"[A-Za-z]{3,}", text)})


def _first_said(view: composer.NoteView, body: str, guide: bool) -> str:
    """The first sentence: what the note is, or the person's own plan."""
    named = _named_as(view, body)
    if named is body and not guide and _ADVICE.match(named) and _verb_led(named):
        return f"{_pick('meant', view.id)} {_fragment(named, _NAMES.get())}"
    return named


def _second_said(view: composer.NoteView, chosen: list[Fact], said: dict[int, str], keep: set[int], guide: bool) -> None:
    """The second sentence against the first: advice to themselves after
    "you ..." ("you interrupt when you're nervous" then "Count to two")
    rides on it; a leading "We" after "you met Daniel" is "You"."""
    a, b = id(chosen[0]), id(chosen[1])
    if not guide and _ADVICE.match(said[b]) and _verb_led(said[b]) and re.match(r"you\b", said[a]):
        said[a] += f", and {_pick('told_self', view.id)} {_fragment(said[b], _NAMES.get())}"
        keep.discard(b)
    elif re.match(r"we\s", said[b], re.I):
        said[b] = "you" + said[b][2:]
    elif _VERB_FIRST.match(said[b][:1].lower() + said[b][1:]):
        #: "Finished your final assignment" after "you put down that uni is
        #: done" has no one doing it (INBOX 1665 g).
        said[b] = _own_subject(said[b][:1].lower() + said[b][1:])


def _list_gist(view: composer.NoteView, items: list[Fact]) -> list[Fact]:
    name = _your_note(view)
    name = name[:1].upper() + name[1:]
    if len(items) == 1:
        #: One item is no list: said as the line it is.
        return items
    if all(f.body.rstrip().endswith("?") for f in items):
        #: "a list: how did that go?, what happened next? And ..." (1420).
        asked = [Fact(f.view, f.sentence, f.label, f.body.rstrip().rstrip("?")) for f in items]
        return [Fact(view, items[0].sentence, "", PHRASES["a_list_asked"].format(name=name, count=realise.count_word(len(items)), items=_listed(asked)))]
    if _context_note(view) or all(_SENTENCES_INSIDE.search(f.body) for f in items):
        #: Each item is whole sentences, a joke's question and its answer: quoted as written, never
        #: run into "and what do you call a fake noodle" (L-chat-19).
        quoted = [Fact(f.view, f.sentence, f.label, f"“{f.body.rstrip().rstrip('.')}”") for f in items]
        return [Fact(view, items[0].sentence, "", PHRASES["a_list"].format(name=name, count=realise.count_word(len(items)), items=_quoted_listed(quoted)))]
    return [Fact(view, items[0].sentence, "", PHRASES["a_list"].format(name=name, count=realise.count_word(len(items)), items=_listed(items)))]


#: "Why don't skeletons fight? They don't have the guts": a sentence ends inside the item.
_SENTENCES_INSIDE = re.compile(r"[?.!] +[A-Z]")


def _quoted_listed(facts: list[Fact]) -> str:
    shown = facts[:GIST_ITEMS + 1] if len(facts) == GIST_ITEMS + 1 else facts[:GIST_ITEMS]
    items = [f.body for f in shown]
    if len(facts) > len(shown):
        items.append(f"{realise.count_word(len(facts) - len(shown))} more")
    return realise.join_items(items)


def _gist_tail(view: composer.NoteView, own: list[Fact], heads: list[Fact], shape: str, sort: _Sorted, chosen: list[Fact], material: bool) -> list[Fact]:
    """The note's closing sentence: its shape, its open tasks, or its list."""
    if not own:
        return []
    if shape:
        return [Fact(view, (heads or sort.tasks or sort.items or own)[0].sentence, "", shape)]
    tasks = [f for f in sort.tasks if _on_subject(view, f.body)]
    if tasks:
        key = "still_list" if all(_verb_led(f.body) for f in tasks) else "still_open"
        said = PHRASES[key].format(items=_listed(tasks), name=_your_note(view))
        return [Fact(view, tasks[0].sentence, "", said, tasks[0].action)]
    if sort.items and not chosen and not sort.labelled and not material:
        return _list_gist(view, sort.items)
    return []


def _gist_kept(own: list[Fact], heads: list[Fact], said: dict[int, str], keep: set[int]) -> list[Fact]:
    """The facts said, in the note's order, each in its new words."""
    return [
        Fact(f.view, f.sentence, f.label, said.get(id(f), f.body), f.action, f.heading)
        for f in own
        if id(f) in keep or (f.label and f.sentence.kind == "prose" and f not in heads and not _QUOTED.match(f.body))
    ]


def _title_said(view: composer.NoteView, body: str) -> str:
    """A note's title said as what was saved (INBOX 1310: "by 27 July,
    **Gym Routine Overview**. Go to the gym" dropped it in as a fragment)."""
    title = (view.title or "").strip()
    if view.titled and body == title and not re.match(r"(?:the|a|an|my|your)\b", title, re.I):
        return f"you saved your {title}"
    return body


_TRAINING = re.compile(r"^(?:push|pull|legs?|upper|lower|chest|back|arms?|shoulders|cardio|core|full body)\b", re.I)
_REST = re.compile(r"^rest(?: days?)?$", re.I)


_DAY_LINE = re.compile(r"^\s*(?:[-*]\s*)?([A-Za-z][\w ]{0,20}?)\s*:\s*(\S.*)$")


def _split_days(content: str) -> tuple[dict[str, list[str]], bool]:
    """A note's training days in the order written, each day's items once,
    and whether it has rest days. Read from the lines, not the sentences: a
    two-word line ("Rest Day", "Pull: deadlifts") is no sentence."""
    items: dict[str, list[str]] = {}
    rest = False
    for line in content.splitlines():
        line = line.strip().rstrip(".")
        day = _DAY_LINE.match(line)
        if day and _TRAINING.match(day.group(1)):
            held = items.setdefault(day.group(1).strip(), [])
            held += [p.strip() for p in re.split(r",(?!\d)\s*(?:and\s+)?|\s+and\s+", day.group(2)) if p.strip() and p.strip() not in held]
        rest = rest or bool(_REST.match(line))
    return items, rest


def _split_shape(view: composer.NoteView, own: list[Fact], days: list[str], rest: bool) -> tuple[str, Fact | None]:
    title = (view.title or "").strip()
    head = next((f for f in own if f.body.strip() == title), None)
    shape = f"a {', '.join(days)} split" + (" with rest days" if rest else "")
    #: A first line the note's own name (INBOX 1515's one title reader) is
    #: not among the body's facts, so the name does not need its fact.
    if title and not re.match(r"(?:the|a|an|my|your)\b", title, re.I) and (head or view.titled):
        return f"you saved your {title}, {shape}", head
    return f"you saved {shape}", head


def _schedule(view: composer.NoteView, own: list[Fact]) -> list[Fact]:
    """A training split said as its shape, each day once (INBOX 1310: "has
    Pull, Push, Legs, Rest Day, Pull, Push and Rest Day"): "you saved your
    Gym Routine Overview, a Pull, Push, Legs split with rest days. Pull days
    have rows and pull-ups; ...". [] for a note that is not one."""
    held = [f for f in own if f.label and _TRAINING.match(f.label)]
    items, rest = _split_days(str(view.note.get("content") or ""))
    if not held or len(items) < 2 or sum(map(len, items.values())) < 3:
        return []
    first, head = _split_shape(view, own, list(items), rest)
    detail = "; ".join(f"{'leg' if d.lower() == 'legs' else d.lower()} days have {realise.join_items(items[d])}" for d in items)
    return [Fact(view, (head or held[0]).sentence, "", first), Fact(view, held[0].sentence, "", detail[:1].upper() + detail[1:])]


def _chosen_facts(chosen: list[Fact]) -> tuple[list[Fact], bool]:
    """A long note is told by its gist: its first sentence, briefly (INBOX 1665 c).
    A picture's caption is another thing the note holds, not a second sentence."""
    long_note = sum(len(f.body.split()) for f in chosen) > composer_brief.BRIEF_WORDS
    if len(chosen) == 2 and long_note and all(getattr(f.sentence, "kind", "prose") == "prose" for f in chosen):
        chosen = chosen[:1]
    return chosen, long_note


def _gist(view: composer.NoteView, own: list[Fact]) -> list[Fact]:
    """One note's facts cut to its gist (see `_QUOTED`), in the note's order:
    labelled facts (its own headings, a to-do, a picture) as they were; the
    rest at most two sentences, its sections or its open tasks the second."""
    planned = _schedule(view, own)
    if planned:
        return planned
    heads, shape = _sections(view, own)
    material = any(_QUOTED.match(f.body) for f in own)
    sort = _sorted(own, heads)
    guide = bool(shape) or material
    chosen, long_note = _chosen_facts(sort.plain[: 1 if (shape or sort.tasks) else 2])
    keep = {id(f) for f in chosen}
    said = {id(f): composer_brief.brief(_title_said(view, f.body.rstrip(":").strip()), squeeze=long_note) for f in chosen}
    if chosen and not sort.labelled:
        said[id(chosen[0])] = _first_said(view, said[id(chosen[0])], guide)
    if len(chosen) == 2:
        _second_said(view, chosen, said, keep, guide)
    return _gist_kept(own, heads, said, keep) + _gist_tail(view, own, heads, shape, sort, chosen, material)


def _gists(members: list, facts: list[Fact]) -> list[Fact]:  # noqa: ANN001
    by_note: dict[int, list[Fact]] = {}
    for f in facts:
        by_note.setdefault(f.view.id, []).append(f)
    out: list[Fact] = []
    for view in members:
        out += _gist(view, by_note.get(view.id, []))
    return out


#: A line that already says when ("on Monday", "yesterday", "last week").
_SAYS_WHEN = re.compile(r"\b(?:(?:on )?(?:mon|tues|wednes|thurs|fri|satur|sun)day|yesterday|today|tonight|last (?:week|month|night|weekend)|this (?:week|morning)|\w+ ago)\b|^(?:back )?in \w+,", re.I)
#: A past-tense line that is not an event: a taste or a report ("you liked
#: pasta", "you mentioned that ...").
_NOT_AN_EVENT = re.compile(
    r"\b(?:liked|loved|enjoyed|wanted|needed|preferred|hated|wished|hoped|mentioned|noted|wrote|said|saved|thought|believed)\b", re.I)


_COMMON = {"that", "this", "with", "your", "have", "were", "from", "about", "then", "they", "them", "there", "back", "also", "still", "after", "before", "into", "over", "when", "what", "went", "told", "said", "note"}


def _one_activity(lines: list[str]) -> bool:
    """Two event lines share a word of their own ("golf", "run")."""
    words = [set(re.findall(r"[a-z]{4,}", x.lower())) - _COMMON for x in lines]
    return any(a & b for i, a in enumerate(words) for b in words[i + 1:])


def _is_event(line: str) -> bool:
    return recognise_questions.told_as_past(line) and not _NOT_AN_EVENT.search(line)


def _event_lines(out: _Out, members) -> list[tuple[int, object]]:  # noqa: ANN001
    """(line index, note) for each told line that is one note's event on a
    day of its own; empty unless two or more notes, on two or more days."""
    by_id = {v.note.get("source_id", v.id): v for v in members}
    told = [(at, by_id.get(row["note_id"])) for at, row in enumerate(out.rows, start=1)]
    events = [(at, v) for at, v in told if v and v.written and at < len(out.lines) and _is_event(out.lines[at])]
    separate = len({v.id for _a, v in events}) >= 2 and len({v.written for _a, v in events}) >= 2
    separate = separate and _one_activity([out.lines[a] for a, _v in events])
    return events if separate and len(out.lines) == len(out.rows) + 1 else []


_DAYS_RE = r"(?:mon|tues|wednes|thurs|fri|satur|sun)day"
_MONTHS_RE = r"(?:jan|febr)uary|march|april|may|june|july|august|(?:sept|nov|dec)ember|october"
#: "On Friday 23 October, you went": the absolute date a weekday carries (1441: relative or none).
_DATED_LEAD = re.compile(rf"^on {_DAYS_RE},? \d{{1,2}} (?:{_MONTHS_RE}),?\s+", re.I)
_DATED_DAY = re.compile(rf"\b({_DAYS_RE}),? (\d{{1,2}}) ({_MONTHS_RE})(?: (\d{{4}}))?\b", re.I)


def _undated_past(found: re.Match, today: date) -> str:
    """The weekday alone for a date gone by; a date still ahead ("Deadline:
    Monday 16 November 2026") is a fact and keeps its day, month and year
    (bt-compcomp-1109 item 4: it was cut to "Monday 2026")."""
    month = [m for m in composer_ask._MONTHS if m.lower().startswith(found.group(3).lower()[:3])]
    try:
        day = date(int(found.group(4) or today.year), composer_ask._MONTHS.index(month[0]) + 1, int(found.group(2)))
    except (ValueError, IndexError):
        return found.group(1)
    return found.group(0) if day >= today else found.group(1)


def _each_says_its_day(out: _Out, members, today: date) -> None:  # noqa: ANN001
    """**Separate events of one activity each say their own day** (INBOX
    1668, the narrow exception to 1441: "the how it went part is kinda
    innaccurate as they are completely separate events and time periods").
    An answer that tells two or more notes, each as something that happened
    on a different day, leads each with its day, relative ("last month", "on
    Monday"), so they read as separate occasions; a line that says its day
    already is left. Every other answer keeps 1441: no day unasked."""
    if _TIMED.get():
        return
    events = _event_lines(out, members)
    held = _REGISTER.set("casual")
    try:
        _drop_absolute_days(out, members, today)
        for at, view in events:
            line = out.lines[at]
            if not _SAYS_WHEN.search(line):
                out.lines[at] = _lead_day(view.written, today) + line[:1].lower() + line[1:]
                #: The citation's words are the line's (grounding finds them in the text).
                out.rows[at - 1]["sentence"] = out.lines[at].rstrip(".")
    finally:
        _REGISTER.reset(held)


def _drop_absolute_days(out: _Out, members, today: date) -> None:  # noqa: ANN001
    """A weekday that came with its date ("On Friday 23 October, you went")
    says its day as any other line does here: relative, or the weekday alone
    (1441: no date unasked). Review of INBOX 1668 c."""
    by_id = {v.note.get("source_id", v.id): v for v in members}
    for at in range(1, len(out.lines)):
        line = out.lines[at]
        if not (_DATED_LEAD.match(line) or _DATED_DAY.search(line)):
            continue
        view = by_id.get(out.rows[at - 1]["note_id"]) if at - 1 < len(out.rows) else None
        bare = _DATED_LEAD.sub("", line)
        if bare != line and view is not None and view.written:
            bare = _lead_day(view.written, today) + bare[:1].lower() + bare[1:]
        else:
            bare = _DATED_DAY.sub(lambda m: _undated_past(m, today), bare[:1].upper() + bare[1:])
        if at - 1 < len(out.rows) and out.rows[at - 1].get("sentence"):
            out.rows[at - 1]["sentence"] = bare.rstrip(".")
        out.lines[at] = bare


def _told_lines(out: _Out, members, facts, today: date, kind: str, moved: str) -> None:  # noqa: ANN001
    told: set = set()
    if not moved:
        for view in members:
            told |= _narrate(out, view, facts, today)
    _lines(out, facts, LINES[kind] - (len(out.lines) - 1), skip=told, by_day=today, more=kind == "overview", weave=True)
    if kind == "overview" and not moved:
        _each_says_its_day(out, members, today)


def _overview_opening(out: _Out, question: str, members, facts, today: date, kind: str, counted=None) -> tuple[str, list[Fact]]:  # noqa: ANN001
    """The overview's first line (the change, the "likes" count or the
    opening), and the facts left to say, each note cut to its gist."""
    topic = _topic(question, members)
    moved = _progress(members, today) if _GOING.search(question) else ""
    if moved:
        out.lines.append(moved)
        quiet = _gone_quiet(members)
        if quiet:
            out.closing.append(quiet)
        return moved, facts
    if kind == "likes":
        times = {1: "once", 2: "twice"}.get(len(members)) or f"{realise.count_word(len(members))} times"
        out.lines.append(PHRASES["likes"].format(topic=topic, times=times, span=_span(members, today)))
    else:
        opening, facts = _opening_line(counted or members, facts, today, topic)
        out.lines.append(opening)
    return moved, _gists(members, facts)


def _below_the_floor(group, by_id: dict, question: str) -> bool:  # noqa: ANN001
    """A loosely related group none of whose notes holds a word of the question is
    padding, not part of the answer: the Also column has it (INBOX 1705)."""
    stems = {composer._stem(w) for w in composer.subject_terms(clean(question))}  # noqa: SLF001
    if group.band != "loose" or group.in_topic or not stems:
        return False
    return not any(composer._holds(st, by_id[i].words | by_id[i].title_words | by_id[i].filed_words) for st in stems for i in group.ids)  # noqa: SLF001


def _framed(out: _Out, question: str, members, facts, today: date, groups: list) -> None:  # noqa: ANN001
    """An overview said by theme, closest first (INBOX 1310, the owner: "it
    just lists every entry, it has no frame of reference"): each group opens
    on one line saying why it answers and how its notes go together, then
    its notes, told oldest first; past the short answer, behind Show more."""
    out.framed = True
    by_id = {v.id: v for v in members}
    told_order = {v.id: n for n, v in enumerate(members)}
    for group in groups:
        #: Named in the order its notes are told below.
        group.ids.sort(key=told_order.get)
    notes = [v.note for v in members]
    topic = _topic(question, members)
    budget = LINES["overview"]
    lead = composer_frame.lead_line(groups, notes, len(members))
    if lead and out.lines:
        out.lines[0] = f"{out.lines[0]} {lead}"
    for n, group in enumerate(groups):
        line = composer_frame.group_line(group, notes, topic, _heading_said, n)
        if _below_the_floor(group, by_id, question):
            continue
        shelf = out.lines if budget > 0 else out.more
        shelf.append(line)
        at, from_lines, from_more = len(shelf) - 1, len(out.lines), len(out.more)
        held = [f for f in facts if f.view.id in group.ids]
        told: set = set()
        for i in group.ids:
            told |= _narrate(out, by_id[i], held, today)
        budget -= min(max(budget, 0), _lines(out, held, max(budget, 0), skip=told, by_day=today, more=True, weave=True))
        #: A quote the group's line made of a whole note is not said again.
        again = composer_frame.echoed(group, notes, " ".join(out.lines[from_lines:] + out.more[from_more:]))
        if again:
            shelf[at] = composer_frame.group_line(group, notes, topic, _heading_said, n, again)


def _in_named_category(question: str, members) -> set[int]:  # noqa: ANN001
    """The members filed in the category the question names."""
    named = (_named_category(clean(question), members) or "").strip().lower()
    return {v.id for v in members if named and str(v.note.get("category") or "").strip().lower() == named}


def _counted_groups(question: str, members, kind: str) -> tuple[list, list | None]:  # noqa: ANN001
    """The frame's groups, and the members the count is of: notes the frame
    calls "more loosely related" are listed as that and not counted, so the
    count and the list share one set (audit 1030 Z9). A note the question's
    own category holds is never loose: it is in the pool, so it is counted
    and told like the rest (INBOX 1665 a: "seven notes" over eleven)."""
    groups = composer_frame.groups([v.note for v in members]) if kind == "overview" and not _GOING.search(question) else []
    held = _in_named_category(question, members)
    for g in groups:
        g.in_topic = g.band == "loose" and set(g.ids) <= held
    loose = {i for g in groups if g.band == "loose" and not g.in_topic for i in g.ids}
    return groups, ([v for v in members if v.id not in loose] if loose else None)


def _overview_tail(out: _Out, kind: str, members, today: date, moved, shown: int) -> None:  # noqa: ANN001
    pattern = "" if moved else _pattern(members, today)
    if pattern:
        out.closing.append(pattern)
    told = {r["note_id"] for r in out.rows}
    hidden = [v for v in members if v.id not in told]
    if kind != "overview" or not hidden:
        return
    #: Every note the opening counts is told, named or counted (INBOX 1524:
    #: "it said 4 notes but only showed or mentioned 2"): a few untold notes
    #: by name, more than that as a count.
    if len(hidden) <= 3 and shown <= LINES[kind]:
        called = [composer_frame.short_name(v.note, _heading_said) for v in hidden]
        names = list(dict.fromkeys(called))
        #: "The other is X" for one, and each note the line names is cited, so
        #: the count, the names and the sources are one set (INBOX 1561).
        out.lines.append(PHRASES["more_named" if len(names) > 1 else "more_named_one"].format(names=realise.join_items(names)))
        for v, name in zip(hidden, called):
            out.rows.append({"sentence": name, "note_id": v.note.get("source_id", v.id), "source": name, "score": 1.0, "digest": True,
                             "kind": getattr(v, "kind", "note")})
    else:
        out.lines.append(PHRASES["more_right"].format(count=_count(len(hidden) + composer_overview.pooled(len(members)) - len(members)).capitalize()))


#: A name a summary line can carry: a title or a short noun phrase, never a
#: quoted sentence or "the note that starts ..." (composer-1031).
_CLEAN_NAME = re.compile(r"^(?!the note that starts|[“\"])")


def _summary_names(members) -> str:  # noqa: ANN001
    """"Cloud computing, Essay plan and eight more": two or three notes by a
    clean name, their own titles first, then how many more (composer-1031,
    item 3)."""
    named = [composer_frame.without_own_day(composer_frame.short_name(v.note, _heading_said)) for v in members]
    order = sorted(range(len(named)), key=lambda i: (not _CLEAN_NAME.match(named[i]), named[i].startswith(("the note", "your ")), i))
    picked = list(dict.fromkeys(named[i] for i in order))[: 3 if len(members) == 3 else 2]
    rest = len(members) - len(picked)
    return realise.join_items([*picked, f"{realise.count_word(rest)} more"] if rest > 0 else picked)


def _summarised(out: _Out, members, kind: str, framed: bool, moved: str) -> bool:  # noqa: ANN001
    """An overview of more notes than it has lines for names a few of them
    and counts the rest, under the count (INBOX 1461: "it just lists every
    entry"); a framed one names its notes by group instead."""
    if kind != "overview" or framed or moved or len(members) <= LINES["overview"]:
        return False
    out.lines.append(_vary("overview_names").format(names=_summary_names(members)))
    return True


def _fold_past_budget(out: _Out, kind: str) -> None:
    """At most LINES[kind] told lines under the opening; the rest go behind
    Show more, in the order told, ahead of what is already folded."""
    keep = 1 + LINES[kind]
    if len(out.lines) > keep:
        out.more[:0] = out.lines[keep:]
        del out.lines[keep:]


def _story_unit(v, gisted: list[Fact], today: date):  # noqa: ANN001, ANN202
    """One note as a clause of the story: its own told line (an event, else its facts), cut down by `composer_story`."""
    scratch = _Out()
    held = [f for f in gisted if f.view.id == v.id]
    _narrate(scratch, v, held, today)
    if not scratch.lines:
        _lines(scratch, held, 1, by_day=today, weave=True)
    return composer_story.clause_of(v, scratch.lines[0] if scratch.lines else "", scratch.rows[0] if scratch.rows else None)


def _story_tellable(members, facts, today: date, lead):  # noqa: ANN001
    """The dated notes, their plan, units and the lead's unit, or None when the notes do not fit the story shape."""
    planned = composer_story.plan_of(members, lead)
    if planned is None:
        return None
    dated, plan = planned
    gisted = _gists(members, facts)
    units = [_story_unit(v, gisted, today) for v in dated]
    first = _story_unit(lead, gisted, today) if lead is not None and lead.written else None
    if None in units or (lead is not None and first is None):
        return None
    return dated, plan, units, first


def _storied(out: _Out, question: str, members, facts, today: date) -> bool:  # noqa: ANN001
    """An overview of several dated notes written as paragraphs (INBOX 1743):
    the lead, a paragraph a stretch, the read of how it went, one insight.
    False, with `out` untouched, when the notes do not fit that shape."""
    lead = members[0] if len(members) > composer_story.MAX_NOTES else None
    told = _story_tellable(members, facts, today, lead)
    if told is None:
        return False
    dated, plan, units, first = told
    out.framed = True
    composer_story.story(out, _count(composer_overview.pooled(len(members))), units, [v.written for v in dated], _topic(question, members), plan, composer_story.themed(dated), (first, lead.written if first else None))
    if (whole := composer_overview.pooled(len(members))) > len(dated) + (lead is not None):
        #: The lead counts every note; the story tells the pool it read, and says so.
        out.lines.append(f"That tells {realise.count_word(len(dated) + (lead is not None))} of the {whole}; ask for a month or a tag to see the rest.")
    return True


#: A question that asks for the figure ("count my notes about Hobart", "how many notes on Sara"): the count, not a story.
_COUNT_ASKED = re.compile(r"^\W*(?:please\s+)?(?:how many|(?:the )?number of|count|tally|check|total)\b", re.I)


def _overview(out: _Out, question: str, members, facts, today: date, kind: str) -> None:  # noqa: ANN001
    if kind == "overview" and not _GOING.search(question) and not _COUNT_ASKED.search(question) and _storied(out, question, _chosen_members(question, members, kind), facts, today):
        return
    groups, counted = _counted_groups(question, members, kind)
    moved, facts = _overview_opening(out, question, members, facts, today, kind, counted)
    shown_notes = {f.view.id for f in facts}
    framed = bool(groups and not moved)
    summed = _summarised(out, counted or members, kind, framed, moved)
    if framed:
        _framed(out, question, members, facts, today, groups)
    else:
        #: The summary heads the lines and is not one of them: the five told
        #: lines and "Show five more" stay as they were (gold B5).
        summary = out.lines.pop() if summed else ""
        _told_lines(out, members, facts, today, kind, moved)
        if summed:
            _fold_past_budget(out, kind)
            out.lines.insert(1, summary)
    #: The pattern line counts the notes the opening counts (audit 1031 C6).
    _overview_tail(out, kind, counted or members, today, moved, len(shown_notes))


_CJK_ENDS = "。！？）」』】〕"
_CJK_STOP = re.compile(r"([。！？）」』】〕\u3040-\u30ff\u4e00-\u9fff])\.(?!\.)")
_GOING = re.compile(r"\bhow(?:'s| is| are) .+ going\b|\bprogress\b|\bhow am i (?:going|doing)\b", re.I)
#: The word a measure is of: "squats" in "squats up to 90 kg".
_MEASURE_OF = re.compile(r"\b([a-z]+)(?: up to| down to| at)? $", re.I)
_FIGURE = re.compile(r"(\d+(?:\.\d+)?)\s?(\S+)")


def _measures(text: str) -> list[tuple[str, float, str, str]]:
    """(what, value, figure, unit) for each measure in `text`: a weight, a
    distance or a time the recogniser reads ("squats up to 90 kg", "ran 5
    km", "30 min"), or a count of reps, beside the word it is of."""
    out = []
    for found in _spans(text, None):
        figure = None
        if found.kind == "duration" or (found.kind == "quantity" and found.value[2] != "ratio"):
            figure = _FIGURE.match(found.text)
        elif found.kind == "number" and text[found.end:found.end + 5].lower() == " reps":
            figure = _FIGURE.match(text[found.start:found.end + 5])
        of = _MEASURE_OF.search(text[:found.start]) if figure else None
        if of:
            out.append((of.group(1).lower(), float(figure.group(1)), figure.group(1), figure.group(2)))
    return out


def _progress(members: list[composer.NoteView], today: date) -> str:
    """"Going up: your squats went from 80 kg to 90 kg": a measure the first
    and the last note both give, said as the change."""
    dated = [v for v in members if v.written]
    if len(dated) < 2:
        return ""
    first, last = dated[0], dated[-1]

    def measures(view: composer.NoteView) -> dict[str, tuple[float, str, str]]:
        found = {}
        for s in view.sentences:
            for word, value, figure, unit in _measures(s.text):
                found.setdefault(word, (value, figure, unit))
        return found

    a, b = measures(first), measures(last)
    for word, (va, ta, unit) in a.items():
        if word in b and b[word][0] != va:
            vb, tb, _ = b[word]
            way = "Going up" if vb > va else "Going down"
            return (f"{way}: your {word} went from {ta} {unit} to {tb} {unit}, "
                    f"{_day(first.written, today)} to {_day(last.written, today)}.")
    return ""


def _week_written(text: str, written: date | None, today: date) -> str:
    """The week a note was written in, said as that week ("this week" in a
    note of 2 September is "in the week of 2 September"): the recogniser
    reads the span, and the one holding the day written is the note's own."""
    if written is None:
        return text
    for found in reversed(_spans(text, written)):
        if found.kind == "range" and found.value[2] == "week" and found.value[0] <= written <= found.value[1]:
            text = f"{text[:found.start]}in the week of {_day(written, today)}{text[found.end:]}"
    return text


def _gone_quiet(members: list[composer.NoteView]) -> str:
    """"Nothing on bench since September": a measure an earlier note gives
    that the latest one does not (B4, how fresh)."""
    dated = [v for v in members if v.written]
    if len(dated) < 2:
        return ""
    said_last = {m[0] for s in dated[-1].sentences for m in _measures(s.text)}
    for v in reversed(dated[:-1]):
        for s in v.sentences:
            for word, *_rest in _measures(s.text):
                if word not in said_last:
                    return PHRASES["gone_quiet"].format(word=word, month=composer_ask._MONTHS[v.written.month - 1])
    return ""


#: "What's the latest on uni", "the most recent thing about X", "when did I
#: last ...": the newest note that fits, not the first the search ranked. Defined in composer_aliases (below the digest).
_LATEST_ASK = composer_aliases.LATEST_ASK


_PRONOUN_OPENERS = frozenset({"he", "she", "they", "his", "her", "their", "hes", "shes"})


#: "what is X", "who's X": an ask for the thing itself, where a note titled X is the answer.
_NAMES_A_THING = re.compile(r"^\s*(?:what|who)(?:'s|’s|\s+(?:is|are|was))\b", re.I)


#: "When is the dentist", "when does the term start": the day still to come, not the one that went by.
_WHEN_NOW = re.compile(r"^\s*(?:when(?:'s|\u2019s|s|\s+(?:is|are|does|will))|what\s+(?:day|date|time)\s+(?:is|are|does|will))\b", re.I)


def _ahead(fact: Fact, today: date) -> bool:
    """Whether the sentence names a day that is today or still to come (R3-18)."""
    from tessellate.ai import composer_body

    return any(fact.sentence.start <= at < fact.sentence.end for _day, at in composer_body._days_named(fact.view, today, "future"))  # noqa: SLF001


#: "When did I last see the dentist": the day that went by, never the booking still ahead.
_WHEN_LAST = re.compile(r"^\s*(?:when\s+(?:did|have)\s+(?:i|we)\s+last|when\s+was\s+the\s+last\s+time\s+(?:i|we))\b", re.I)


def _behind_if(on: bool, fact: Fact, today: date | None) -> bool:
    """Whether a "when did I last" ask is answered by a sentence naming a day that has gone by."""
    from tessellate.ai import composer_body

    return on and today is not None and any(fact.sentence.start <= at < fact.sentence.end for _day, at in composer_body._days_named(fact.view, today, "past"))  # noqa: SLF001


def _ahead_if(on: bool, fact: Fact) -> bool:
    """Whether a present-tense "when" ask is answered by a day still to come (R3-18)."""
    return on and _ahead(fact, _TODAY.get())


#: "what am I reading": the doing as it is going on, which a sentence saying it leads (R3-22).
_AM_DOING = re.compile(r"^\s*what (?:\w+ )?am i (?:\w+ )?([a-z]{3,}ing)\b", re.I)


def _says_now(going_on: re.Pattern | None, fact: Fact) -> bool:
    """Whether the sentence says the doing asked about ("Currently reading Piranesi")."""
    return bool(going_on and going_on.search(fact.sentence.text))


def _opening(fact: Fact) -> bool:
    """Whether the sentence is the first its note says."""
    return bool(fact.view.sentences) and fact.sentence is fact.view.sentences[0]


#: The verb a question asks with ("how do I feed the starter", "who teaches Spanish", "what did Hannah
#: think of it"): the sentence that holds it answers, before one that only names the subject (R9-2).
_ASK_VERB = re.compile(
    r"\b(?:how (?:do|can|should|would|did) (?:i|we|you|they)|what (?:did|do|does|should) (?:i |we |you |they |he |she |\w+ )?|who(?:m)?|how to) *([a-z]{3,})\b", re.I)
#: "how much flour for the starter": the thing asked for is the attribute.
_ASK_NOUN = re.compile(r"\bhow (?:much|many) ([a-z]{3,}) (?:for|of|do|does|did|is|are)\b", re.I)
#: "my last run", "the last one": the newest by the sentence's own day, as "latest" asks.
_LAST_ONE = re.compile(r"\b(?:my|the) last (?!week|month|year|night|weekend|time|few)\w+", re.I)
_NOT_AN_ASK_VERB = frozenset("is are was were have has had get got put find know need mention mentions write wrote the my and for did does".split())
#: What a note says in place of the ask's verb.
_ASK_VERB_SAYS = {
    "think": "think thought loved liked hated enjoyed disliked", "teach": "teach teacher taught", "love": "love loved liked",
    "like": "like liked loved", "eat": "eat eats ate", "live": "live lives lived", "feed": "feed fed",
    "say": "say says said tell tells told", "want": "want wants wanted",
}


#: "why is my bread dense": the word that says what is wrong is the point of the question (R9-2).
_ASK_PREDICATE = re.compile(r"^why (?:is|are|was|were) (?:my|the|our) [a-z]{3,20} (?P<word>[a-z]{4,20})$", re.I)


def _predicate_stems(question: str) -> set[str]:
    """The stem of the word a "why is my X <word>" question asks the reason of; empty for any other question."""
    found = _ASK_PREDICATE.match(" ".join(clean(question).split())[:120].rstrip("?.! ")) if question else None
    return {composer._stem(found["word"].lower())} if found else set()  # noqa: SLF001


def _ask_stems(question: str) -> set[str]:
    """The stems that say the question's own verb: empty when it has none."""
    found = _ASK_VERB.search(clean(question)) or _ASK_NOUN.search(clean(question))
    verb = (found.group(1) if found else "").lower()
    if not verb or verb in _NOT_AN_ASK_VERB:
        return set()
    stem = composer._stem(verb)  # noqa: SLF001
    return {stem, *(composer._stem(w) for w in _ASK_VERB_SAYS.get(stem, "").split())}  # noqa: SLF001


def _sentence_day(fact: Fact) -> date:
    """The latest day the sentence names itself ("ran 12 km on 8 November"), else the day it was written."""
    days = [f.value.date() if isinstance(f.value, datetime) else f.value for f in _spans(fact.sentence.text, fact.view.written) if f.kind in ("date", "datetime")]
    return max(days) if days else (fact.view.written or date.min)


def _fact_words(f: Fact) -> set:
    """"He works on the data team" in the note titled "Tom" is Tom's line (audit 1031 C1); a sentence's own words beat the note's."""
    words = set(f.sentence.words)
    return words | f.view.title_words if f.sentence.words and f.sentence.words[0] in _PRONOUN_OPENERS else words


def _says_the_ask(f: Fact, words: set, asks: set, stems: set, predicate: frozenset | set = frozenset()) -> bool:  # noqa: B008
    """The sentence that holds the ask's own verb, in a note that holds the rest of the subject (R9-2), or the
    word a "why is my bread dense" asks the reason of (R9-2)."""
    if any(composer._holds(st, words) for st in predicate):  # noqa: SLF001
        return True
    if not asks or not any(composer._holds(st, words) for st in asks):
        return False
    return all(composer._holds(st, f.view.words | f.view.title_words | f.view.filed_words) for st in stems - asks)


def _names_it(text: str, names_a_thing: bool, subject_words: list) -> bool:
    """"is called Doug", "Builder is Marek": the sentence says what the subject is (R9-3)."""
    if not (names_a_thing and subject_words):
        return False
    return bool(re.search(rf"\b(?:is|are|was) (?:called |named |known as )?(?:the )?{re.escape(' '.join(subject_words))}\b", text, re.I))


def _yes_no(question: str) -> bool:
    from tessellate.ai import composer_intent  # at the call: composer_intent reads the digest

    return bool(composer_intent._PRESENT_ASK.match(question or ""))  # noqa: SLF001


def _titled_for_yes_no(f: Fact, stems: set[str], yes_no: bool) -> bool:
    """A yes/no ask's subject is the note titled for it."""
    return bool(yes_no and stems and f.view.titled and all(composer._holds(st, f.view.title_words) for st in stems))


#: Words a heading can carry beside its subject and still be the note that defines it: "Reading list", "Budget November".
_HEADING_EXTRA = frozenset({"list", "checklist", "note", "notes", *(m for m in ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"))})


def _title_is_subject(f: Fact, stems: set[str]) -> bool:
    """The note's heading is the subject, bar a kind or month word: the note that defines it (F8, 1110).
    "Dentist bill" is a note about a bill, so a line on the dentist can beat it."""
    return bool(stems and f.view.titled and all(composer._holds(st, f.view.title_words) for st in stems)  # noqa: SLF001
                and not {w for w in f.view.title_words if not composer._holds(w, stems)} - _HEADING_EXTRA)  # noqa: SLF001


#: "when did I buy that gaming mouse": one thing that happened, asked for
#: its day, against "when are my uni days" (a habit, said as its days).
_WHEN_DID = re.compile(r"^\s*when (?:did|was|were|have|had|do i|i)\b", re.I)


#: The composer's grammar pass (INBOX 1299): closed lists, no model. Words
#: the person wrote are never touched: quoted spans, links, addresses, file
#: names and a joke's or quote's own sentences are set aside first.
#: Spelled for writing capitals, never read into a date (that is
#: `ai/recognise.py`'s), so they come from the calendar module.
_WEEKDAY_WORDS = frozenset(name.lower() for name in calendar.day_name)
_WEEKDAYS = "|".join(sorted(_WEEKDAY_WORDS))
#: "may" and "march" are also words: they are months only beside a day number.
_MONTH_NAMES = "january|february|april|june|july|august|september|october|november|december"
_DAY_NAME = re.compile(rf"\b(?:{_WEEKDAYS}|{_MONTH_NAMES})\b", re.I)


def _chosen_members(question: str, members, kind: str):  # noqa: ANN001
    """The notes an overview counts: the ones the frame does not call loosely related."""
    return _counted_groups(question, members, kind)[1] or members
