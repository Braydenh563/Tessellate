"""What a question asks the composer to do: `Plan` and `plan`, its kind, its
time window and its constraints (not `composer_plan.py`, which plans the
person's deadlines).

Moved whole from `composer.py` (audit AR3, gods-1101): the code is unchanged,
and `composer` re-exports every name here that anything reads, so
`composer.plan` still works. Imports run one way, down
the layer list in `composer.py`'s docstring, never back to `composer`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from tessellate.ai import composer_numbers, question_noise, recognise as rec, utilities, when as when_words
from tessellate.ai.composer_ask import _ASKING_WORDS, _holds, _stem, _words, classify, rephrase, subject_terms, user_today
from tessellate.ai.composer_body import length_wish


# --- the query plan (CHAT_PLAN Phase 6, decision 31) ------------------------------

#: The answer kinds a plan names (decision 31's discourse schemas): the shape
#: a question is read in, plus what only the plan sees (a time window, a
#: utility, a recall by time, an insight, a recommendation).
PLAN_KINDS = (
    "fact", "when", "list", "timeline", "comparison", "count", "yesno", "why", "how", "status",
    "recommendation", "recall", "insight", "utility",
)


_SHAPE_KIND = {
    "what": "fact", "who": "fact", "where": "fact", "when": "when", "count": "count", "yesno": "yesno",
    "list": "list", "compare": "comparison", "status": "status", "recent": "recall",
}


_WHY = re.compile(r"^\s*(?:why|how come|what (?:made|makes|caused|causes)|explain why)\b", re.I)


_RECALL = re.compile(
    r"\bwhat (?:did|have|had) (?:i|we) (?:do|did|done|write|wrote|written|get up to|work on|worked on|note|noted|been up to)\b"
    r"|\bwhat (?:did|have|had) (?:i|we) (?:add|added|save|saved|make|made|jot|jotted|capture|captured)\b"
    r"|\banything (?:i|we) (?:added|saved|made|wrote|noted|jotted|did|captured)\b|\bdid (?:i|we) (?:add|write|save|make|note|jot) anything\b"
    r"|\bwhat happened\b|\bwhat was i (?:doing|up to)\b|\bwhat(?:'s| is| was) (?:been )?going on\b|\banything (?:new|happen)\b",
    re.I,
)


#: The verbs of such a question, which are not subjects to search for.
#: "do I have anything on Wednesday" asks what is on the day, as "what is on Wednesday" does (R3-8).
_ANYTHING_ON = re.compile(r"^\W*(?:do i have|have i got|have i|got|is there|are there)\s+(?:anything|something)\b", re.I)


_RECALL_VERBS = frozenset("add added save saved make made jot jotted capture captured anything write wrote note noted".split())


_INSIGHT = re.compile(r"\b(?:patterns?|habits?|trends?|keeps? coming up|how often do i|what do i (?:keep|always))\b", re.I)


_RECOMMEND = re.compile(r"^\s*(?:what|which) should (?:i|we)\b|^\s*should (?:i|we)\b|\brecommend|\bsuggest(?:ion)?s?\b", re.I)


_TAGGED = re.compile(r"\b(?:tagged(?: with)?|with the tags?|under the tags?)\s+#?([\w-]{1,40})|(?<![\w&])#([A-Za-z][\w-]{0,39})", re.I)


#: The words that name a kind of source (decision 37), and the kind.
_SOURCE_WORDS = (
    ("board", re.compile(r"\b(?:white)?boards?\b", re.I)),
    ("map", re.compile(r"\bmind ?maps?\b|\bmaps?\b", re.I)),
    ("document", re.compile(r"\bdocuments?\b|\bdocs\b", re.I)),
    ("picture", re.compile(r"\b(?:pictures?|photos?|images?|screenshots?)\b", re.I)),
)


@dataclass
class Plan:
    """What a question asks for, read before any note is (decision 31):
    the answer kind, the time window, the constraints, the subject's words
    and the length wished for. `compose` follows it; the route reads it to
    fetch the right notes (a recall by time fetches the window's notes)."""

    kind: str
    shape: str
    terms: list[str]
    window: tuple | None = None
    grain: str | None = None
    window_phrase: str = ""
    constraints: dict = field(default_factory=dict)
    source_kind: str | None = None
    length: str = ""
    utility: str | None = None


def _time_phrase(question: str) -> str:
    found = when_words.find(question or "")
    return found[0][2] if found else ""


def _plan_phrase(question: str, terms: list[str]) -> str:
    """The question's time phrase, or "" for a bare "recently" with no subject:
    "what did I write recently" asks for the newest notes, not a fortnight."""
    phrase = _time_phrase(question)
    return "" if not terms and rec.is_lately(phrase) else phrase


#: What the planner reads of a question. Its passes cost words x length, so a
#: 20,000-character paste took 38 s; the model still gets the whole question.
PLAN_CHARS = 2000


def _planned_text(question: str | None) -> str:
    return composer_numbers.normalise((question or "")[:PLAN_CHARS])


def _plan_constraints(question: str, terms: list[str]) -> tuple[dict, list[str], str | None]:
    """The tags and source kind a question names, and its terms without them."""
    constraints: dict = {}
    tags = [a or b for a, b in _TAGGED.findall(question or "")]
    if tags:
        constraints["tags"] = [t.lower() for t in tags]
        terms = [t for t in terms if t not in ("tagged", "tag", "tags") and t.lower() not in constraints["tags"]]
    source_kind = None
    for kind, pattern in _SOURCE_WORDS:
        if pattern.search(question or ""):
            source_kind = kind
            terms = [t for t in terms if not pattern.fullmatch(t)]
            break
    if source_kind:
        constraints["source_kind"] = source_kind
    return constraints, terms, source_kind


#: "what do I have on Friday", "do I have anything on Friday": the day's items (R3-8).
_DAY_ASK = re.compile(r"^\W*(?:what do i have|do i have|have i got|have i|got|is there|are there)\s+(?:(?:anything|something)\s+)?(?:on|for)\b", re.I)


def asks_the_day(question: str, today: date) -> bool:
    """Whether the question asks what is on one named day, which the recall
    answers the same way however it is put."""
    if not _DAY_ASK.search(question or ""):
        return False
    p = plan(question, today)
    return p.kind == "recall" and bool(p.window) and p.window[0] == p.window[1]


def _asks_recall(question: str, shape: str) -> bool:
    """A day or window with no subject asks what the notes hold from then;
    "do I have anything on Wednesday" asks it as a yes/no (R3-8)."""
    return bool(_RECALL.search(question or "")) or shape in ("what", "recent", "list") or (shape == "yesno" and bool(_ANYTHING_ON.search(question or "")))


def _plan_kind(question: str, utility: str | None, shape: str, spanned: bool, has_terms: bool) -> str:
    if utility and utility != "until_note":
        return "utility"
    if spanned and not has_terms and _asks_recall(question, shape):
        return "recall"
    if _INSIGHT.search(question or ""):
        return "insight"
    if _RECOMMEND.search(question or ""):
        return "recommendation"
    if shape == "explain":
        return "why" if _WHY.match(rephrase(question)) else "how"
    return _SHAPE_KIND.get(shape, "fact")


def _subject_left(question: str, terms: list[str], phrase: str) -> bool:
    """Whether the question has a subject besides its time phrase. A window
    still ahead ("May next year") is dropped when it has ("my trip next
    month" is notes about the trip, written now) and kept when it has none
    ("what did I write in May next year": nothing yet, said as that)."""
    said = set(phrase.lower().split())
    left = [t for t in terms if t.lower() not in said]
    return bool([t for t in left if t.lower() not in _RECALL_VERBS] if _RECALL.search(question or "") else left)


def window_verb_stems(question: str, phrase: str) -> list[str]:
    """The words of a question that is not a recall but names a window and no
    subject ("how much did I save in October": save): what a note in the
    window must hold to be read, the phrase's own words and the asking words
    left out."""
    said = {_stem(w) for w in re.findall(r"[\w']+", (phrase or "").lower())}
    return [st for st in _words(question) if st not in said and st not in _ASKING_WORDS and len(st) > 2]


def holds_any(stems: list[str], text: str) -> bool:
    """Whether `text` holds any of the stems, or a word that starts with one
    ("save" in "saved")."""
    words = set(_words(text))
    return any(_holds(st, words) or any(w.startswith(st) for w in words) for st in stems)


#: A present or future yes/no ("is the plumber coming this week"): its window dates the event, not the note.
_PRESENT_ASK = re.compile(r"^\W*(?:is|are|will)\s+(?:the|my|our|a)\b", re.I)


_EVENT_TAIL = re.compile(r"\s+(?:this|next)\s+(?:week|month|weekend)\s*[?.!]*$|\s+(?:today|tomorrow|tonight)\s*[?.!]*$", re.I)


def without_event_window(question: str) -> str:
    """"is the plumber coming this week" asked of the notes as "is the plumber coming": the window dates the
    event, so searching for it finds the notes that happen to say "week" (R9-7)."""
    return _EVENT_TAIL.sub("", question) if _PRESENT_ASK.match(question or "") else question


def _plan_window(question: str, terms: list[str], phrase: str, today: date) -> tuple[tuple | None, list[str]]:
    """The window the phrase names (None for none, or for one still ahead
    that sits beside a subject) and the subject terms left once the phrase's
    own words are taken out."""
    if phrase and rec.a_topic_phrase(question, phrase):
        said = [w for w in re.findall(r"[\w']+", phrase.lower()) if w not in rec.PHRASE_FILLER]
        return None, terms + [w for w in said if w not in terms]
    span = when_words.span(phrase, today, "past") if phrase else None
    #: "is the plumber coming this week": the week is when it happens, not when the note was written (R9-7).
    if span and (span[0] > today or _PRESENT_ASK.match(question or "")) and _subject_left(question, terms, phrase):
        return None, terms
    return span, _without_window_words(question, terms, phrase) if span else terms


def _without_window_words(question: str, terms: list[str], phrase: str) -> list[str]:
    """"what did I write on Monday": the day is the window, not a subject to
    search the notes for (the phrase's own words, "monday", go, and a recall
    verb, and "archived", a state of the notes)."""
    gone = set(phrase.lower().split())
    if _RECALL.search(question or ""):
        gone |= _RECALL_VERBS
    if question_noise.asks_archived(question):
        gone.add("archived")
    return [t for t in terms if t.lower() not in gone]


def plan(question: str, today: date | None = None, *, recent: bool = False, embed=None) -> Plan:  # noqa: ANN001
    """The query plan for `question` on `today` (the person's own day), read
    from its first `PLAN_CHARS` characters."""
    question = _planned_text(question)
    today = today or user_today()
    utility = utilities.kind_of(question)
    shape = "recent" if recent else classify(question, embed)
    terms = subject_terms(question)
    verb = _lead_act_verb(question)
    if verb:
        #: The instruction is not a subject: "add" in "add milk to my
        #: shopping list" matched "add tomatoes" in a recipe (E12).
        terms = [t for t in terms if t.lower() != verb] or terms
    constraints, terms, source_kind = _plan_constraints(question, terms)
    phrase = _plan_phrase(question, terms)
    span, terms = _plan_window(question, terms, phrase, today)
    kind = _plan_kind(question, utility, shape, bool(span), bool(terms))
    return Plan(
        kind=kind,
        shape=shape,
        terms=terms,
        window=(span[0], min(span[1], today)) if span else None,
        grain=span[2] if span else None,
        window_phrase=phrase if span else "",
        constraints=constraints,
        source_kind=source_kind,
        length=length_wish(question),
        utility=utility,
    )


#: The words that start an act on a note, and the act (`act_registry`).
_ACT_VERBS = {
    "rename": "rename", "retitle": "rename", "tag": "tag", "label": "tag", "untag": "untag", "pin": "pin", "unpin": "unpin",
    "star": "pin", "unstar": "unpin", "delete": "delete", "remove": "delete", "bin": "delete", "trash": "delete",
    "erase": "delete", "discard": "delete", "link": "link", "unlink": "unlink", "connect": "link", "add": "append",
    "append": "append", "move": "move", "file": "move",
}


_ACT_LEADS = ("please ", "pls ", "can you ", "could you ", "would you ", "will you ", "i want to ", "i'd like to ", "i would like to ", "just ", "ok ", "okay ", "hey ")


def _lead_act_verb(question: str) -> str | None:
    """The act verb a command opens with ("please rename ..."), or None for a
    question or any other sentence."""
    text = " ".join((question or "").lower().split()).strip(" .!?")
    changed = True
    while changed:
        changed = False
        for lead in _ACT_LEADS:
            if text.startswith(lead):
                text, changed = text[len(lead):], True
    first, _, rest = text.partition(" ")
    if first not in _ACT_VERBS or not rest or len(text.split()) > 14:
        return None
    #: "add up the budget" is a sum, not a line to add to a note.
    return None if first == "add" and rest.split()[0] in ("up", "together") else first


_TAG_ACTS = frozenset({"tag", "untag"})
_TAG_FILLER = frozenset("my the a an that this one note notes entry".split())


def _spoken(tags: list[str]) -> str:
    named = [f"#{t}" for t in tags]
    return named[0] if len(named) == 1 else ", ".join(named[:-1]) + " and " + named[-1]


def _named_note(question: str, notes: list[dict]) -> tuple[dict | None, list[str]]:
    """The one note a tag act's words name (every word in its title), and those words."""
    from tessellate.ai.composer_read import _title

    text = " ".join((question or "").lower().split()).strip(" .!?")
    for lead in _ACT_LEADS:
        text = text[len(lead):] if text.startswith(lead) else text
    named = [w for w in re.findall(r"[a-z0-9']+", text.partition(" ")[2]) if w not in _TAG_FILLER]
    stems = {_stem(w) for w in named}
    held = [n for n in notes or [] if stems and stems <= {_stem(w) for w in _words(_title(str(n.get("content") or ""))[0])}]
    return (held[0] if len(held) == 1 else None), named


def tag_gap(verb: str, question: str, notes: list[dict]) -> str:
    """The question a tag act asks when it names one note and no tag ("untag
    my gym note", audit 1028 E55): which tag, with the note's own tags as the
    choices to take off. "" when the words are not one note's name."""
    from tessellate.ai.composer_read import _title

    if _ACT_VERBS.get(verb) not in _TAG_ACTS:
        return ""
    note, named = _named_note(question, notes)
    if note is None:
        return ""
    title = _title(str(note.get("content") or ""))[0].strip()
    tags = [str(t).strip("#") for t in note.get("tags") or [] if str(t).strip("#")]
    spoken = f"the {' '.join(named)} note"
    if verb != "untag":
        return f"Which tag should I add to “{title}”? Say it like this: tag {spoken} with kitchen."
    if not tags:
        return f"“{title}” has no tags to take off."
    return f"Which tag should I take off “{title}”? It has {_spoken(tags)}. Say it like this: remove the tag {tags[0]} from {spoken}."
