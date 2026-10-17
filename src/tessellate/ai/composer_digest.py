"""The answer a person would give from the notes (CHAT_PLAN decision 70).

INBOX 812, the owner: "the response feels plain, boring, lifeless, and doesnt
give me anything more. I may as well just read the notes I made on the
right". The composer quoted: each note's sentence under a bar with a
bracketed day, then the same notes again as chips and a count. The right
column already shows the notes, so the answer's job is what the column
cannot do: say how many and over which days, put the facts in the
person's terms under a label each, say what the notes do not cover, and
offer one thing to do next.

The shape, from the gold answers (`tests/fixtures/gold_answers.json`):

- one opening sentence that answers, with a count and a span or the fact;
- grouped facts, a bold label and a rewritten sentence each, not a quote;
- what the notes do not say;
- one offer that acts (a reminder, a checklist), never a question for its own sake.

No model and nothing invented: every fact line is a note's own sentence,
cut and turned to the second person, and it carries the note it came
from (`grounding`), so the one citation mark per line lights its card.
Jokes, quotes and other people's words are never said as the person's
facts (decision 67): a note tagged joke is left out unless jokes are asked
for. `answer` returns None for a question this shape does not fit; the
caller then asks `composer.compose`.

The connecting words are in `PHRASES`, one table, so a voice preset
(decision 72) swaps them without touching the facts or the shape.
"""

from __future__ import annotations

import re
import sys
import zlib
from collections import Counter
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from functools import lru_cache
from pathlib import Path

from tessellate.ai import composer, composer_tables, glossary, realise, verdicts
from tessellate.ai import recognise as recogniser
from tessellate.ai import when as when_words

#: The connecting words, one table (decision 72: a voice swaps this, never
#: the facts). `{}` slots are filled in order.
_BASE = {
    "overview": "You have {count} about {topic}, {span}.",
    "likes": "It looks that way: you've written about {topic} {times}, {span}.",
    "from_note": "{fact}, from your note of {day}.",
    "from_list": "{count}, from your {what} of {day}: {items}.",
    "only_one": "It's your only note on {topic} so far.",
    "who_once": "{name} comes up once, on {day}: {fact}.",
    "who_many": "{name} comes up in {count}, {span}.",
    "pick": "The {side}, by your notes: {why}.",
    "more_right": "{count} more on the right.",
    "more_show": "Show {count} more",
    "stands_for": "{abbr} is short for {phrase}, from your note of {day}.",
    "stands_for_seen": "{abbr} looks like {phrase}: your note of {day} names it in full.",
    "uses": "You use {abbr} in {count}, the last on {day}.",
    "all_said": "That's all your notes say on {topic} so far: {count}, {span}.",
    "tie": "{Topic} also comes up in {category}: {count} on something else.",
    "tie_chip": "What have I saved about {topic} in {category}?",
    #: A line the person pinned as true (B32): said as their word.
    "pinned": "{said} (you pinned this as true, {day})",
    "this_note": "Your {title} note of {day}{where}, in {points}:",
    "this_one": "Your {title} note of {day}{where}{pause} says one thing: {fact}.",
    "this_many": "{Count} in {topic}, {span}.",
    "nothing_open": "Nothing is open to sum up. Open a note, or pick a category in the sidebar, and ask again; or name it: \"summarise Travel\".",
    "nothing_yet": "Nothing yet on {facets}.",
    "remind": "Remind you to {action}?",
    "checklist": "Save it as a checklist note?",
    "pick_note": "Note the {side} as your pick?",
    "start_list": "Start a list of {noun}s to watch next?",
    "gather": "Gather them into one note?",
    "go_again": "Remind you to go to {place} again?",
    "try_one": "Remind you to try {item}?",
    "log_weekly": "Remind you each week to log your spending?",
    "track_table": "Track your {what} in a table?",
    "only_week": "It's the only week you've written down.",
    "only_names": "It's the only note that names {name}.",
    "none_own": "None of them has a note of its own yet.",
    "gone_quiet": "Nothing on {word} since {month}.",
    "also": "Also",
    "only_note": "It's your only note on that so far.",
    "only_kind": "It's your only {noun} so far.",
    #: The joins between lines and the closing pattern (INBOX 870: "one or
    #: two words between directly giving me what I can see from the notes
    #: on the right ... feels like the response is completely useless").
    #: Each a full clause, each from the dates or the notes, never a guess;
    #: several wordings, picked by the question, so answers do not all read
    #: the same.
    "gap": ("{gap} later, ", "{gap} on, ", "after {gap}, "),
    #: A note told as what happened (the owner, 2026-10-11): its event re-said
    #: from today, then its facts in one flowing sentence, never label lines.
    "told": ("you mentioned", "you said", "you noted"),
    "told_future": ("You'll have {np}.", "That means {np}."),
    #: A note's own heading said as prose (the owner, 2026-10-11: "it didnt
    #: do the understanding and rewrite for the rest of the response"): one
    #: wording a paragraph, turned by the line, so no two read alike.
    "learned": ("you learned that", "you took away that", "you heard that"),
    "noted": ("you noted", "you wrote down", "you jotted down"),
    "set_task": ("you gave yourself {obj} to {verb}", "you set yourself {obj} to {verb}"),
    "meant": ("you meant to", "you planned to", "you set out to"),
    "drift_woven": "though no later note says how that went",
    "meaning_loading": "The search by meaning is still loading, so this read your words only; ask again in a few seconds.",
    "landed": ("{opening}, and you're {landed}.", "{opening}. For now you're {landed}."),
    "open_count": ("{opening}, with {left} still open.", "{opening}, and {left} still to settle."),
    "stale": (
        "The newest of these is {age} old, so things may have moved on since.",
        "You last wrote about it {age} ago, which is a while; a fresh note would bring it up to date.",
        "Nothing new on it for {age}, so this is where it stood then rather than now.",
    ),
    "burst": (
        "All {count} came within {span} of each other, the newest {age} ago.",
        "They were written close together, within {span}, the newest {age} ago.",
    ),
    "cadence": (
        "That's about one every {every}, the newest {age} ago.",
        "You've come back to it roughly every {every}, most recently {age} ago.",
    ),
    "fresh": ("The newest is from {age} ago, so it's current.", "The latest is only {age} old."),
    "aim_under": ("{said}, under your aim of {aim}.", "{said}, which keeps you inside your {aim}."),
    "aim_over": ("{said}, over your aim of {aim}.", "{said}, which is more than the {aim} you were aiming for."),
    "price_gap": ", a gap of {gap} between them",
    "months_away": (", which is {away} from now", ", {away} away"),
    "mixed": (
        "So a mixed {score}: one thing you loved, one that let it down.",
        "That makes it a {score} with a clear high and a clear low.",
    ),
}

#: The voices (CHAT_PLAN decision 72): Warm and concise (the default,
#: stored as "natural", the composer's own name for it), Neutral
#: ("professional"), Playful and Plain. A voice changes the openings, the
#: joins and the closings, never a fact or the shape. A tuple is several
#: openings said in turn, so a conversation does not open the same way five
#: times running (B6).
VOICES: dict[str, dict[str, str | tuple[str, ...]]] = {
    "natural": {
        "overview": ("You have {count} about {topic}, {span}.",
                     "There are {count} about {topic}, {span}.",
                     "{Count} about {topic}, {span}.",
                     "Your notes on {topic}: {count}, {span}.",
                     "On {topic} you've written {count}, {span}."),
    },
    "professional": {
        "overview": ("Your notebook holds {count} on {topic}, {span}.",
                     "{Count} concern {topic}, {span}.",
                     "On {topic}: {count}, {span}.",
                     "Recorded on {topic}: {count}, {span}.",
                     "The notebook has {count} on {topic}, {span}."),
        "likes": "The notes suggest so: {topic} appears {times}, {span}.",
        "from_note": "{fact}, as recorded on {day}.",
        "nothing_yet": "The notes do not yet cover {facets}.",
        "remind": "Set a reminder to {action}?",
        "only_one": "This is the only note on {topic}.",
        "only_week": "This is the only week recorded.",
        "only_names": "This is the only note naming {name}.",
        "none_own": "None of them has a note of its own.",
        "gone_quiet": "No record of {word} since {month}.",
        "also": "In addition",
        "only_note": "This is the only note on that.",
        "only_kind": "This is the only {noun}.",
    },
    "playful": {
        "overview": ("Found {count} about {topic}, {span}.",
                     "Here's the lot: {count} about {topic}, {span}.",
                     "Ooh, {topic}: {count}, {span}.",
                     "Dug up {count} about {topic}, {span}.",
                     "Right, {topic}: {count}, {span}."),
        "likes": "Sounds like it: you've written about {topic} {times}, {span}.",
        "from_note": "{fact}, says your note of {day}.",
        "nothing_yet": "No word yet on {facets}.",
        "remind": "Want a nudge to {action}?",
        "only_week": "That's the only week you've jotted down so far.",
        "none_own": "None of them has its own note yet, so they're all still ideas.",
        "gone_quiet": "{Word} has gone quiet since {month}.",
    },
    "plain": {
        "overview": ("{Count} about {topic}, {span}.",),
        "likes": "Yes. {Topic} comes up {times}, {span}.",
        "from_note": "{fact}. Note of {day}.",
        "nothing_yet": "Not in your notes: {facets}.",
        "remind": "Remind you to {action}?",
        "only_week": "Only one week is written down.",
        "only_names": "Only one note names {name}.",
        "none_own": "None has its own note.",
        "gone_quiet": "No {word} since {month}.",
        "only_note": "Only one note on that.",
        "only_kind": "Only one {noun}.",
    },
}
#: The voice and the turn of the answer being written.
_VOICE: ContextVar[str] = ContextVar("digest_voice", default="natural")
_TURN: ContextVar[int] = ContextVar("digest_turn", default=0)
#: The question's own number (INBOX 870): picks among a phrase's wordings,
#: so two questions in a row are not joined the same way.
_SEED: ContextVar[int] = ContextVar("digest_seed", default=0)


def _vary(key: str) -> _Capitals:
    said = VOICES.get(_VOICE.get(), {}).get(key) or _BASE[key]
    if isinstance(said, tuple):
        said = said[(_SEED.get() + _TURN.get()) % len(said)]
    return _Capitals(said)


def _gap(days: int) -> str:
    """Days as a person says them: "a day", "a few days", "a week",
    "three weeks", "nearly two months"."""
    if days <= 1:
        return "a day"
    if days == 2:
        return "two days"
    if days <= 5:
        return "a few days"
    if days <= 9:
        return "a week"
    if days <= 24:
        return f"{realise.count_word(round(days / 7))} weeks"
    if days <= 45:
        return "about a month"
    months = round(days / 30)
    return f"about {realise.count_word(months)} months" if months < 12 else "over a year"


class _Phrases(dict):
    """`PHRASES[key]` in the voice of the answer being written; a capital
    `{Count}` or `{Topic}` in a phrase is that value with a capital letter."""

    def __getitem__(self, key: str) -> str:
        said = VOICES.get(_VOICE.get(), {}).get(key) or _BASE[key]
        if isinstance(said, tuple):
            said = said[_TURN.get() % len(said)]
        return _Capitals(said)


class _Capitals(str):
    def format(self, *args, **kwargs) -> str:  # noqa: D102
        for k, v in list(kwargs.items()):
            if isinstance(v, str) and "{" + k.capitalize() + "}" in self:
                kwargs[k.capitalize()] = v[:1].upper() + v[1:]
        return str.format(self, *args, **kwargs)


PHRASES = _Phrases(_BASE)


def sample(voice: str) -> str:
    """The live sample Settings shows beside the voice choice: an opening,
    a missing line and an offer, in that voice."""
    token = _VOICE.set(voice if voice in VOICES else "natural")
    try:
        return " ".join([
            PHRASES["overview"].format(count="four notes", topic="uni", span="17 July to 4 August"),
            PHRASES["nothing_yet"].format(facets="assessments or due dates"),
            PHRASES["remind"].format(action="ask the tutor on Thursday"),
        ])
    finally:
        _VOICE.reset(token)

#: A note under one of these tags is someone else's words or not a claim
#: about the person (decision 67): left out unless the question asks for it.
CONTEXT_TAGS = frozenset({"joke", "jokes", "quote", "quotes", "fiction", "story", "poem", "lyrics", "test", "draft"})

#: Lines a kind of answer holds after its opening (decision 71: length
#: follows the question's kind).
LINES = {"overview": 5, "likes": 2, "fact": 2, "when": 1, "count": 2, "opinion": 2, "who": 1, "left": 1, "compare": 2}

#: A topic's usual parts, and the words that show a note covers one: what
#: is missing is said only of a topic the notes are plainly about.
FACETS: tuple[tuple[str, re.Pattern, tuple[tuple[str, re.Pattern], ...]], ...] = (
    ("study", re.compile(r"\b(uni|university|lecture|semester|course|class|classes|tutor|study|subject)\b", re.I), (
        ("assessments", re.compile(r"\b(assessment|assignment|exam|quiz|test|essay|midterm)s?\b", re.I)),
        ("due dates", re.compile(r"\b(due|deadline)\b", re.I)),
    )),
    ("trip", re.compile(r"\b(trip|travel|flight|flights|hotel|holiday|itinerary)\b", re.I), (
        ("the dates", re.compile(r"\b\d{1,2}(st|nd|rd|th)? (jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\b|\bdates?\b", re.I)),
        ("a budget", re.compile(r"\b(budget|cost|costs|\$\d)", re.I)),
    )),
    ("purchase", re.compile(r"\b(buy|buying|price|looking at a new|shopping)\b|\$\d", re.I), (
        ("where or when you'll buy it", re.compile(r"\b(order(ed)?|bought|buy (it )?(at|from|on)|in stock|sale)\b", re.I)),
    )),
    ("sport", re.compile(r"\b(golf|range|tennis|footy|soccer|basketball)\b", re.I), (
        ("a full game or round", re.compile(r"\b(round|course|match|game|holes?)\b", re.I)),
    )),
)

_DAYS_PLURAL = re.compile(r"\b(?:(?:mon|tues|wednes|thurs|fri|satur|sun)days?(?:\s+(?:and|or|,)\s+|,\s*)?)+\b", re.I)
_RELATIVE = re.compile(r"\s*\b(?:before |by |until )?(?:next|this|last) (?:week|month|weekend)\b", re.I)
_PREFIX = re.compile(r"^([^:.!?\n]{2,34}):\s+(\S.*)$")
_TIME_LABEL = re.compile(r"^((?:this|next|last) (?:semester|term|year|month|week|weekend)),?\s+(.+)$", re.I)
_ACTION = re.compile(r"(?:^|,\s*|;\s*|\band\s+)((?:ask|call|email|text|book|buy|order|read|check|remember to|pay|send|bring)\b[^.;,]*)$", re.I)
_STILL_TO = re.compile(r"\b([a-z]+(?: [a-z]+)?) (?:are |is )?still to (book|buy|pay|do|send|order|sort)\b", re.I)
_PAST_START = re.compile(
    r"^(went|hit|got|saw|had|did|made|tried|watched|closed|opened|finished|started|played|bought|ate|met|"
    r"wrote|ran|walked|visited|spent|called|booked|fixed|cooked|cleaned|learnt|took)\b",
    re.I,
)
_RATING = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:out of|/)\s*(10|5|100)\b", re.I)
_WORK = re.compile(r"^(?:watched|saw|read|played|finished|listened to)\s+(.+?)\.?$", re.I)
_GOOD = re.compile(r"\b(incredible|amazing|great|loved|love|brilliant|beautiful|fun|good|excellent|fantastic|enjoyed|perfect)\b", re.I)
_BAD = re.compile(r"\b(dragged|boring|bad|hated|awful|terrible|slow|meh|disappointing|too long|weak|annoying)\b", re.I)

#: Labels for a fact in a note with no heading of its own, first match wins.
_CUES: tuple[tuple[str, re.Pattern], ...] = (
    ("Booked", re.compile(r"\b(is|are|was|were|all) booked\b", re.I)),
    ("Where you landed", re.compile(r"\b(leaning towards|decided|going with|chose|picked|settled on)\b", re.I)),
    ("What you want", re.compile(r"\b(i|you) (want|need) (it|one|them)\b|\blooking for\b", re.I)),
    ("Prices", re.compile(r"\$\s?\d.*\$\s?\d")),
    ("Your aim", re.compile(r"^(trying|aiming|hoping|planning) to\b", re.I)),
    ("Your week", re.compile(r"\b(mon|tues|wednes|thurs|fri|satur|sun)days\b|\bevery (mon|tues|wednes|thurs|fri|satur|sun)day\b", re.I)),
    ("How it went", re.compile(r"\b(felt|fun|incredible|amazing|dragged|boring|straighter|better|worse)\b", re.I)),
)

#: The first cues say what a fact is plainly enough to beat the note's own
#: heading: "Mouse update: ... Leaning towards the Logitech" is where you
#: landed, whatever the note is called.
_STRONG_CUES = 4
#: Words that frame a topic without saying anything about it.
_FRAME_WORDS = frozenset(composer._stem(w) for w in "look looking new idea ideas thought thinking about some".split())
#: Words a question asks with that are not its subject ("what have I learned
#: in psych" is about psych; "when are my uni days" about uni).
_ASKING = frozenset(
    composer._stem(w)
    for w in "learned learnt saved save written wrote noted kept think thought know day days week weeks time times "
    "thing things stuff note notes plan plans going".split()
)

#: Verbs a question names its subject with ("spend on groceries"): never the
#: subject's missing word.
_VERBS = frozenset(composer._stem(w) for w in "spend spent buy get make do go like want need try see say use pay cost".split())

_ASKS = {
    "compare": re.compile(r"^\s*(?:the\s+)?(?P<a>[\w' -]{2,30}?)\s+or\s+(?:the\s+)?(?P<b>[\w' -]{2,30}?)\s*\??\s*$", re.I),
    "who": re.compile(r"^\s*who(?:'s| is| was)\s+(?P<name>[A-Za-z][\w' -]{0,30}?)\s*\??\s*$", re.I),
    "when": re.compile(r"^\s*(?:when|what days?|which days?)\b", re.I),
    "count": re.compile(r"^\s*how (?:much|many)\b", re.I),
    "likes": re.compile(r"^\s*(?:do|did) i (?:like|enjoy|love|play|do)\b|^\s*am i (?:into|a fan of)\b", re.I),
    "opinion": re.compile(r"\bwhat did i (?:think|make) of\b|\bhow did i (?:find|like)\b|\bmy (?:review|opinion|thoughts) (?:of|on)\b", re.I),
    "left": re.compile(r"\bwhat do i (?:still )?(?:need|have) to\b|\bwhat(?:'s| is) (?:left|outstanding|still to do)\b|\bto buy\b", re.I),
    "overview": re.compile(
        r"\bwhat (?:have|did) i (?:saved|save|written|write|noted|got|kept)\b|\bwhat(?:'s| is) there\b|\bwhat do i have\b|"
        r"\bwhat \w+(?: \w+)? (?:have|did) i (?:saved|save|written|write|kept|got|noted)\b|\bwhat do my notes say\b|\btell me about\b|\beverything (?:about|on)\b|\bsummari[sz]e\b|\bwhat(?:'s| is) the plan\b|"
        r"\bplans? for\b|^\s*how(?:'s| is| are) (?:my |the )?.+ going\b|\bwhat have i (?:learned|learnt)\b",
        re.I,
    ),
}


def clean(question: str) -> str:
    """The question without the stray marks a hurried hand leaves (INBOX 808:
    "'what is there about a gaming mouse?\\\\'" searched with the backslash
    kept): slashes and quotes at its ends, doubled spaces."""
    text = " ".join((question or "").split())
    return text.lstrip("\\/'\"` ").rstrip("\\/'\"` ")


#: A question that opens with none of these is a topic ("games notes"):
#: an overview.
_ASKED = re.compile(r"^(?:what|what's|whats|when|who|whom|whose|how|how's|do|does|did|is|are|was|were|where|why|which|can|could|should|will|have|has|had|tell|show|list|give|any)\b", re.I)


#: "Summarise this", "what's this about", "tl;dr" (B10): a question about
#: whatever is open where it was asked, with no subject of its own.
_THIS = re.compile(
    r"^(?:(?:can|could) you |please )?(?:"
    r"(?:summari[sz]e|sum up|recap|give me the gist of|what(?:'s| is| are) the (?:gist|main points) of)"
    r"(?: (?:this|it|these|this note|the note|this page|this category|what(?:'s| is| i have) open))?"
    r"|what(?:'s| is) (?:this|it) about|what does (?:this|it) say|tl;? ?dr"
    r")(?: for me| please)?$",
    re.I,
)
#: "summarise Travel", "what's in Uni?", "what do I have in my Work notes":
#: a category by its name (B10), matched against the notebook's own names.
_IN_CATEGORY = re.compile(
    r"^(?:(?:can|could) you |please )?(?:summari[sz]e|sum up|recap|what(?:'s| is) in|what do i have in|what have i got in|show me)"
    r" (?:my |the )?(?P<name>[\w&' -]{2,60}?)(?: notes| category| folder)?$",
    re.I,
)


def about_this(question: str) -> bool:
    """Whether `question` asks about what is open ("Summarise this")."""
    return bool(_THIS.match(clean(question).rstrip("?.! ")))


def named_category(question: str, names: list[str]) -> str | None:
    """The category "summarise Travel" names, from `names` (the notebook's
    categories), or None. Only a whole name counts: "summarise my trip"
    is a topic, not a category."""
    m = _IN_CATEGORY.match(clean(question).rstrip("?.! "))
    if not m:
        return None
    asked = m.group("name").strip().lower()
    return next((n for n in names if n.lower() == asked), None)


def kind_of(question: str) -> str:
    q = clean(question)
    for kind in ("compare", "who", "count", "likes", "opinion", "left", "when", "overview"):
        if _ASKS[kind].search(q):
            return kind
    return "overview" if q and not _ASKED.match(q) else "fact"


#: The notebook's names (words capitalised mid-sentence), for this answer.
_NAMES: ContextVar[set[str]] = ContextVar("digest_names", default=set())


@dataclass
class Fact:
    view: composer.NoteView
    sentence: composer.Sentence
    label: str
    body: str
    action: str = ""
    #: The label is the note's own heading ("Psych lecture 1: ..."), which
    #: the answer says as prose, never as a label line (the owner, 2026-10-11).
    heading: bool = False


@dataclass
class _Out:
    lines: list[str] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)
    offer: dict | None = None
    #: The "so what" after the facts (B1, B4): how alone or how stale they
    #: are, said once, before the offer.
    closing: list[str] = field(default_factory=list)
    #: Lines past the short answer (B5): sent, cited, and folded behind one
    #: "Show two more" the page draws, so the answer is short by default and
    #: the rest is a press away rather than only in the notes on the right.
    more: list[str] = field(default_factory=list)
    #: The one clarifying chip (B9): the other reading, shown only on a tie.
    next: list[str] = field(default_factory=list)
    #: Volunteered insights said (decision 73), for Confirm and Not right.
    insights: list[dict] = field(default_factory=list)


def _day(d: date | None, today: date) -> str:
    if d is None:
        return "an undated day"
    month = composer._MONTHS[d.month - 1]
    return f"{d.day} {month}" if d.year == today.year else f"{d.day} {month} {d.year}"


def _span(views: list[composer.NoteView], today: date) -> str:
    days = sorted(v.written for v in views if v.written)
    if not days:
        return "undated"
    first, last = days[0], days[-1]
    if first == last:
        return f"on {_day(first, today)}"
    if (first.year, first.month) == (last.year, last.month):
        return f"{first.day} to {_day(last, today)}"
    return f"{_day(first, today)} to {_day(last, today)}"


def _capitalised_inside(views: list[composer.NoteView]) -> set[str]:
    """Words written with a capital away from a sentence's start: names, which
    keep their capital when a fact is lowered to follow a label."""
    names: set[str] = set()
    capital: dict[str, int] = {}
    lower: set[str] = set()
    for view in views:
        for s in view.sentences:
            for word in re.findall(r"(?<=[\w,] )([A-Z][\w'-]*)", s.text):
                names.add(word.lower())
            for word in re.findall(r"\b[A-Za-z][\w'-]*", s.text):
                if word[0].isupper():
                    capital[word.lower()] = capital.get(word.lower(), 0) + 1
                else:
                    lower.add(word)
    #: "Lisbon" opens both its notes and is never written small: a name.
    names |= {w for w, n in capital.items() if n >= 2 and w not in lower and not re.search(r"(ing|ed|ly)$", w)}
    return names


@lru_cache(maxsize=1)
def _dictionary() -> frozenset[str]:
    """The shipped English word list (the one spelling uses), read once; a
    word not in it ("Minecraft") is a name and keeps its capital."""
    root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) if getattr(sys, "frozen", False) \
        else Path(__file__).resolve().parents[3]
    try:
        return frozenset((root / "frontend/vendor/wordlist/en.txt").read_text(encoding="utf-8").split())
    except OSError:
        return frozenset()


def _lower_first(text: str, names: set[str]) -> str:
    first = re.match(r"[A-Za-z][\w'-]*", text or "")
    if not first:
        return text
    word = first.group(0)
    if word == "I" or word.lower() in names or (len(word) > 1 and word[1:].isupper()):
        return text
    known = _dictionary()
    if known and word.lower() not in known:
        return text
    return text[0].lower() + text[1:]


def _second_person(text: str) -> str:
    """The writer's words said to them: "I'm doing" to "you're doing", and a
    diary line with no subject ("Went to the range") given its "you"."""
    text = realise.shift_person(text)
    if _PAST_START.match(text):
        text = "you " + text[0].lower() + text[1:]
    return text


#: The day the note being read was written and the day it is now, so a
#: relative time is said as the day it meant (B3).
_TODAY: ContextVar[date | None] = ContextVar("digest_today", default=None)
#: Every note the route read, for "none of them has a note of its own".
_VIEWS: ContextVar[list] = ContextVar("digest_views", default=[])
#: Whether the question asks what a picture says. The words the app read in
#: a picture can run to pages and are private in a way its caption is not:
#: they are quoted when asked for, when there is no caption to say instead,
#: or when the note is mostly its picture.
_ASKS_WORDS: ContextVar[bool] = ContextVar("digest_asks_words", default=False)
#: The person's word on sentences (B31, B32; `ai/verdicts.py`): one marked
#: wrong is not quoted, one pinned is said as theirs.
_KNOWN: ContextVar = ContextVar("digest_known", default=None)
_PIN = re.compile(
    r"\b(?P<pre>(?:before|by|until|in|from) )?(?:the (?P<nth>\d{1,2})(?:st|nd|rd|th) of )?(?P<which>next|this|last) (?P<unit>week|month|weekend)\b",
    re.I,
)


def _pin(text: str, written: date) -> str:
    """"This week" written on 17 July is "the week of 17 July" now (CHAT_PLAN
    B3): true on the day it was written, and wrong said today with no day.
    "The 14th of next month" written in October is 14 November."""
    today = _TODAY.get() or written

    def said(m: re.Match) -> str:
        step = {"next": 1, "this": 0, "last": -1}[m.group("which").lower()]
        pre, unit = m.group("pre") or "", m.group("unit").lower()
        if unit == "month":
            index = written.month - 1 + step
            year, month = written.year + index // 12, index % 12 + 1
            name = composer._MONTHS[month - 1] + (f" {year}" if year != today.year else "")
            if m.group("nth"):
                return f"{pre}{int(m.group('nth'))} {name}"
            return f"{pre if pre.strip().lower() != 'in' else ''}in {name}"
        if unit == "weekend":
            saturday = written + timedelta(days=(5 - written.weekday()) % 7 + 7 * step)
            return f"{pre}the weekend of {_day(saturday, today)}"
        #: The week the app's one resolver means (`when.span`, Monday first,
        #: as the Mentions chip draws it); "before next week" is before its
        #: Monday, a day the person can check (the owner, 2026-10-11).
        found = when_words.span(f"{m.group('which').lower()} week", written, "future")
        monday = found[0] if found else written + timedelta(days=7 * step)
        if pre.strip().lower() in ("before", "by", "until"):
            return f"{pre}{_day(monday, today)}"
        return f"{pre}the week of {_day(monday, today)}"

    text = _PIN.sub(said, text)
    #: "Trimmed my first bowl today", written 2 September, is "on 2
    #: September"; under that day's own label the day is dropped (`_lines`).
    for found in reversed(_spans(text, written)):
        if found.kind in ("date", "datetime") and found.text.lower() in _DEICTIC:
            day = found.value.date() if isinstance(found.value, datetime) else found.value
            text = f"{text[:found.start].rstrip()} on {_day(day, today)}{text[found.end:]}"
    return text


#: The words for the day a note was written, said as that day once read:
#: the recogniser gives the day each means from the note's own date.
_DEICTIC = frozenset(("today", "tonight", "yesterday"))


@lru_cache(maxsize=4096)
def _spans_at(text: str, written: date) -> tuple:
    """The recogniser's first reading of each span in `text`, anchored at
    noon on the day the note was written (the one reader of date words and
    units, CHAT_PLAN decision 46)."""
    return tuple(s for s in recogniser.recognise(text, now=datetime.combine(written, time(12))) if not s.rank)


def _spans(text: str, written: date | None) -> tuple:
    return _spans_at(text, written or _UNDATED) if text else ()


#: The anchor for text with no day of its own: units and figures do not
#: depend on it, and a day read against it is never said.
_UNDATED = date(2000, 1, 1)


#: The note's own asides, dropped when its words are said back (the owner,
#: 2026-10-11: "You just bought a new gaming mouse ... haha" is "you bought a
#: gaming mouse"): laughter, emoji, and "just" or "literally" before a verb
#: in the past ("just bought"), never "just two left", which is "only".
_LAUGHED = re.compile(r"[\s,]*\b(?:(?:ha|he){2,}h?|lo+l+|lmf?a+o+|rofl|xd+)\b[.!]*", re.I)
_EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]+")
_JUST = re.compile(
    r"\b(?:just|literally|finally just)\s+(?=(?:\w+ed|bought|got|went|made|found|sold|paid|spent|won|lost|had|took|saw|met|"
    r"left|came|ran|did|began|set|put|read|heard|told|gave|sent|built|broke|fell|felt|kept|wrote)\b)",
    re.I,
)


def _unfilled(text: str) -> str:
    text = _EMOJI.sub("", _LAUGHED.sub("", text))
    return re.sub(r"\s{2,}", " ", _JUST.sub("", text)).strip()


def _tidy(text: str, written: date | None = None) -> str:
    text = _unfilled(text)
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


def _facts(view: composer.NoteView, names: set[str], subject: set[str] | None = None) -> list[Fact]:
    """A note as labelled facts. A note that names its own heading ("Study
    plan: ...") gives its facts that label, unless a fact says plainly what
    it is (a booking, a choice); otherwise each fact is labelled by what it
    says (a day of the week, a price, a verdict). A sentence that only
    names the topic ("Looking at a new gaming mouse") is the note's frame,
    not a fact, and the answer's opening already says it."""
    out: list[Fact] = []
    if _context_note(view):
        #: A joke or a quote is one piece (decision 67): its question and
        #: its punchline are never two facts.
        whole = " ".join(s.text.strip() for s in view.sentences)
        head = _PREFIX.match(whole)
        label = head.group(1).strip() if head else "Joke"
        body = head.group(2) if head else whole
        return [Fact(view, view.sentences[0], label, body.strip().rstrip("."), "")] if view.sentences else []
    note_label = ""
    shown = [s for s in view.sentences if s.kind == "picture"]
    read = [s for s in view.sentences if s.kind == "picture_text"]
    #: A note that is mostly its picture ("League stats" and a screenshot):
    #: the words in it are what the note says.
    mostly = sum(1 for s in view.sentences if s.kind not in ("picture", "picture_text")) <= 1
    if shown or read:
        #: A picture is one fact, what it shows and the words in it, the
        #: words quoted as read (INBOX 787: never run into the caption).
        what = shown[0].text.strip().rstrip(".") if shown else ""
        words = realise.join_items([f"\u201c{r.text.strip()}\u201d" for r in read[:3]]) if (_ASKS_WORDS.get() or not shown or mostly) else ""
        body = (f"a picture of {_lower_first(what, set())}" if what else "a picture") + (f" reading {words}" if words else "")
        out.append(Fact(view, (shown or read)[0], "", body, ""))
    #: Verdicts are on notes: a document's id is another table's.
    known = _KNOWN.get() if composer.source_kind(view.note) == "note" else None
    owner = view.id
    for i, s in enumerate(view.sentences):
        text = s.text.strip().rstrip(".!")
        if s.kind in ("picture", "picture_text"):
            continue
        if known and known.is_wrong(owner, s.text):
            continue
        pinned = known.pinned_on(owner, s.text) if known else None
        label, body, own = "", text, False
        head = _PREFIX.match(text)
        #: "Watched Dune Part Two: 7 out of 10" names what was done, not a
        #: heading: the sentence stays whole ("you watched Dune Part Two").
        if head and _WORK.match(head.group(1)):
            head = None
        if head and len(head.group(1).split()) <= 5:
            label, body, own = head.group(1).strip(), head.group(2), True
            if i == 0:
                note_label = label
        timed = _TIME_LABEL.match(body)
        if timed and not label:
            label, body, own = timed.group(1)[:1].upper() + timed.group(1)[1:], timed.group(2), True
        if subject and not own and len(body.split()) <= 7:
            content = {composer._stem(w) for w in composer._words(body)} - _FRAME_WORDS
            if content and all(any(composer._holds(st, {w}) for st in subject) for w in content):
                continue
        action = ""
        acted = _ACTION.search(body)
        if acted and acted.start(1) > 0:
            action = acted.group(1).strip()
            body = body[: acted.start()].rstrip(" ,;")
        elif acted and acted.start(1) == 0 and re.search(r"\b(on|by|before) (mon|tues|wednes|thurs|fri|satur|sun)day\b", body, re.I):
            action = body
        pieces = [(body, "")]
        still = _STILL_TO.search(body)
        if still and still.start() > 0 and re.search(r",\s*$", body[: still.start()]):
            #: "Hotel is booked, flights still to book": two facts, and the
            #: second is a to-do.
            pieces = [(body[: still.start()].rstrip(" ,"), ""), (f"{still.group(2).lower()} the {still.group(1).lower()}", "Still to do")]
        for piece, fixed in pieces:
            words = piece.split()
            if not own and len(words) <= 6 and _RELATIVE.search(piece):
                #: "Uni starts back next week.": true on the day it was
                #: written, and misleading said now with no day.
                continue
            strong = next((name for name, cue in _CUES[:_STRONG_CUES] if cue.search(piece)), "")
            cue = fixed or (label if own else "") or strong or note_label or next((name for name, cue in _CUES if cue.search(piece)), "")
            said = _tidy(_second_person(piece), view.written)
            if cue == "Your week":
                said = re.sub(r"\b(?:are|is) (on|every)\b", r"\1", said)
            if cue == "What you want":
                said = re.sub(r"^you (?:want|need) (?:it|one|them) ", "", said)
            if said and pinned and piece is pieces[-1][0]:
                said = PHRASES["pinned"].format(said=said.rstrip("."), day=verdicts.day_words(pinned))
            if said:
                out.append(Fact(view, s, cue, said, _tidy(action, view.written) if piece is pieces[0][0] else "", heading=bool(cue and ((own and head and cue == label) or cue == note_label))))
    return out


def _subject(question: str) -> list[str]:
    return [st for st in (composer._stem(t) for t in composer.subject_terms(clean(question))) if st not in _ASKING]


def _members(question: str, views: list[composer.NoteView]) -> list[composer.NoteView]:
    """The notes the question is about: a category it names, else the notes
    that hold most of its words (in the text, the title or the tags)."""
    q = clean(question).lower()
    named = [v for v in views if str(v.note.get("category") or "").strip() and str(v.note.get("category")).lower() in q]
    stems = _subject(question)
    if named:
        #: "python in Pets": the category's notes that hold the subject, when
        #: the subject is more than the category's own name (B9's chip).
        rest = [st for st in stems if not composer._holds(st, set(composer._words(str(named[0].note.get("category") or ""))))]
        held = [v for v in named if rest and any(composer._holds(st, v.words | v.title_words | v.filed_words) for st in rest)]
        return held or named
    if not stems:
        return []
    scored = []
    for v in views:
        pool = v.words | v.title_words | v.filed_words
        hits = sum(1 for st in stems if composer._holds(st, pool))
        if hits:
            scored.append((hits, v))
    if not scored:
        return []
    everywhere = set().union(*(v.words | v.title_words | v.filed_words for v in views))
    if any(st not in _VERBS and not composer._holds(st, everywhere) for st in stems):
        #: "the weather on Mars": a subject word no note holds is a question
        #: the notes cannot answer, and the composer says which word is missing.
        return []
    best = max(h for h, _ in scored)
    need = best if best >= 2 else 1
    return [v for h, v in scored if h >= need]


def _topic(question: str, members: list[composer.NoteView]) -> str:
    """What the notes are about, in the person's word: the tag they share,
    or the subject as typed."""
    q = clean(question)
    tags: dict[str, int] = {}
    for v in members:
        for t in {str(t).lower().strip("#") for t in (v.note.get("tags") or [])}:
            tags[t] = tags.get(t, 0) + 1
    shared = [t for t, n in sorted(tags.items(), key=lambda kv: -kv[1]) if n >= max(2, len(members) * 3 // 4) and t not in CONTEXT_TAGS]
    typed = re.search(r"\b(?:about|on|for|regarding|in)\s+(.+?)\s*\??$", q, re.I)
    category = next((str(v.note.get("category")) for v in members if str(v.note.get("category") or "").lower() in q.lower() and v.note.get("category")), "")
    if category and shared:
        return shared[0]
    if typed:
        return re.sub(r"^(?:my|the)\s+", "", typed.group(1))
    terms = composer.subject_terms(q)
    if shared and (not terms or shared[0] in " ".join(terms)):
        return shared[0]
    return " ".join(terms) or (shared[0] if shared else "this")


#: How many lines the More fold holds past the short answer; the rest stay
#: "N more on the right".
MORE_LINES = 8


def _lines(out: _Out, facts: list[Fact], limit: int, skip: set[tuple] | None = None, by_day: date | None = None, more: bool = False, weave: bool = False) -> int:
    """Facts grouped under their labels, oldest note first, one line a label;
    the line carries its first note for its one citation mark."""
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
    shown = 0
    before: date | None = None
    seen_days: list[date] = []
    for i, (label, held) in enumerate(list(groups.items())[: limit + (MORE_LINES if more else 0)]):
        bodies = list(dict.fromkeys(_lower_first(f.body.replace(f" on {label}", ""), _NAMES.get()) for f in held))
        #: A line made of pinned sentences says so once, at its end (B32).
        pins = [m.group(0) for b in bodies for m in [_PINNED.search(b)] if m]
        bodies = [_PINNED.sub("", b) for b in bodies]
        line_body = _join(bodies) + (pins[-1] if pins else "")
        said = line_body + (_relate(line_body, by_day) if weave else "")
        written = held[0].view.written
        #: The time since the latest note told above that came before this
        #: one (gold Q2: "a week later, you tried the Viper", though the line
        #: above it was made from the same later note).
        before = max((d for d in seen_days if written and d < written), default=None)
        #: How this line stands to the one before (INBOX 870): the time
        #: between them, said as a clause, when they are days apart.
        #: Only before a clause of the person's own ("you tried ..."): "a
        #: week later, tram 28, pasteis de Belem" joins nothing.
        heading = weave and all(f.heading and f.label == label for f in held)
        mine = re.match(r"you\b|you're\b|your\b", line_body)
        if weave and label in days and not mine:
            #: A day's note in its own shorthand ("squats 80 kg for 5") said
            #: as what the person did that day (the owner, 2026-10-11: every
            #: paragraph gets the first one's treatment).
            told = [_day_clause(b) for b in bodies]
            if all(told):
                #: "..., going on Mondays", not "..., and you were going on Mondays".
                line_body = told[0] + "".join(
                    ", " + c.removeprefix("you were ") if c.startswith("you were going ") else ", and " + c for c in told[1:]
                ) + (pins[-1] if pins else "")
                mine = True
        if weave and label in days and mine:
            #: A day's line is said as that day, not under it (the owner,
            #: 2026-10-11: no label lines), the time since the last one first.
            gap = (written - before).days if i and before and written else 0
            lead = _gap_on(gap, label) if gap >= 2 else f"on {label}, "
            heading, line_body = True, lead[0].upper() + lead[1:] + _reported(line_body, i)
            said = line_body + _relate(line_body, by_day)
        elif heading:
            line_body = _prose(label, held, bodies, i, by_day) + (pins[-1] if pins else "")
            #: A note told by its day after an earlier one says the time
            #: between (gold Q2: "a week later, you tried the Viper").
            on_day = f"On {_day(written, by_day or written)}, " if written else ""
            if on_day and before and (written - before).days >= 2 and line_body.startswith(on_day):
                lead = _gap_on((written - before).days, _day(written, by_day or written))
                line_body = lead[0].upper() + lead[1:] + _reported(line_body[len(on_day):], i)
            said = line_body + _relate(line_body, by_day)
        elif weave and i and before and written and (written - before).days >= 2 and mine:
            #: "A week later" names its day too (the owner, 2026-10-11).
            said = _gap_on((written - before).days, _day(written, by_day or written)) + _reported(line_body, i)
        if written:
            seen_days.append(written)
        (out.lines if i < limit else out.more).append(f"{said}." if heading else f"**{label}:** {said}.")
        row = _row(line_body, held[0])
        #: Every sentence the line was made from (B31, B32): a verdict on
        #: the line is a verdict on each of them.
        parts = list({(f.view.id, f.sentence.start): f for f in held}.values())
        if len(parts) > 1:
            row["parts"] = [{"note_id": f.view.note.get("source_id", f.view.id), "source": f.sentence.text, "start": f.sentence.start, "end": f.sentence.end} for f in parts]
        out.rows.append(row)
        shown += 1
    return shown


def _gap_on(days: int, day: str) -> str:
    """"A week later, on 4 August, "; "three weeks on" takes "by", not a
    second "on"."""
    lead = _vary("gap").format(gap=_gap(days))
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
)
_PAST_PARTICIPLE = {
    "began": "begun", "went": "gone", "saw": "seen", "took": "taken", "did": "done", "wrote": "written",
    "ate": "eaten", "gave": "given", "came": "come", "ran": "run", "drove": "driven", "rode": "ridden",
    "swam": "swum", "sang": "sung", "drank": "drunk", "spoke": "spoken", "broke": "broken", "chose": "chosen",
    "forgot": "forgotten", "knew": "known", "grew": "grown", "threw": "thrown", "flew": "flown", "fell": "fallen",
    "became": "become", "wore": "worn", "hid": "hidden", "woke": "woken", "froze": "frozen", "stole": "stolen",
}
_HAD_PAST = re.compile(r"^you((?: (?:just|recently|only|finally|already|also|actually))*) ([a-z]+ed|" + "|".join(_PAST_PARTICIPLE) + r"|bought|felt|made|found|left|met|paid|sent|spent|told|thought|heard|kept|lost|read|said|sat|slept|stood|taught|won|built|got|put|set|cut|hit|quit)\b")
_REPORTS = ("you mentioned that ", "you wrote that ", "you noted that ", "you said that ", "you recorded that ",
            "you put down that ", "you jotted down that ", "your note said that ")


def _reported(body: str, i: int) -> str:
    """`body`, a clause of the person's own under a dated lead, as reported
    speech when it is in the present or pinned to its note's day; as it is
    otherwise. The reporting verb turns with the line (`i`)."""
    if not re.match(r"you\b", body) or not (_NOW_WORDS.search(body) or _PRESENT.search(body)):
        return body
    said = body
    past = _HAD_PAST.match(said)
    if past and not _PRESENT.match(said):
        verb = past.group(2)
        said = f"you had{past.group(1)} {_PAST_PARTICIPLE.get(verb, verb)}" + said[past.end():]
    for pattern, repl in _BACKSHIFT:
        said = pattern.sub(repl, said)
    return _REPORTS[i % len(_REPORTS)] + said


_PINNED = re.compile(r" \(you pinned this as true, [^)]+\)")

#: What a note's heading names, and how a paragraph opens on it (the owner,
#: 2026-10-11: "In your first psych lecture you learned that ...").
_HEARD = re.compile(r"\b(lecture|class|seminar|talk|tutorial|lesson|workshop|webinar|podcast|reading|course)\b", re.I)
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
_BODY_PART = re.compile(r"^(knees?|back|shoulders?|legs?|arms?|ankles?|hips?|wrists?|neck|feet|foot|hamstrings?|calves|elbows?)\b", re.I)
_PLANNED_FOR = re.compile(r"^(.+?)\s+(planned|booked|set|moved|pencilled in)\s+(for|to)\s+(.+)$", re.I)
_WEEKDAY_WORD = re.compile(r"\b(Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day\b")


def _day_clause(body: str) -> str | None:
    """A day's shorthand as the person's own clause, or None when it is not
    one of the shapes read here: a plan ("Lisbon trip planned for May"), a
    lift log ("squats 80 kg for 5, bench 60 kg for 5"), how a body part felt,
    and "going Monday and Friday"."""
    planned = _PLANNED_FOR.match(body)
    if planned:
        thing = _lower_first(planned.group(1), _NAMES.get())
        return f"you {planned.group(2).lower()} the {thing} {planned.group(3).lower()} {planned.group(4)}"
    if _BODY_PART.match(body):
        return f"your {body[0].lower() + body[1:]}"
    going = re.match(r"^going\s+((?:on\s+)?(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day\b.*)$", body)
    if going:
        days = _WEEKDAY_WORD.sub(lambda m: m.group(0) + "s", going.group(1).removeprefix("on "))
        return f"you were going on {days}"
    lifts = [_LIFT.match(p.strip()) for p in re.split(r",\s*(?:and\s+)?|\s+and\s+", body) if p.strip()]
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
        return f"{_ORDINALS[int(numbered.group(2)) - 1]} {_lower_first(numbered.group(1), _NAMES.get())}"
    return _lower_first(label.strip(), _NAMES.get())


def _past(body: str) -> str:
    """A note's present said from later: "you're still shaky" was then."""
    body = re.sub(r"\byou're\b", "you were", body)
    body = re.sub(r"\byou are\b", "you were", body)
    return re.sub(r"\byou were going to\b", "you planned to", body)


def _clause(body: str, frame: str, i: int, first: bool) -> str:
    """One fact as a clause of the paragraph: a statement heard is what was
    learned, a note-to-self is the task set, a plain noun is what the plan
    has, and the person's own "you ..." stays theirs."""
    body = re.sub(r", not (a|an|the) ", r" rather than \1 ", body)
    if body.lower().startswith("still "):
        return f"you were {body}"
    if re.match(r"(?:you|your)\b", body, re.I):
        return _past(body)
    if body.lower().startswith("going to "):
        return f"{_pick('meant', i)} {body[9:]}"
    task = _TASK.match(body)
    if task:
        verb, obj, when = task.group(1).lower(), task.group(2), task.group(3) or ""
        return _pick("set_task", i).format(obj=obj, verb=verb) + when
    if _DOING.match(body):
        return f"{_pick('meant', i)} {body[0].lower() + body[1:]}"
    if frame == "heard":
        return f"{_pick('learned', i)} {body}"
    if frame in ("planned", "noted"):
        items = [("the " + p if _PLACE_NOUN.match(p) else p) for p in re.split(r",\s*(?:and\s+)?", body) if p]
        return ("has " if first else "it has ") + realise.join_items(items)
    return f"{_pick('noted', i)} {body}"


def _prose(label: str, held: list, bodies: list[str], i: int, today: date | None) -> str:
    """A heading-labelled line said as a paragraph that understands its note
    (the owner, 2026-10-11): "In your first psych lecture you learned that
    memory is reconstructive rather than a recording, and you gave yourself
    chapters 1 to 3 of the Myers textbook to read before 27 July"."""
    named = _heading_said(label)
    written = held[0].view.written
    on = f" on {_day(written, today or written)}" if written else ""
    if _PLANNED.search(label):
        frame, opening = "planned", f"Your {named}"
    elif _DID.search(label):
        frame, opening = "did", f"At the {named}{on}"
    elif _HEARD.search(label):
        frame, opening = "heard", f"In your {named}" + (f", on {_day(written, today or written)}," if written else "")
    elif re.match(r"(?:the|a|an|this|my|your)\b", named, re.I):
        #: "Your the split follows this structure note" (owner, 2026-10-12):
        #: a heading that is a sentence cannot stand between "Your" and "note".
        frame, opening = "noted", "Your note" + (f" of {_day(written, today or written)}" if written else "")
    else:
        frame, opening = "noted", f"Your {named} note"
    clauses = [_clause(b, frame, i + n, n == 0) for n, b in enumerate(bodies)]
    if frame in ("planned", "noted") and re.match(r"you\b", clauses[0]):
        #: The person's own doing needs no heading: its day says when.
        opening = f"On {_day(written, today or written)}," if written else f"In your {named} note,"
    line = f"{opening} {clauses[0]}"
    for clause in clauses[1:]:
        line += (", though " if clause.startswith("you were still") else ", and ") + clause
    return line[0].upper() + line[1:]


#: The joins inside a line (INBOX 870): "; still shaky on big O" reads as
#: a list; ", though you're still shaky on big O" reads as a thought.
_STILL_VERB = re.compile(r"^still (need|have|want|haven't|hasn't|don't|to)\b", re.I)


def _join(bodies: list[str]) -> str:
    out = bodies[0] if bodies else ""
    for body in bodies[1:]:
        if _STILL_VERB.match(body):
            out += ", but you " + body
        elif body.lower().startswith("still "):
            out += ", though you're " + body
        elif body.lower().startswith("going to "):
            out += ", and you're " + body
        else:
            out += "; " + body
    return out


_MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december")
_FOR_MONTH = re.compile(r"\b(?:for|in|by|until) (" + "|".join(m.capitalize() for m in _MONTHS) + r")\b")


def _relate(body: str, today: date | None) -> str:
    """A clause the line's own note does not say (INBOX 870): the gap
    between two prices, or how far off a month it is planned for."""
    prices = re.findall(r"\$\s?(\d+(?:\.\d+)?)", body)
    if len(prices) == 2 and prices[0] != prices[1]:
        gap = abs(float(prices[0]) - float(prices[1]))
        return PHRASES["price_gap"].format(gap=("about " if "about $" in body else "") + f"${gap:g}")
    month = _FOR_MONTH.search(body)
    if month and today:
        ahead = (_MONTHS.index(month.group(1).lower()) + 1 - today.month) % 12
        if ahead >= 2:
            return _vary("months_away").format(away=f"{realise.count_word(ahead)} months")
    return ""


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
    if age >= 21:
        return _vary("stale").format(age=_gap(age))
    if span <= 9:
        return _vary("burst").format(count=realise.count_word(len(days)), span=_gap(max(span, 1)), age=_gap(max(age, 1)))
    if len(days) >= 3:
        #: "every a week" (owner, 2026-10-12): "every" takes the bare unit.
        every = re.sub(r"^(?:about |nearly )?an? ", "", _gap(max(1, round(span / (len(days) - 1)))))
        return _vary("cadence").format(every=every, age=_gap(max(age, 1)))
    return _vary("fresh").format(age=_gap(max(age, 1)))


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
    }


def _missing(members: list[composer.NoteView]) -> str:
    text = " ".join(s.text for v in members for s in v.sentences)
    for _, topic, facets in FACETS:
        if len(topic.findall(text)) >= 2 or (len(members) == 1 and topic.search(text)):
            absent = [name for name, cue in facets if not cue.search(text)]
            if absent:
                return PHRASES["nothing_yet"].format(facets=" or ".join(absent[:2]))
            return ""
    return ""


def _offer(facts: list[Fact]) -> dict | None:
    """One thing to do next, from the notes' own to-dos: the one with a day
    first ("ask the tutor on Thursday"), then something still to book."""
    #: A day in a to-do is the note's day ("ask the tutor on Thursday",
    #: written 4 August, was 6 August): one gone by is not offered for this
    #: Thursday (the owner, 2026-10-11: relative time resolved everywhere).
    actions = [_asked_about(_still_ahead(f.action, f.view.written), f.body) for f in facts if f.action]
    actions.sort(key=lambda a: not any(s.kind in ("date", "datetime") for s in _spans(a, None)))
    if not actions:
        for f in facts:
            still = _STILL_TO.search(f.sentence.text)
            if still:
                actions.append(f"{still.group(2).lower()} the {still.group(1).lower()}")
    if not actions:
        return None
    action = realise.shift_person(actions[0])
    action = action[0].lower() + action[1:]
    return {"kind": "reminder", "label": PHRASES["remind"].format(action=action), "text": action[0].upper() + action[1:]}


_ON_DAY = re.compile(r"\s+on\s+((?:mon|tues|wednes|thurs|fri|satur|sun)day)\b", re.I)


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
        return ("this month" if same else f"in {composer._MONTHS[start.month - 1]}"), ahead
    weeks = (start - (today - timedelta(days=today.weekday()))).days // 7
    return ({0: "this week", 1: "next week"}.get(weeks) or f"the week of {_day(start, today)}"), weeks >= 0


def _narrate(out: _Out, view, facts: list[Fact], today: date) -> set:
    """One note told as what happened, when it has an event with a relative
    time: the event from today ("you're back at uni next week"; months on,
    "you went back to uni the week of 24 July"), then its facts woven in
    with a reporting verb, one citation for the line. The keys of the
    sentences said, for `_lines` to skip; empty when the note has no event."""
    event = next((s for s in view.sentences if s.kind == "prose" and _event(s.text.strip(), view.written)), None)
    if event is None or not view.written:
        return set()
    m = _event(event.text.strip(), view.written)
    when, ahead = _when_now(m.group("when"), view.written, today)
    subj, verb, adv = m.group("subj").strip(), m.group("verb").lower(), (m.group("adv") or "")
    place = subj.lower()
    if place in _BACK_AT and adv.strip() == "back" and verb.startswith(("start", "begin", "go")):
        clause = f"you're back at {place} {when}" if ahead else f"you went back to {place} {when}"
    else:
        name = subj if subj[:1].isupper() and subj.split()[0].lower() not in ("the", "a", "my") else subj[:1].lower() + subj[1:]
        clause = f"{name} {verb if ahead else _PAST.get(verb, verb)}{adv} {when}"
    own = sorted((f for f in facts if f.view.id == view.id and f.sentence.key != event.key), key=lambda f: f.sentence.start)[:3]
    told, trailing = [], []
    for f in own:
        body = _lower_first(f.body, _NAMES.get())
        timed = f.label if _TIME_LABEL.match(f.label + " x") else ""
        if timed and timed.lower() not in body.lower():
            body = f"{body} {timed.lower()}"
        (told if re.match(r"you\b|you're\b|your\b", body) else trailing).append(body)
    line = clause[0].upper() + clause[1:]
    if told:
        line += f", and {_vary('told')} {realise.join_items(told)}"
    if trailing and not ahead:
        line += f", with {realise.join_items(trailing)}"
    line += "."
    if trailing and ahead:
        weekly = " each week" if _DAYS_PLURAL.search(" ".join(trailing)) and "every" not in " ".join(trailing) else ""
        line += " " + _vary("told_future").format(np=realise.join_items(trailing) + weekly)
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


def _overview(out: _Out, question: str, members, facts, today: date, kind: str) -> None:
    topic = _topic(question, members)
    moved = _progress(members, today) if _GOING.search(question) else ""
    if moved:
        out.lines.append(moved)
        quiet = _gone_quiet(members)
        if quiet:
            out.closing.append(quiet)
    elif kind == "likes":
        times = "once" if len(members) == 1 else ("twice" if len(members) == 2 else f"{realise.count_word(len(members))} times")
        out.lines.append(PHRASES["likes"].format(topic=topic, times=times, span=_span(members, today)))
    else:
        opening = PHRASES["overview"].format(count=_count(len(members)), topic=topic, span=_span(members, today))
        #: The opening answers in the person's terms (INBOX 870): where they
        #: have got to, or how much is still open, not only how many notes.
        landed = next((f for f in facts if f.label == "Where you landed"), None)
        left = [f for f in facts if f.label == "Still to do"]
        if landed:
            opening = _vary("landed").format(opening=opening.rstrip("."), landed=_lower_first(landed.body, _NAMES.get()))
            #: Said once, up front, as the answer; not again as a line.
            facts = [f for f in facts if f is not landed]
        elif left:
            opening = _vary("open_count").format(opening=opening.rstrip("."), left="one thing" if len(left) == 1 else f"{realise.count_word(len(left))} things")
        out.lines.append(opening)
    shown_notes = {f.view.id for f in facts}
    told: set = set()
    if not moved:
        for view in members:
            told |= _narrate(out, view, facts, today)
    _lines(out, facts, LINES[kind] - (len(out.lines) - 1), skip=told, by_day=today, more=kind == "overview", weave=True)
    if not moved:
        pattern = _pattern(members, today)
        if pattern:
            out.closing.append(pattern)
    hidden = len(members) - len({r["note_id"] for r in out.rows})
    if kind == "overview" and hidden > 0 and len(shown_notes) > LINES[kind]:
        out.lines.append(PHRASES["more_right"].format(count=_count(hidden).capitalize()))


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
                    return PHRASES["gone_quiet"].format(word=word, month=composer._MONTHS[v.written.month - 1])
    return ""


def _best(facts: list[Fact], question: str, cue: re.Pattern | None = None) -> Fact | None:
    stems = {composer._stem(t) for t in composer.subject_terms(clean(question))}

    def rank(f: Fact) -> tuple:
        words = set(f.sentence.words)
        hits = sum(1 for st in stems if composer._holds(st, words | f.view.filed_words | f.view.title_words))
        return (bool(cue and cue.search(f.sentence.text)), hits, -f.sentence.order)

    return max(facts, key=rank) if facts else None


def _say_fact(out: _Out, lead: Fact, today: date, question: str) -> None:
    body = lead.body if not lead.label else f"{lead.body}"
    items = [i.strip() for i in re.split(r",\s*", body) if i.strip()]
    if lead.label and len(items) >= 3 and all(len(i.split()) <= 4 for i in items):
        #: "Hobbies I want to try: bouldering, film photography, ukulele":
        #: asked what the hobbies are, the answer is the count and the list.
        out.lines.append(f"{realise.count_word(len(items)).capitalize()}, from your note of {_day(lead.view.written, today)}: {realise.join_items(items)}.")
        others = [v for v in _VIEWS.get() if v.id != lead.view.id]
        if not any(composer._holds(composer._stem(w), v.words) for v in others for i in items for w in composer.subject_terms(i)[-1:]):
            out.closing.append(PHRASES["none_own"])
    elif lead.label and lead.label not in {name for name, _ in _CUES} and not _TIME_LABEL.match(lead.label + " x"):
        #: A heading the note gives itself ("Psych lecture") names the note;
        #: a label the answer gave the fact ("How it went") does not.
        out.lines.append(f"From your {lead.label[0].lower() + lead.label[1:]} note, {_day(lead.view.written, today)}: {body}.")
    else:
        out.lines.append(PHRASES["from_note"].format(fact=body[0].upper() + body[1:], day=_day(lead.view.written, today)))
    out.rows.append(_row(body, lead))


#: "when did I buy that gaming mouse": one thing that happened, asked for
#: its day, against "when are my uni days" (a habit, said as its days).
_WHEN_DID = re.compile(r"^\s*when (?:did|was|were|have|had|do i|i)\b", re.I)
#: "have bought", "'ve got": said in the past once its day leads.
_PERFECT = re.compile(r"(?:'ve|\s+have|\s+has)\s+(?=(?:\w+ed|bought|got|gone|made|found|sold|paid|spent|won|lost|had|taken|seen|met|left|done|read|heard|sent|built|kept|written)\b)", re.I)
_PARTICIPLE = {"gone": "went", "taken": "took", "seen": "saw", "done": "did", "written": "wrote"}


def _event_lead(out: _Out, lead: Fact, today: date) -> bool:
    """"On 17 July you bought a gaming mouse, discounted from $150 to $68.":
    the day first, then what happened, in the past and without the note's
    asides (the owner, 2026-10-11). The day is the one the sentence names
    ("bought it yesterday" is the day before the note), else the note's."""
    if lead.view.written is None:
        return False
    text = _unfilled(lead.sentence.text.strip().rstrip(".!"))
    if re.match(r"(?:finally|then|eventually|also|at last)\s+\w+ed\b", text, re.I):
        #: "Finally finished the 5k": the writer did it.
        text = "I " + text[0].lower() + text[1:]
    body = _second_person(text)
    day = lead.view.written
    for found in _spans(body, lead.view.written):
        if found.kind in ("date", "datetime"):
            value = found.value.date() if isinstance(found.value, datetime) else found.value
            if isinstance(value, date):
                day = value
                body = f"{body[:found.start]}{body[found.end:]}"
            break
    body = re.sub(r"\s+(?:on|at)\s*$|\s+on(?=\s*[,.])", "", body.strip())
    body = _tidy(body, None)
    body = _PERFECT.sub(" ", body)
    body = re.sub(r"\b(gone|taken|seen|done|written)\b", lambda m: _PARTICIPLE[m.group(1).lower()], body, count=1)
    if not re.match(r"you\s", body, re.I):
        #: "Dentist appointment went fine": no one did it; said as before.
        return False
    body = body[4:].lstrip()
    #: "bought a new gaming mouse": a thing bought is new; "a new" goes.
    body = re.sub(r"\b(bought|got|ordered|picked up) (?:a|an) new (\w)", lambda m: f"{m.group(1)} {'an' if m.group(2).lower() in 'aeiou' else 'a'} {m.group(2)}", body)
    body = re.sub(r"(\w) ((?:discounted|reduced|marked down|down|on sale) from\b)", r"\1, \2", body)
    if len(body.split()) < 2:
        return False
    said = _day(day, today)
    out.lines.append(f"On {said} you {body}.")
    row = _row(out.lines[-1], lead)
    #: The mark sits after the day it vouches for ("On 17 July[1] you ...").
    row["anchor"] = f"On {said}"
    out.rows.append(row)
    return True


def _single(out: _Out, kind: str, question: str, members, facts, today: date) -> None:
    cue = {
        "when": re.compile(r"\b(mon|tues|wednes|thurs|fri|satur|sun)days\b|\bin (jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*", re.I),
        "count": re.compile(r"\$\s?\d|\d"),
        "opinion": _RATING,
    }.get(kind)
    lead = _best(facts, question, cue)
    if lead is None:
        return
    rest = [f for f in facts if f is not lead]
    if kind == "when" and _WHEN_DID.match(clean(question)) and _event_lead(out, lead, today):
        rest = []
    elif kind == "when":
        days = _DAYS_PLURAL.search(lead.body)
        if days and len(days.group(0).strip()) > 3:
            said = days.group(0).strip(" ,")
            out.lines.append(PHRASES["from_note"].format(fact=said[0].upper() + said[1:], day=_day(lead.view.written, today)))
            out.rows.append(_row(said, lead))
            rest = [f for f in rest if re.search(r"\b(mon|tues|wednes|thurs|fri|satur|sun)days\b|\bafternoons\b|\bmornings\b|\bevenings\b", f.sentence.text, re.I)]
            if rest:
                rest = [Fact(f.view, f.sentence, "Also on your week", f.body, f.action) for f in rest]
        else:
            _say_fact(out, lead, today, question)
            rest = [f for f in rest if f.view.id == lead.view.id]
    elif kind == "opinion":
        work = next((_WORK.match(f.sentence.text.strip()) for f in facts if _WORK.match(f.sentence.text.strip())), None)
        rating = next((_RATING.search(f.sentence.text) for f in facts if _RATING.search(f.sentence.text)), None)
        if work and rating:
            #: "Watched Dune Part Two: 7 out of 10, the sound was incredible":
            #: the title is the words before the rating or its first colon.
            title = re.split(r"\s*[:,(]\s+|\s+-\s+|\s+\d+(?:\.\d+)?\s*(?:/|out of)\b", work.group(1))[0].strip()
            out.lines.append(f"You gave {title} {rating.group(1)} out of {rating.group(2)} on {_day(lead.view.written, today)}.")
            out.rows.append(_row(f"{title} {rating.group(1)} out of {rating.group(2)}", lead))
            rest = []
            for f in facts:
                for part in re.split(r"\s+but\s+|;\s*|,\s*|:\s+", f.sentence.text.strip().rstrip(".")):
                    if _RATING.search(part) or _WORK.match(part):
                        continue
                    label = "Loved" if _GOOD.search(part) else "Didn't" if _BAD.search(part) else ""
                    if label:
                        rest.append(Fact(f.view, f.sentence, label, _lower_first(_second_person(part), set()), ""))
        else:
            _say_fact(out, lead, today, question)
    elif kind == "count":
        clauses = re.split(r"\s+and\s+(?=\$?\d)", lead.sentence.text.strip().rstrip("."))
        stems = {composer._stem(t) for t in composer.subject_terms(clean(question))}
        main = next((c for c in clauses if any(composer._holds(st, set(composer._words(c))) for st in stems)), clauses[0])
        said = _second_person(main)
        said = _week_written(said, lead.view.written, today)
        said = _tidy(said, lead.view.written)
        #: Against the aim the notes set (INBOX 870): "$84 ..., under your
        #: aim of $100 a week", which no one note says.
        spent = re.search(r"\$\s?(\d+(?:\.\d+)?)", said)
        aim = next((m for f in facts for m in [re.search(r"\bunder \$\s?(\d+(?:\.\d+)?)((?: a| per) (?:week|month|day))?", f.sentence.text)] if m), None)
        line = said[0].upper() + said[1:]
        if spent and aim:
            key = "aim_under" if float(spent.group(1)) <= float(aim.group(1)) else "aim_over"
            line = _vary(key).format(said=line, aim=f"${aim.group(1)}{aim.group(2) or ''}")
            facts = [f for f in facts if not re.search(r"\bunder \$", f.sentence.text) or f is lead]
        out.lines.append(line if line.endswith(".") else line + ".")
        out.rows.append(_row(said, lead))
        if "week of" in said and len(members) == 1:
            out.closing.append(PHRASES["only_week"])
        extra = [c for c in clauses if c is not main]
        rest = [Fact(lead.view, lead.sentence, "Also that week", _tidy(_second_person(c), lead.view.written).lstrip("you spent ").strip(), "") for c in extra]
        rest += [f for f in facts if f is not lead and f.view.id == lead.view.id]
    elif lead.heading and (_HEARD.search(lead.label) or _DID.search(lead.label) or _PLANNED.search(lead.label)):
        #: The note's heading said as prose, its other sentences in the same
        #: paragraph (the owner, 2026-10-11), one mark for all of them.
        rest = [f for f in rest if f.view.id == lead.view.id]
        along = [f for f in rest if f.heading and f.label == lead.label][:2]
        rest = [f for f in rest if f not in along]
        held = [lead, *along]
        line = _prose(lead.label, held, [_lower_first(f.body, _NAMES.get()) for f in held], 0, today)
        out.lines.append(line + ".")
        row = _row(line, lead)
        if along:
            row["parts"] = [{"note_id": f.view.note.get("source_id", f.view.id), "source": f.sentence.text, "start": f.sentence.start, "end": f.sentence.end} for f in held]
        out.rows.append(row)
    else:
        _say_fact(out, lead, today, question)
        rest = [f for f in rest if f.view.id == lead.view.id]
    _lines(out, rest, LINES.get(kind, 2))
    labels = {f.label for f in rest}
    score = re.search(r"You gave .+? (\d+(?:\.\d+)?) out of", out.lines[0]) if out.lines else None
    if kind == "opinion" and score and {"Loved", "Didn't"} <= labels:
        #: The verdict the two lines add up to (INBOX 870).
        out.closing.append(_vary("mixed").format(score=score.group(1)))
    if len(members) == 1 and kind in ("fact", "opinion"):
        noun = "film review" if kind == "opinion" else "note"
        out.lines.append(PHRASES["only_note"] if noun == "note" else PHRASES["only_kind"].format(noun=noun))


def _who(out: _Out, name: str, views, names: set[str], today: date) -> bool:
    found = [(v, s) for v in views for s in v.sentences if re.search(rf"\b{re.escape(name)}\b", s.text, re.I)]
    if not found:
        return False
    notes = {v.id for v, _ in found}
    view, s = found[0]
    fact = _tidy(_second_person(s.text.strip()), view.written)
    if len(notes) == 1:
        out.lines.append(PHRASES["who_once"].format(name=name[:1].upper() + name[1:], day=_day(view.written, today), fact=fact))
        out.closing.append(PHRASES["only_names"].format(name=name[:1].upper() + name[1:]))
    else:
        out.lines.append(PHRASES["who_many"].format(name=name[:1].upper() + name[1:], count=_count(len(notes)), span=_span([v for v, _ in found], today)))
        for v, s2 in found[:LINES["overview"]]:
            body = _tidy(_second_person(s2.text.strip()), v.written)
            out.lines.append(f"**{_day(v.written, today)}:** {body}.")
    out.rows.append({"sentence": fact, "note_id": view.note.get("source_id", view.id), "source": s.text, "score": 1.0, "digest": True})
    return True


def _compare(out: _Out, a: str, b: str, views, today: date, names: set[str]) -> bool:
    sentences = [(v, s) for v in views for s in v.sentences]

    def aliases(side: str) -> set[str]:
        said = {side.lower()}
        for _, s in sentences:
            m = re.search(rf"(?i:\b{re.escape(side)})((?:\s+[A-Z0-9][\w-]*){{1,4}})", s.text)
            if m:
                said |= {w.lower() for w in m.group(1).split() if len(w) > 2}
        return said

    sides = {a: aliases(a), b: aliases(b)}

    def about(side: str, text: str) -> bool:
        return any(re.search(rf"\b{re.escape(w)}\b", text, re.I) for w in sides[side])

    full = {}
    for side in (a, b):
        for _, s in sentences:
            m = re.search(rf"\b((?i:the\s+)?(?i:{re.escape(side)})(?:\s+[A-Z0-9][\w-]*){{0,4}})", s.text)
            if m:
                full[side] = re.sub(r"^the\s+", "", m.group(1), flags=re.I)
                break
    if len(full) < 2:
        return False
    lean = re.compile(r"\b(leaning towards|prefer|decided on|going with|chose|picked)\s+(?:the\s+)?(\w+)", re.I)
    winner, why_view, why = "", None, ""
    for v, s in sentences:
        m = lean.search(s.text)
        if m:
            for side in (a, b):
                if m.group(2).lower() in sides[side]:
                    winner, why_view = side, v
                    against = [x.text for x in v.sentences if x is not s and (about(a, x.text) or about(b, x.text))]
                    why = "you're leaning towards it"
                    if against:
                        reason = _tidy(_second_person(re.sub(r"^[^:]{2,30}:\s+", "", against[0])), v.written)
                        why += f" after {_lower_first(reason, names)}"
    if not winner:
        return False
    out.lines.append(PHRASES["pick"].format(side=winner[:1].upper() + winner[1:], why=why))
    out.offer = _note_offer(PHRASES["pick_note"].format(side=winner[:1].upper() + winner[1:]), f"My pick: the {full[winner]}")
    out.rows.append({"sentence": why, "note_id": why_view.note.get("source_id", why_view.id), "source": why, "score": 1.0, "digest": True})
    #: Decision 71: a comparison is a table, a column a side, a row a thing
    #: the notes say of both (the price, what you found, how often it comes
    #: up), so the two can be read across rather than one after the other.
    cells: dict[str, dict[str, str]] = {"Price": {}, "What you found": {}, "In your notes": {}}
    for side in (a, b):
        named = [(v, s) for v, s in sentences if about(side, s.text)]
        for v, s in named:
            for clause in re.split(r"\s+and\s+(?=the\s)|;\s*|:\s+", s.text.strip().rstrip(".")):
                alone = about(side, clause) and not any(about(o, clause) for o in (a, b) if o != side)
                price = re.search(r"\$\s?\d[\d,.]*", clause)
                if alone and price and side not in cells["Price"]:
                    cells["Price"][side] = ("about " if "about" in clause else "") + price.group(0)
                elif alone and not price and not lean.search(clause) and side not in cells["What you found"]:
                    said = _tidy(_second_person(clause), v.written)
                    said = re.sub(rf"^.*?\b(?:it|{re.escape(side)}\w*)\s+", "", said, count=1, flags=re.I) if len(said.split()) > 8 else said
                    cells["What you found"][side] = said
        days = sorted(v.written for v in {v.id: v for v, _ in named}.values() if v.written)
        count = len({v.id for v, _ in named})
        cells["In your notes"][side] = f"{_count(count)}, last on {_day(days[-1], today)}" if days else _count(count)
    #: A row the same on both sides compares nothing; it is left out.
    rows = [(name, got) for name, got in cells.items() if got and not (len(got) == 2 and got[a] == got[b])]
    if rows:
        head = f"| | {full[a]} | {full[b]} |"
        body = [f"| {name} | {got.get(a, 'nothing yet')} | {got.get(b, 'nothing yet')} |" for name, got in rows]
        out.lines.append("\n".join([head, "| --- | --- | --- |", *body]))
    return True


def _stands_for(out: _Out, abbr: str, views: list, today: date) -> bool:
    """"What does CC stand for?" from the person's own notes (B7): the
    phrase their notes give it, the note that says so, and how much they
    use it. Never a dictionary's reading."""
    learned = glossary.learn(str(v.note.get("content") or "") for v in views)
    phrase = learned.get(abbr)
    if not phrase:
        return False
    dated = sorted(views, key=lambda v: (v.written or date.min, v.rank))
    holds = [v for v in dated if phrase.lower() in str(v.note.get("content") or "").lower()]
    both = [v for v in holds if re.search(rf"\b{re.escape(abbr)}\b", str(v.note.get("content") or ""))]
    view = (both or holds or [None])[0]
    if view is None:
        return False
    sentence = next((s for s in view.sentences if phrase.lower() in s.text.lower()), view.sentences[0] if view.sentences else None)
    if sentence is None:
        return False
    #: Said outright ("Cloud Computing (CC)") or only seen beside it: the
    #: second is a reading, and the answer says so.
    line = PHRASES["stands_for" if both else "stands_for_seen"].format(abbr=abbr, phrase=phrase, day=_day(view.written, today))
    out.lines.append(line)
    out.rows.append(_row(line.rstrip("."), Fact(view, sentence, "", phrase)))
    using = [v for v in dated if re.search(rf"\b{re.escape(abbr)}\b", str(v.note.get("content") or ""))]
    if len(using) > 1 and using[-1].written:
        out.closing.append(PHRASES["uses"].format(abbr=abbr, count=_count(len(using)), day=_day(using[-1].written, today)))
    return True


def all_said(question: str, notes: list[dict], *, today: date | None = None) -> dict | None:
    """"Tell me more" when the answer before said everything (B8): that it
    did, how many notes and over which days, rather than "Nothing in the
    notes found answers that" about a topic it has just answered."""
    today = today or date.today()
    asked = clean(question)
    views = [v for v in (composer.read_note(n, i) for i, n in enumerate(composer._distinct_ids(notes or []))) if v]
    members = _members(asked, views) if asked and views else []
    if not members:
        return None
    _TODAY.set(today)
    out = _Out()
    line = PHRASES["all_said"].format(topic=_topic(asked, members), count=_count(len(members)), span=_span(members, today))
    out.lines.append(line)
    first = min(members, key=lambda v: (v.written or date.min, v.rank))
    if first.sentences:
        out.rows.append(_row(line.rstrip("."), Fact(first, first.sentences[0], "", "")))
    return _result(out, "more", asked)


def answer(
    question: str, notes: list[dict], *, today: date | None = None, voice: str = "natural", turn: int = 0,
    insight: str = "one", learned=None, known=None,  # noqa: ANN001
) -> dict | None:
    """The decision-70 answer to `question` from the route's `notes`, or None
    when the question is not one this shape answers (a sum, a time, a
    command, nothing found): the caller then asks `composer.compose`."""
    today = today or date.today()
    asked = clean(question)
    if not asked:
        return None
    kind = kind_of(asked)
    views = [v for v in (composer.read_note(n, i) for i, n in enumerate(composer._distinct_ids(notes or []))) if v]
    if not views:
        return None
    names = _capitalised_inside(views)
    _NAMES.set(names)
    _TODAY.set(today)
    _VOICE.set(voice if voice in VOICES else "natural")
    _TURN.set(turn)
    _SEED.set(zlib.crc32(asked.lower().encode()))
    _VIEWS.set(views)
    _KNOWN.set(known)
    _ASKS_WORDS.set(bool(re.search(r"\b(?:says?|said|reads?|written|text|words?|wording)\b", question, re.I)))
    wants_context = bool(set(composer._words(asked)) & {composer._stem(t) for t in CONTEXT_TAGS})
    if not wants_context:
        views = [v for v in views if not _context_note(v)]
    out = _Out()
    abbr = glossary.asked(question)
    if abbr and _stands_for(out, abbr, views, today):
        return _result(out, "fact", asked)
    if kind == "who":
        name = _ASKS["who"].search(asked).group("name").strip()
        if not _who(out, name, views, names, today):
            return None
        return _result(out, kind, asked)
    if kind == "compare":
        m = _ASKS["compare"].search(asked)
        if not _compare(out, m.group("a").strip(), m.group("b").strip(), views, today, names):
            return None
        facts = [f for v in views for f in _facts(v, names)]
        want = next((f for f in facts if f.label == "What you want"), None)
        if want:
            out.lines.append(f"You want it {want.body}; nothing says which one meets that.")
        return _result(out, kind, asked)
    if about_this(asked) or named_category(asked, list({str(v.note.get("category") or "") for v in views})):
        #: The route sent only what is open, or the category named (B10):
        #: every note is the subject.
        return _this(out, views, names, today, asked)
    if wants_context:
        members = [v for v in views if _context_note(v) or any(composer._holds(st, v.words) for st in composer._words(asked))]
    else:
        members = _members(asked, views)
    if not members:
        return None
    members.sort(key=lambda v: (v.written or date.min, v.rank))
    tie = _tie(asked, members) if kind == "overview" else None
    other, others = "", []
    if tie:
        members, other, others = tie
    subject = set(_subject(asked))
    facts = [f for v in members for f in _facts(v, names, subject)]
    if not facts:
        return None
    if kind == "left":
        if not _left(out, asked, members, views, names, today):
            return None
        return _result(out, kind, asked)
    if kind in ("overview", "likes") and len(members) >= 2:
        _overview(out, asked, members, facts, today, kind)
    elif kind in ("overview", "likes") and (told := _narrate(out, members[0], facts, today)):
        #: One note with an event: told as what happened, then the rest.
        _lines(out, [f for f in facts if f.sentence.key not in told], 2)
        out.lines.append(PHRASES["only_note"])
    elif kind in ("overview", "likes"):
        _single(out, "fact", asked, members, facts, today)
    else:
        _single(out, kind, asked, members, facts, today)
    if not out.lines:
        return None
    if kind in ("overview", "likes") and len(members) >= 2:
        missing = _missing(members)
        if missing:
            out.lines.append(missing)
    if tie:
        topic = _topic(asked, members)
        out.closing.insert(0, PHRASES["tie"].format(topic=topic, category=other, count=_count(len(others))))
        out.next.append(PHRASES["tie_chip"].format(topic=topic, category=other))
    if kind in ("overview", "likes") and not tie:
        _confirmed_first(out, asked, members, learned)
        _volunteer(out, asked, members, notes, today, insight, learned)
    out.offer = out.offer or _offer(facts) or _kind_offer(kind, asked, members, facts, today, out)
    return _result(out, kind, asked)


#: Volunteered insight (CHAT_PLAN decision 73): "off", "one" line, or "all"
#: as found. What it may say: a pattern, a plan gone quiet, a change of mind,
#: from `ai/insights`' measured rules, each over these notes only.
INSIGHT_LEVELS = ("off", "one", "all")
#: How much of an insight must rest on the notes the answer is about, before
#: any dismissal; each "Not right" raises it, so a person who keeps
#: dismissing hears fewer, and only the closest.
INSIGHT_BAR = 0.5
INSIGHT_STEP = 0.1


def insight_bar(learned) -> float:  # noqa: ANN001
    dismissed = len(getattr(learned, "dismissed", ()) or ())
    return min(1.0, INSIGHT_BAR + INSIGHT_STEP * dismissed)


def _volunteer(out: _Out, asked: str, members, notes: list[dict], today: date, level: str, learned) -> None:  # noqa: ANN001, ARG001
    """At most one measured insight (all, at "all") the answer has not
    already said, scored by how much of it rests on the answer's notes."""
    if level not in INSIGHT_LEVELS or level == "off":
        return
    from tessellate.ai import insights

    ids = {v.note.get("source_id", v.id) for v in members}
    #: The route's notes carry their day as `written` words; the rules read
    #: an ISO `created_at` (the composer's `_insights_for` does the same).
    own = [{**v.note, "id": v.note.get("source_id", v.id), "created_at": v.written.isoformat()} if v.written else v.note for v in members]
    topic = _topic(asked, members)
    found = [*insights.for_subject(topic, own, today, asked), *insights.drift(own, today), *insights.contrast(own, today)]
    dismissed = getattr(learned, "dismissed", frozenset()) or frozenset()
    said = " ".join(out.lines).lower()
    scored = []
    for item in found:
        if insights.key(item) in dismissed or not item.note_ids:
            continue
        #: The person's word on a sentence beats an inference that quotes it.
        known = _KNOWN.get()
        if known and known.quoted_in(item.text):
            continue
        #: Novelty: "you have written about uni 4 times" after "You have
        #: four notes about uni" says nothing new.
        #: Except a hobby forming: the count is old news, the hobby is not.
        hobby = item.slots.get("hedge") == composer_tables.INSIGHT_HEDGES["hobby"]
        if item.rule in ("recurrence", "streak") and not hobby and realise.count_word(len(members)) in said:
            continue
        relevance = len(set(item.note_ids) & ids) / len(item.note_ids)
        if relevance >= insight_bar(learned):
            scored.append((relevance, item))
    scored.sort(key=lambda pair: -pair[0])
    for _, item in scored[: 1 if level == "one" else 3]:
        row = insights.as_row(item, learned)
        if row["confirmed"]:
            #: The person's word, said as theirs, once (and first when it is
            #: about the subject asked, `_confirmed_first`).
            if row["text"] not in out.lines:
                out.closing.insert(0, row["text"])
            out.insights.append(row)
            continue
        if item.rule == "drift" and _weave_drift(out, str(item.slots.get("plan") or "")):
            #: Said once, in the line that already tells the plan (the owner,
            #: 2026-10-11); the row under the answer only asks if it is right.
            row["in_answer"] = True
        elif item.rule == "recurrence" and realise.count_word(len(members)) in said:
            #: The count is the opening's; what is new is the hedge.
            hedge = str(item.slots.get("hedge") or "")
            out.closing.insert(0, hedge[:1].upper() + hedge[1:] + ".")
            row["in_answer"] = True
        else:
            out.closing.insert(0, item.text)
        out.insights.append(row)


def _confirmed_first(out: _Out, asked: str, members, learned) -> None:  # noqa: ANN001
    """A subject the person confirmed an insight on opens with their word,
    as a fact (decision 60, as `composer._confirmed_lead` does)."""
    confirmed = getattr(learned, "subjects", None)
    if not callable(confirmed):
        return
    from tessellate.ai import insights

    about = {insights._stems(_topic(asked, members)), *(insights._stems(t) for t in _subject(asked))}
    for subject, line in confirmed().items():
        if subject in about:
            out.lines.insert(0, line)
            return


def _weave_drift(out: _Out, plan: str) -> bool:
    """A plan no later note picks up, said as a clause of the line that
    tells the plan. False when no line tells it."""
    words = re.findall(r"[a-z0-9]+", re.sub(r"^(?:i'?m |i am )?going to ", "", plan.lower()))
    if len(words) < 3:
        return False
    tail = r"\W+".join(words[-4:])
    for i, line in enumerate(out.lines):
        if i and re.search(tail, line.lower()) and not line.startswith("**"):
            out.lines[i] = line.rstrip(".") + ", " + PHRASES["drift_woven"] + "."
            #: The line's mark goes at its end, so its row says all of it.
            for row in out.rows:
                if row.get("sentence") and line.rstrip(".").endswith(row["sentence"]):
                    row["sentence"] = out.lines[i].rstrip(".")
            return True
    return False


def _this(out: _Out, views: list, names: set[str], today: date, asked: str) -> dict | None:
    """"Summarise this" (B10): the open note, its facts under their labels;
    or the open category, as an overview of its notes."""
    views = sorted(views, key=lambda v: (v.written or date.min, v.rank))
    facts = [f for v in views for f in _facts(v, names)]
    if not facts:
        return None
    if len(views) == 1:
        v = views[0]
        title = _tidy(str(v.note.get("title") or "")) or (facts[0].label if facts[0].label else "")
        category = str(v.note.get("category") or "").strip()
        where = f", in {category}" if category and category.lower() != "uncategorised" else ""
        title = title.lower() if title and title not in names else title or "untitled"
        said = [(_lower_first(_second_person(f.body), names), f) for f in facts]
        if len(said) == 1:
            out.lines.append(PHRASES["this_one"].format(title=title, day=_day(v.written, today), where=where, pause="," if where else "", fact=said[0][0]))
            out.rows.append(_row(said[0][0], said[0][1]))
        else:
            out.lines.append(PHRASES["this_note"].format(
                title=title, day=_day(v.written, today), where=where, points=f"{realise.count_word(len(said))} points"))
            #: One point a line, as a list: the note's own heading is the
            #: lead's, so it is not repeated as every line's label.
            #: One block, so the list renders tight rather than spaced.
            points = []
            for text, fact in said[:MORE_LINES]:
                label = f"**{fact.label}:** " if fact.label and fact.label.lower() != title.lower() else ""
                points.append(f"- {label}{text[:1].upper() + text[1:]}.")
                out.rows.append(_row(text, fact))
            out.lines.append("\n".join(points))
    else:
        category = Counter(str(v.note.get("category") or "") for v in views).most_common(1)[0][0] or "these notes"
        out.lines.append(PHRASES["this_many"].format(count=_count(len(views)), topic=category, span=_span(views, today)))
        _lines(out, facts, LINES["overview"], by_day=today, more=True)
        missing = _missing(views)
        if missing:
            out.lines.append(missing)
    if not out.lines:
        return None
    out.offer = _offer(facts)
    return _result(out, "overview", asked)


def _tie(question: str, members: list) -> tuple[list, str, list] | None:
    """Two readings of one word that tie (B9): the notes split evenly
    between two categories and, past the asked word, share no word at all
    ("python" in Coding and in Pets). The newer reading is answered; the
    other is named, with one chip to ask about it. Anything short of an
    even split with nothing shared is one subject, answered whole."""
    q = clean(question).lower()
    groups: dict[str, list] = {}
    for v in members:
        category = str(v.note.get("category") or "").strip()
        if not category or category.lower() in q or category.lower() == "uncategorised":
            return None
        groups.setdefault(category, []).append(v)
    if len(groups) != 2:
        return None
    (a, first), (b, second) = groups.items()
    #: One note on each side is a passing mention, not a second reading
    #: (a joke note and the homework it was about).
    if len(first) != len(second) or len(first) < 2:
        return None
    asked = set(_subject(question))
    def words(group: list) -> set[str]:
        return {w for v in group for w in v.words if len(w) > 2 and not any(composer._holds(st, {w}) for st in asked)}
    if words(first) & words(second):
        return None
    newest = max(members, key=lambda v: (v.written or date.min, v.rank))
    if newest in second:
        (a, first), (b, second) = (b, second), (a, first)
    return first, b, second


_PLACE = re.compile(r"\b(?:the )?(driving range|range|gym|pool|court|course|track|studio|climbing wall|park)\b", re.I)
_REVIEWED = re.compile(r"\b(film|movie|book|show|series|album|game)s?\b", re.I)


def _note_offer(label: str, text: str) -> dict:
    return {"kind": "note", "label": label, "text": text}


def _kind_offer(kind: str, question: str, members, facts: list[Fact], today: date, out: _Out) -> dict | None:
    """The one acting offer when the notes name no to-do of their own (B12):
    what the kind of question suggests doing with the answer, each one a
    thing the app does in one press (a reminder or a note)."""
    text = " ".join(s.text for v in members for s in v.sentences)
    if kind == "likes":
        places = sorted({m.group(1).lower() for m in _PLACE.finditer(text)}, key=len, reverse=True)
        if places:
            where = "the " + places[0]
            return {"kind": "reminder", "label": PHRASES["go_again"].format(place=where), "text": f"Go to {where}"}
    if kind == "opinion":
        noun = _REVIEWED.search(question + " " + " ".join(str(t) for v in members for t in (v.note.get("tags") or [])) + " " + text)
        noun_word = {"movie": "film"}.get(noun.group(1).lower(), noun.group(1).lower()) if noun else "film"
        return _note_offer(PHRASES["start_list"].format(noun=noun_word), f"{noun_word.capitalize()}s to watch next\n\n- [ ] ")
    if kind == "count" and re.search(r"\$\s?\d", text) and re.search(r"\b(spen[dt]|budget|cost)", question + " " + text, re.I):
        return {"kind": "reminder", "label": PHRASES["log_weekly"], "text": "Log your spending every Sunday"}
    if kind == "fact":
        listed = re.search(r"^\w+, from your note of [^:]+: (.+)\.$", out.lines[0]) if out.lines else None
        if listed:
            first = re.split(r",\s*| and ", listed.group(1))[0].strip()
            return {"kind": "reminder", "label": PHRASES["try_one"].format(item=first), "text": f"Try {first}"}
    if kind == "overview" and members and all(_context_note(v) for v in members) and len(members) >= 2:
        pieces = [f.body for f in facts]
        topic = _topic(question, members)
        return _note_offer(PHRASES["gather"], f"{topic[:1].upper() + topic[1:]}\n\n" + "\n\n".join(pieces))
    if kind == "overview" and _GOING.search(question):
        table = _lift_table(members, today)
        if table:
            return _note_offer(PHRASES["track_table"].format(what=table[0]), table[1])
    landed = next((f for f in facts if f.label == "Where you landed"), None)
    if landed:
        side = re.search(r"towards (?:the )?(.+)$", landed.body)
        if side:
            return _note_offer(PHRASES["pick_note"].format(side=side.group(1).strip()), f"My pick: the {side.group(1).strip()}")
    return None


def _lift_table(members, today: date) -> tuple[str, str] | None:
    """Each dated note's measures as one table row ("Track your lifts in a
    table?"): the columns are the measures any note gives."""
    rows, columns = [], []
    for v in members:
        found = {}
        for s in v.sentences:
            for word, _value, figure, unit in _measures(s.text):
                found.setdefault(word, f"{figure} {unit}")
        if found and v.written:
            rows.append((v.written, found))
            columns += [c for c in found if c not in columns]
    if len(rows) < 2:
        return None
    what = "lifts" if any(r[1].endswith("kg") for _, f in rows for r in [tuple(f.items())[0]]) else "numbers"
    head = "| Day | " + " | ".join(c.capitalize() for c in columns) + " |"
    rule = "| --- |" + " --- |" * len(columns)
    body = ["| " + _day(d, today) + " | " + " | ".join(f.get(c, "") for c in columns) + " |" for d, f in rows]
    return what, "\n".join([what.capitalize(), "", head, rule, *body])


def _left(out: _Out, question: str, members, views, names: set[str], today: date) -> bool:
    """"What do I need to buy": the open list first, then the other things
    still to do the notes name."""
    buying = re.search(r"\b(buy|shop|get)\b", question, re.I)
    lists = []
    for v in views:
        for s in v.sentences:
            head = _PREFIX.match(s.text.strip())
            if head and len(head.group(2).split(",")) >= 3:
                shop = re.search(r"\b(grocer|shopping|buy|list)", head.group(1) + " " + " ".join(v.note.get("tags") or []) + " " + str(v.note.get("category") or ""), re.I)
                if shop or not buying:
                    lists.append((v, s, head))
    if not lists:
        return False
    v, s, head = lists[-1]
    items = [i.strip().rstrip(".") for i in head.group(2).split(",") if i.strip()]
    what = head.group(1).strip().lower()
    #: Decision 71: what is left is a checklist, the opening then a box an
    #: item, so the list reads down rather than along one sentence.
    opening = f"{realise.count_word(len(items)).capitalize()} {what}, from your list of {_day(v.written, today)}"
    out.lines.append(opening + ":\n" + "\n".join(f"- [ ] {item}" for item in items))
    out.rows.append({"sentence": opening, "note_id": v.note.get("source_id", v.id), "source": s.text,
                     "start": s.start, "end": s.end, "score": 1.0, "digest": True})
    open_bits = []
    for w in views:
        for t in w.sentences:
            still = _STILL_TO.search(t.text)
            if still and w is not v:
                topic = next((str(x) for x in (w.note.get("tags") or []) if str(x).lower() not in still.group(1).lower()), "")
                open_bits.append(f"the {topic[:1].upper() + topic[1:] + ' ' if topic else ''}{still.group(1).lower()}")
    if open_bits:
        out.lines.append(f"**Also still open:** {realise.join_items(open_bits[:2])}.")
    out.offer = {"kind": "checklist", "label": PHRASES["checklist"], "text": head.group(1).strip(), "items": items}
    return True


def _more(out: _Out) -> dict | None:
    """What the page folds: the More lines by their labels (the bold words
    each opens with), and the button's words."""
    if not out.more:
        return None
    labels = [m.group(1) for line in out.more if (m := re.match(r"\*\*(.+?):\*\*", line))]
    #: A line said as prose has no label (the owner, 2026-10-11): the page
    #: finds every folded line by the words it opens with.
    starts = [" ".join(re.sub(r"\*\*", "", line).split()[:5]) for line in out.more]
    return {"labels": labels, "starts": starts, "label": PHRASES["more_show"].format(count=realise.count_word(len(out.more))), "lines": list(out.more)}


def _lead_figure(line: str) -> str | None:
    """The figure a count opens with ("$84", "90 kg", "12"), as the
    recogniser reads it, for the page to draw large (`digestShape`): the
    page finds it by its text and never reads a figure itself."""
    lead = re.sub(r"\*\*", "", line)
    found = next((s for s in _spans(lead, None) if s.kind in ("money", "quantity", "number", "duration")), None)
    return found.text if found and found.start <= len("You've spent ") else None


def _result(out: _Out, kind: str, question: str) -> dict:
    #: One paragraph a line: a single newline inside a paragraph is a space
    #: to every markdown reader, so the labelled lines ran together.
    paragraphs = list(out.lines) + out.more + out.closing[: 2 + len(out.insights)]
    if out.offer:
        paragraphs.append(out.offer["label"])
    text = "\n\n".join(paragraphs)
    n = len(out.rows)
    return {
        "text": text,
        "grounding": out.rows,
        #: `digest` and `offer` ride on the support too: it is what the Ask
        #: box hands its grounding renderer, which then draws one mark a line
        #: and no chips or count under the answer.
        "support": {"supported": n, "sentences": n, "unsupported": [], "digest": True, "offer": out.offer, "shape": kind, "more": _more(out),
                    "figure": _lead_figure(out.lines[0]) if kind == "count" and out.lines else None},
        "shape": f"digest:{kind}",
        "parts": [("template", text)],
        "next": list(out.next),
        "next_parts": [[("template", n)] for n in out.next],
        "insights": list(out.insights),
        "broad": kind == "overview",
        "digest": True,
        "offer": out.offer,
    }


#: "search the web for X", "look up X": the words that ask, not the subject.
_WEB_ASK = re.compile(r"^(?:(?:hey|hi|ok|okay),? )?(?:(?:can|could|will) (?:you|u) )?(?:(?:please|pls|plz) )?(?:search (?:the )?(?:web|internet|online) (?:for|about)|search up|look up|google|find (?:on|from) the web|web search(?: for)?)\s+", re.I)


def web_query(question: str) -> str:
    """What to search for: the turn without its "can you search the web for"."""
    return clean(_WEB_ASK.sub("", clean(question))) or question


def web(question: str, pages: list[dict], composed: dict | None = None) -> dict | None:
    """An answer from web pages in decision 70's shape (decision 66): what
    was searched and how many pages were read, then one line a page, its
    title as the label and its own sentence that best meets the question,
    cited by the page's address. Never empty when a page has text (INBOX
    810: "searched the web ... and then didnt even output the results")."""
    asked = clean(_WEB_ASK.sub("", clean(question)))
    terms = set(composer._words(asked))
    picked: dict[int, dict] = {}
    for row in (composed or {}).get("grounding") or []:
        picked.setdefault(row.get("note_id"), row)
    out = _Out()
    def meets(page: dict) -> int:
        return len(terms & set(composer._words(str(page.get("content") or ""))))

    order = sorted(pages, key=lambda p: (p["id"] not in picked, -meets(p), pages.index(p)))
    for page in order[:3]:
        view = composer.read_note({**page, "tags": []}, 0)
        if view is None:
            continue
        row = picked.get(page["id"])
        span = str(row["sentence"]) if row else ""
        if not span:
            ranked = sorted(
                (s for s in view.sentences if len(s.text.split()) >= 5 and len(s.text) <= 260),
                key=lambda s: -len(terms & set(s.words)),
            )
            span = ranked[0].text.strip() if ranked else ""
        if not span:
            continue
        title = " ".join((view.title or page.get("domain") or "A page").split()[:8])
        out.lines.append(f"**{title}:** {span}")
        out.rows.append({
            "sentence": span, "note_id": page["id"], "kind": "web", "url": page["url"], "title": title,
            "score": 1.0, "digest": True, "said": "quoted",
        })
    if not out.lines:
        return None
    n = len(out.lines)
    out.lines.insert(0, f"I searched the web for “{asked}” and read {realise.count_word(n)} {'page' if n == 1 else 'pages'}; each is under the answer to read here.")
    return _result(out, "web", question)
