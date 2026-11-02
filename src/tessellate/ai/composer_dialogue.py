"""The conversation around an answer: the next questions to offer, a
follow-on ("tell me more", "the second one") read against the turn before,
and `Dialogue`, the turns so far.

Moved whole from `composer.py` (audit AR3, gods-1101): the code is unchanged,
and `composer` re-exports every name here that anything reads, so
`composer.follow_on` still works. Imports run one way, down
the layer list in `composer.py`'s docstring, never back to `composer`.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from tessellate.ai import question_noise, recognise as rec, when as when_words
from tessellate.ai.composer_ask import _stem, _words, classify, rephrase, subject_terms
from tessellate.ai.composer_body import _BRIEF, _FULL, _NOTE_NOUNS, _asked_span
from tessellate.ai.composer_phrases import PHRASES
from tessellate.ai.composer_quote import _pick
from tessellate.ai.composer_read import NoteView
from tessellate.search import query as query_understanding


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


def _subject_pick(question: str, shape: str, terms: list[str]) -> list[tuple] | None:
    #: The question's own subject, when it is a short name ("dentist
    #: check-up", "sourdough"), asked the other way round in time.
    own = _own_terms(terms)
    subject = _asked_span(question, own)
    if subject and len(subject.split()) == len(own) <= 3 and shape not in ("status", "recent", "compare"):
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
        _subject_pick(question, shape, terms),
    )
    picks = [pick for pick in found if pick]
    out = [p for p in picks if len("".join(part[1] for part in p)) <= NEXT_MAX_CHARS]
    return out[:3]


# --- a follow-up, read against the turn before ----------------------------------

_MORE = re.compile(
    r"^\s*(?:tell me more|more|go on|continue|keep going|say more|what else|anything else|and|more please|"
    r"more about (?:that|it|this|those))[\s?.]*$",
    re.I,
)


_ORDINALS = {"first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2, "fourth": 3, "4th": 3, "fifth": 4, "5th": 4, "last": -1}


_ORDINAL = re.compile(r"\bthe (first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th|last) (?:one|note)\b", re.I)


_PRONOUN = re.compile(r"\b(it|that|this|them|those|they)\b", re.I)


#: A question that leans on the answer before it (audit 1030 Z53): it opens
#: with an asking word and either says "it" or has no subject of its own.
_ASKS_SLOT = re.compile(r"^(?:and |so |ok |okay )*(?:what|when|where|who|which|how|why|is|are|was|were|does|do|did|can|could|will|would|should)\b", re.I)


_SLOT_PRONOUN = re.compile(r"\b(?:it|its|that|them|those)\b", re.I)


#: A question about a total or an instance with no subject of its own:
#: "how far in total", "what's the total", "when was the last one".
_TOTAL_WORDS = frozenset({"far", "much", "many", "long", "total", "last", "latest", "first", "next", "previous", "one", "altogether"})


_TOTAL_ASK = re.compile(
    r"^(?:and |so |ok |okay )*(?:what|when|where|how)\b(?!.*(?-i:[A-Z]\w|\d))"
    r"(?=.*\b(?:in total|in all|altogether|the total|(?:the )?(?:last|latest|first|next|previous) one)\b)[^.]*$",
    re.I,
)


#: A pronoun that is the point of the phrase, not a reference to a note.
_NOT_REFERRING = re.compile(r"\b(?:what|how|when) (?:is|was) (?:it|that) like\b|\bwhat is (?:it|that)\b$|\bhow is it\b", re.I)


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
_SWAP = re.compile(
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
_MEANT = re.compile(r"^\s*did you mean\s+[“\"']?(\S.*)$", re.I)


_BARE = re.compile(r"^\s*(?:(?:and|but|so|ok|okay)[, ]+)?(why|when|where|who|how come|how many|how much|how|since when)[\s?.!]*$", re.I)


_BOLD = re.compile(r"\*\*(.+?)\*\*")


#: "no, the gym one", "not that one, the running note", "I meant the dentist
#: note": the turn before answered from the wrong note (decision 35).
_CORRECTION = re.compile(
    r"^\s*(?:no|nope|not that(?: one)?|wrong one|not quite)[,.!]?\s+(?:i meant\s+|i mean\s+|the one about\s+)?(?P<x>\S.*)$"
    r"|^\s*i meant\s+(?P<x2>\S.*)$",
    re.I,
)


#: "shorter", "in more detail": the turn before again, at another length.
_LENGTH = re.compile(
    r"^\s*(?:shorter|briefer|less|in short|tl;?dr|summari[sz]e that|longer|more detail|in (?:more )?detail|"
    r"(?:make it|say it|be|can you be) (?:shorter|briefer|longer|more detailed))(?:\s+please)?[\s.?!]*$",
    re.I,
)


#: "and last week?", "what about yesterday?": the turn before over another time.
_WINDOW_ONLY = re.compile(r"^\s*(?:(?:and|but|so|ok)[, ]+)?(?:(?:what|how) about\s+)?(?P<w>[^\s,].*)$", re.I)


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


_DEFINING = re.compile(
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
    turns = [
        t for t in (history or [])
        if str(t.get("question") or "").strip() and not question_noise.social_kind(str(t.get("question") or ""))
    ]
    defining = _defining_ask(question, turns)
    if defining is not None:
        return defining
    if not turns:
        return None
    return _follow_one(question, _standing(turns))


#: Follow-on kinds whose reading is a question in its own right ("and last
#: week?", "what about Lisbon?"). The others ("longer", "why?", "no, the
#: launch one") lean on the question before, which stays the one the next
#: terse turn leans on: "why?" after "longer" asks about the subject, not
#: about "longer".
_RESTATES = frozenset({"window", "subject", "entity", "pronoun", "did_you_mean", "ordinal"})


def _standing(turns: list[dict]) -> list[dict]:
    """The turns with each terse one replaced by the question it stood for,
    read forwards, so a follow-on never leans on another follow-on's words."""
    out: list[dict] = []
    for turn in turns:
        text = str(turn.get("question") or "").strip()
        follow = _follow_one(text, out) if out else None
        prefer = ""
        if follow:
            text = follow.question if follow.kind in _RESTATES else follow.previous
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


def _follow_correction(text: str, previous: str, last: dict, turns: list[dict]) -> Any:
    correction = _CORRECTION.match(text)
    if not correction:
        return _NOT_THIS
    #: The second alternative ("I meant the dentist note") fills x2, not x.
    said = (correction.group("x") or correction.group("x2") or "").rstrip(" \t.?!")
    prefer = re.sub(r"^(?:the|my|that|this)\s+", "", said.strip(), flags=re.I)
    prefer = re.sub(r"\s(?:one|note|entry)$", "", prefer, flags=re.I).strip()
    return FollowOn(previous, previous, "", "correction", prefer) if prefer else _NOT_THIS


def _follow_length(text: str, previous: str, last: dict, turns: list[dict]) -> Any:
    if not _LENGTH.match(text):
        return _NOT_THIS
    shorter = text.lstrip().lower().startswith(("shorter", "briefer", "in short", "tl;dr", "tldr", "summarise that", "summarize that", "less"))
    base = _without_length(previous)
    return FollowOn(f"briefly, {base}" if shorter else f"{base.rstrip('?.!')} in detail?", previous, "", "length", str(last.get("prefer") or ""))


def _follow_window(text: str, previous: str, last: dict, turns: list[dict]) -> Any:
    window = _WINDOW_ONLY.match(text)
    window_text = window.group("w").rstrip(" \t?.!") if window else ""
    found_time = when_words.find(window_text) if window else []
    #: Only a turn that is nothing but a time ("and last week?"): "what did
    #: I write yesterday" is a question of its own.
    if not (found_time and not window_text.replace(found_time[0][2], "").strip(" ,")):
        return _NOT_THIS
    base = previous
    for _s, _e, old_phrase in when_words.find(previous):
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
        other = re.sub(r"^(the|my|a|an)\s+", "", other, flags=re.I)
    resolved = before + other + previous[start + len(subject):]
    return FollowOn(resolved, previous, "", "entity" if entity else "subject")


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


def _follow_swap(text: str, previous: str, last: dict, turns: list[dict]) -> Any:
    swap = _SWAP.match(text) or _SWAP.match(rephrase(text))
    if swap and swap.group("y") is not None and not text.rstrip().endswith("?"):
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
_PERSON_PRONOUN = re.compile(r"\b(?:her|him|she|he|hers|his)\b", re.I)


def _pronoun_kind(text: str) -> str:
    """Which pronoun follow-on `text` is: "bare" (a pronoun and no subject),
    "slot" ("how much does it cost"), "person" ("what should I get her"),
    "total" (no subject of its own at all), or "" for none."""
    bare = _PRONOUN.search(text) and not [t for t in subject_terms(text) if not _PRONOUN.fullmatch(t)]
    if bare:
        return "bare"
    #: "how much does it cost", "when is it due": the slot word is not a subject.
    if refers_back(text) and _SLOT_PRONOUN.search(text):
        return "slot"
    if _ASKS_SLOT.match(text.strip()) and _PERSON_PRONOUN.search(text) and not re.search(r"\b[A-Z][a-z]", text.strip()[1:]):
        return "person"
    #: "what's the total", "how far in total": no subject of its own at all.
    if _TOTAL_ASK.search(text) and not _PRONOUN.search(text) and not set(subject_terms(text)) - _TOTAL_WORDS:
        return "total"
    return ""


def _pronoun_swap(text: str, named: str, kind: str) -> str:
    """`text` with its pronoun replaced by the subject's name."""
    pattern = _PRONOUN if kind == "bare" else (_SLOT_PRONOUN if kind == "slot" else _PERSON_PRONOUN)

    def said(match: re.Match) -> str:
        #: "her birthday" is "Sara's birthday"; "get her" is "get Sara".
        word = match.group(0).lower()
        possessive = word in ("his", "hers") or (word == "her" and bool(text[match.end():].strip(" ?.!")))
        return named + ("'s" if possessive and kind == "person" else "")

    return pattern.sub(said, text, count=1)


def _follow_pronoun(text: str, previous: str, last: dict, turns: list[dict]) -> Any:
    kind = _pronoun_kind(text)
    if not kind:
        return None
    subject = _asked_span(previous, subject_terms(previous))
    if not subject:
        return None
    article = re.search(r"\b(?:the|my|our)\s+$", previous[: previous.lower().find(subject.lower())], re.I)
    #: A bare "that" keeps the old bare subject; the newer slot and person
    #: follow-ons read with the article ("how much does the Lisbon trip cost").
    named = (article.group(0).strip() + " " if article and kind != "bare" else "") + subject
    if kind == "total":
        return FollowOn(f"{text.rstrip(' ?.!')} for {named}?", previous, "", "pronoun")
    return FollowOn(_pronoun_swap(text, named, kind), previous, "", "pronoun")


#: Tried in this order: a "more" is not a correction, and a correction is not a swap.
_FOLLOW_READERS = (
    _follow_more, _follow_ordinal, _follow_correction, _follow_length, _follow_window, _follow_meant,
    _follow_bare, _follow_swap, _follow_pronoun,
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
_TEMPLATE_WORDS = re.compile(r"[A-Za-z]{3}")


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
