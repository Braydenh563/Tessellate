"""The conversation around an answer: the next questions to offer, a
follow-on ("tell me more", "the second one") read against the turn before,
and `Dialogue`, the turns so far.

Moved whole from `composer.py` (audit AR3, gods-1101): the code is unchanged,
and `composer` re-exports every name here that anything reads, so
`composer.follow_on` still works. Imports run one way, down
the layer list in `composer.py`'s docstring, never back to `composer`.
"""

from __future__ import annotations

import calendar
import hashlib
import re
from dataclasses import dataclass, field
from datetime import date as date_type, datetime, time as time_type
from typing import TYPE_CHECKING, Any

from tessellate.ai import composer_chip_subject, composer_tables, composer_frame, composer_shift, question_noise, recognise as rec, repair_turn, when as when_words
from tessellate.ai.composer_ask import _stem, _words, classify, compare_sides, rephrase, subject_terms
from tessellate.ai.composer_body import _BRIEF, _FULL, _NOTE_NOUNS, _asked_span
from tessellate.ai.composer_phrases import PHRASES
from tessellate.ai.composer_quote import _pick
from tessellate.ai.composer_read import NoteView
from tessellate.core import clock
from tessellate.search import query as query_understanding
from tessellate.core.lazyre import lazy_compile

if TYPE_CHECKING:
    from tessellate.ai.composer_answer import _Answer


# --- what to ask next -----------------------------------------------------------

#: A suggested question longer than this is not a chip (`followups.MAX_LENGTH`).
NEXT_MAX_CHARS = 90


def _own_terms(terms: list[str]) -> list[str]:
    """"notes" is how the question was put, not what it is about: the chip
    once asked "What is the latest on notes about sourdough?" (row 410)."""
    return [t for t in terms if t.lower() not in _NOTE_NOUNS]


def _tag_holders(views: list[NoteView], asked: set[str]) -> dict[str, list[NoteView]]:
    holders: dict[str, list[NoteView]] = {}
    for view in sorted(views, key=lambda v: v.rank):
        if view.note.get("connected"):
            continue
        for tag in dict.fromkeys(str(t) for t in (view.note.get("tags") or [])):
            if re.fullmatch(r"\w[\w -]{1,30}", tag) and _words(tag) and not set(_words(tag)) & asked:
                holders.setdefault(tag.lower(), []).append(view)
    return holders


def _shared_tag_pick(views: list[NoteView], asked: set[str], cited: set[int]) -> list[tuple] | None:
    #: A tag two or more of the notes found share, the question did not name:
    #: a thread through them ("harbor" under a question about beta testers).
    #: One note's tag alone ("admin" on the dentist note) is not a thread.
    holders = _tag_holders(views, asked)
    shared = [(tag, held) for tag, held in holders.items() if len(held) >= 2 and any(v.id in cited for v in held)]
    if not shared:
        return None
    tag, held = max(shared, key=lambda pair: (len(pair[1]), -min(v.rank for v in pair[1])))
    view = next(v for v in held if v.id in cited)
    original = next(str(t) for t in view.note.get("tags") or [] if str(t).lower() == tag)
    return [("template", PHRASES["next_tag_a"]), ("filed", original, view.id), ("template", PHRASES["next_tag_b"])]


def _unquoted_note_pick(views: list[NoteView], asked: set[str], cited: set[int]) -> list[tuple] | None:
    #: A note found and not quoted that has something to say about the
    #: question (a sentence of it scored at least half the best), by its name.
    best = max((s.score for v in views for s in v.sentences), default=0.0)
    for view in sorted(views, key=lambda v: v.rank):
        if view.id in cited or view.note.get("connected") or not view.titled:
            continue
        if (view.title_words and view.title_words <= asked) or not any(s.score >= best / 2 > 0 for s in view.sentences):
            continue
        return [("template", PHRASES["next_note_a"]), ("title", view.title, view.id), ("template", PHRASES["next_note_b"])]
    return None


def _subject_pick(question: str, shape: str, terms: list[str], views: list[NoteView] = ()) -> list[tuple] | None:  # noqa: B006
    #: The question's own subject, when it is a short name ("dentist
    #: check-up", "sourdough"), asked the other way round in time.
    own = _own_terms(terms)
    subject = _asked_span(question, own)
    #: A noun phrase the notes use, never the question's leftover words (R9-1).
    subject = composer_chip_subject.clean(subject, views, question) if subject else subject
    #: Never a stop word, a pronoun or a piece of a contraction (INBOX 1590: "about ve").
    if subject and query_understanding.is_chip_subject(subject) and len(subject.split()) == len(own) <= 3 and shape not in ("status", "recent", "compare", "yesno"):
        #: A yes or no question's span holds its predicate ("Harbor work offline"): no subject to ask the latest on.
        prefix = "next_latest_a" if shape == "when" or _pick(question, "next", ["a", "b"]) == "a" else "next_when_a"
        return [("template", PHRASES[prefix]), ("asked", subject), ("template", PHRASES["next_tag_b"])]
    return None


def _next_questions(question: str, shape: str, terms: list[str], views: list[NoteView], cited: set[int]) -> list[list[tuple]]:
    """Two or three questions the answer opens up, built from what it found and
    did not say (INBOX 725, 5): a tag of the notes it quoted that the question
    did not name, a note it found and did not quote, and the latest on the
    question's own subject. Each is a fixed question around the person's own
    words, so a chip never offers what the notes cannot answer about."""
    asked = {_stem(t) for t in terms} | {_stem(w) for w in query_understanding.search_terms(question)}
    #: "random ahh" names no subject: the chips about it would ask for nothing.
    if question_noise.filler_subject(" ".join(terms)):
        terms = []
    found = (
        _shared_tag_pick(views, asked, cited),
        _unquoted_note_pick(views, asked, cited),
        _subject_pick(question, shape, terms, views),
    )
    picks = [pick for pick in found if pick]
    out = [p for p in picks if len("".join(part[1] for part in p)) <= NEXT_MAX_CHARS]
    return out[:3]


# --- a follow-up, read against the turn before ----------------------------------

_MORE = lazy_compile(
    r"^\s*(?:tell me more|more|go on|continue|keep going|say more|what else|anything else|and|more please|"
    r"more about (?:that|it|this|those)|(?:and |what about |what are )?the (?:others|rest|other ones))[\s?.]*$",
    re.I,
)


_ORDINALS = {"first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2, "fourth": 3, "4th": 3, "fifth": 4, "5th": 4, "last": -1}


_ORDINAL = lazy_compile(r"\bthe (first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th|last) (?:one|note)\b", re.I)


_PRONOUN = lazy_compile(r"\b(it|that|this|them|those|they)\b", re.I)


#: A question that leans on the answer before it (audit 1030 Z53): it opens
#: with an asking word and either says "it" or has no subject of its own.
_ASKS_SLOT = lazy_compile(r"^(?:and |so |ok |okay )*(?:what|when|where|who|which|how|why|is|are|was|were|does|do|did|can|could|will|would|should)\b", re.I)


_SLOT_PRONOUN = lazy_compile(r"\b(?:it|its|that|them|those)\b", re.I)


#: A question about a total or an instance with no subject of its own:
#: "how far in total", "what's the total", "when was the last one".
_TOTAL_WORDS = frozenset({"far", "much", "many", "long", "total", "last", "latest", "first", "next", "previous", "one", "altogether"})


_TOTAL_ASK = lazy_compile(
    r"^(?:and |so |ok |okay )*(?:what|when|where|how)\b(?!.*(?-i:[A-Z]\w|\d))"
    r"(?=.*\b(?:in total|in all|altogether|the total|(?:the )?(?:last|latest|first|next|previous) one)\b)[^.]*$",
    re.I,
)


#: A pronoun that is the point of the phrase, not a reference to a note.
_NOT_REFERRING = lazy_compile(r"\b(?:what|how|when) (?:is|was) (?:it|that) like\b|\bwhat is (?:it|that)\b$|\bhow is it\b", re.I)


def refers_back(question: str) -> bool:
    """Whether `question` is about whatever the last answer was about: it says
    "it" ("when is it", "how much does it cost", "what did we decide about
    it") or has no subject of its own ("what time", "who is it with"). Not a
    question with a name, a number or a time window of its own, nor one that
    compares: those stand alone."""
    q = " ".join((question or "").split()).rstrip("?.! ")
    if not q or not _ASKS_SLOT.match(q) or _NOT_REFERRING.search(q) or rec.without_windows(q) != q:
        return False
    if re.search(r"\b[A-Z][a-z]|\d|\b(?:compare|versus|vs|than|between)\b", q[1:]):
        return False
    pronoun = bool(_SLOT_PRONOUN.search(q))
    return pronoun or not [t for t in subject_terms(q) if not _SLOT_PRONOUN.fullmatch(t)]


#: "what about the boiler?", "and the boiler?", "how about Porto": the turn
#: before asked again of something else (INBOX 741, turn-aware follow-ons).
_SWAP = lazy_compile(
    r"^\s*(?:(?:and|but|ok|okay|so)[, ]+)?(?:what|how) about\s+(?P<x>[^\s,].*)$"
    r"|^\s*(?:and|but)\s+(?P<y>(?!(?:what|when|who|where|why|how|which|is|are|do|does|did)\b)[^\s?].*)$",
    re.I,
)


#: "why?", "and when?", "how come?": the asking word alone, about the turn
#: before's subject.
#: The "Did you mean “how”?" chip, pressed.
#: Closing quote and "?" come off in code: `(.+?)...\s*\?*\s*$` was quadratic
#: on a run of whitespace (CodeQL); so for `_CORRECTION`, `_LENGTH`,
#: `_WINDOW_ONLY` and `_BARE` below.
_MEANT = lazy_compile(r"^\s*did you mean\s+[“\"']?(\S.*)$", re.I)


_BARE = lazy_compile(r"^\s*(?:(?:and|but|so|ok|okay)[, ]+)?(why|when|where|who|how come|how many|how much|how|since when)[\s?.!]*$", re.I)


_BOLD = lazy_compile(r"\*\*(.+?)\*\*")


#: "no, the gym one", "not that one, the running note", "I meant the dentist
#: note": the turn before answered from the wrong note (decision 35).
_CORRECTION = lazy_compile(
    r"^\s*(?:no|nope|not that(?: one)?|wrong one|not quite)[,.!]?\s+(?:i meant\s+|i mean\s+|the one about\s+)?(?P<x>\S.*)$"
    r"|^\s*i meant\s+(?P<x2>\S.*)$",
    re.I,
)


#: "shorter", "in more detail": the turn before again, at another length.
_LENGTH = lazy_compile(
    r"^\s*(?:shorter|briefer|briefly|less|in short|tl;?dr|summari[sz]e that|longer|more detail|in (?:more )?detail|"
    r"(?:make it|say it|be|can you be) (?:shorter|briefer|longer|more detailed))(?:\s+please)?[\s.?!]*$",
    re.I,
)


#: "and last week?", "what about yesterday?": the turn before over another time.
_WINDOW_ONLY = lazy_compile(r"^\s*(?:(?:and|but|so|ok)[, ]+)?(?:(?:what|how) about\s+)?(?P<w>[^\s,].*)$", re.I)


def _without_length(question: str) -> str:
    """The question with a length wish ("briefly", "in detail") taken off."""
    text = _BRIEF.sub("", question)
    text = _FULL.sub("", text)
    return " ".join(text.replace(" ,", ",").split()).strip(" ,")


@dataclass
class FollowOn:
    """A question read against the turn before it: `question` is what is
    searched for and answered, `previous` the earlier question it leans on,
    `said` the earlier answer (a "tell me more" quotes something new)."""

    question: str
    previous: str
    said: str = ""
    kind: str = "more"
    #: A correction's words ("no, the gym one": "gym"): the notes they name
    #: are put first, the ones the answer before quoted after (decision 35).
    prefer: str = ""
    #: The question a later terse turn leans on in place of this one, when this one only asked a
    #: property of the subject ("what should I pack"): the subject's own question stays the one.
    stands: str = ""
    #: The notes the last answer's frame says this turn is about ("who is it with" after the
    #: dentist answer): read like an open note, rechecked by the server (`chat_turn._cited_scope`).
    note_ids: tuple = ()
    #: Asked instead when the reading gives the answer before again ("and kyoto?" after the
    #: budget is not the budget twice): the new subject asked plainly (fable-composer-1110 F1).
    fallback: str = ""


def _named_notes(answer: str) -> list[str]:
    """The notes an earlier composed answer named, in the order it named
    them: its bold names, less the bold words that are not a note's."""
    fixed = {value.strip("* ") for value in PHRASES.values()}
    names: list[str] = []
    for name in _BOLD.findall(answer or ""):
        if name not in fixed and name not in names:
            names.append(name)
    return names


#: "Which is the main note on uni", "which one is the defining note": the
#: note that is plainly about the subject (`composer_digest._defines`), asked
#: for, not a note property to search for (audit 1031 C26).
_DEFINING_WORD = r"(?:main|defining|key|best|central|principal|primary|core|top|most important|definitive)"


_DEFINING = lazy_compile(
    rf"(?:and |so |ok |okay )?(?:which|whats?)(?:'s| is| one is| note is| one's)?(?: (?:is|note is|one is))? (?:my |the |your )?{_DEFINING_WORD}"
    r"(?: (?:note|one|entry))?(?: (?:note|one|entry))?(?: (?:on|about|for|in|of) (?P<x>.+?))?[?.!\s]*",
    re.I,
)


def _defining_ask(question: str, turns: list[dict]) -> FollowOn | None:
    """The overview of the subject, whose lead is its defining note: the
    subject is named, or the earlier question's."""
    found = _DEFINING.fullmatch((question or "").strip())
    if not found:
        return None
    previous = str(turns[-1].get("question") or "").strip() if turns else ""
    named = re.sub(r"^(?:the|my|our)\s+", "", (found.group("x") or "").strip(), flags=re.I)
    terms = subject_terms(previous) if previous else []
    subject = named or (_asked_span(previous, terms) or " ".join(terms) if previous else "")
    return FollowOn(f"what do I know about {subject}", previous, "", "subject") if subject else None


#: "what did I just add", "what have I last written": the newest note, asked plainly (ledger 1112 F4).
_JUST_MADE = lazy_compile(
    r"(?:and |so |ok |okay )?what (?:did|have) i (?:just |last |most recently |only )?(?:add|added|write|written|wrote|save|saved|create|created|make|made|jot|jotted|put|type|typed)(?: down| in| here| in here| to (?:my|the) (?:notes|notebook))?[?.!\s]*",
    re.I,
)


#: A bare "who am I going with" is the line a trip note holds, "Travelling with Sam" (F13 a).
_GOING_WITH = lazy_compile(r"who am i going with[?.!\s]*", re.I)


def said_plainly(question: str) -> FollowOn | None:
    """A question that needs no turn before it, said as the notes hold it ("what did I just add", "who am I going with")."""
    text = (question or "").strip()
    if _JUST_MADE.fullmatch(text):
        return FollowOn("what is my newest note", "", "", "subject")
    return FollowOn("who am I travelling with", "", "", "subject") if _GOING_WITH.fullmatch(text) else None


_ABOUT_THE_TALK = lazy_compile(r"^\s*(?:thanks|thank you|thx|cheers)\b|\b(?:did|are|were) you\b(?! mean)|\bwhere(?:'d| did) you\b", re.I)


def _spoken_turns(history: list[dict] | None) -> list[dict]:
    return [t for t in (history or []) if str(t.get("question") or "").strip() and not question_noise.social_kind(str(t.get("question") or ""))]


def follow_on(question: str, history: list[dict] | None) -> FollowOn | None:
    """"Tell me more", "what about the second one", "when was that": a
    follow-up that only means something against the turn before (INBOX 725,
    6). None for a question that stands on its own, or with no turn before.

    - "Tell me more" is the earlier question again, quoting what it did not.
    - "The second one" is the second note the earlier answer named.
    - A question whose only subject is "it" or "that" takes the earlier
      question's subject in its place.
    """
    #: Small talk between ("ty", "lol ok") is not the turn a follow-on leans
    #: on: "what about the boiler?" after "ty" still means the question
    #: before the thanks (measured in Chat, INBOX 741).
    turns = _spoken_turns(history)
    defining = _defining_ask(question, turns) or (None if turns else said_plainly(question))
    if defining is not None:
        return defining
    #: "I don't need that" is a reply, not a question about "that" (INBOX 1668 b); "thanks that's
    #: all" and "where did you get that" are about the talk, not a subject (fable-composer-1110 F1).
    if not turns or repair_turn.is_repair(question) or _ABOUT_THE_TALK.search(question or ""):
        return None
    standing = _standing(turns)
    #: Said plainly last: after an answer these bind to the framed note first (F13 a); the server
    #: lets the binding go when that note has no such line (`chat_turn._framed_scope`).
    return _follow_one(question, standing) or _follow_one_repaired(question, standing) or said_plainly(question)


def _follow_one_repaired(question: str, standing: list[dict]) -> FollowOn | None:
    """A follow-on typed with a slip ("any othjer notes around that time") is
    read as the words the speller puts it right to, as the answer itself is
    (INBOX 1739); a question needing no repair is not read twice."""
    tidy = question_noise.tidy(" ".join((question or "").split()))
    repaired = question_noise.repair(tidy)
    return _follow_one(repaired, standing) if repaired and repaired != tidy else None


#: Follow-on kinds whose reading is a question in its own right ("and last
#: week?", "what about Lisbon?"). The others ("longer", "why?", "no, the
#: launch one") lean on the question before, which stays the one the next
#: terse turn leans on: "why?" after "longer" asks about the subject, not
#: about "longer".
_RESTATES = frozenset({"window", "subject", "entity", "pronoun", "did_you_mean", "ordinal", "part", "bound"})


def _standing(turns: list[dict]) -> list[dict]:
    """The turns with each terse one replaced by the question it stood for,
    read forwards, so a follow-on never leans on another follow-on's words."""
    out: list[dict] = []
    for turn in turns:
        text = str(turn.get("question") or "").strip()
        follow = _follow_one(text, out) if out else None
        prefer = ""
        if follow:
            text = follow.stands or (follow.question if follow.kind in _RESTATES else follow.previous)
            #: A correction's note stays chosen for the turns that lean on it:
            #: "no, the data structures one", then "shorter", is still that note (B8).
            prefer = follow.prefer or (out[-1].get("prefer", "") if follow.kind != "subject" else "")
        out.append({**turn, "question": text, "prefer": prefer})
    return out


#: A reader that does not recognise the turn returns this, so the next one is
#: tried; None means "recognised, and nothing to lean on", which ends the read.
_NOT_THIS: Any = object()


def _follow_more(text: str, previous: str, last: dict, turns: list[dict]) -> Any:
    if not _MORE.match(text):
        return _NOT_THIS
    #: A "more" after a "more" still means the question before both.
    for turn in reversed(turns):
        if not _MORE.match(str(turn.get("question") or "")):
            previous = str(turn.get("question") or "").strip()
            break
    said = "\n".join(str(t.get("answer") or "") for t in turns[-3:])
    return FollowOn(previous, previous, said, "more")


def _follow_ordinal(text: str, previous: str, last: dict, turns: list[dict]) -> Any:
    ordinal = _ORDINAL.search(text)
    if not ordinal:
        return _NOT_THIS
    names = _named_notes(str(last.get("answer") or ""))
    index = _ORDINALS[ordinal.group(1).lower()]
    if names and (index == -1 or index < len(names)):
        resolved = text[: ordinal.start()] + f"“{names[index]}”" + text[ordinal.end():]
        return FollowOn(resolved, previous, "", "ordinal")
    #: No list to count in: "when was the last one" may still lean on the subject.
    return _NOT_THIS


#: "the third item", "how many are left" after a checklist answer (CHAT_PLAN U13): said again about that list.
_ITEM_NTH = lazy_compile(r"^\s*(?:and |what(?:'s| is) )?(?:the )?(first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th|last)(?: item| one| thing)?[\s?.]*$", re.I)
_ITEMS_LEFT = lazy_compile(r"^\s*(?:and )?how many (?:items |are |is )*(left|open|done|remaining|ticked|unticked|to go)[\s?.]*$", re.I)
_LIST_NAME = lazy_compile(r"\bYour (?:note )?\**([^*\n]+?)\**(?: note)? has\b")


def _follow_item(text: str, previous: str, last: dict, turns: list[dict]) -> Any:
    nth, left = _ITEM_NTH.match(text), _ITEMS_LEFT.match(text)
    if not (nth or left):
        return _NOT_THIS
    #: The list may be a turn or two back ("the second one", then "how many are left").
    named = next((m for t in reversed(turns[-4:]) if "- [" in str(t.get("answer") or "") and (m := _LIST_NAME.search(str(t.get("answer"))))), None)
    if not named:
        return _NOT_THIS
    if nth:
        return FollowOn(f"what is the {nth.group(1).lower()} item on the {named.group(1)}", previous, "", "ordinal")
    if left:
        state = "done" if left.group(1).lower() in ("done", "ticked") else "open"
        return FollowOn(f"how many items are {state} on the {named.group(1)}", previous, "", "ordinal")
    return _NOT_THIS


def _follow_correction(text: str, previous: str, last: dict, turns: list[dict]) -> Any:
    correction = _CORRECTION.match(text)
    #: "no, that's wrong" complains; it names no note to prefer (INBOX 1668 b).
    if not correction or repair_turn.is_repair(text):
        return _NOT_THIS
    #: The second alternative ("I meant the dentist note") fills x2, not x.
    said = (correction.group("x") or correction.group("x2") or "").rstrip(" \t.?!")
    prefer = re.sub(r"^(?:the|my|that|this)\s+", "", said.strip(), flags=re.I)
    prefer = re.sub(r"\s(?:one|note|entry)$", "", prefer, flags=re.I).strip()
    return FollowOn(previous, previous, "", "correction", prefer) if prefer else _NOT_THIS


def _follow_length(text: str, previous: str, last: dict, turns: list[dict]) -> Any:
    if not _LENGTH.match(text):
        return _NOT_THIS
    shorter = text.lstrip().lower().startswith(("shorter", "briefer", "briefly", "in short", "tl;dr", "tldr", "summarise that", "summarize that", "less"))
    base = _without_length(previous)
    return FollowOn(f"briefly, {base}" if shorter else f"{base.rstrip('?.!')} in detail?", previous, "", "length", str(last.get("prefer") or ""))


def _follow_shift(text: str, previous: str, last: dict, turns: list[dict]) -> Any:
    """"and the week before?", "what else is on that week?" (`composer_shift`)."""
    asked = composer_shift.follow(text, previous, last, clock.today())
    return FollowOn(asked, previous, "", "window") if asked else _NOT_THIS


def _follow_window(text: str, previous: str, last: dict, turns: list[dict]) -> Any:
    window = _WINDOW_ONLY.match(text)
    window_text = window.group("w").rstrip(" \t?.!") if window else ""
    found_time = when_words.find(window_text) if window else []
    #: Only a turn that is nothing but a time ("and last week?"): "what did
    #: I write yesterday" is a question of its own.
    if not (found_time and not window_text.replace(found_time[0][2], "").strip(" ,")):
        return _NOT_THIS
    base = previous
    if not when_words.find(previous):
        #: "what about yesterday" after "summarise it": the turn that had a time is asked again,
        #: not "summarise first yesterday" (fable-composer-1110 F1).
        base = next((q for q in (str(t.get("question") or "") for t in reversed(turns[:-1])) if when_words.find(q)), previous)
    for _s, _e, old_phrase in when_words.find(base):
        base = base.replace(old_phrase, "")
    base = " ".join(base.split()).rstrip(" ?.!")
    return FollowOn(f"{base} {found_time[0][2]}?", previous, "", "window")


def _follow_meant(text: str, previous: str, last: dict, turns: list[dict]) -> Any:
    meant = _MEANT.match(text)
    if not meant:
        return _NOT_THIS
    word = meant.group(1).rstrip(" \t?").rstrip("”\"'").strip(" \t?")
    tokens = re.findall(r"[\w']+", previous)
    candidates = [t for t in tokens if t.lower() != word.lower() and len(t) >= 2]
    if not candidates:
        return None
    typed = min(candidates, key=lambda t: question_noise.distance(t, word))
    if question_noise.distance(typed, word) > max(1.0, question_noise.allowance(word) + 0.5):
        return None
    resolved = re.sub(rf"\b{re.escape(typed)}\b", word, previous, count=1)
    return FollowOn(resolved, previous, "", "did_you_mean")


def _follow_bare(text: str, previous: str, last: dict, turns: list[dict]) -> Any:
    bare = _BARE.match(text) or _BARE.match(rephrase(text))
    if not bare:
        return _NOT_THIS
    subject = _asked_span(previous, subject_terms(previous))
    if not subject:
        return None
    start = previous.lower().find(subject.lower())
    article = re.search(r"\b(?:the|my|our|a|an)\s+$", previous[:start], re.I)
    subject = previous[article.start():start] + subject if article else subject
    word = bare.group(1).lower()
    word = "why" if word == "how come" else word
    verb = {"why": "", "how": "do I", "how many": "", "how much": "is", "since when": ""}.get(word, "is")
    resolved = " ".join(w for w in (word.capitalize(), verb, subject) if w) + "?"
    return FollowOn(resolved, previous, "", word)


def _swap_in_shape(previous: str, other: str, subject: str, entity: bool) -> FollowOn:
    """The previous question with its subject swapped for `other`, when the
    question has a shape of its own."""
    start = previous.lower().find(subject.lower())
    before = previous[:start]
    if re.search(r"\b(the|my|a|an)\s+$", before, re.I):
        #: "and kyoto?" after "how much is the budget" is "how much is kyoto", not "the kyoto".
        bare = " " not in other.strip() and not entity
        other = re.sub(r"^(the|my|a|an)\s+", "", other, flags=re.I)
        before = re.sub(r"\b(?:the|a|an)\s+$", "", before, flags=re.I) if bare else before
    resolved = before + other + previous[start + len(subject):]
    return FollowOn(resolved, previous, "", "entity" if entity else "subject", fallback=f"what do my notes say about {other}?")


def _swap_plain_what(previous: str, other: str, subject: str, entity: bool) -> FollowOn:
    #: A plain "what" asked again of something else ("what did I do
    #: at the gym", then "what about running?"): the subject's phrase
    #: (its preposition and article too) gives way to the new one.
    start = previous.lower().find(subject.lower())
    lead_in = re.search(r"(?:\b(?:at|in|on|for|about|with|of|to)\s+)?(?:\b(?:the|my|a|an)\s+)?$", previous[:start], re.I)
    head = previous[: lead_in.start() if lead_in else start].rstrip()
    tail = previous[start + len(subject):]
    kind = "entity" if entity else "subject"
    if re.search(r"\b(?:is|are|was|were|'s)$", head, re.I):
        #: "What is the launch plan?" then "what about the boiler?":
        #: not "what is the boiler", which asks something else.
        return FollowOn(f"What do my notes say about {other}?", previous, "", kind)
    bare_other = re.sub(r"^(the|my|a|an)\s+", "", other, flags=re.I)
    joined = f"with {other}" if entity else f"about {bare_other}"
    return FollowOn(f"{head} {joined}{tail}", previous, "", kind)


#: A question that asked for an act ("remind me about it a week before") is not asked again of
#: something else: "what about mia" after it stands as typed (fable-composer-1110 F1).
_ACT_LEAD = lazy_compile(r"^\s*(?:remind|add|delete|remove|tick|untick|rename|move|tag|pin|create|cancel|undo|new note)\b", re.I)


def _follow_swap(text: str, previous: str, last: dict, turns: list[dict]) -> Any:
    person = _person_swap(text, last)
    if person is not None:
        return person
    if _ACT_LEAD.match(previous) and (_SWAP.match(text) or _SWAP.match(rephrase(text))):
        return None
    return _swap_reading(text, previous)


#: "and the dentist" with no "?" after a question: a thing of its own (an article, then up to three words), so it
#: asks the turn before again of it (L-chat-9); "and I went home" or "and then" is a statement.
_BARE_AND_THING = lazy_compile(r"^(?:the|my|our|his|her|their)\s+[a-z][\w'-]*(?:\s+[a-z][\w'-]*){0,2}$", re.I)


def _statement_not_ask(swap: Any, text: str) -> bool:
    """A swap with a side but no "?" is a statement, unless the side is a bare thing ("and the dentist")."""
    return swap.group("y") is not None and not text.rstrip().endswith("?") and not _BARE_AND_THING.match(swap.group("y").strip())


def _swap_reading(text: str, previous: str) -> Any:
    swap = _SWAP.match(text) or _SWAP.match(rephrase(text))
    if swap and _statement_not_ask(swap, text):
        swap = None
    if not swap:
        return _NOT_THIS
    other = (swap.group("x") or swap.group("y") or "").rstrip(" \t?.!").strip()
    subject = _asked_span(previous, subject_terms(previous))
    #: Only a question with a shape of its own is asked again of the
    #: new subject; "what about X" after a plain "what" is its own
    #: question, and stands as typed.
    entity = bool(re.fullmatch(r"(?:[A-Z][\w'-]*)(?: [A-Z][\w'-]*)*", other))
    if other and subject and classify(previous) not in ("what", "recent") and subject_terms(other):
        return _swap_in_shape(previous, other, subject, entity)
    if other and subject and subject_terms(other):
        return _swap_plain_what(previous, other, subject, entity)
    return None


#: "what should I get her", "what else do I know about him": a person the turn
#: before named (audit 1031 C12).
_PERSON_PRONOUN = lazy_compile(r"\b(?:her|him|she|he|hers|his)\b", re.I)


#: "and his address", "what about her birthday": a thing of the person the turn before named, with no asking word.
_PERSON_THING = lazy_compile(r"^(?:(?:and|also|but|so)[, ]+)?(?:(?:what|how) about\s+)?(?:his|her|their)\s+[a-z][\w' -]{1,30}$", re.I)


#: The thing of a subject a question asks for by its kind alone ("what should I
#: pack", "when is the next appointment", "how much did it cost" without the
#: "it"): it has no subject of its own, so the turn before's is the one (audit E5, D6).
_PROPERTY_WORDS = frozenset(
    "appointment appointments cost costs price prices deadline address pack bring wear start end flight flights hotel hotels next".split()
)
_OWNED = lazy_compile(r"\b(?:my|our|your)\b", re.I)


def _property_only(text: str) -> bool:
    """Whether `text` asks for a property of an unnamed subject: every word it
    is about is one of `_PROPERTY_WORDS`, it names nothing of its own (no
    capital, no number, no "my") and it opens with an asking word."""
    q = " ".join(text.split()).rstrip("?.! ")
    if not _ASKS_SLOT.match(q) or _OWNED.search(q) or re.search(r"\b[A-Z][a-z]|\d", q[1:]):
        return False
    terms = [t.lower() for t in subject_terms(q) if t.lower() not in _SLOT_PRONOUN.pattern]
    return bool(terms) and all(t in _PROPERTY_WORDS or t.rstrip("s") in _PROPERTY_WORDS for t in terms)


def _pronoun_kind(text: str) -> str:
    """Which pronoun follow-on `text` is: "bare" (a pronoun and no subject),
    "slot" ("how much does it cost"), "person" ("what should I get her"),
    "total" (no subject of its own at all), or "" for none."""
    bare = _PRONOUN.search(text) and not [t for t in subject_terms(text) if not _PRONOUN.fullmatch(t)]
    if bare:
        return "bare"
    #: "how much does it cost", "when is it due": the slot word is not a subject.
    if _PERSON_THING.match(text.strip().rstrip("?.! ")):
        return "person_thing"
    if refers_back(text) and _SLOT_PRONOUN.search(text):
        return "slot"
    if _ASKS_SLOT.match(text.strip()) and _PERSON_PRONOUN.search(text) and not re.search(r"\b[A-Z][a-z]", text.strip()[1:]):
        return "person"
    #: "what's the total", "how far in total": no subject of its own at all.
    if _TOTAL_ASK.search(text) and not _PRONOUN.search(text) and not set(subject_terms(text)) - _TOTAL_WORDS:
        return "total"
    return "property" if _property_only(text) else ""


def _pronoun_swap(text: str, named: str, kind: str) -> str:
    """`text` with its pronoun replaced by the subject's name."""
    pattern = _PRONOUN if kind == "bare" else (_SLOT_PRONOUN if kind == "slot" else _PERSON_PRONOUN)

    def said(match: re.Match) -> str:
        #: "her birthday" is "Sara's birthday"; "get her" is "get Sara".
        word = match.group(0).lower()
        possessive = word in ("his", "hers") or (word == "her" and bool(text[match.end():].strip(" ?.!")))
        return named + ("'s" if possessive and kind == "person" else "")

    return pattern.sub(said, text, count=1)


def _carried_source(previous: str, turns: list[dict]) -> str:
    """The question whose subject a pronoun stands for: the turn before, unless
    that one only names a bare lower-case word ("what should I pack") and an
    earlier turn named a thing by a capitalised name ("tell me about the Tokyo
    trip"), which is what "it" still means (round 2 E5)."""
    def named(question: str) -> bool:
        span = _asked_span(question, subject_terms(question))
        return bool(span) and any(w[:1].isupper() for w in span.split())

    if named(previous):
        return previous
    for turn in reversed(turns[:-1]):
        question = str(turn.get("question") or "").strip()
        if named(question):
            return question
    return previous


#: "those distinct tags", "that month": the demonstrative names its own thing, the one the
#: answer before showed. It keeps its noun; the question before is not its subject (INBOX 1729).
_DEMONSTRATIVE_THING = lazy_compile(
    r"\b(?:those|these|that|this)\s+(?:[a-z]+\s+)?(?:tags?|categor(?:y|ies)|documents?|docs|months?|weeks?|notes?|reminders?|tasks?|charts?|graphs?|diagrams?)\b", re.I)


def _follow_pronoun(text: str, previous: str, last: dict, turns: list[dict]) -> Any:
    kind = _pronoun_kind(text)
    if not kind:
        return _NOT_THIS
    if _DEMONSTRATIVE_THING.search(text):
        return None
    bound = _bound_pronoun(text, kind, previous, last, turns)
    if bound is not None:
        return bound
    source = _carried_source(previous, turns)
    subject = _asked_span(source, subject_terms(source))
    if not subject:
        return None
    article = re.search(r"\b(?:the|my|our)\s+$", source[: source.lower().find(subject.lower())], re.I)
    #: A bare "that" keeps the old bare subject; the newer slot and person
    #: follow-ons read with the article ("how much does the Lisbon trip cost").
    named = (article.group(0).strip() + " " if article and kind != "bare" else "") + subject
    return _pronoun_read(text, kind, named, previous, source if kind == "property" else "")


def _pronoun_read(text: str, kind: str, named: str, previous: str, stands: str, ids: tuple = ()) -> FollowOn:
    """`text` with its pronoun read as `named`, the way its kind asks."""
    if kind in ("total", "property"):
        return FollowOn(f"{text.rstrip(' ?.!')} for {named}?", previous, "", "pronoun", stands=stands, note_ids=ids)
    if kind == "person_thing":
        thing = re.sub(r"^(?:(?:and|also|but|so)[, ]+)?(?:(?:what|how) about\s+)?", "", text.strip().rstrip("?.! "), flags=re.I)
        return FollowOn("what is " + _pronoun_swap(thing, named, "person"), previous, "", "pronoun", note_ids=ids)
    return FollowOn(_pronoun_swap(text, named, kind), previous, "", "pronoun", note_ids=ids)


# --- the turn frame (fable-composer-1110 F1) -------------------------------------
#
# Each composed answer sends a frame (`turn_frame`): the notes it used, the person or thing it was
# about, the question it answered, the days and list lines it showed. The page sends it back on
# the next turn; a follow-on binds to it first, and the text reading above stays for a turn
# without one (an older page, an act, a model's answer).


def _frames(turns: list[dict]) -> list[dict]:
    """The frames the last four turns carried, newest first."""
    return [t["frame"] for t in reversed(turns[-4:]) if isinstance(t.get("frame"), dict)]


def _frame_of(turn: dict) -> dict:
    frame = turn.get("frame")
    return frame if isinstance(frame, dict) else {}


def _frame_thing(frame: dict, *, article: bool) -> tuple[str, tuple]:
    """The thing a frame was about, as a question names it, and its lead note."""
    subject = " ".join(str(frame.get("subject") or "").split())
    ids = tuple(i for i in frame.get("note_ids") or [] if isinstance(i, int))[:1]
    if not subject or not ids:
        return "", ()
    plain = not article or not subject[:1].islower() or re.match(r"(?:the|my|our|a|an)\s", subject, re.I)
    return (subject if plain else f"the {subject}"), ids


def _bound_pronoun(text: str, kind: str, previous: str, last: dict, turns: list[dict]) -> FollowOn | None:
    """"what does she like": the person the last answers were about, not the last question's words;
    "who is it with": the thing the last answer showed, read on its note."""
    if kind in ("person", "person_thing"):
        person = next((str(f.get("person")) for f in _frames(turns) if f.get("person")), "")
        return _pronoun_read(text, kind, person, previous, "") if person else None
    frame = _frame_of(last)
    named, ids = _frame_thing(frame, article=kind != "bare")
    if not named:
        return None
    return _pronoun_read(text, kind, named, previous, str(frame.get("ask") or "") if kind == "property" else "", ids)


#: A turn that names an app thing is its own question, never a slot of the note before.
_APP_NOUNS = lazy_compile(r"\b(?:you|your|reminders?|tasks?|tags?|categor(?:y|ies)|documents?|notes?|charts?|lists?|statistics|stats|todo)\b", re.I)
_SLOT_WORDS_MAX = 5


#: Comparing or counting over what was shown ("which is higher", "what's the difference") is
#: computed from it (audit F6), not read as a slot of one note.
_COMPARES = lazy_compile(r"^which\b|\b(?:difference|between|total|compare|versus|vs|more|less|first|last)\b", re.I)


def _follow_slot(text: str, previous: str, last: dict, turns: list[dict]) -> Any:
    """"what temperature", "what room", "who am I going with" right after an answer: a slot of
    the note that answer showed, read on that note, not searched for "temperature"
    (fable-composer-1110 F1, step 3). Asked of the note's subject; the server keeps the person's
    own words when the note holds them, and lets go when they are another note's
    (`chat_turn._framed_scope`)."""
    q = " ".join(text.split()).rstrip("?.! ")
    if not _ASKS_SLOT.match(q) or len(q.split()) > _SLOT_WORDS_MAX or _OWNED.search(q) or _APP_NOUNS.search(q) or _COMPARES.search(q):
        return _NOT_THIS
    if re.search(r"\b[A-Z][a-z]|\d", q[1:]) or rec.without_windows(q) != q or _PRONOUN.search(q):
        return _NOT_THIS
    named, ids = _frame_thing(_frame_of(last), article=True)
    return FollowOn(f"{q} about {named}?", previous, "", "bound", note_ids=ids) if ids else _NOT_THIS


#: "until then", "before then": the day the last answer showed.
_THEN = lazy_compile(r"\b(?:until|till|til|before|after|since|by) then\b", re.I)


def _follow_then(text: str, previous: str, last: dict, turns: list[dict]) -> Any:
    found = _THEN.search(text)
    days = [d for d in _frame_of(last).get("dates") or [] if isinstance(d, str)]
    if not found or not days:
        return _NOT_THIS
    try:
        day = date_type.fromisoformat(days[0])
    except ValueError:
        return _NOT_THIS
    said = found.group(0)[: -len("then")] + f"{day.day} {day:%B} {day.year}"
    return FollowOn(text[: found.start()] + said + text[found.end():], previous, "", "bound")


#: "and mia", "what about Sam?": the same question of another person.
_AND_WHO = lazy_compile(r"^(?:and|(?:and |so )?(?:what|how) about)\s+(?P<x>[a-z][\w'-]*(?: [a-z][\w'-]*)?)\W*$", re.I)
_NOT_A_NAME = lazy_compile(r"^(?:the|a|an|my|our|your|that|this|it|then|so|more|else|now|next|last|other|again|after|before)\b|\b(?:it|that|this|them)$", re.I)


def _person_swap(text: str, last: dict) -> FollowOn | None:
    """"and mia" after "when is anna's birthday" is "when is mia's birthday": the last answer's
    person, swapped in the question it answered (`_follow_swap` reads anything else)."""
    got = _AND_WHO.match(text.strip())
    frame = _frame_of(last)
    person, ask = str(frame.get("person") or ""), str(frame.get("ask") or "")
    if not got or _NOT_A_NAME.search(got.group("x")) or not person or _ACT_LEAD.match(ask):
        return None
    if not re.search(rf"\b{re.escape(person)}\b", ask, re.I):
        return None
    return FollowOn(re.sub(rf"\b{re.escape(person)}\b", got.group("x"), ask, flags=re.I), ask, "", "entity")


#: "and the other" after "the first one": the next note the list before it showed.
_OTHER_ONE = lazy_compile(r"^(?:and |what about |how about )?the other(?: one| note)?\W*$", re.I)


def other_in_frames(text: str, turns: list[dict]) -> bool:
    """Whether "and the other" is answered by the frames the page echoed (the list before the pick still
    holds a note the pick was not), so it is bound to that note and `reading.follow` leaves it alone."""
    if not _OTHER_ONE.match(text.strip()) or len(turns) < 2:
        return False
    picked = _frame_of(turns[-1]).get("note_ids") or []
    return any(isinstance(i, int) and i not in picked[:1] for i in _frame_of(turns[-2]).get("note_ids") or [])


def _follow_other(text: str, previous: str, last: dict, turns: list[dict]) -> Any:
    if not _OTHER_ONE.match(text.strip()) or len(turns) < 2:
        return _NOT_THIS
    listed, picked = _frame_of(turns[-2]), _frame_of(last).get("note_ids") or []
    left = [i for i in listed.get("note_ids") or [] if isinstance(i, int) and i not in picked[:1]]
    if not left:
        return _NOT_THIS
    return FollowOn(str(listed.get("ask") or previous), previous, "", "bound", note_ids=(left[0],))


#: "and the flights", "also the hotel?": a part of the thing the turn before named, with no verb.
_AND_PART = lazy_compile(r"^(?:and|also)\s+(?:the\s+)?(?P<part>[a-z][a-z'-]*(?: [a-z][a-z'-]*)?)\s*[?.!]?\s*$")


def _follow_part(text: str, previous: str, last: dict, turns: list[dict]) -> Any:
    """"and the flights" after "what is the Lisbon trip" asks for the Lisbon
    trip's flights, not for every note about flights (audit 1107 R3-27). Only a
    plain lower-case noun phrase after a capitalised subject: "and the Tokyo
    trip" names its own subject and is the swap reader's."""
    got = _AND_PART.match(text.strip())
    if not got:
        return _NOT_THIS
    source = _carried_source(previous, turns)
    subject = _asked_span(source, subject_terms(source))
    if not subject or not any(w[:1].isupper() for w in subject.split()):
        return _NOT_THIS
    start = source.lower().find(subject.lower())
    article = re.search(r"\b(?:the|my|our)\s+$", source[:start], re.I)
    named = (article.group(0).strip() + " " if article else "") + subject
    return FollowOn(f"What are the {got.group('part')} for {named}?", previous, "", "part")


#: Tried in this order: a "more" is not a correction, and a correction is not a swap.
_WHICH_IS = lazy_compile(r"^(?:and |so )?which (?:one )?(?:is|was|would be) (?:the )?(cheaper|cheapest|better|bigger|longer|shorter|faster|sooner|older|newer|nearer|closer|more expensive|pricier)\W*$", re.I)


def _follow_which(text: str, previous: str, last: dict, turns: list[dict]) -> Any:
    """"Which is cheaper" after "compare Japan and Portugal": the same two sides, ranked (R9-9)."""
    found = _WHICH_IS.match(text)
    sides = compare_sides(previous) if found else None
    if not sides or len(sides) != 2:
        return _NOT_THIS
    return FollowOn(f"which is {found.group(1).lower()}, {sides[0]} or {sides[1]}", previous, "", "compare", stands=previous)


#: "how is it now", "how's it going today": the latest on the subject the turn before named (R9-9).
_HOW_NOW = lazy_compile(r"^(?:and )?(?:how is|how's|how are|how was|what's|what is) (?:it|that|this|he|she|they)(?: going)? (?:now|today|these days|at the moment|currently)$")


def _follow_now(text: str, previous: str, last: dict, turns: list[dict]) -> Any:
    got = " ".join(text.lower().split()).rstrip("?.! ")
    if len(got) > 60 or not _HOW_NOW.match(got):
        return _NOT_THIS
    source = _carried_source(previous, turns)
    subject = _asked_span(source, subject_terms(source))
    if not subject:
        return _NOT_THIS
    start = source.lower().find(subject.lower())
    article = re.search(r"\b(?:the|my|our)\s+$", source[:start], re.I)
    return FollowOn(f"What's the latest on {article.group(0).strip() + ' ' if article else ''}{subject}?", previous, "", "pronoun")


_FOLLOW_READERS = (
    _follow_shift, _follow_more, _follow_item, _follow_ordinal, _follow_other, _follow_correction, _follow_length, _follow_window, _follow_meant,
    _follow_then, _follow_bare, _follow_part, _follow_swap, _follow_which, _follow_now, _follow_pronoun, _follow_slot,
)


def _follow_one(question: str, turns: list[dict]) -> FollowOn | None:
    last = turns[-1]
    previous = str(last.get("question") or "").strip()
    text = (question or "").strip()
    for reader in _FOLLOW_READERS:
        got = reader(text, previous, last, turns)
        if got is not _NOT_THIS:
            return got
    return None


@dataclass
class Dialogue:
    """What a conversation has said so far (decision 35), built from the
    request's history, never kept on the server: the turns, the sentences
    and notes already quoted, the subjects in order, the names mentioned,
    the last answer's measured values, the corrections, and the salt that
    makes "Ask again" in this chat a different wording of the same answer.
    `compose(dialogue=...)` reads it and adds the turn it answers."""

    history: list[dict] = field(default_factory=list)
    quoted: list[str] = field(default_factory=list)
    quoted_ids: set[int] = field(default_factory=set)
    topic_stack: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    last_measures: list[str] = field(default_factory=list)
    corrections: list[str] = field(default_factory=list)
    used: set[str] = field(default_factory=set)
    salt: str = ""
    #: The label of the act card the last turn left waiting for Confirm, "" when none.
    pending_act: str = ""

    @property
    def turns(self) -> int:
        return len(self.history)

    @classmethod
    def from_history(cls, history: list[dict] | None, salt: str = "") -> Dialogue:
        """The dialogue a request's history describes: the chat's salt is
        its first question's (stable for the chat) unless one is given, and
        the words earlier answers used are found in their text."""
        turns = [{"question": str(t.get("question") or ""), "answer": str(t.get("answer") or "")} for t in history or []]
        dialogue = cls(history=turns, salt=salt or (hashlib.sha1(turns[0]["question"].encode()).hexdigest()[:12] if turns else ""))
        dialogue.pending_act = str((history or [{}])[-1].get("pending_act") or "").strip()
        for turn in turns:
            dialogue.used |= _templates_in(turn["answer"])
            dialogue.topic_stack += [t for t in subject_terms(turn["question"]) if t not in dialogue.topic_stack]
        return dialogue

    def record(self, question: str, result: dict) -> None:
        """Add the turn `result` answered."""
        self.history.append({"question": question, "answer": result.get("text", "")})
        for row in result.get("grounding") or []:
            self.quoted.append(row["sentence"])
            self.quoted_ids.add(row["note_id"])
        self.topic_stack += [t for t in subject_terms(question) if t not in self.topic_stack]
        self.entities += [p[1] for p in result.get("parts") or [] if p[0] == "title" and p[1] not in self.entities]
        self.last_measures = [p[1] for p in result.get("parts") or [] if p[0] == "measure"]
        self.used |= {p[1] for p in result.get("parts") or [] if p[0] == "template" and _TEMPLATE_WORDS.search(p[1])}


#: A joining or opening phrase (letters and length), as opposed to a stop or
#: a space: the words a conversation should not hear twice.
_TEMPLATE_WORDS = lazy_compile(r"[A-Za-z]{3}")


def _templates_in(answer: str) -> set[str]:
    """The worded `PHRASES` an earlier answer's text holds."""
    if not answer:
        return set()
    return {v for v in _WORDED_PHRASES() if v in answer}


_WORDED: list[str] = []


def _WORDED_PHRASES() -> list[str]:  # noqa: N802  # a cached table, read like one
    if not _WORDED:
        _WORDED.extend(v for v in set(PHRASES.values()) if len(v.strip()) >= 6 and _TEMPLATE_WORDS.search(v))
    return _WORDED


# --- the frame a composed answer sends (fable-composer-1110 F1) ---------------------

FRAME_NOTES = 5
FRAME_ITEMS = 12
FRAME_TEXT = 80
_LINKED = lazy_compile(r"\]\(#/notes/(\d+)\)")
_NAME = lazy_compile(r"(?<![.!?]\s)(?<!^)\b[A-Z][a-z]{1,20}\b", re.M)
_CALENDAR_NAMES = frozenset([*calendar.month_name[1:], *calendar.day_name])
_THIRD_PERSON = lazy_compile(r"\b(?:she|he|her|his|him)\b", re.I)
_LIST_LINE = lazy_compile(r"^\s*(?:[-*]|\d+[.)])\s+(?P<line>\S.*)$", re.M)
_MARKS = lazy_compile(r"\[([^\]]*)\]\([^)]*\)|[*_`]|\[\s*[xX ]?\s*\]")


def _frame_ids(result: dict) -> list[int]:
    ids: list[int] = []
    for row in result.get("grounding") or []:
        if isinstance(row.get("note_id"), int) and row["note_id"] not in ids:
            ids.append(row["note_id"])
    ids += [int(i) for i in _LINKED.findall(str(result.get("text") or "")) if int(i) not in ids]
    return list(dict.fromkeys(ids))[:FRAME_NOTES]


def _plain(text: str) -> str:
    return " ".join(_MARKS.sub(lambda m: m.group(1) or "", text).split())[:FRAME_TEXT]


def _person(asked: str, lead: dict) -> str:
    """The person the answer was about: a name the question used that the lead note writes as a
    name (in its title or mid-sentence) and says "she" or "he" of."""
    body = str(lead.get("content") or "")
    if not _THIRD_PERSON.search(body):
        return ""
    names = set(re.findall(r"\b[A-Z][a-z]{1,20}\b", composer_frame.note_title(lead))) | set(_NAME.findall(body))
    #: "28 November" names a day, not a person.
    return next((n for n in sorted(names) if re.search(rf"\b{n}\b", asked, re.I) and n not in _CALENDAR_NAMES), "")


def _frame_days(text: str, today) -> list[str]:  # noqa: ANN001  # a date
    lead = text.strip().split("\n\n", 1)[0]
    days: list[str] = []
    for _s, _e, phrase in when_words.find(lead):
        got = when_words.resolve(phrase, datetime.combine(today, time_type(9)))
        if got is not None and got.date().isoformat() not in days:
            days.append(got.date().isoformat())
    return days[:FRAME_NOTES]


#: The question's own words inside or at the edge of a subject span: "book am I reading" holds
#: "am I", "left on my todo list" starts with a state word and "on my" (L125).
_SPAN_VERB = re.compile(r"\b(?:am|is|are|do|does|did|have|has|was|were|will|can|could|would)\s+(?:i|we|you)\s+", re.I)
_SPAN_EDGE = re.compile(r"^(?:(?:left|on|in|my|the|of|about|for)\s+)+", re.I)


def _noun_span(span: str) -> str:
    """A subject span as a noun phrase: no question verb inside it, no leading state word."""
    return _SPAN_EDGE.sub("", _SPAN_VERB.sub("", span)).strip()


def turn_frame(asked: str, result: dict, notes: list[dict], today) -> dict:  # noqa: ANN001  # a date
    """What a composed answer showed, sent with it and echoed back by the page with the next
    turn: the notes it used (ids, at most five), the thing and person it was about, the
    question it answered, the days its lead named and its list lines. Small, and nothing a
    later turn could not already read: ids, names and the answer's own words, never a note's
    body. Empty when the answer used no note."""
    ids = _frame_ids(result)
    if not ids:
        return {}
    by_id = {n.get("source_id", n.get("id")): n for n in notes or []}
    lead = by_id.get(ids[0]) or {}
    span = _noun_span(_asked_span(asked, subject_terms(asked)).strip(" “”\"'")) if asked else ""
    text = str(result.get("text") or "")
    return {
        "note_ids": ids,
        "subject": _plain(span or composer_frame.note_title(lead)),
        "person": _person(asked, lead) if lead else "",
        "ask": " ".join(asked.split())[:200],
        "dates": _frame_days(text, today),
        "items": [_plain(m.group("line")) for m in _LIST_LINE.finditer(text)][:FRAME_ITEMS],
    }


def repeats(text: str, history: list[dict] | None) -> bool:
    """Whether `text` opens as the last answer did: a follow-on that gives the answer before
    again ("and kyoto?" answered with the budget) was read wrongly."""
    lead = (text or "").strip().split("\n", 1)[0].strip()
    last = str(((history or [{}])[-1] or {}).get("answer") or "").strip().split("\n", 1)[0].strip()
    return bool(lead) and lead == last


#: The wording of each next-question chip in the natural voice, to the key whose variants the other voice has.
_CHIP_KEYS = ("next_tag_a", "next_tag_b", "next_note_a", "next_note_b", "next_latest_a", "next_when_a")


def voiced_chips(out: "_Answer", chips: list[list[tuple]]) -> list[list[tuple]]:
    """The chips' fixed words in the answer's voice (L97). A chip is built with the natural wording; the second
    half of a pair takes the index its first half chose, so "What does the entry “X” state?" never splits."""
    voice = composer_tables.VOICE_VARIANTS[out.voice]
    keys = {PHRASES[k]: k for k in _CHIP_KEYS}
    chosen: dict[str, int] = {}

    def said(part: tuple) -> tuple:
        key = keys.get(part[1]) if part[0] == "template" else None
        if key is None:
            return part
        lead = composer_tables.PAIRED.get(key, key)
        if lead == key:
            chosen[key] = voice[key].index(out.voiced(key))
        return ("template", PHRASES[voice[key][chosen.get(lead, 0)]])

    return [[said(part) for part in chip] for chip in chips]
