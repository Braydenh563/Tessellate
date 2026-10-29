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

import calendar
import re
import sys
import zlib
from collections import Counter
from collections.abc import Callable, Iterable
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import NamedTuple
from datetime import date, datetime, time, timedelta
from functools import lru_cache
from pathlib import Path

from tessellate.ai import composer, composer_frame, composer_lists, composer_slots, composer_tables, glossary, realise, verdicts
from tessellate.ai.composer_lists import clean
from tessellate.ai import recognise as recogniser
from tessellate.ai import when as when_words

#: The connecting words, one table (decision 72: a voice swaps this, never
#: the facts). `{}` slots are filled in order.
_BASE = {
    "overview": "You have {count} about {topic}‹, {span}›.",
    "likes": "It looks that way: you've written about {topic} {times}‹, {span}›.",
    "from_note": "{fact}, from {name}{when}.",
    "from_list": "{count}, from your {what}‹ of {day}›: {items}.",
    "only_one": "It's your only note on {topic} so far.",
    "who_once": "{name} comes up once‹, on {day}›: {fact}.",
    "who_many": "{name} comes up in {count}‹, {span}›.",
    "pick": "The {side}, by your notes: {why}.",
    "more_right": "{count} more on the right.",
    "more_show": "Show {count} more",
    "stands_for": "{abbr} is short for {phrase}, from {name}‹, written on {day}›.",
    "stands_for_seen": "{abbr} looks like {phrase}: {name}‹, written on {day},› names it in full.",
    "uses": "You use {abbr} in {count}‹, the last on {day}›.",
    "all_said": "That's all your notes say on {topic} so far: {count}‹, {span}›.",
    "tie": "{Topic} also comes up in {category}: {count} on something else.",
    "tie_chip": "What have I saved about {topic} in {category}?",
    #: A line the person pinned as true (B32): said as their word.
    "pinned": "{said} (you pinned this as true, {day})",
    "this_note": "{Name}‹ of {day}›{where}, in {points}:",
    "this_one": "{Name}‹ of {day}›{where}{pause} says one thing: {fact}.",
    "this_many": "{Count} in {topic}‹, {span}›.",
    "nothing_open": "Nothing is open to sum up. Open a note, or pick a category in the sidebar, and ask again; or name it: \"summarise Travel\".",
    "nothing_yet": "Nothing yet on {facets}.",
    "remind": "Remind you to {action}?",
    "checklist": "Save it as a checklist note?",
    "pick_note": "Note the {side} as your pick?",
    "start_list": "Start a list of {noun}s to {verb} next?",
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
    #: One wording each: a reporting verb the note did not make ("you heard
    #: that", "you took away that") is an invented speech act (C38).
    "learned": ("you learned that",),
    "noted": ("you noted", "you wrote down", "you jotted down"),
    "set_task": ("you gave yourself {obj} to {verb}", "you set yourself {obj} to {verb}"),
    "meant": ("you planned to",),
    #: A note's own sections said as its shape (INBOX 1301 D5: "Your first
    #: Phase note has the Opener" read four sections of one note as four notes).
    "in_parts": "it's in {count} {kind}: {names}",
    "has_parts": "it has {count} sections: {names}",
    "still_list": "you still need to {items}",
    #: Open items that are things, not verbs ("passport, charger"): C3.
    "still_open": "{name} still has {items}",
    "a_list": "a list: {items}",
    "a_list_asked": "questions to ask: {items}",
    "told_self": ("you told yourself to", "you reminded yourself to"),
    "drift_woven": "though no later note says how that went",
    "meaning_loading": "The search by meaning is still loading, so this read your words only; ask again in a few seconds.",
    "meaning_off": "Search by meaning is off, so this read your words only; turn it on in Settings, Search and index.",
    "landed": ("{opening}, and you're {landed}.", "{opening}. For now you're {landed}."),
    "open_count": ("{opening}, with {left} still open.", "{opening}, and {left} still to settle."),
    "stale": (
        "The newest of these is {age} old, so things may have moved on since.",
        "You last added to it {age} ago, which is a while; a fresh note would bring it up to date.",
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
        #: Chosen by the question's own number (`_SEEDED`), so the same
        #: closing line is not under every answer ("responses are exactly the
        #: same", the owner, 2026-10-25).
        "only_note": ("It's your only note on that so far.",
                      "That is the only note you have on it so far.",
                      "So far this is your only note on it.",
                      "You have just the one note on that so far."),
        "only_one": ("It's your only note on {topic} so far.",
                     "That is the only note you have on {topic} so far.",
                     "So far this is your only note on {topic}.",
                     "You have just the one note on {topic} so far."),
        "overview": ("You have {count} about {topic}‹, {span}›.",
                     "There are {count} about {topic}‹, {span}›.",
                     "{Count} about {topic}‹, {span}›.",
                     "Your notes on {topic}: {count}‹, {span}›.",
                     "On {topic} you've written {count}‹, {span}›."),
    },
    "professional": {
        "overview": ("Your notebook holds {count} on {topic}‹, {span}›.",
                     "{Count} concern {topic}‹, {span}›.",
                     "On {topic}: {count}‹, {span}›.",
                     "Recorded on {topic}: {count}‹, {span}›.",
                     "The notebook has {count} on {topic}‹, {span}›."),
        "likes": "The notes suggest so: {topic} appears {times}‹, {span}›.",
        "from_note": "{fact}, as recorded in {name}{when}.",
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
        "overview": ("Found {count} about {topic}‹, {span}›.",
                     "Here's the lot: {count} about {topic}‹, {span}›.",
                     "Ooh, {topic}: {count}‹, {span}›.",
                     "Dug up {count} about {topic}‹, {span}›.",
                     "Right, {topic}: {count}‹, {span}›."),
        "likes": "Sounds like it: you've written about {topic} {times}‹, {span}›.",
        "from_note": "{fact}, says {name}{when}.",
        "nothing_yet": "No word yet on {facets}.",
        "remind": "Want a nudge to {action}?",
        "only_week": "That's the only week you've jotted down so far.",
        "none_own": "None of them has its own note yet, so they're all still ideas.",
        "gone_quiet": "{Word} has gone quiet since {month}.",
    },
    "plain": {
        "overview": ("{Count} about {topic}‹, {span}›.",),
        "likes": "Yes. {Topic} comes up {times}‹, {span}›.",
        "from_note": "{fact}. {Name}{when}.",
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


#: The gap leads already said in this answer, in order (reset per answer).
_GAPS: ContextVar[tuple[str, ...]] = ContextVar("digest_gaps", default=())
#: **A date is said only when the question is about time** (INBOX 1441, the
#: owner: "I dont like how it refers to dates"). Otherwise the sentence
#: carries the fact and the record card carries the date: no "On 4
#: September, you saved", no "your note of 27 July", no "A week on, by 3
#: August", no span in the count opener. `_CURRENT`: the question is about
#: how current something is, the only time the staleness footer is said.
_TIMED: ContextVar[bool] = ContextVar("digest_timed", default=True)
_CURRENT: ContextVar[bool] = ContextVar("digest_current", default=True)
#: "Do I like golf?" asks how a taste stands now, so old notes say their
#: age; "what do I like to cook?" asks for a list, not a verdict.
_ASKS_CURRENT = re.compile(
    r"\b(?:latest|current(?:ly)?|up to date|still|now|stale|how old|recent(?:ly)?|newest|lately)\b|"
    r"^\W*(?:so,? )?(?:do|am) i (?:really )?(?:like|love|enjoy|prefer|hate|into)\b", re.I)


def _set_timing(question: str) -> None:
    """What this answer may say about time, from the question (INBOX 1441)."""
    _TIMED.set(composer.asks_time(question))
    _CURRENT.set(bool(_ASKS_CURRENT.search(question or "")))


#: A phrase's date clause, marked ‹...› whole: kept when the question is
#: about time, dropped with every word of it otherwise ("You have six notes
#: about hobbies." says the count; "the last on {day}" never leaves "the last").
_DATE_CLAUSE = re.compile(r"‹([^›]*)›")


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
    if days <= 10:
        #: 10 days rounds to one week: "one weeks on" (INBOX 1310).
        return "a week"
    if days <= 24:
        return f"{realise.count_word(round(days / 7))} weeks"
    if days <= 45:
        return "about a month"
    months = round(days / 30)
    return f"about {realise.count_word(months)} months" if months < 12 else "over a year"


def _bare_gap(gap: str) -> str:
    """`_gap` without its hedge or article, for a frame that brings its own:
    "every a week" (owner, 2026-10-12) and "every about three months" (audit
    1029 C7) are both "every week" and "every three months"."""
    return re.sub(r"^(?:(?:about|nearly|over) )?(?:an? )?", "", gap)


#: Phrases worded by the question as well as the turn: the same question says
#: the same thing, a different one does not.
_SEEDED = frozenset({"only_note", "only_one"})


class _Phrases(dict):
    """`PHRASES[key]` in the voice of the answer being written; a capital
    `{Count}` or `{Topic}` in a phrase is that value with a capital letter."""

    def __getitem__(self, key: str) -> str:
        said = VOICES.get(_VOICE.get(), {}).get(key) or _BASE[key]
        if isinstance(said, tuple):
            at = _SEED.get() + _TURN.get() if key in _SEEDED else _TURN.get()
            said = said[at % len(said)]
        return _Capitals(said)


class _Capitals(str):
    def format(self, *args, **kwargs) -> str:  # noqa: D102
        for k, v in list(kwargs.items()):
            if isinstance(v, str) and "{" + k.capitalize() + "}" in self:
                kwargs[k.capitalize()] = v[:1].upper() + v[1:]
        return str.format(_DATE_CLAUSE.sub(r"\1" if _TIMED.get() else "", self), *args, **kwargs)


PHRASES = _Phrases(_BASE)


def sample(voice: str) -> str:
    """The live sample Settings shows beside the voice choice: an opening,
    a missing line and an offer, in that voice."""
    token = _VOICE.set(voice if voice in VOICES else "natural")
    #: An ordinary question, not about time: no span (INBOX 1441).
    timed = _TIMED.set(False)
    try:
        return " ".join([
            PHRASES["overview"].format(count="four notes", topic="uni", span="17 July to 4 August"),
            PHRASES["nothing_yet"].format(facets="assessments or due dates"),
            PHRASES["remind"].format(action="ask the tutor on Thursday"),
        ])
    finally:
        _TIMED.reset(timed)
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
#: Stemmed on first use, not at import: the first stem builds the spelling-pair
#: table (about 0.3s), which a launch that never composes should not pay.
def _stems(words: str) -> "Callable[[], frozenset[str]]":
    return lru_cache(maxsize=1)(lambda: frozenset(composer._stem(w) for w in words.split()))


_FRAME_WORDS = _stems("look looking new idea ideas thought thinking about some")
#: Words a question asks with that are not its subject ("what have I learned
#: in psych" is about psych; "when are my uni days" about uni).
_ASKING = _stems(
    "learned learnt saved save written wrote noted kept think thought know day days week weeks time times "
    "thing things stuff note notes plan plans going"
)

#: Verbs a question names its subject with ("spend on groceries"): never the
#: subject's missing word.
_VERBS = _stems("spend spent buy get make do go like want need try see say use pay cost")

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
        r"\bplans? for\b|^\s*how(?:'s| is| are) (?:my |the )?.+ going\b|\bwhat have i (?:learned|learnt)\b|"
        #: "what about social connections" asks for the lot (INBOX 1420).
        r"^\s*(?:and |so )?what about (?:my |the )?\w+(?: \w+)?\s*\??\s*$|\bwhat do i know (?:about|on)\b",
        re.I,
    ),
}


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
    r"|what(?:'s| is) (?:the )?(?:main|key|big|core) (?:point|idea|takeaway)s?(?: of (?:this|it))?|(?:the )?(?:main|key) (?:points?|ideas?|takeaways?)|(?:key )?take-?aways?"
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
    #: Said by theme (INBOX 1310): a facet gap on one note is not the answer's.
    framed: bool = False


_KIND_NOUN = {"document": "document", "board": "board", "map": "mind map", "picture": "picture"}


def _from_source(view, fact: str, today: date) -> str:  # noqa: ANN001
    """"Fact, from your note of 3 March." for a note; a document, board or
    map is said as itself by its title (INBOX 1357, class F: "Hamlet delays
    ..., from your note of an undated day" for a document)."""
    noun = _KIND_NOUN.get(getattr(view, "kind", "note") or "note")
    #: "... that work in most settings:, from your note" (INBOX 1420).
    fact = fact.rstrip().rstrip(":;,").rstrip()
    if not noun and _title_only(view) and fact.lower() == view.title.strip().lower():
        #: "Atlas retro meeting, from your note of 26 October": a title said
        #: as a fact (C2). The note is named; it holds nothing more.
        said = _note_called(view.title)
        day = f" of {_day(view.written, today)}" if view.written and _TIMED.get() else ""
        return f"{said[0].upper() + said[1:]}{day} has only its title so far."
    if noun and view.title:
        return f"{fact}, from your {noun} **{view.title}**."
    if view.written is None or not _TIMED.get() and not getattr(view, "titled", False):
        return f"{fact}, from one of your notes."
    when = f", written on {_day(view.written, today)}" if _TIMED.get() else ""
    if not getattr(view, "titled", False):
        return f"{fact}{when}."
    return PHRASES["from_note"].format(fact=fact, name=_your_note(view), when=when)


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
        return "all from today" if first == today else f"on {_day(first, today)}"
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
        for text in [s.text for s in view.sentences]:
            for word in re.findall(r"(?<=[\w,] )([A-Z][\w'-]*)", text):
                names.add(word.lower())
            for word in re.findall(r"\b[A-Za-z][\w'-]*", text):
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


# --- naming and fragments (audit 1029 C1, C2, C3, C8, C38, C39) ---------------------
#: One rule for every frame the answer puts a note's words in: a fragment
#: keeps a name's or a title's capital, a verb frame ("you still need to",
#: "Remind you to", "you planned to") goes only before a verb, a title is
#: named and never said as if spoken, and "[[x]]" is said as x.

_WIKI = re.compile(r"\[\[([^\]|\n]{1,120})(?:\|([^\]\n]{1,120}))?\]\]")


def _unlinked(text: str) -> str:
    """"Check [[Reading list]] later" as "Check Reading list later"; an
    alias ("[[Trips|the trip note]]") is said as the alias."""
    return _WIKI.sub(lambda m: (m.group(2) or m.group(1)).strip(), text or "")


_CALENDAR_WORD = re.compile(r"(?:(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day|January|February|March|April|May|June|July|August|September|October|November|December)\b")


def _titles() -> list[str]:
    """The titles of the notes this answer read, longest first."""
    return sorted({v.title for v in _VIEWS.get() if v.title and v.titled}, key=len, reverse=True)


def _title_capitals() -> set[str]:
    """Words a title writes with a capital past its first word ("Project
    Atlas kickoff meeting"): names, which keep their capital in a fragment
    and in the topic (C1: "project Atlas", "notes about atlas"). Kept apart
    from `_NAMES`, which also says who a question is about."""
    #: Only a title written in sentence case says so: in "The Complete Social
    #: Skills Guide" every word has a capital, so none is a name by it.
    mixed = [t for t in _titles() if re.search(r"\s(?!(?:of|and|the|a|an|to|in|on|for|by)\b)[a-z]", t)]
    return {w.lower() for t in mixed for w in re.findall(r"(?<=\s)[A-Z][\w'-]*", t)}


#: Words that open a clause, never a title: "At Mia's barbecue" is lowered
#: though a name follows; "The Overstory" is not.
_FUNCTION_WORDS = frozenset("""
at in on with for to from by of and but or so after before when while if then this that these those my your his her our
their it we they he she you a an as about into over under during since until because there here
""".split())


def _keeps_capital(word: str, names: set[str]) -> bool:
    return word == "I" or word.lower() in names | _title_capitals() or any(c.isupper() for c in word[1:])


def _starts_a_title(text: str, verb: bool) -> bool:
    if verb:
        return False
    nxt = re.match(r"[A-Za-z][\w'-]*,? +([A-Z][\w'-]*)", text)
    if nxt and not _CALENDAR_WORD.match(nxt.group(1)) and nxt.group(1) != "I":
        #: "Deep Work", "Sara, Tom", "Dune Part Two"; "Invite Daniel" is a verb.
        return True
    return any(text.startswith(t) for t in _titles())


def _fragment(text: str, names: set[str]) -> str:
    """`text` placed after other words ("you noted ..."): its first letter
    lowered only when that word is a plain dictionary word. A name, a title
    ("Deep Work by Cal Newport", "The Overstory", "Project Atlas kickoff
    meeting": a capital on the next word marks one) or a word written with a
    capital inside keeps its capital (C1: "the Overstory", "project Atlas")."""
    text = _unlinked(text)
    first = re.match(r"[A-Za-z][\w'-]*", text or "")
    if not first:
        return text
    word = first.group(0)
    if _keeps_capital(word, names):
        return text
    verb = _verb_led(text) or _did(word) or word.lower() in _FUNCTION_WORDS
    if _starts_a_title(text, bool(verb)):
        return text
    known = _dictionary()
    if known and word.lower() not in known:
        return text
    return text[0].lower() + text[1:]


#: The verbs a to-do or a piece of advice starts with. A list item that does
#: not start with one ("passport", "Tom to draft the spec", "pay cut") is a
#: thing, never put after "you still need to" (C3).
_LEAD_VERBS = frozenset("""
ask book buy call cancel change charge check clean collect compare confirm cook count decide do draft drop email
file fill find finish fix follow get give go invite keep learn listen look make meet message move order organise organize
pack pay phone pick plan post practise practice prepare print protect read register remember renew reply research
return review revise ring schedule sell send ship sign sort start stop study submit suggest take text tidy try update
use visit wash watch water write bring breathe arrange apply back focus feed hand note plant print prep put
set share slow smile stay walk wait sweep save see spend
""".split())
#: A verb that is also the first half of a noun ("pay cut", "book club",
#: "check list"): the item is the noun.
_NOUN_AFTER = frozenset("cut cuts rise raise slip day date list club form centre center room line rate card shop shelf store".split())


def _verb_led(text: str) -> bool:
    """Whether `text` starts with a verb, so a verb frame fits it."""
    words = re.findall(r"[A-Za-z][\w'-]*", text or "")
    if not words or words[0].lower() not in _LEAD_VERBS:
        return False
    return not (len(words) >= 2 and words[1].lower() in _NOUN_AFTER)


def _note_called(title: str) -> str:
    """A note named by its title, the title as written: "your Sourdough
    loaf note", "your note The Overstory" (C2: named, never spoken)."""
    title = _unlinked(title).strip()
    if re.match(r"(?:the|a|an|my|your)\b", title, re.I) or re.search(r"\bnotes?$", title, re.I):
        return f"your note {title}"
    return f"your {title} note"


def _your_note(view) -> str:  # noqa: ANN001
    """The one name for a note in a frame: a titled note by its title, a
    title-less one by its clipped first clause (C8, INBOX 1420), never by a
    section's label or "untitled"."""
    if getattr(view, "titled", False) and view.title:
        return _note_called(view.title)
    note = getattr(view, "note", None) or {"content": getattr(view, "title", "")}
    #: "Trip planning: flights to Lisbon" is your trip planning note.
    label = composer_frame.note_label(note)
    return _note_called(composer_frame.lower_name(label)) if label else composer_frame.short_name(note)


def _title_only(view) -> bool:  # noqa: ANN001
    """A note that is only its name ("Atlas retro meeting")."""
    content = str(view.note.get("content") or "").strip()
    return bool(content) and "\n" not in content and composer_frame.own_title(content) != ""


#: A diary line's "-ing" start is what the writer was doing then, but only
#: before a lower-case word: "Thinking, Fast and Slow" is a book (C39).
_DOING_NOW = re.compile(r"^(?:thinking|planning|looking|hoping|considering|saving up|trying|learning|getting into)\s+(?=[a-z])", re.I)
#: "-ed" words that describe the writer rather than say what they did.
_FELT = frozenset("""
tired bored excited scared stressed worried interested pleased relieved annoyed surprised confused exhausted motivated
inspired determined frustrated disappointed amazed impressed satisfied overwhelmed embarrassed delighted thrilled shocked
married engaged injured hooked obsessed sorted done prepared organised organized sunburned sunburnt
""".split())


def _did(word: str) -> bool:
    """A word that says what the writer did ("Baked", "Repotted"): a listed
    past verb, or an "-ed" dictionary word that is not a feeling."""
    low = word.lower()
    if _PAST_START.match(low):
        return True
    known = _dictionary()
    if not re.fullmatch(r"[a-z]{3,}ed", low) or low.endswith("eed") or low in _FELT or not known:
        return False
    #: "baked", "repotted": the word or its stem ("bake", "repot") is English.
    return any(w in known for w in (low, low[:-1], low[:-2], low[:-3]))


def _second_person(text: str) -> str:
    """The writer's words said to them: "I'm doing" to "you're doing", and a
    diary line with no subject ("Went to the range") given its "you"."""
    text = realise.shift_person(text)
    if _DOING_NOW.match(text):
        #: "thinking of buying the mouse": what the writer was doing then.
        return "you were " + text[0].lower() + text[1:]
    first = re.match(r"[A-Za-z]+", text)
    if first and _did(first.group(0)):
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
        if found.kind in ("date", "datetime") and (found.text.lower() in _DEICTIC or (found.text.lower() == "tomorrow" and written != today)):
            day = found.value.date() if isinstance(found.value, datetime) else found.value
            text = f"{text[:found.start].rstrip()} on {_day(day, today)}{text[found.end:]}"
    return text


#: The words for the day a note was written, said as that day once read:
#: the recogniser gives the day each means from the note's own date.
#: "Tomorrow" is said as its day too once that day is past (INBOX 1357, class
#: D: "tomorrow you pick up your student card" from a July note).
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
    punchline are never two facts."""
    whole = " ".join(s.text.strip() for s in view.sentences)
    head = _PREFIX.match(whole)
    label = head.group(1).strip() if head else "Joke"
    body = head.group(2) if head else whole
    return [Fact(view, view.sentences[0], label, body.strip().rstrip("."), "")] if view.sentences else []


def _picture_fact(view: composer.NoteView, shown: list, read: list) -> Fact:
    """A picture is one fact, what it shows and the words in it, the words
    quoted as read (INBOX 787: never run into the caption)."""
    #: A note that is mostly its picture ("League stats" and a screenshot):
    #: the words in it are what the note says.
    mostly = sum(1 for s in view.sentences if s.kind not in ("picture", "picture_text")) <= 1
    what = shown[0].text.strip().rstrip(".") if shown else ""
    words = realise.join_items([f"“{r.text.strip()}”" for r in read[:3]]) if (_ASKS_WORDS.get() or not shown or mostly) else ""
    body = (f"a picture of {_fragment(what, set())}" if what else "a picture") + (f" reading {words}" if words else "")
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


def _cue_for(piece: str, fixed: str, label: str, own: bool, note_label: str) -> str:
    strong = next((name for name, cue in _CUES[:_STRONG_CUES] if cue.search(piece)), "")
    return fixed or (label if own else "") or strong or note_label or next((name for name, cue in _CUES if cue.search(piece)), "")


def _said_piece(piece: str, cue: str, written: date | None, pinned, last: bool, asked: bool = False) -> str:  # noqa: ANN001
    #: A listed question is a line to ask someone ("I like your jacket,
    #: where is it from?"): its "I" and its "this week" are the asker's,
    #: never "you like your jacket" or "the week of 20 July" (INBOX 1420).
    said = _tidy(piece, None) if asked else _tidy(_second_person(piece), written)
    if cue == "Your week":
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


def _sentence_facts(view: composer.NoteView, s, split: _Split, note_label: str, subject: set[str] | None, pinned) -> list[Fact]:  # noqa: ANN001
    """The facts one sentence gives: its to-do split off, and a sentence of
    two halves ("booked, flights still to book") said as two."""
    if _only_the_subject(split.body, split.own, subject):
        return []
    action, body = _action_of(split.body)
    pieces = _pieces_of(body)
    out: list[Fact] = []
    for n, (piece, fixed) in enumerate(pieces):
        if not split.own and len(piece.split()) <= 6 and _RELATIVE.search(piece):
            #: "Uni starts back next week.": true on the day it was
            #: written, and misleading said now with no day.
            continue
        cue = _cue_for(piece, fixed, split.label, split.own, note_label)
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


def _left_out(view: composer.NoteView, s, known) -> bool:  # noqa: ANN001
    """A picture's sentences are said as one fact; one the person marked wrong is not said."""
    return s.kind in ("picture", "picture_text") or bool(known and known.is_wrong(view.id, s.text))


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
    if _context_note(view):
        return _context_facts(view)
    picture = _picture_of(view)
    out: list[Fact] = [picture] if picture else []
    note_label = ""
    #: Verdicts are on notes: a document's id is another table's.
    known = _KNOWN.get() if composer.source_kind(view.note) == "note" else None
    for i, s in enumerate(view.sentences):
        if _left_out(view, s, known):
            continue
        pinned = known.pinned_on(view.id, s.text) if known else None
        split = _node_split(view, s) or _split_label(_its_title(view, s.text.strip().rstrip(".!"), i))
        if i == 0 and split.titled:
            note_label = split.label
        out += _sentence_facts(view, s, split, note_label, subject, pinned)
    return out


def _subject(question: str) -> list[str]:
    return [st for st in (composer._stem(t) for t in composer.subject_terms(clean(question))) if st not in _ASKING()]


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
    return [v for v in views if str(v.note.get("category") or "").strip() and str(v.note.get("category")).lower() in q]


def _unanswerable(stems: list[str], views: list[composer.NoteView]) -> bool:
    """"the weather on Mars": a subject word no note holds is a question
    the notes cannot answer, and the composer says which word is missing."""
    everywhere = set().union(*(_pool(v) for v in views))
    return any(st not in _VERBS() and not composer._holds(st, everywhere) for st in stems)


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
    named = [st for st in stems if st not in _VERBS()] or stems
    scored = [
        (hits, v) for v in views
        if any(composer._holds(st, _pool(v)) for st in named) and (hits := sum(1 for st in stems if composer._holds(st, _pool(v))))
    ]
    if not scored or _unanswerable(stems, views):
        return []
    best = max(h for h, _ in scored)
    need = best if best >= 2 else 1
    return [v for h, v in scored if h >= need]


def _shared_tags(members: list[composer.NoteView]) -> list[str]:
    """The tags most of the notes carry, commonest first (a joke's or quote's own tag is not a topic)."""
    tags: dict[str, int] = {}
    for v in members:
        for t in {str(t).lower().strip("#") for t in (v.note.get("tags") or [])}:
            tags[t] = tags.get(t, 0) + 1
    return [t for t, n in sorted(tags.items(), key=lambda kv: -kv[1]) if n >= max(2, len(members) * 3 // 4) and t not in CONTEXT_TAGS]


def _named_category(q: str, members: list[composer.NoteView]) -> str:
    """The first member's category that the question names, or empty."""
    return next((str(v.note.get("category")) for v in members if str(v.note.get("category") or "").lower() in q.lower() and v.note.get("category")), "")


def _topic_typed(typed: "re.Match[str] | None") -> str:
    """The subject after "about/on/for", as typed, without a time window."""
    if not typed:
        return ""
    #: "for next month" is a time, not a topic (1324).
    return re.sub(r"^(?:my|the)\s+", "", recogniser.without_windows(typed.group(1))).strip(" ,")


def _topic_sides(q: str) -> str:
    """"compare the Porto and Lisbon notes": about Porto and Lisbon, as typed,
    not "porto lisbon" (1324)."""
    sides = composer.compare_sides(q)
    return " and ".join(re.sub(r"^(?:my|the|our)\s+", "", side, flags=re.I) for side in sides) if sides else ""


def _as_written(topic: str, members: list[composer.NoteView]) -> str:
    """The topic with each name in the capitals the notes write it in:
    "lisbon" typed small is "Lisbon" (C1: "two notes about lisbon")."""
    #: A name: a word not in the dictionary ("lisbon") or one a title writes
    #: with a capital ("atlas"); "social" in "Complete Social Skills" is neither.
    names = {w for w in _NAMES.get() if w not in _dictionary()} | _title_capitals()
    text = " ".join(f"{v.title} " + " ".join(s.text for s in v.sentences) for v in members)
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
    typed = re.search(r"\b(?:about|on|for|regarding|in)\s+(.+?)\s*\??$", q, re.I)
    category = _named_category(q, members)
    if category and shared:
        #: "social connections", tagged social: the category as typed, not
        #: its first word (INBOX 1301 D5); "Courses & Study" tagged uni: uni.
        return category.lower() if shared[0] in category.lower().split() else shared[0]
    said = (not typed and _topic_sides(q)) or _topic_typed(typed)
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


_DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


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
_SHORTHAND = re.compile(r"^(?!(?:you|your|at|in|on|with|after|before|from|for|during|to|by|this|last|next|the day)\b)[a-z]", re.I)


_HERE_ARE = re.compile(r"^here(?:'s| is| are)\s+((?:some|a few|a list of|a|an)\s+)?", re.I)
_WH_SUBJECT = re.compile(r"(?:what|how|why|which|who|where)\b", re.I)


def _dated_lead(label: str, i: int, by_day: date | None, written: date | None, before: date | None) -> str:
    """The line's lead: the time since the line before, a recent day, or its date."""
    if not _TIMED.get():
        return ""
    gap = (written - before).days if i and before and written else 0
    #: The time since the line before reads first; a run's first line, or
    #: one the same days as the last, says a recent day as a person would.
    recent = _recent(written, by_day) if not gap or (by_day and written and (by_day - written).days <= 7) else ""
    return recent or (_gap_on(gap, label) if gap >= 2 else f"on {label}, ")


def _cleaned_body(line_body: str, label: str) -> str:
    """The note's words with its own date, a pasted "however" and a "here are" opener taken out."""
    #: A note that opens on its own day ("on 21 September, you have work")
    #: already has it in the lead: kept, it read "on 21 September, on 21
    #: September, you have work", and the present tense went unshifted.
    line_body = re.sub(rf"^on {re.escape(label)},?\s*", "", line_body, flags=re.I) or line_body
    #: A pasted summary's "however" answers text that is not there (1420).
    line_body = re.sub(r",\s*however,", "", line_body)
    #: "Here are some refined ... starters" is what was saved, not said.
    return _HERE_ARE.sub(lambda m: "you saved " + (m.group(1) or ""), line_body, count=1)


def _said_as_written(line_body: str, i: int) -> str:
    """The body as reported speech: shorthand noted, a statement about something else written, else retold."""
    #: "What your notes leave out is how ...": a clause of its own, its verb late.
    asked_clause = bool(_WH_SUBJECT.match(line_body) and _FINITE.search(line_body))
    if _OBLIGED.match(line_body):
        #: "you wrote down need to cut eating out" (audit 1029 C13): a need
        #: is said as one, not as an object of "wrote down".
        return f"you {line_body[0].lower() + line_body[1:]}"
    if _SHORTHAND.match(line_body) and not _FINITE.search(line_body.split(",")[0]) and not asked_clause:
        #: "golf practice after work, hit a bucket ...": shorthand with no
        #: verb is what the person wrote down, never a dated fragment.
        return f"{_pick('noted', i)} {line_body}"
    if _SHORTHAND.match(line_body) and not _CLAUSE_HEAD.match(line_body):
        #: "by 20 July, Cloud computing is the delivery of ...": a statement
        #: about something else is what the person wrote (INBOX 1420).
        return _REPORTS[i % len(_REPORTS)] + _fragment(line_body, _NAMES.get())
    return _reported(line_body, i)


def _dated_line(line_body: str, label: str, i: int, by_day: date | None, written: date | None, before: date | None) -> tuple[str, str]:
    """A day's line is said as that day, not under it (the owner,
    2026-10-11: no label lines), the time since the last one first."""
    lead = _dated_lead(label, i, by_day, written, before)
    reported = _said_as_written(_cleaned_body(line_body, label), i)
    line_body = lead + reported
    line_body = line_body[:1].upper() + line_body[1:]
    return line_body, line_body + _relate(line_body, by_day)


def _heading_line(label: str, held: list[Fact], bodies: list[str], i: int, by_day: date | None, tail: str, before: date | None, same: bool = False) -> tuple[str, str]:
    line_body = _prose(label, held, bodies, i, by_day, same) + tail
    written = held[0].view.written
    #: A note told by its day after an earlier one says the time
    #: between (gold Q2: "a week later, you tried the Viper").
    on_day = f"On {_day(written, by_day or written)}, " if written and _TIMED.get() else ""
    if on_day and before and (written - before).days >= 2 and line_body.startswith(on_day):
        lead = _gap_on((written - before).days, _day(written, by_day or written))
        line_body = lead[0].upper() + lead[1:] + _reported(line_body[len(on_day):], i)
    return line_body, line_body + _relate(line_body, by_day)


def _said_body(f: Fact, label: str) -> str:
    """A fact's words as a line says them; a note that is only its title
    is named, never said as if spoken ("you noted atlas retro meeting", C2)."""
    if _title_only(f.view) and f.body.strip().rstrip(".") == f.view.title.strip():
        return f"you started {_note_called(f.view.title)}"
    return _fragment(f.body.replace(f" on {label}", ""), _NAMES.get())


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
        said = _gap_on(_days_apart(before, written), _day(written, by_day or written)) + _reported(line_body, i)
    return said, line_body, bool(heading)


def _line_row(line_body: str, held: list[Fact]) -> dict:
    row = _row(line_body, held[0])
    #: Every sentence the line was made from (B31, B32): a verdict on
    #: the line is a verdict on each of them.
    parts = list({(f.view.id, f.sentence.start): f for f in held}.values())
    if len(parts) > 1:
        row["parts"] = [{"note_id": f.view.note.get("source_id", f.view.id), "source": f.sentence.text, "start": f.sentence.start, "end": f.sentence.end} for f in parts]
    return row


def _lines(out: _Out, facts: list[Fact], limit: int, skip: set[tuple] | None = None, by_day: date | None = None, more: bool = False, weave: bool = False) -> int:
    """Facts grouped under their labels, oldest note first, one line a label;
    the line carries its first note for its one citation mark."""
    groups, days = _group_by_label(facts, skip, by_day)
    shown = 0
    seen_days: list[date] = []
    last = None
    for i, (label, held) in enumerate(list(groups.items())[: limit + (MORE_LINES if more else 0)]):
        written = held[0].view.written
        #: The time since the latest note told above that came before this
        #: one (gold Q2: "a week later, you tried the Viper", though the line
        #: above it was made from the same later note).
        before = max((d for d in seen_days if written and d < written), default=None)
        said, line_body, heading = _line_of(label, held, i, weave, by_day, days, before, last == held[0].view.id)
        last = held[0].view.id
        if written:
            seen_days.append(written)
        (out.lines if i < limit else out.more).append(f"{said}." if heading else f"**{label}:** {said}.")
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


def _reported(body: str, i: int) -> str:
    """`body`, a clause of the person's own under a dated lead, as reported
    speech when it is in the present or pinned to its note's day; as it is
    otherwise. The reporting verb turns with the line (`i`)."""
    if not re.match(r"you\b", body) or not (_NOW_WORDS.search(body) or _PRESENT.search(body)):
        return body
    if _HABIT.match(body):
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
        thing = _fragment(planned.group(1), _NAMES.get())
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
        return f"{_ORDINALS[int(numbered.group(2)) - 1]} {_fragment(numbered.group(1), _NAMES.get())}"
    #: "League of Legends", "Gym Routine Overview": a later capital marks a
    #: name, kept whole (INBOX 1310: "Your league of Legends note").
    if any(w[:1].isupper() for w in label.split()[1:3]):
        return label.strip()
    return _fragment(label.strip(), _NAMES.get())


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


def _clause_of_frame(body: str, frame: str, i: int, first: bool) -> str:
    """The clause a body gets from the frame alone, once no task or doing claimed it."""
    if frame == "heard":
        return f"{_pick('learned', i)} {body}"
    if frame in ("planned", "noted"):
        items = [("the " + p if _PLACE_NOUN.match(p) else p) for p in re.split(r",\s*(?:and\s+)?", body) if p]
        return ("has " if first else "it has ") + realise.join_items(items)
    return f"{_pick('noted', i)} {body}"


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
    return realise.join_items([p for b in bodies for p in re.split(r",\s*(?:and\s+)?", b) if p])


def _noted_section(head: str, items: str, view, today: date | None) -> str:  # noqa: ANN001
    """A title-less note that is one labelled thought: "On 22 October, you noted an idea: ..."."""
    article = "" if head.endswith("s") or head[:1].isupper() else ("an " if head[:1] in "aeiou" else "a ")
    written = view.written
    lead = _recent(written, today) or (f"on {_day(written, today or written)}, " if written and _TIMED.get() else "")
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
    if not view.titled and first.startswith(label.strip().lower()):
        line = _noted_section(head, items, view, today)
    elif same:
        line = f"it also has {head}: {items}"
    else:
        line = f"{_your_note(view)} has {head}: {items}"
    return line[0].upper() + line[1:]


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
        opening = (recent[:1].upper() + recent[1:] + "," if recent else f"On {_day(written, today or written)},") if written else f"In your {named} note,"
        if written and not _TIMED.get():
            opening = ""
    line = f"{opening} {clauses[0]}".lstrip()
    for clause in clauses[1:]:
        line += (", though " if clause.startswith("you were still") else ", and ") + clause
    return line[0].upper() + line[1:]


#: The joins inside a line (INBOX 870): "; still shaky on big O" reads as
#: a list; ", though you're still shaky on big O" reads as a thought.
_STILL_VERB = re.compile(r"^still (need|have|want|haven't|hasn't|don't|to)\b", re.I)


_FRAGMENT = re.compile(r"^(?:[a-z]+ing\b|(?!(?:you|i|we|he|she|they|it)\b)\w+(?:\s+\w+){0,2}$)", re.I)


def _join(bodies: list[str], sentences: bool = False) -> str:
    """A line's bodies as one line. Woven into an overview (`sentences`),
    two facts are two sentences, never a ";" run (INBOX 1301 D5)."""
    out = bodies[0] if bodies else ""
    for body in bodies[1:]:
        if sentences and _FRAGMENT.match(body):
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
    #: How the notes sit in time is said only when time was asked, and how
    #: stale they are only when the question is about now (INBOX 1441).
    if age >= 21:
        return _vary("stale").format(age=_gap(age)) if _CURRENT.get() else ""
    if not _TIMED.get():
        return ""
    if span <= 9:
        return _vary("burst").format(count=realise.count_word(len(days)), span=_gap(max(span, 1)), age=_gap(max(age, 1)))
    if len(days) >= 3:
        every = _bare_gap(_gap(max(1, round(span / (len(days) - 1)))))
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
        #: The source's kind, so a closing line reads a document's id in its
        #: own table (INBOX 1357).
        "kind": getattr(fact.view, "kind", "note"),
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


def _offer(facts: list[Fact], asked: str | None = None) -> dict | None:
    """One thing to do next, from the notes' own to-dos: the one with a day
    first ("ask the tutor on Thursday"), then something still to book. With
    `asked`, only a to-do the question is about (`_on_topic`)."""
    #: A day in a to-do is the note's day ("ask the tutor on Thursday",
    #: written 4 August, was 6 August): one gone by is not offered for this
    #: Thursday (the owner, 2026-10-11: relative time resolved everywhere).
    actions = [_asked_about(_still_ahead(a, f.view.written), f.body) for f in facts if (a := _task_of(f))]
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


_ON_DAY = re.compile(r"\s+on\s+((?:mon|tues|wednes|thurs|fri|satur|sun)day)\b", re.I)
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
        return ("this month" if same else f"in {composer._MONTHS[start.month - 1]}"), ahead
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


def _opening_line(members, facts: list[Fact], today: date, topic: str) -> tuple[str, list[Fact]]:  # noqa: ANN001
    """The opening of an overview, and the facts still to say. It answers in
    the person's terms (INBOX 870): where they have got to, or how much is
    still open, not only how many notes."""
    opening = PHRASES["overview"].format(count=_count(len(members)), topic=topic, span=_span(members, today))
    landed = next((f for f in facts if f.label == "Where you landed"), None)
    left = [f for f in facts if f.label == "Still to do"]
    if landed:
        opening = _vary("landed").format(opening=opening.rstrip("."), landed=_fragment(landed.body, _NAMES.get()))
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
    _, start = composer._title(content)
    heads = [h for line in content[start:].splitlines() if (h := composer._heading_text(line)) is not None]
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
    items = [_fragment(f.body.rstrip("."), _NAMES.get()) for f in facts[:GIST_ITEMS]]
    if len(facts) > GIST_ITEMS:
        items.append(f"{realise.count_word(len(facts) - GIST_ITEMS)} more")
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
    return out


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


def _list_gist(view: composer.NoteView, items: list[Fact]) -> list[Fact]:
    if all(f.body.rstrip().endswith("?") for f in items):
        #: "a list: how did that go?, what happened next? And ..." (1420).
        asked = [Fact(f.view, f.sentence, f.label, f.body.rstrip().rstrip("?")) for f in items]
        return [Fact(view, items[0].sentence, "", PHRASES["a_list_asked"].format(items=_listed(asked)))]
    return [Fact(view, items[0].sentence, "", PHRASES["a_list"].format(items=_listed(items)))]


def _gist_tail(view: composer.NoteView, own: list[Fact], heads: list[Fact], shape: str, sort: _Sorted, chosen: list[Fact], material: bool) -> list[Fact]:
    """The note's closing sentence: its shape, its open tasks, or its list."""
    if not own:
        return []
    if shape:
        return [Fact(view, (heads or sort.tasks or sort.items or own)[0].sentence, "", shape)]
    if sort.tasks:
        key = "still_list" if all(_verb_led(f.body) for f in sort.tasks) else "still_open"
        said = PHRASES[key].format(items=_listed(sort.tasks), name=_your_note(view))
        return [Fact(view, sort.tasks[0].sentence, "", said, sort.tasks[0].action)]
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


_DAY_LINE = re.compile(r"^\s*[-*]?\s*([A-Za-z][\w ]{0,20}?)\s*:\s*(\S.*)$")


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
            held += [p.strip() for p in re.split(r",\s*(?:and\s+)?|\s+and\s+", day.group(2)) if p.strip() and p.strip() not in held]
        rest = rest or bool(_REST.match(line))
    return items, rest


def _split_shape(view: composer.NoteView, own: list[Fact], days: list[str], rest: bool) -> tuple[str, Fact | None]:
    title = (view.title or "").strip()
    head = next((f for f in own if f.body.strip() == title), None)
    shape = f"a {', '.join(days)} split" + (" with rest days" if rest else "")
    if head and not re.match(r"(?:the|a|an|my|your)\b", title, re.I):
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
    chosen = sort.plain[: 1 if (shape or sort.tasks) else 2]
    keep = {id(f) for f in chosen}
    said = {id(f): _title_said(view, f.body.rstrip(":").strip()) for f in chosen}
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


def _told_lines(out: _Out, members, facts, today: date, kind: str, moved: str) -> None:  # noqa: ANN001
    told: set = set()
    if not moved:
        for view in members:
            told |= _narrate(out, view, facts, today)
    _lines(out, facts, LINES[kind] - (len(out.lines) - 1), skip=told, by_day=today, more=kind == "overview", weave=True)


def _overview_opening(out: _Out, question: str, members, facts, today: date, kind: str) -> tuple[str, list[Fact]]:  # noqa: ANN001
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
        opening, facts = _opening_line(members, facts, today, topic)
        out.lines.append(opening)
    return moved, _gists(members, facts)


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
    for group in groups:
        (out.lines if budget > 0 else out.more).append(composer_frame.group_line(group, notes, topic, _heading_said))
        held = [f for f in facts if f.view.id in group.ids]
        told: set = set()
        for i in group.ids:
            told |= _narrate(out, by_id[i], held, today)
        budget -= min(max(budget, 0), _lines(out, held, max(budget, 0), skip=told, by_day=today, more=True, weave=True))


def _overview(out: _Out, question: str, members, facts, today: date, kind: str) -> None:  # noqa: ANN001
    moved, facts = _overview_opening(out, question, members, facts, today, kind)
    shown_notes = {f.view.id for f in facts}
    groups = composer_frame.groups([v.note for v in members]) if kind == "overview" and not moved else []
    if groups:
        _framed(out, question, members, facts, today, groups)
    else:
        _told_lines(out, members, facts, today, kind, moved)
    pattern = "" if moved else _pattern(members, today)
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
        #: Between sources that say it equally well, the one the search ranked first.
        return (bool(cue and cue.search(f.sentence.text)), hits, -f.view.rank, -f.sentence.order)

    return max(facts, key=rank) if facts else None


def _say_list(out: _Out, lead: Fact, items: list[str], today: date) -> None:
    """"Hobbies I want to try: bouldering, film photography, ukulele": asked
    what the hobbies are, the answer is the count and the list."""
    day = f", written on {_day(lead.view.written, today)}" if _TIMED.get() and lead.view.written else ""
    name = f"your note “{lead.label}”" if _label_names(lead.label, lead.view) else _your_note(lead.view)
    out.lines.append(f"{realise.count_word(len(items)).capitalize()}, from {name}{day}: {realise.join_items(items)}.")
    others = [v for v in _VIEWS.get() if v.id != lead.view.id]
    if not any(composer._holds(composer._stem(w), v.words) for v in others for i in items for w in composer.subject_terms(i)[-1:]):
        out.closing.append(PHRASES["none_own"])


def _say_fact(out: _Out, lead: Fact, today: date, question: str) -> None:
    body = lead.body
    items = [i.strip() for i in re.split(r",\s*", body) if i.strip()]
    if lead.label and len(items) >= 3 and all(len(i.split()) <= 4 for i in items):
        _say_list(out, lead, items, today)
    elif lead.label and lead.label not in {name for name, _ in _CUES} and not _TIME_LABEL.match(lead.label + " x"):
        #: A heading the note gives itself ("Psych lecture") names the note;
        #: a label the answer gave the fact ("How it went") does not.
        name = f"your {_fragment(lead.label, _NAMES.get())} note" if _label_names(lead.label, lead.view) else _your_note(lead.view)
        day = f", {_day(lead.view.written, today)}" if _TIMED.get() else ""
        out.lines.append(f"From {name}{day}: {body}.")
    else:
        out.lines.append(_from_source(lead.view, body[0].upper() + body[1:], today))
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


class _WhenCue:
    """What a "when" answer leads with: a habit's weekdays, or a sentence that
    holds a day as the recogniser reads one ("Exam on 12 November", where the
    old month pattern wanted "in November")."""

    _DAYS = re.compile(r"\b(mon|tues|wednes|thurs|fri|satur|sun)days\b", re.I)

    def search(self, text: str) -> bool:
        return bool(self._DAYS.search(text)) or any(s.kind in ("date", "datetime", "range") for s in _spans(text, None))


_SINGLE_CUES = {
    "when": _WhenCue(),
    "count": re.compile(r"\$\s?\d|\d"),
    "opinion": _RATING,
}


def _single_when(out: _Out, lead: Fact, rest: list[Fact], question: str, today: date) -> list[Fact]:
    """A "when" ask: the day of one thing that happened, or a habit said as
    its days. Returns the facts still to say."""
    if _WHEN_DID.match(clean(question)) and _event_lead(out, lead, today):
        return []
    days = _DAYS_PLURAL.search(lead.body)
    if not (days and len(days.group(0).strip()) > 3):
        _say_fact(out, lead, today, question)
        return [f for f in rest if f.view.id == lead.view.id]
    said = days.group(0).strip(" ,")
    out.lines.append(_from_source(lead.view, said[0].upper() + said[1:], today))
    out.rows.append(_row(said, lead))
    rest = [f for f in rest if re.search(r"\b(mon|tues|wednes|thurs|fri|satur|sun)days\b|\bafternoons\b|\bmornings\b|\bevenings\b", f.sentence.text, re.I)]
    return [Fact(f.view, f.sentence, "Also on your week", f.body, f.action) for f in rest]


def _opinion_rest(facts: list[Fact]) -> list[Fact]:
    """What was loved and what was not, one fact each, from a review's clauses."""
    rest: list[Fact] = []
    for f in facts:
        for part in re.split(r"\s+but\s+|;\s*|,\s*|:\s+", f.sentence.text.strip().rstrip(".")):
            if _RATING.search(part) or _WORK.match(part):
                continue
            label = "Loved" if _GOOD.search(part) else "Didn't" if _BAD.search(part) else ""
            if label:
                rest.append(Fact(f.view, f.sentence, label, _fragment(_second_person(part), set()), ""))
    return rest


def _single_opinion(out: _Out, lead: Fact, facts: list[Fact], rest: list[Fact], question: str, today: date) -> list[Fact]:
    work = next((_WORK.match(f.sentence.text.strip()) for f in facts if _WORK.match(f.sentence.text.strip())), None)
    rating = next((_RATING.search(f.sentence.text) for f in facts if _RATING.search(f.sentence.text)), None)
    if not (work and rating):
        _say_fact(out, lead, today, question)
        return rest
    #: "Watched Dune Part Two: 7 out of 10, the sound was incredible":
    #: the title is the words before the rating or its first colon.
    title = re.split(r"\s*[:,(]\s+|\s+-\s+|\s+\d+(?:\.\d+)?\s*(?:/|out of)\b", work.group(1))[0].strip()
    out.lines.append(f"You gave {title} {rating.group(1)} out of {rating.group(2)} on {_day(lead.view.written, today)}.")
    out.rows.append(_row(f"{title} {rating.group(1)} out of {rating.group(2)}", lead))
    return _opinion_rest(facts)


def _against_aim(said: str, facts: list[Fact], lead: Fact) -> tuple[str, list[Fact]]:
    """Against the aim the notes set (INBOX 870): "$84 ..., under your aim of
    $100 a week", which no one note says. Returns the line and the facts left."""
    spent = re.search(r"\$\s?(\d+(?:\.\d+)?)", said)
    aim = next((m for f in facts for m in [re.search(r"\bunder \$\s?(\d+(?:\.\d+)?)((?: a| per) (?:week|month|day))?", f.sentence.text)] if m), None)
    line = said[0].upper() + said[1:]
    if not (spent and aim):
        return line, facts
    key = "aim_under" if float(spent.group(1)) <= float(aim.group(1)) else "aim_over"
    line = _vary(key).format(said=line, aim=f"${aim.group(1)}{aim.group(2) or ''}")
    return line, [f for f in facts if not re.search(r"\bunder \$", f.sentence.text) or f is lead]


def _single_count(out: _Out, lead: Fact, facts: list[Fact], members, question: str, today: date) -> list[Fact]:  # noqa: ANN001
    clauses = re.split(r"\s+and\s+(?=\$?\d)", lead.sentence.text.strip().rstrip("."))
    stems = {composer._stem(t) for t in composer.subject_terms(clean(question))}
    main = next((c for c in clauses if any(composer._holds(st, set(composer._words(c))) for st in stems)), clauses[0])
    said = _tidy(_week_written(_second_person(main), lead.view.written, today), lead.view.written)
    line, facts = _against_aim(said, facts, lead)
    out.lines.append(line if line.endswith(".") else line + ".")
    out.rows.append(_row(said, lead))
    if "week of" in said and len(members) == 1:
        out.closing.append(PHRASES["only_week"])
    rest = [Fact(lead.view, lead.sentence, "Also that week", _tidy(_second_person(c), lead.view.written).lstrip("you spent ").strip(), "") for c in clauses if c is not main]
    return rest + [f for f in facts if f is not lead and f.view.id == lead.view.id]


def _single_heading(out: _Out, lead: Fact, rest: list[Fact], today: date) -> list[Fact]:
    """The note's heading said as prose, its other sentences in the same
    paragraph (the owner, 2026-10-11), one mark for all of them."""
    rest = [f for f in rest if f.view.id == lead.view.id]
    along = [f for f in rest if f.heading and f.label == lead.label][:2]
    rest = [f for f in rest if f not in along]
    held = [lead, *along]
    line = _prose(lead.label, held, [_fragment(f.body, _NAMES.get()) for f in held], 0, today)
    out.lines.append(line + ".")
    row = _row(line, lead)
    if along:
        row["parts"] = [{"note_id": f.view.note.get("source_id", f.view.id), "source": f.sentence.text, "start": f.sentence.start, "end": f.sentence.end} for f in held]
    out.rows.append(row)
    return rest


def _single_close(out: _Out, kind: str, rest: list[Fact], members, question: str = "") -> None:  # noqa: ANN001
    labels = {f.label for f in rest}
    score = re.search(r"You gave .+? (\d+(?:\.\d+)?) out of", out.lines[0]) if out.lines else None
    if kind == "opinion" and score and {"Loved", "Didn't"} <= labels:
        #: The verdict the two lines add up to (INBOX 870).
        out.closing.append(_vary("mixed").format(score=score.group(1)))
    if len(members) == 1 and kind in ("fact", "opinion"):
        word = _reviewed_word(question, members) if kind == "opinion" else ""
        noun = f"{word} review" if word else "note"
        out.lines.append(PHRASES["only_note"] if noun == "note" else PHRASES["only_kind"].format(noun=noun))


_TASKY = re.compile(r"\b(?:to-?do|tasks?|checklist|left|open|unfinished)\b", re.I)


def _drop_tasks(kind: str, lead: Fact, rest: list[Fact], question: str) -> list[Fact]:
    """An unticked checklist item is not a fact about the thing asked
    (composer5: "what is the Krebs cycle" listing "read chapter 4")."""
    if kind != "fact" or lead.sentence.kind == "task" or _TASKY.search(question):
        return rest
    return [f for f in rest if f.sentence.kind != "task"]


def _single(out: _Out, kind: str, question: str, members, facts, today: date) -> None:
    lead = _best(facts, question, _SINGLE_CUES.get(kind))
    if lead is None:
        return
    rest = [f for f in facts if f is not lead]
    rest = _drop_tasks(kind, lead, rest, question)
    if kind == "when":
        rest = _single_when(out, lead, rest, question, today)
    elif kind == "opinion":
        rest = _single_opinion(out, lead, facts, rest, question, today)
    elif kind == "count":
        rest = _single_count(out, lead, facts, members, question, today)
    elif lead.heading and (_HEARD.search(lead.label) or _DID.search(lead.label) or _PLANNED.search(lead.label)):
        rest = _single_heading(out, lead, rest, today)
    else:
        _say_fact(out, lead, today, question)
        rest = [f for f in rest if f.view.id == lead.view.id]
    _lines(out, rest, LINES.get(kind, 2))
    _single_close(out, kind, rest, members, question)


_NAME_ASKS = ("tell me about ", "what do i know about ", "what about ", "anything on ", "anything about ")


def _one_name(asked: str, names: set[str]) -> str:
    """The name in "tell me about Tom" and its kin when the notebook writes it
    as a name; empty for anything else. Word steps, no regex, so nothing here
    can go quadratic on a long run of blanks."""
    text = " ".join(asked.lower().split()).rstrip("?.! ")
    for lead in _NAME_ASKS:
        if text.startswith(lead):
            rest = text[len(lead):]
            return rest if rest.isalpha() and rest in names else ""
    return ""


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
        said: set[str] = set()
        for v, s2 in found[:LINES["overview"]]:
            body = _tidy(_second_person(s2.text.strip()), v.written)
            if not _TIMED.get() and body.lower() in said:
                continue
            said.add(body.lower())
            body = re.sub(r"^(You|Your)\b", lambda m: m.group().lower(), body)
            out.lines.append(f"On {_day(v.written, today)}, {body}." if _TIMED.get() else f"{body[:1].upper() + body[1:]}.")
    out.rows.append({"sentence": fact, "note_id": view.note.get("source_id", view.id), "source": s.text, "score": 1.0, "digest": True})
    return True


def _aliases(sentences: list, side: str) -> set[str]:
    """What a side is called in the notes: its own word and the capitalised
    words that follow it ("Sony" then "WH-1000XM5")."""
    said = {side.lower()}
    for _, s in sentences:
        m = re.search(rf"(?i:\b{re.escape(side)})((?:\s+[A-Z0-9][\w-]*){{1,4}})", s.text)
        if m:
            said |= {w.lower() for w in m.group(1).split() if len(w) > 2}
    return said


def _about(sides: dict[str, set[str]], side: str, text: str) -> bool:
    return any(re.search(rf"\b{re.escape(w)}\b", text, re.I) for w in sides[side])


def _full_names(sentences: list, a: str, b: str) -> dict[str, str]:
    """Each side as the notes write it in full ("Sony WH-1000XM5"), for the ones found."""
    full: dict[str, str] = {}
    for side in (a, b):
        for _, s in sentences:
            m = re.search(rf"\b((?i:the\s+)?(?i:{re.escape(side)})(?:\s+[A-Z0-9][\w-]*){{0,4}})", s.text)
            if m:
                full[side] = re.sub(r"^the\s+", "", m.group(1), flags=re.I)
                break
    return full


_LEANING = re.compile(r"\b(leaning towards|prefer|decided on|going with|chose|picked)\s+(?:the\s+)?(\w+)", re.I)


def _leaning(sentences: list, sides: dict[str, set[str]], a: str, b: str, names: set[str]) -> tuple[str, object, str]:
    """The side a note leans towards, the note, and why: (side, view, why)."""
    winner, why_view, why = "", None, ""
    for v, s in sentences:
        m = _LEANING.search(s.text)
        if not m:
            continue
        for side in (a, b):
            if m.group(2).lower() in sides[side]:
                winner, why_view = side, v
                against = [x.text for x in v.sentences if x is not s and (_about(sides, a, x.text) or _about(sides, b, x.text))]
                why = "you're leaning towards it"
                if against:
                    reason = _tidy(_second_person(re.sub(r"^[^:]{2,30}:\s+", "", against[0])), v.written)
                    why += f" after {_fragment(reason, names)}"
    return winner, why_view, why


def _clause_cell(cells: dict[str, dict[str, str]], side: str, clause: str, written: date | None, sides: dict[str, set[str]], others: list[str]) -> None:
    """One clause of a note, put in the side's price or "what you found" cell."""
    alone = _about(sides, side, clause) and not any(_about(sides, o, clause) for o in others)
    price = re.search(r"\$\s?\d[\d,.]*", clause)
    if alone and price and side not in cells["Price"]:
        cells["Price"][side] = ("about " if "about" in clause else "") + price.group(0)
    elif alone and not price and not _LEANING.search(clause) and side not in cells["What you found"]:
        said = _tidy(_second_person(clause), written)
        said = re.sub(rf"^.*?\b(?:it|{re.escape(side)}\w*)\s+", "", said, count=1, flags=re.I) if len(said.split()) > 8 else said
        cells["What you found"][side] = said


def _side_cells(cells: dict[str, dict[str, str]], side: str, sentences: list, sides: dict[str, set[str]], a: str, b: str, today: date) -> None:
    """What the notes say of one side, put in its column of the table."""
    named = [(v, s) for v, s in sentences if _about(sides, side, s.text)]
    for v, s in named:
        for clause in re.split(r"\s+and\s+(?=the\s)|;\s*|:\s+", s.text.strip().rstrip(".")):
            _clause_cell(cells, side, clause, v.written, sides, [o for o in (a, b) if o != side])
    days = sorted(v.written for v in {v.id: v for v, _ in named}.values() if v.written)
    count = len({v.id for v, _ in named})
    cells["In your notes"][side] = f"{_count(count)}, last on {_day(days[-1], today)}" if days else _count(count)


def _compare_table(sentences: list, sides: dict[str, set[str]], full: dict[str, str], a: str, b: str, today: date) -> str:
    """Decision 71: a comparison is a table, a column a side, a row a thing
    the notes say of both (the price, what you found, how often it comes
    up), so the two can be read across rather than one after the other."""
    cells: dict[str, dict[str, str]] = {"Price": {}, "What you found": {}, "In your notes": {}}
    for side in (a, b):
        _side_cells(cells, side, sentences, sides, a, b, today)
    #: A row the same on both sides compares nothing; it is left out.
    rows = [(name, got) for name, got in cells.items() if got and not (len(got) == 2 and got[a] == got[b])]
    if not rows:
        return ""
    head = f"| | {full[a]} | {full[b]} |"
    body = [f"| {name} | {got.get(a, 'nothing yet')} | {got.get(b, 'nothing yet')} |" for name, got in rows]
    return "\n".join([head, "| --- | --- | --- |", *body])


def _compare(out: _Out, a: str, b: str, views, today: date, names: set[str]) -> bool:  # noqa: ANN001
    sentences = [(v, s) for v in views for s in v.sentences]
    sides = {a: _aliases(sentences, a), b: _aliases(sentences, b)}
    full = _full_names(sentences, a, b)
    if len(full) < 2:
        return False
    winner, why_view, why = _leaning(sentences, sides, a, b, names)
    if not winner:
        return False
    out.lines.append(PHRASES["pick"].format(side=winner[:1].upper() + winner[1:], why=why))
    out.offer = _note_offer(PHRASES["pick_note"].format(side=winner[:1].upper() + winner[1:]), f"My pick: the {full[winner]}")
    out.rows.append({"sentence": why, "note_id": why_view.note.get("source_id", why_view.id), "source": why, "score": 1.0, "digest": True})
    table = _compare_table(sentences, sides, full, a, b, today)
    if table:
        out.lines.append(table)
    return True


def _states_it(dated: list, abbr: str, phrase: str):  # noqa: ANN202
    """The note that gives the abbreviation's phrase, and its sentence, as
    (view, sentence, said outright); None when no note does. A note that
    holds both the phrase and the abbreviation is preferred."""
    holds = [v for v in dated if phrase.lower() in str(v.note.get("content") or "").lower()]
    both = [v for v in holds if re.search(rf"\b{re.escape(abbr)}\b", str(v.note.get("content") or ""))]
    view = (both or holds or [None])[0]
    if view is None:
        return None
    sentence = next((s for s in view.sentences if phrase.lower() in s.text.lower()), view.sentences[0] if view.sentences else None)
    return None if sentence is None else (view, sentence, bool(both))


def _stands_for(out: _Out, abbr: str, views: list, today: date) -> bool:
    """"What does CC stand for?" from the person's own notes (B7): the
    phrase their notes give it, the note that says so, and how much they
    use it. Never a dictionary's reading."""
    phrase = glossary.learn(str(v.note.get("content") or "") for v in views).get(abbr)
    dated = sorted(views, key=lambda v: (v.written or date.min, v.rank))
    found = _states_it(dated, abbr, phrase) if phrase else None
    if found is None:
        return False
    view, sentence, both = found
    #: Said outright ("Cloud Computing (CC)") or only seen beside it: the
    #: second is a reading, and the answer says so.
    line = PHRASES["stands_for" if both else "stands_for_seen"].format(abbr=abbr, phrase=phrase, name=_your_note(view), day=_day(view.written, today))
    out.lines.append(line[:1].upper() + line[1:])
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
    _set_timing(question)
    out = _Out()
    line = PHRASES["all_said"].format(topic=_topic(asked, members), count=_count(len(members)), span=_span(members, today))
    out.lines.append(line)
    first = min(members, key=lambda v: (v.written or date.min, v.rank))
    if first.sentences:
        out.rows.append(_row(line.rstrip("."), Fact(first, first.sentences[0], "", "")))
    return _result(out, "more", asked)


#: `_early` found nothing special in the question: the ordinary answer follows.
_ORDINARY = object()


def _begin(question: str, asked: str, notes: list[dict], today: date, voice: str, turn: int, known) -> list:  # noqa: ANN001
    """Read the route's notes and set what this answer's helpers read; the
    notes, or none when there is nothing to answer from."""
    views = [v for v in (composer.read_note(n, i) for i, n in enumerate(composer._distinct_ids(notes or []))) if v]
    if not views:
        return []
    _NAMES.set(_capitalised_inside(views))
    _TODAY.set(today)
    _set_timing(question)
    _VOICE.set(voice if voice in VOICES else "natural")
    _TURN.set(turn)
    _SEED.set(zlib.crc32(asked.lower().encode()))
    _GAPS.set(())
    _VIEWS.set(views)
    _KNOWN.set(known)
    _ASKS_WORDS.set(bool(re.search(r"\b(?:says?|said|reads?|written|text|words?|wording)\b", question, re.I)))
    return views


def _compared(out: _Out, asked: str, views: list, names: set[str], today: date) -> dict | None:
    m = _ASKS["compare"].search(asked)
    if not _compare(out, m.group("a").strip(), m.group("b").strip(), views, today, names):
        return None
    want = next((f for f in (f for v in views for f in _facts(v, names)) if f.label == "What you want"), None)
    if want:
        out.lines.append(f"You want it {want.body}; nothing says which one meets that.")
    return _result(out, "compare", asked)


def _person_asked(asked: str, names: set[str], views: list) -> str:
    """The name "tell me about Tom" asks after; empty when the word is one
    notes are tagged or filed under ("Golf"), which is a topic, not a person."""
    said = _one_name(asked, names)
    stem = composer._stem(said) if said else ""  # noqa: SLF001
    return "" if not said or any(stem in v.filed_words for v in views) else said


def _early(out: _Out, kind: str, asked: str, question: str, views: list, today: date):  # noqa: ANN202
    """The answers that are one notebook-wide lookup (what an abbreviation
    stands for, who someone is, a comparison, what a category holds): the
    result, None when the ask fits but nothing answers it, or `_ORDINARY`."""
    names = _NAMES.get()
    abbr = glossary.asked(question)
    if abbr and _stands_for(out, abbr, views, today):
        return _result(out, "fact", asked)
    if composer_slots.answer(out, asked, views, today):
        #: The question's slot (a tick, an open task, a dated line) is what
        #: answers it, or the answer says no note holds it (audit 1029 rank 19).
        return _result(out, "fact", asked)
    computed = composer_lists.computed_kind(asked)
    if computed and composer_lists.answer(out, computed, asked, views, today):
        #: A day, a count or a filing worked out from the notes (probes P10
        #: to P13); when the notes do not hold what it needs the ordinary
        #: shapes below still answer.
        return _result(out, "fact", asked)
    if kind == "overview" and (said := _person_asked(asked, names, views)):
        #: "tell me about Tom" is "who is Tom": a name has one answer shape
        #: (audit 1029 C17), never an attendee list read as a count.
        kind, asked = "who", f"who is {said}"
    if kind == "who":
        name = _ASKS["who"].search(asked).group("name").strip()
        return _result(out, kind, asked) if _who(out, name, views, names, today) else None
    if kind == "compare":
        return _compared(out, asked, views, names, today)
    if about_this(asked) or named_category(asked, list({str(v.note.get("category") or "") for v in views})):
        #: The route sent only what is open, or the category named (B10):
        #: every note is the subject.
        return _this(out, views, names, today, asked)
    return _ORDINARY


def _compose_body(out: _Out, kind: str, asked: str, members: list, facts: list[Fact], today: date) -> bool:
    """The lines of the answer proper; False when there are none to say."""
    many = kind in ("overview", "likes") and len(members) >= 2
    if many:
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
        return False
    missing = _missing(members) if many and not out.framed else ""
    if missing:
        out.lines.append(missing)
    return True


def _finish(out: _Out, kind: str, asked: str, members: list, facts: list[Fact], tie, notes: list[dict], today: date, insight: str, learned) -> dict:  # noqa: ANN001
    """What follows the lines: the tie's question, or the insights a broad
    answer volunteers, then the one offer."""
    if tie:
        _tie_closing(out, asked, members, tie[1], tie[2])
    elif kind in ("overview", "likes"):
        _confirmed_first(out, asked, members, learned)
        _volunteer(out, asked, members, notes, today, insight, learned)
    #: A fact answer ("what is the Krebs cycle") offers a to-do only when it is
    #: about it; an overview of notes that hold an open task still offers it.
    out.offer = out.offer or _offer(_answered(out, facts), asked if kind == "fact" else None) or _kind_offer(kind, asked, members, facts, today, out)
    return _result(out, kind, asked)


def _scope(question: str, asked: str, notes: list[dict], today: date, voice: str, turn: int, known) -> tuple[list, bool]:  # noqa: ANN001
    """The notes the answer reads, and whether the question asks for the
    context notes (jokes, quotes) that are otherwise left out."""
    views = _begin(question, asked, notes, today, voice, turn, known)
    wants_context = bool(set(composer._words(asked)) & {composer._stem(t) for t in CONTEXT_TAGS})
    return (views if wants_context else [v for v in views if not _context_note(v)]), wants_context


def _defining_first(asked: str, members: list) -> list:
    """The note that says what the subject is ("Cloud computing is the
    delivery of ...") leads, ahead of a passing mention the search ranked
    higher (INBOX 1420: "it missed my main note about what cloud computing is")."""
    terms = composer.subject_terms(clean(asked))
    if not terms or len(members) < 2:
        return members
    said = re.compile(r"^(?:the\s+)?" + r"\s+".join(re.escape(t) for t in terms) + r"\s+(?:is|are|means|refers to)\b", re.I)
    defining = [v for v in members if any(said.match(x.text) for x in v.sentences[:2])]
    return defining[:1] + [v for v in members if v not in defining[:1]] if defining else members


def _named_checklist(kind: str, asked: str, members: list):  # noqa: ANN202
    """The note the question names when that note is nothing but a checklist
    and the question asks for it plainly ("what is the checklist note", "tell
    me about gear"), else None: its list is shown with its ticks
    (`_show_checklist`), never quoted as a lead fact with "Also" the rest."""
    if kind not in ("fact", "overview") or not members:
        return None
    stems = _subject(asked)
    #: "the gear list" names Gear; "list" and "checklist" only say what kind.
    needed = [st for st in stems if st not in _KIND_WORDS] or stems
    named = [v for v in members if needed and all(composer._holds(st, v.title_words) for st in needed)]
    if len(named) != 1:
        return None
    tasks = [s for s in named[0].sentences if s.kind == "task"]
    return named[0] if len(tasks) >= 2 and len(tasks) == len(named[0].sentences) else None


def _show_checklist(out: _Out, view: composer.NoteView) -> None:
    """A checklist note as the list it is: how many are ticked, then every
    item with its box, as the composer's own list block does."""
    tasks = [s for s in view.sentences if s.kind == "task"]
    ticked = sum(1 for s in tasks if s.done)
    total = realise.count_word(len(tasks))
    name = _your_note(view)
    done = f"{realise.count_word(ticked)} of {total}" if ticked else f"none of its {total}"
    opening = f"{name[0].upper()}{name[1:]} has {done} checklist items done"
    boxes = [f"- [{'x' if s.done else ' '}] {s.text[:1].upper()}{s.text[1:]}" for s in tasks]
    out.lines.append(opening + ":\n\n" + "\n".join(boxes))
    out.rows.append({"sentence": opening, "note_id": view.note.get("source_id", view.id), "source": tasks[0].text,
                     "start": tasks[0].start, "end": tasks[0].end, "score": 1.0, "digest": True,
                     "kind": getattr(view, "kind", "note")})


_KIND_WORDS = frozenset({"list", "checklist", "note", "tasklist"})


def _pick_members(asked: str, views: list, wants_context: bool) -> list:
    """The notes the question is about, oldest first."""
    if wants_context:
        members = [v for v in views if _context_note(v) or any(composer._holds(st, v.words) for st in composer._words(asked))]
    else:
        members = _members(asked, views)
    members.sort(key=lambda v: (v.written or date.min, v.rank))
    return members


def _tie_closing(out: _Out, asked: str, members: list, other: str, others: list) -> None:
    topic = _topic(asked, members)
    out.closing.insert(0, PHRASES["tie"].format(topic=topic, category=other, count=_count(len(others))))
    out.next.append(PHRASES["tie_chip"].format(topic=topic, category=other))


def _kind_if_mine(asked: str) -> str | None:
    """The question's kind, or None when the digest should not answer it: an
    empty question, or two things named ("Lisbon vs Porto", "how does A differ
    from B"), which the composer's side-by-side answers; a digest of the best
    note would say one side and drop the other."""
    if not asked or composer.asks_written_when(asked):
        return None  # a note's own day is the composer's, not a digest of its words (E6)
    kind = kind_of(asked)
    return None if kind != "compare" and composer.compare_sides(asked) else kind


def answer(
    question: str, notes: list[dict], *, today: date | None = None, voice: str = "natural", turn: int = 0,
    insight: str = "one", learned=None, known=None,  # noqa: ANN001
) -> dict | None:
    """The decision-70 answer to `question` from the route's `notes`, or None
    when the question is not one this shape answers (a sum, a time, a
    command, nothing found): the caller then asks `composer.compose`."""
    today = today or date.today()
    asked = composer.what_is(clean(question))
    kind = _kind_if_mine(asked)
    #: An act ("rename my gym log") is not a topic to digest: with its verb off
    #: the subject, it would find the gym log and summarise it.
    if kind is None or composer._lead_act_verb(question):
        return None
    views, wants_context = _scope(question, asked, notes, today, voice, turn, known)
    if not views:
        return None
    names = _NAMES.get()
    out = _Out()
    early = _early(out, kind, asked, question, views, today)
    if early is not _ORDINARY:
        return early
    members = _defining_first(asked, _pick_members(asked, views, wants_context))
    tie = _tie(asked, members) if members and kind == "overview" else None
    members = tie[0] if tie else members
    if checklist := _named_checklist(kind, asked, members):
        _show_checklist(out, checklist)
        return _result(out, "fact", asked)
    facts =[f for v in members for f in _facts(v, names, set(_subject(asked)))]
    if not facts:
        return None
    if kind == "left":
        return _result(out, kind, asked) if _left(out, asked, members, views, names, today) else None
    if not _compose_body(out, kind, asked, members, facts, today):
        return None
    return _finish(out, kind, asked, members, facts, tie, notes, today, insight, learned)


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


def _scored_insights(found: list, ids: set, members, said: str, learned) -> list:  # noqa: ANN001
    """The insights worth saying as (relevance, item), best first: not
    dismissed, not what the person ruled out, not news the opening gave, and
    resting enough on the answer's own notes."""
    from tessellate.ai import insights

    dismissed = getattr(learned, "dismissed", frozenset()) or frozenset()
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
    return scored


def _say_insight(out: _Out, item, row: dict, members, said: str) -> None:  # noqa: ANN001
    """One insight said where it belongs: woven into the line that tells its
    plan, as the hedge after the count, or as a closing line."""
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
    said = " ".join(out.lines).lower()
    for _, item in _scored_insights(found, ids, members, said, learned)[: 1 if level == "one" else 3]:
        row = insights.as_row(item, learned)
        if not row["confirmed"]:
            _say_insight(out, item, row, members, said)
            continue
        #: The person's word, said as theirs, once (and first when it is
        #: about the subject asked, `_confirmed_first`).
        if row["text"] not in out.lines:
            out.closing.insert(0, row["text"])
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


def _this_note(out: _Out, v, facts: list[Fact], names: set[str], today: date) -> None:  # noqa: ANN001
    """The open note: its facts under their labels."""
    #: The heading `read_note` found: the note dict carries no `title` of its own
    #: (the 22-10 bug doc: "Your untitled note of 25 October" over a titled note).
    title = _tidy(str(v.note.get("title") or (v.title if v.titled else "")))
    category = str(v.note.get("category") or "").strip()
    where = f", in {category}" if category and category.lower() != "uncategorised" else ""
    #: A title keeps its capital (C1); a note without one is named by its
    #: first clause (C8), never by a section's label or "untitled".
    name = _note_called(title) if title else _your_note(v)
    said = [(_fragment(_second_person(f.body), names), f) for f in facts]
    if len(said) == 1:
        out.lines.append(PHRASES["this_one"].format(name=name, day=_day(v.written, today), where=where, pause="," if where else "", fact=said[0][0]))
        out.rows.append(_row(said[0][0], said[0][1]))
        return
    out.lines.append(PHRASES["this_note"].format(
        name=name, day=_day(v.written, today), where=where, points=f"{realise.count_word(len(said))} points"))
    out.lines.append(_points_block(out, said[:MORE_LINES], title or composer_frame.note_label(v.note)))


def _points_block(out: _Out, said: list, title: str) -> str:
    """One point a line, as a list: the note's own heading is the lead's, so
    it is not repeated as every line's label. One block, so the list renders
    tight rather than spaced."""
    points = []
    for text, fact in said:
        label = f"**{fact.label}:** " if fact.label and fact.label.lower() != title.lower() else ""
        points.append(f"- {label}{text[:1].upper() + text[1:]}.")
        out.rows.append(_row(text, fact))
    return "\n".join(points)


def _this_category(out: _Out, views: list, facts: list[Fact], today: date) -> None:
    """The open category, as an overview of its notes."""
    category = Counter(str(v.note.get("category") or "") for v in views).most_common(1)[0][0] or "these notes"
    out.lines.append(PHRASES["this_many"].format(count=_count(len(views)), topic=category, span=_span(views, today)))
    _lines(out, facts, LINES["overview"], by_day=today, more=True)
    missing = _missing(views)
    if missing:
        out.lines.append(missing)


def _this(out: _Out, views: list, names: set[str], today: date, asked: str) -> dict | None:
    """"Summarise this" (B10): the open note, its facts under their labels;
    or the open category, as an overview of its notes."""
    views = sorted(views, key=lambda v: (v.written or date.min, v.rank))
    facts = [f for v in views for f in _facts(v, names)]
    if not facts:
        return None
    if len(views) == 1:
        _this_note(out, views[0], facts, names, today)
    else:
        _this_category(out, views, facts, today)
    if not out.lines:
        return None
    out.offer = _offer(_answered(out, facts))
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


def _likes_offer(text: str) -> dict | None:
    places = sorted({m.group(1).lower() for m in _PLACE.finditer(text)}, key=len, reverse=True)
    if not places:
        return None
    where = "the " + places[0]
    return {"kind": "reminder", "label": PHRASES["go_again"].format(place=where), "text": f"Go to {where}"}


#: What to do with each kind of thing reviewed: a book is read, not watched.
_REVIEW_VERB = {"book": "read", "album": "listen to", "game": "play"}


def _reviewed_word(question: str, members, text: str = "") -> str:  # noqa: ANN001
    """What the opinion is about ("film", "book"), from the question, the
    tags and the notes' words; "" when none names it. A review was called a
    "film review" whatever it was (audit 1029 C5: a book), so the word is
    never assumed."""
    tags = " ".join(str(t) for v in members for t in (v.note.get("tags") or []))
    own = " ".join(s.text for v in members for s in v.sentences)
    found = _REVIEWED.search(f"{question} {tags} {text or own}")
    return {"movie": "film"}.get(found.group(1).lower(), found.group(1).lower()) if found else ""


def _opinion_offer(question: str, members, text: str) -> dict | None:  # noqa: ANN001
    noun_word = _reviewed_word(question, members, text)
    if not noun_word:
        return None
    verb = _REVIEW_VERB.get(noun_word, "watch")
    return _note_offer(PHRASES["start_list"].format(noun=noun_word, verb=verb), f"{noun_word.capitalize()}s to {verb} next\n\n- [ ] ")


def _count_offer(question: str, text: str) -> dict | None:
    if re.search(r"\$\s?\d", text) and re.search(r"\b(spen[dt]|budget|cost)", question + " " + text, re.I):
        return {"kind": "reminder", "label": PHRASES["log_weekly"], "text": "Log your spending every Sunday"}
    return None


def _fact_offer(out: _Out) -> dict | None:
    listed = re.search(r"^\w+, from [^:]+: (.+)\.$", out.lines[0]) if out.lines else None
    if not listed:
        return None
    first = re.split(r",\s*| and ", listed.group(1))[0].strip()
    if not first[:1].islower() or first.split()[0].lower() in _NAMES.get():
        #: "Remind you to try Sara?": a name is not a thing to try (C3).
        return None
    return {"kind": "reminder", "label": PHRASES["try_one"].format(item=first), "text": f"Try {first}"}


def _overview_offer(kind: str, question: str, members, facts: list[Fact], today: date) -> dict | None:  # noqa: ANN001
    """What an overview suggests: gathering jokes or quotes into one note, a
    table to track a lift, or the pick a comparison landed on."""
    if kind == "overview" and members and all(_context_note(v) for v in members) and len(members) >= 2:
        topic = _topic(question, members)
        return _note_offer(PHRASES["gather"], f"{topic[:1].upper() + topic[1:]}\n\n" + "\n\n".join(f.body for f in facts))
    table = _lift_table(members, today) if kind == "overview" and _GOING.search(question) else None
    if table:
        return _note_offer(PHRASES["track_table"].format(what=table[0]), table[1])
    landed = next((f for f in facts if f.label == "Where you landed"), None)
    side = re.search(r"towards (?:the )?(.+)$", landed.body) if landed else None
    if side:
        return _note_offer(PHRASES["pick_note"].format(side=side.group(1).strip()), f"My pick: the {side.group(1).strip()}")
    return None


def _kind_offer(kind: str, question: str, members, facts: list[Fact], today: date, out: _Out) -> dict | None:  # noqa: ANN001
    """The one acting offer when the notes name no to-do of their own (B12):
    what the kind of question suggests doing with the answer, each one a
    thing the app does in one press (a reminder or a note)."""
    text = " ".join(s.text for v in members for s in v.sentences)
    if kind == "opinion":
        return _opinion_offer(question, members, text)
    offer = {"likes": lambda: _likes_offer(text), "count": lambda: _count_offer(question, text), "fact": lambda: _fact_offer(out)}.get(kind)
    return (offer() if offer else None) or _overview_offer(kind, question, members, facts, today)


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


def _open_lists(question: str, views) -> list:  # noqa: ANN001
    """The notes' lists of three or more things as (view, sentence, heading
    match); for "what do I need to buy", only the shopping ones."""
    buying = re.search(r"\b(buy|shop|get)\b", question, re.I)
    lists = []
    for v in views:
        for s in v.sentences:
            head = _PREFIX.match(s.text.strip())
            if not (head and len(head.group(2).split(",")) >= 3):
                continue
            shop = re.search(r"\b(grocer|shopping|buy|list)", head.group(1) + " " + " ".join(v.note.get("tags") or []) + " " + str(v.note.get("category") or ""), re.I)
            if shop or not buying:
                lists.append((v, s, head))
    return lists


def _still_open(views, listed) -> list[str]:  # noqa: ANN001
    """The other things still to do that notes besides the list name."""
    open_bits = []
    for w in views:
        for t in w.sentences:
            still = _STILL_TO.search(t.text)
            if still and w is not listed:
                topic = next((str(x) for x in (w.note.get("tags") or []) if str(x).lower() not in still.group(1).lower()), "")
                #: "the Camping the tent" doubled the article.
                what = re.sub(r"^(the|a|an) ", "", still.group(1).lower()) if topic else still.group(1).lower()
                open_bits.append(f"the {topic[:1].upper() + topic[1:] + ' ' if topic else ''}{what}")
    return open_bits


def _left(out: _Out, question: str, members, views, names: set[str], today: date) -> bool:  # noqa: ANN001
    """"What do I need to buy": the open list first, then the other things
    still to do the notes name."""
    lists = _open_lists(question, views)
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
    open_bits = _still_open(views, v)
    if open_bits:
        left = open_bits[:2]
        out.lines.append(f"{realise.join_items(left)[:1].upper()}{realise.join_items(left)[1:]} {'is' if len(left) == 1 else 'are'} also still open.")
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
_DAY_OF_MONTH = re.compile(r"\b(?:(\d{1,2}(?:st|nd|rd|th)?) (may|march)|(may|march) (\d{1,2})(?:st|nd|rd|th)?)\b(?!:\d)", re.I)
_SET_ASIDE = re.compile(
    r"“[^”]*”|\"[^\"\n]*\"|`[^`]*`|\[[^\]]*\]\([^)]*\)|https?://\S+|\S+@\S+|"
    r"[\w-]+\.(?:txt|md|pdf|docx?|pptx?|xlsx?|csv|json|png|jpe?g|gif|zip|py|js|html?)\b|^>.*$",
    re.M,
)
#: A sentence opens at a line start or after a full stop; "e.g." and "5 p.m."
#: do not end one.
_SENTENCE_START = re.compile(r"(?:^|(?<=[.!?] ))(\*\*)?([a-z][a-z']*)(?!\w)", re.M)
_NOT_AN_END = re.compile(r"(?:\b(?:e\.g|i\.e|etc|vs|approx|dr|mr|mrs|ms|st|no|cf)|\b[ap]\.m)\. $", re.I)
_VERB_TO = r"(?:go|goes|going|went|gone|head|heads|heading|headed|walk|walks|walking|walked|drive|drives|driving|drove|run|runs|running|ran|come|comes|coming|came|nip|nipped|pop|popped|back)"
#: Places said with "the". Not school, work, bed, church, hospital, uni,
#: college or town, which are said bare.
_PLACES = (
    "gym|shop|shops|supermarket|store|bank|library|pharmacy|chemist|chemists|dentist|doctor|cinema|beach|park|airport|station|"
    "market|mall|barber|barbers|hairdresser|hairdressers|salon|bakery|butcher|butchers|pool|post office|optician|opticians|vet|office"
)
#: What may follow the place: the phrase must end there, so "gym class" and
#: "bank holiday" (a noun on it) are left alone.
_AFTER_WORDS = (
    "and", "or", "but", "then", "on", "at", "in", "after", "before", "every", "today", "tonight", "tomorrow",
    "yesterday", "this", "next", "last", "again", "for", "with", "so", "when", "if", "as", "by", "from", "until",
    "once", "twice", "daily", "weekly", "early", "late", "now", "soon", "later", "instead", "still", "too", "to",
)
_AFTER_PLACE = rf"(?=\s*(?:$|[.,;:!?)]|(?i:{'|'.join(_AFTER_WORDS)}|{_WEEKDAYS})\b))"
_NEEDS_THE = re.compile(rf"\b((?i:{_VERB_TO}(?: back)?)) to ({_PLACES}){_AFTER_PLACE}")


def _capital(m: re.Match) -> str:
    word = m.group(2)
    if _NOT_AN_END.search(m.string[max(0, m.start() - 12):m.start()]):
        return m.group(0)
    known = _dictionary()
    if word in ("a", "i") or word in _WEEKDAY_WORDS or (known and len(word) > 1 and word in known):
        return f"{m.group(1) or ''}{word[0].upper()}{word[1:]}"
    return m.group(0)


def polish(text: str, keep: Iterable[str] = ()) -> str:
    """`text`, composed by the app, with its lead capitals, day and month
    names and "to gym" (to the gym) fixed. `keep` holds sentences that are the
    person's own words (a joke, a quote), left exactly as they are."""
    held: list[str] = []
    text = _unlinked(text)

    def hold(m: re.Match) -> str:
        held.append(m.group(0))
        return f"{len(held) - 1}"

    for phrase in sorted({k.strip() for k in keep if k and k.strip()}, key=len, reverse=True):
        text = re.sub(re.escape(phrase), hold, text, flags=re.I)
    text = _SET_ASIDE.sub(hold, text)
    text = _NEEDS_THE.sub(r"\1 to the \2", text)
    text = _DAY_NAME.sub(lambda m: m.group(0).capitalize(), text)
    text = _DAY_OF_MONTH.sub(lambda m: m.group(0).title() if m.group(1) or m.group(3) else m.group(0), text)
    text = _SENTENCE_START.sub(_capital, text)
    return realise.mend_stops(re.sub("(\\d+)", lambda m: held[int(m.group(1))], text))


def _polish_out(out: _Out, kind: str) -> None:
    """The composed lines, said with the grammar pass. A web answer is the
    pages' own words under a one-line lead, so it is not touched."""
    if kind == "web":
        return
    keep = []
    for v in _VIEWS.get():
        for s in v.sentences if _context_note(v) else ():
            text = s.text.strip().rstrip(".!")
            #: Said without its "Joke:" label, so the words alone are kept too.
            head = _PREFIX.match(text)
            keep += [text, head.group(2)] if head else [text]
    for lines in (out.lines, out.more, out.closing, out.next):
        lines[:] = [polish(line, keep) for line in lines]
    if out.offer and out.offer.get("label"):
        out.offer = {**out.offer, "label": polish(str(out.offer["label"]), keep)}


def _result(out: _Out, kind: str, question: str) -> dict:
    _polish_out(out, kind)
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


#: A question whose answer depends on where the person is ("the weather
#: today", "pharmacies near me") and that names no place itself.
_LOCAL = re.compile(r"\b(?:weather|forecast|temperature|rain(?:ing)?|sunrise|sunset|near me|nearby|open now)\b", re.I)
_NAMES_PLACE = re.compile(r"\b(?:in|at|for|near) (?-i:[A-Z])\w+")


def web_query(question: str, place: str = "") -> str:
    """What to search for: the turn without its "can you search the web for",
    and, for a local question that names no place, the person's own place
    (their timezone's city), so "what's the weather like today" is not
    searched as if from nowhere. `place` comes from settings, never typed."""
    asked = clean(_WEB_ASK.sub("", clean(question))) or question
    if place and _LOCAL.search(asked) and not _NAMES_PLACE.search(asked) and place.lower() not in asked.lower():
        asked = f"{asked.rstrip(' ?.!')} {place}"
    return asked


def _page_span(view, row: dict | None, terms: set[str]) -> str:  # noqa: ANN001
    """The sentence of a page that best meets the question: the one the
    composer picked, else the page's best sentence of five words or more
    that is under 260 characters."""
    if row and row.get("sentence"):
        return str(row["sentence"])
    ranked = sorted(
        (s for s in view.sentences if len(s.text.split()) >= 5 and len(s.text) <= 260),
        key=lambda s: -len(terms & set(s.words)),
    )
    return ranked[0].text.strip() if ranked else ""


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
        span = _page_span(view, picked.get(page["id"]), terms) if view else ""
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


composer_lists.bind(_day, _row, Fact, _span)
