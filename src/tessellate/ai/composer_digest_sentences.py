"""The digest's words and the sentence-level text rules (audit-1028 K24, moved whole out of composer_digest.py).

The connecting-words table (`PHRASES`, the voices), the per-turn context variables, the timing and day words, the facets and cues that read a question, the `Fact` and `_Out` shapes, and the naming, fragment, second-person and date-pinning rules that turn a note's sentence into one the answer can say. Nothing here reads a later layer: `composer_digest_lines` (facts and lines) and `composer_digest` (the answer) import from it."""

from __future__ import annotations

import re
import sys
from collections.abc import Callable
from contextvars import ContextVar, copy_context
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from functools import lru_cache, wraps
from pathlib import Path
from tessellate.ai import (
    composer,
    composer_ahead,
    composer_ask,
    composer_frame,
    composer_property,
    filed_name,
    realise,
    recognise as recogniser,
    when as when_words,
)
from tessellate.ai import recognise_questions
from tessellate.ai.composer_lists import clean


#: The connecting words, one table (decision 72: a voice swaps this, never
#: the facts). `{}` slots are filled in order.
_BASE = {
    "overview": "You have {count} about {topic}‹, {span}›.",
    "likes": "It looks that way: you've written about {topic} {times}‹, {span}›.",
    #: Turned by "Ask again" only: a first answer says "from", a retry may say "as ... has it".
    "from_note": ("{fact}, from {name}{when}.", "{fact}, as {name} has it{when}."),
    "from_list": "{count}, from your {what}‹ of {day}›: {items}.",
    "only_one": "It's your only note on {topic} so far.",
    "who_once": "{name} comes up once‹, on {day}›: {fact}.",
    "who_many": "{name} comes up in {count}‹, {span}›.",
    "pick": "The {side}, by your notes: {why}.",
    "more_right": "{count} more on the right.",
    "more_named": "The others are {names}.",
    "more_named_one": "The other is {names}.",
    "more_show": "Show {count} more",
    "overview_names": "They include {names}.",
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
    #: A title-less one-liner is named by its own words: say them once.
    "this_line": "Your note of {day}{where}{pause} says: {fact}.",
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
    "no_place": "Your notes don't say where, but they do say this.",
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
    #: A list says whose it is and how long ("Your Ice Breakers note lists three
    #: questions to ask: ..."), never as something the person said (C32).
    "a_list": "{name} lists {count} items: {items}",
    "a_list_asked": "{name} lists {count} questions to ask: {items}",
    "told_self": ("the same note adds:",),
    "drift_woven": "though no later note says how that went",
    "meaning_loading": "The search by meaning is still loading, so this read your words only; ask again in a few seconds.",
    "meaning_off": "Search by meaning is off, so this read your words only; turn it on in Settings, Search and index.",
    "landed": ("{opening}, and you're {landed}.", "{opening}. For now you're {landed}."),
    #: A landing that is already a sentence ("you picked token-based
    #: retrieval", "we have not decided"): "you're" in front garbled it.
    "landed_said": ("{opening}, and {landed}.", "{opening}; {landed}."),
    "landed_we": ("{opening}, and the latest says {landed}.", "{opening}. One of them says {landed}."),
    "open_count": ("{opening}, with {left} still open.", "{opening}, and {left} still to settle."),
    "stale": (
        "The newest of these is {age} old, so things may have moved on since.",
        "You last added to it {age} ago, which is a while; a fresh note would bring it up to date.",
        "Nothing new on it for {age}, so this is where it stood then rather than now.",
    ),
    #: `{ago}` is "today" or "a week ago": a note written today was "a day
    #: ago" when the age was rounded up to one (audit 1028 E17).
    "burst": (
        "{all_of} came within {span} of each other, the newest written {ago}.",
        "They were written close together, within {span}; the newest is from {ago}.",
    ),
    "cadence": (
        "That's about one every {every}, the newest written {ago}.",
        "You've come back to it roughly every {every}, most recently {ago}.",
    ),
    "fresh": ("The newest is from {ago}, so it's current.", "The latest was written {ago}."),
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
__all__ = ["CONTEXT_TAGS", "FACETS", "LINES", "shows_the_lot", "_GAPS", "_ASKED_AS", "_REMINDABLE", "_DAYS_PLURAL", "_RELATIVE", "_PREFIX", "_TIME_LABEL", "_ACTION", "_STILL_TO", "_RATING", "_WORK", "_FEELING_ASK", "_CUES", "_STRONG_CUES", "_FRAME_WORDS", "_ASKING", "_VERBS", "_NAMES", "_ASKS_WORDS", "_SUBJECT_STEMS", "_KNOWN"]  # read by the digest halves that import them

#: The gap leads already said in this answer, in order (reset per answer).
_GAPS: ContextVar[tuple[str, ...]] = ContextVar("digest_gaps", default=())
#: The question as asked, so an offer to remind is made only to a question about a date or a task (audit 1110 F12); None = not set, offer as before.
_ASKED_AS: ContextVar[str | None] = ContextVar("digest_asked_as", default=None)
_REMINDABLE = re.compile(
    r"\b(?:when|due|deadlines?|remind\w*|to-?do|to do|tasks?|need(?:s)? to|have to|has to|must|should|supposed|expir\w+|renew\w*|book(?:ed|ing)?|appointments?|schedul\w+|upcoming|plans?|planned|forgot\w*|missed|left to|still to|outstanding|pending|overdue|(?:want|wanna|hope|hoping|wish|meaning|going) to|to (?:try|visit|watch|read|see)|bucket|wish ?list)\b",
    re.I,
)


def _isolated(fn):  # noqa: ANN001, ANN202
    """Run a public entry in a copy of the caller's context: `_begin` sets a
    dozen variables, and none may outlive the answer it was set for, or the
    next answer in the same context (a test, the Today voice, `_told_sources`
    answering three earlier questions) starts from the last one's names,
    seed, voice and timing (second eye F7)."""

    @wraps(fn)
    def run(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        return copy_context().run(fn, *args, **kwargs)

    return run
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


#: **How a day a note named is said back** (the owner, 2026-10-31, INBOX
#: 1461: "both", the date and how far back, and "changed in how they are
#: referred based on context or perceived user speech patterns or emotion").
#: The register is the question's; the distance is the day's from today:
#: "close" is today or yesterday (said relatively only, in every register),
#: "week" two to six days back (by its weekday), "near" within five weeks,
#: "far" within six months, "distant" beyond. INBOX 1483 (the owner: "it
#: sounds wierd and not natural"): the relative time leads and the date
#: follows only where it helps ("three weeks ago, on 8 October", "back in
#: July", "last Tuesday"), never a bracketed "(three weeks ago)" after a
#: date; "when did I" keeps the date first, said as a person would ("on 8
#: October, about three weeks ago"). One table, never a branch per case.
_REGISTER: ContextVar[str] = ContextVar("digest_register", default="plain")
_SAY_WHEN: dict[str, dict[str, str]] = {
    "plain": {"close": "{rel}", "week": "{weekday}", "near": "{rel}, {on}", "far": "back in {month}", "distant": "back in {month}"},
    "casual": {"close": "{rel}", "week": "{weekday}", "near": "{rel}", "far": "back in {month}", "distant": "back in {month}"},
    "exact": {"close": "{rel}", "week": "{on_weekday}", "near": "{on}, {about}", "far": "{on}, {about}", "distant": "{on}, {about}"},
    #: "How long ago did I ...": the distance first, then the date.
    "ago": {"close": "{rel}", "week": "{rel}, {on_weekday}", "near": "{rel}, {on}", "far": "{rel}, {on}", "distant": "{rel}, {on}"},
}
#: "When did I ...", "what date ...": the exact date first, every time.
_EXACT = re.compile(r"^\W*(?:when (?:did|was|were|have|had|is|are)|what (?:date|day)|which (?:date|day))\b", re.I)
_AGO = re.compile(r"\bhow long (?:ago|since|has it been)\b", re.I)
#: A question said casually, or with a relative time of its own, is
#: answered in kind ("what did I do last week", "yooo what's been going on").
_CASUAL = re.compile(
    r"\b(?:yo+|lol|haha|gonna|wanna|kinda|lately|been up to|going on|what'?s up|the other day|recently|"
    r"last (?:week|month|weekend|night)|yesterday|this (?:week|month)|on (?:mon|tues|wednes|thurs|fri|satur|sun)day)\b",
    re.I,
)
#: The person's own time words, said back when the day falls in them: they
#: said "last week", the answer says "last week" (the owner, 2026-10-31).
_ECHO_WORDS = re.compile(r"\b(today|yesterday|this week|last week|this month|last month)\b", re.I)
_ECHO: ContextVar[tuple] = ContextVar("digest_echo", default=())


def _set_timing(question: str) -> None:
    """What this answer may say about time, from the question (INBOX 1441),
    and in which register (INBOX 1461)."""
    _TIMED.set(composer_ask.asks_time(question))
    _CURRENT.set(bool(_ASKS_CURRENT.search(question or "")))
    asked = question or ""
    register = "ago" if _AGO.search(asked) else "exact" if _EXACT.search(asked) else "casual" if _CASUAL.search(asked) else "plain"
    _REGISTER.set(register)
    _ECHO.set(tuple(dict.fromkeys(m.lower() for m in _ECHO_WORDS.findall(asked))))


def _echoed(start: date, today: date) -> str:
    """The question's own time word that holds `start`, or ""."""
    monday = today - timedelta(days=(today.weekday() - _week_first()) % 7)
    first = today.replace(day=1)
    spans = {
        "today": (today, today), "yesterday": (today - timedelta(days=1),) * 2,
        "this week": (monday, today), "last week": (monday - timedelta(days=7), monday - timedelta(days=1)),
        "this month": (first, today), "last month": ((first - timedelta(days=1)).replace(day=1), first - timedelta(days=1)),
    }
    return next((w for w in _ECHO.get() if spans[w][0] <= start <= spans[w][1]), "")


def _ago(day: date, today: date) -> str:
    """How far back `day` is, as a person says it: "yesterday", "five days
    ago", "three weeks ago", "three months ago"."""
    gap = (today - day).days
    if gap <= 1:
        return ("today", "yesterday")[max(gap, 0)]
    if gap < 7:
        return f"{realise.count_word(gap)} days ago"
    if gap < 35:
        #: The card's rounding (`realise.weeks_gone`), so 27 days is four weeks on both.
        weeks = realise.weeks_gone(gap)
        return "a week ago" if weeks == 1 else f"{realise.count_word(weeks)} weeks ago"
    #: Whole months gone, as people count them: 109 days is "three months ago".
    months = int(gap / 30.44)
    if months < 12:
        return "a month ago" if months <= 1 else f"{realise.count_word(months)} months ago"
    years = gap // 365
    return "a year ago" if years <= 1 else f"{realise.count_word(years)} years ago"


def _about_ago(gap: int) -> str:
    """How far back, rounded as a person rounds after "about": 86 days is
    "about three months ago", never "about two months ago" (`_ago` counts
    whole units gone, for a phrase said without "about")."""
    if gap < 35:
        weeks = max(round(gap / 7), 1)
        return "about a week ago" if weeks == 1 else f"about {realise.count_word(weeks)} weeks ago"
    months = round(gap / 30.44)
    if months < 12:
        return "about a month ago" if months <= 1 else f"about {realise.count_word(months)} months ago"
    years = round(gap / 365.25)
    return "about a year ago" if years <= 1 else f"about {realise.count_word(years)} years ago"


def _week_first() -> int:
    """The person's first day of the week (0 Monday), from the settings the
    app has loaded; Monday with none (a unit test, a prompt before start)."""
    from tessellate.core import config

    deps = sys.modules.get("tessellate.core.deps")
    loaded = deps.peek_config() if deps else None
    return config.week_first_day(loaded) if loaded is not None else 0


def _gone_distance(gap: int, week: bool, close: bool) -> str:
    """How far back a gone day is, as the rule table keys it."""
    if gap <= 1 or close:
        return "close"
    if gap < 7 and not week:
        return "week"
    return "near" if gap < 35 else "far" if gap < 183 else "distant"


def _when_gone(on: str, start: date, today: date, week: bool = False) -> str:
    """A day (or a week from its first day) that has gone by, said by the
    rule table: `on` is its exact form ("on 20 July", "in the week of 13 July")."""
    gap = (today - start).days
    this_monday = today - timedelta(days=(today.weekday() - _week_first()) % 7)
    last_week = week and this_monday - timedelta(days=7) <= start < this_monday
    rel = "last week" if last_week else _ago(start, today)
    exact = _REGISTER.get() == "exact"
    echoed = _echoed(start, today)
    if echoed and not exact:
        return echoed
    if echoed:
        #: "When did I ... last week": the date, then their own words.
        return f"{on}, {echoed}" if gap > 1 else rel
    #: Last week is close, said as "last week", except to "when did I":
    #: only today and yesterday go without their date there.
    distance = _gone_distance(gap, week, last_week and not exact)
    name = _DAY_NAMES[start.weekday()]
    weekday = f"on {name}" if start >= this_monday else f"last {name}"
    month = composer_ask._MONTHS[start.month - 1] + ("" if start.year == today.year else f" {start.year}")
    about = _about_ago(gap) if rel.endswith(" ago") else rel
    return _SAY_WHEN[_REGISTER.get()][distance].format(
        on=on, rel=rel, month=month, weekday=weekday, on_weekday=f"on {name} {_day(start, today)}", about=about)


def _said_day(day: date, today: date | None) -> str:
    """A day as a lead says it, by the one rule table (`_when_gone`): "three
    weeks ago, on 8 October", "back in July", "yesterday"; the bare "on 8
    October" only for a day not yet gone or with no today to count from
    (INBOX 1483, composer5: a timed answer never leads with a bare date)."""
    on = f"on {_day(day, today or day)}"
    return _when_gone(on, day, today) if today and day <= today else on


def _lead_day(day: date | None, today: date | None, capital: bool = True) -> str:
    """`_said_day` as the first words of a sentence (or, with no `capital`,
    of a clause after another), comma and space after."""
    said = _said_day(day, today) if day else "on an undated day"
    return f"{said[:1].upper() if capital else said[:1]}{said[1:]}, "


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


def only_note_lines() -> frozenset[str]:
    """Every wording of the closing "your only note on that" claim, in every
    voice (a voice may hold several, a tuple)."""
    said: set[str] = set()
    for table in (_BASE, *VOICES.values()):
        value = table.get("only_note")
        if value:
            said.update(value if isinstance(value, tuple) else (value,))
    return frozenset(said)


#: What a review is of (`_reviewed_word`): the only nouns `only_kind` is said with.
_REVIEWED_WORDS = "film|movie|book|show|series|album|game"


def is_only_claim(line: str) -> bool:
    """Whether a paragraph is that closing claim: a wording the composer
    emits ("only note", "only film review"), never any line that has "only"
    in it ("Only one reminder is due on Friday.")."""
    line = line.strip()
    if line in only_note_lines():
        return True
    fills = {"noun": rf"(?:{_REVIEWED_WORDS}) review", "topic": r"[^\n.]+?"}
    return any(re.fullmatch(re.sub(r"\\\{(\w+)\\\}", lambda m: fills[m.group(1)], re.escape(template)), line) for template in _only_templates())


def _only_templates() -> list[str]:
    """The `only_kind` and `only_one` wordings, in every voice."""
    said: list[str] = []
    for table in (_BASE, *VOICES.values()):
        for key in ("only_kind", "only_one"):
            value = table.get(key)
            said += [value] if isinstance(value, str) else list(value or ())
    return said


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
_RELATIVE = re.compile(r"(?<!\s)\s*\b(?:before |by |until )?(?:next|this|last) (?:week|month|weekend)\b", re.I)
_PREFIX = re.compile(r"^([^:.!?\n]{2,34}):\s+(\S.*)$")
_TIME_LABEL = re.compile(r"^((?:this|next|last) (?:semester|term|year|month|week|weekend)),?\s+(.+)$", re.I)
_ACTION = re.compile(r"(?:^|,\s*|;\s*|\band\s+)((?:ask|call|email|text|book|buy|order|read|check|remember to|pay|send|bring)\b[^.;,]*)$", re.I)
_STILL_TO = re.compile(r"\b([a-z]+(?: [a-z]+)?) (?:are |is )?still to (book|buy|pay|do|send|order|sort)\b", re.I)
_PAST_START = re.compile(
    r"^(went|hit|got|saw|had|did|made|tried|watched|closed|opened|finished|started|played|bought|ate|met|"
    r"wrote|ran|walked|visited|spent|called|rang|rung|booked|fixed|cooked|cleaned|learnt|took)\b",
    re.I,
)
_RATING = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:out of|/)\s*(10|5|100)\b", re.I)
_WORK = re.compile(r"^(?:watched|saw|read|played|finished|listened to)\s+(.+?)\.?$", re.I)
_GOOD = re.compile(r"\b(incredible|amazing|great|loved|love|brilliant|beautiful|fun|good|excellent|fantastic|enjoyed|perfect)\b", re.I)
_BAD = re.compile(r"\b(dragged|boring|bad|hated|awful|terrible|slow|meh|disappointing|too long|weak|annoying)\b", re.I)

#: What a feeling question looks for in a sentence (audit 1030 Z20: "how did
#: I feel on Saturday" dropped "Felt happy."), and how such a question is asked.
_FELT_LINE = re.compile(r"\b(?:felt|feel|feels|happy|sad|calm|calmer|tired|anxious|stressed|glad|proud|relaxed|annoyed|excited|liked|enjoyed)\b", re.I)
_FEELING_ASK = re.compile(r"\b(?:feel|feeling|felt|happy|sad|calm|tired|anxious|stressed|mood|enjoy|enjoyed|like|liked|think of|think about)\b", re.I)


def _feeling(text: str) -> bool:
    return bool(_FELT_LINE.search(text) or _GOOD.search(text) or _BAD.search(text))


#: Labels for a fact in a note with no heading of its own, first match wins.
_CUES: tuple[tuple[str, re.Pattern], ...] = (
    ("Booked", re.compile(r"\b(is|are|was|were|all) booked\b", re.I)),
    ("Where you landed", re.compile(r"\b(leaning towards|decided|going with|chose|picked|settled on)\b", re.I)),
    ("What you want", re.compile(r"\b(i|you) (want|need) (it|one|them)\b|\blooking for\b", re.I)),
    ("Prices", re.compile(r"\$\s?\d.*\$\s?\d")),
    ("Your aim", re.compile(r"^(trying|aiming|hoping|planning) to\b", re.I)),
    ("Your schedule", re.compile(r"\b(mon|tues|wednes|thurs|fri|satur|sun)days\b|\bevery (mon|tues|wednes|thurs|fri|satur|sun)day\b", re.I)),
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
    "learned learnt saved save written wrote noted kept think thought know day days date dates week weeks time times "
    "thing things stuff note notes plan plans going"
)

#: Verbs a question names its subject with ("spend on groceries"): never the
#: subject's missing word.
_VERBS = _stems("spend spent buy get make do go like want need try see say use pay cost")

#: "show me my study notes", "pull up my uni notes": the notes on a subject, said
#: whole (`filed_name.shows_the_lot`, the one rule: the verb decides, CHAT_PLAN decision 81).
_SHOW_NOTES = filed_name.SHOW_NOTES
shows_the_lot = filed_name.shows_the_lot


_ASKS = {
    "compare": re.compile(r"^\s*+(?:the\s+)?(?P<a>[\w' -]{2,30}?)\s+or\s+(?:the\s+)?(?P<b>[\w' -]{2,30}?)\s*\??\s*$", re.I),
    #: "who is coming for Christmas" asks who does something: its first word is a verb in -ing, not a name.
    "who": re.compile(r"^\s*who(?:'s| is| was)\s+(?!\w+ing\s)(?P<name>[A-Za-z][\w' -]{0,30}?)\s*\??\s*$", re.I),
    "when": re.compile(r"^\s*(?:when|what (?:days?|dates?|times?)|which (?:days?|dates?))\b", re.I),
    #: "How many notes mention Lisbon" counts notes: the overview, which leads
    #: with that count (2026-10-30 sweep: it answered with a dated line).
    "count": re.compile(r"^\s*how (?:much|many)\b(?! (?:of my )?(?:notes|entries)\b)", re.I),
    "likes": re.compile(r"^\s*(?:do|did) i (?:like|enjoy|love|play|do)\b|^\s*am i (?:into|a fan of)\b", re.I),
    "opinion": re.compile(r"\bwhat did i (?:think|make) of\b|\bhow did i (?:find|like)\b|\bmy (?:review|opinion|thoughts) (?:of|on)\b", re.I),
    "left": re.compile(r"\bwhat do i (?:still )?(?:need|have|want|plan|hope) to\b|\bwhat would i like to\b|\bwhat(?:'s| is) (?:left|outstanding|still to do)\b|\bto buy\b", re.I),
    "overview": re.compile(
        r"\bwhat (?:have|did) i (?:saved|save|written|write|noted|got|kept)\b|\bwhat(?: else)?(?:'s| is) there\b|\bwhat (?:else )?do i have\b|"
        r"\bwhat \w+(?: \w+)? (?:have|did) i (?:saved|save|written|write|kept|got|noted)\b|\bwhat (?:else )?(?:do|does|did) (?:my|the) (?:notes|entries) (?:say|tell me|have|mention|know|cover)\b|\btell me about\b|\beverything (?:about|on)\b|\bsummari[sz]e\b|\bwhat(?:'s| is) the plan\b|"
        r"\bplans? for\b|^\s*how(?:'s| is| are) (?:my |the )?.+ going\b|\bwhat have i (?:learned|learnt)\b|^\s*how many (?:of my )?(?:notes|entries)\b|"
        #: "what about social connections" asks for the lot (INBOX 1420).
        r"^\s*(?:and |so )?what about (?:my |the )?\w+(?: \w+)?\s*\??\s*$|\bwhat (?:else )?do i know (?:about|on)\b|"
        #: "show me my study notes": the notes on a subject, said whole, not one fact from one of them.
        + _SHOW_NOTES,
        re.I,
    ),
}


#: A question that opens with none of these is a topic ("games notes"):
#: an overview.
_ASKED = re.compile(r"^(?:what|what's|whats|when|who|whom|whose|how|how's|do|does|did|is|are|was|were|where|why|which|can|could|should|will|have|has|had|tell|show|list|give|any)\b"
                    r"|^(?:the )?(?:latest|newest|most recent|news|updates?) (?:on|about|with)\b", re.I)


#: "Summarise this", "what's this about", "tl;dr" (B10): a question about
#: whatever is open where it was asked, with no subject of its own.
_THIS = re.compile(
    r"^(?:(?:can|could) you |please )?(?:"
    r"(?:summari[sz]e|sum up|recap|give me the gist of|what(?:'s| is| are) the (?:gist|main points) of)"
    r"(?: (?:this|it|these|this note|the note|this page|this category|what(?:'s| is| i have) open))?"
    r"|what(?:'s| is) (?:this|it) (?:note |page )?about|what does (?:this|it)(?: note| page)? say|tl;? ?dr"
    #: Every demonstrative is the open note (audit 1030 Z54): "what is this",
    #: "what's in here", "explain this", "describe this note", "what is here".
    r"|what(?:'s| is) (?:this|here)(?: note| page)?|what(?:'s| is) in (?:here|this(?: note| page)?)"
    r"|what(?:'s| is) (?:going on|happening)(?: in)? (?:here|this(?: note| page)?)|what happened(?: in)? (?:here|this(?: note| page)?)"
    r"|(?:explain|describe|read(?: out)?|go (?:over|through)|run (?:me )?through) (?:this|it)(?: note| page)?"
    #: "tell me about this", "give me a summary of this note" (L46): a request for the open note, said as a request.
    r"|(?:tell|talk|walk) me (?:about|through) this(?: note| page| one)?|give me (?:a |an |the )?(?:summary|overview|rundown) of this(?: note| page| one)?"
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


#: "tell me more", "what else": with a note open and nothing said before, more
#: of the only thing in view (audit 1030 Z54).
_MORE_OF_THIS = re.compile(r"^(?:(?:please )?(?:tell|show|give) me (?:some )?more(?: about (?:this|it|that))?|more(?: please)?|what else|anything else)$", re.I)


def more_of_this(question: str) -> bool:
    """Whether `question` asks for more with no subject of its own."""
    return bool(_MORE_OF_THIS.match(clean(question).rstrip("?.! ")))


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
    #: "dentist number" is a fact asked bare, not a topic to overview (E12).
    return "overview" if q and not _ASKED.match(q) and not composer_property.asked(q) else "fact"


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
    #: The insight a woven overview keeps in reserve (INBOX 1743): (line, row).
    spare: tuple = ()


_KIND_NOUN = {"document": "document", "board": "board", "map": "mind map", "picture": "picture"}


def _says_day(text: str, day: date | None, today: date) -> bool:
    """Whether `text` names `day` already, "on Sunday 25 October" as much as
    "on 25 October": the day is said once (audit 1031 C28)."""
    return day is not None and bool(re.search(rf"\b{re.escape(_day(day, today))}\b", text, re.I))


def _only_a_title(view, today: date) -> str:  # noqa: ANN001
    """"Atlas retro meeting, from your note of 26 October": a title said as a
    fact (C2). The note is named; it holds nothing more."""
    said = _note_called(view.title)
    day = f" of {_day(view.written, today)}" if view.written and _TIMED.get() else ""
    return f"{said[0].upper() + said[1:]}{day} has only its title so far."


def _fact_names_title(view, fact: str) -> bool:  # noqa: ANN001
    """Whether `fact` says the note's title as a name, so "from" it again is a
    repeat (C36). One common word ("Sister") inside "your sister's birthday"
    is the subject of the fact, not the note named: it needs the title as
    written, and never as a possessive."""
    title = re.sub(r"^(?:the|a|an)\s+", "", (view.title or "").strip(), flags=re.I)
    if not title:
        return False
    flags = re.I if " " in title else 0
    return bool(re.search(rf"\b{re.escape(title)}\b(?!['\u2019]s)", fact, flags))


def _when_tail(view, fact: str, today: date) -> str:  # noqa: ANN001
    """", written on 11 August, ..." after a fact, or, for a fact whose own day is still ahead, how far off it
    is (", in 23 days"): the write date is noise beside it (R9-17)."""
    ahead = composer_ahead.distance(fact, today)
    if ahead and _TIMED.get() and _WHEN_ASK.get():
        return f", {ahead}"
    #: A fact that carries its own date ("Her birthday is on 14 March") is not dated again by the day it was written (W8 B11).
    if _WHEN_ASK.get() and composer_ahead.date_in(fact, today) is not None:
        return ""
    return f", written {_said_day(view.written, today)}" if _TIMED.get() and not _says_day(fact, view.written, today) else ""


def _from_source(view, fact: str, today: date) -> str:  # noqa: ANN001
    """"Fact, from your note of 3 March." for a note; a document, board or
    map is said as itself by its title (INBOX 1357, class F: "Hamlet delays
    ..., from your note of an undated day" for a document)."""
    noun = _KIND_NOUN.get(getattr(view, "kind", "note") or "note")
    #: "... that work in most settings:, from your note" (INBOX 1420).
    fact = fact.rstrip().rstrip(":;,").rstrip()
    fact = _clause_list(fact) or fact
    if not noun and _title_only(view) and fact.lower() == view.title.strip().lower():
        return _only_a_title(view, today)
    if noun and view.title:
        return f"{fact}, from your {noun} **{view.title}**."
    if view.written is None or not _TIMED.get() and not getattr(view, "titled", False):
        #: The citation mark says which note (INBOX 1483: "chill :D,¹ from
        #: one of your notes" read as a tail on the person's own words).
        return f"{fact}."
    #: Not again when the fact already says the day it was written.
    when = _when_tail(view, fact, today)
    #: A fact that already names the note is not "from" it again (audit 1031 C36).
    if not getattr(view, "titled", False) or _fact_names_title(view, fact):
        return f"{fact}{when}."
    return PHRASES["from_note"].format(fact=fact, name=_your_note(view), when=when)


def _day(d: date | None, today: date) -> str:
    if d is None:
        return "an undated day"
    month = composer_ask._MONTHS[d.month - 1]
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


def _titled_names() -> set[str]:
    """A word with a capital in two titles, one of them past the title's first
    word ("Tokyo trip", "Packing for Tokyo"): a name, which keeps its capital
    when the question typed it small (E22). "Meeting notes" and "Meeting with
    Priya" do not make "meeting" one."""
    seen: dict[str, int] = {}
    inside: set[str] = set()
    for t in _titles():
        words = re.findall(r"\b[A-Z][\w'-]*", t)
        for w in {w.lower() for w in words}:
            seen[w] = seen.get(w, 0) + 1
        inside |= {w.lower() for w in re.findall(r"(?<=\s)[A-Z][\w'-]*", t)}
    return {w for w, n in seen.items() if n > 1 and w in inside}


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


_CITED = re.compile(r"[A-Z][\w'-]+(?: [A-Z][\w'-]+)?,? \(?(?:1[5-9]|20)\d\d[a-z]?\b")


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
    #: An author and a year ("Hunter 1999", "Clark (2012), The ...") is a citation (E19).
    if _keeps_capital(word, names) or _CITED.match(text):
        return text
    verb = _verb_led(text) or _did(word) or word.lower() in _FUNCTION_WORDS
    if _starts_a_title(text, bool(verb)):
        return text
    known = _dictionary()
    if known and (word.lower() not in known or _a_name(word.lower(), known)):
        return text
    return text[0].lower() + text[1:]


def _a_name(word: str, known: frozenset[str]) -> bool:
    """Whether a capitalised word the shipped list holds is a name all the
    same ("Lisbon", "Tokyo", "Sara"): the list is lower case, so a name
    and a word look alike in it; a word has its kin there ("glaze", "glazes",
    "glazed"), a name has none, and it is not one of the common words.
    Calendar words are names in English (hub, 2026-10-31: "proper-noun
    casing must survive the clause rewrite")."""
    from tessellate.ai import common_words

    if _CALENDAR_WORD.fullmatch(word.capitalize()):
        return True
    if word in common_words.WORDS or len(word) < 3:
        return False
    kin = {word + end for end in ("s", "es", "ed", "d", "ing", "er", "ers", "ly", "al", "y")}
    kin |= {word[: -len(end)] + add for end, add in (("s", ""), ("es", ""), ("ed", ""), ("ed", "e"), ("ing", ""), ("ing", "e"), ("y", "ies")) if word.endswith(end)}
    return not kin & known


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
    # "Do not buy perfume again" is a rule to quote, and "Order 4471 from Amazon" names a thing: neither fits "you planned to" (R3-10).
    if len(words) >= 2 and words[0].lower() == "do" and words[1].lower() in ("not", "nt"):
        return False
    if re.match(r"\s*[A-Za-z][\w'-]*\s+#?\d{3,}\b", text or ""):
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
    """The one name for a note in a frame: a titled note by its title, a title-less
    one by its first line cut at about six words (`composer_frame.name_of`), never
    by a section's label or "untitled" (C8, INBOX 1420; owner 2026-11-10: one name
    in lists, compare and prose, so "Trip planning: flights to Lisbon" is named by
    its first line like any other)."""
    if getattr(view, "titled", False) and view.title:
        return _note_called(view.title)
    note = getattr(view, "note", None) or {"content": getattr(view, "title", "")}
    return composer_frame.short_name(note)


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


def _as_you(text: str) -> str:
    """A note's own past-tense start said as "you ...": "Rung mum" is "you rang mum" (the participle is the
    British note-taker's short form, never the you-form)."""
    return "you " + re.sub(r"^rung\b", "rang", text[:1].lower() + text[1:])


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


_WEATHER_VERBS = frozenset("rained snowed poured drizzled hailed stormed thundered sleeted misted".split())


def _fresh(written: date | None) -> bool:
    """Whether a note is under a month old: what it says is still said in the
    present ("you need new running shoes"), not backshifted (audit 1031 C32)."""
    today = _TODAY.get()
    return bool(written and today and 0 <= (today - written).days <= 30)


def _second_person(text: str, written: date | None = None) -> str:
    """The writer's words said to them: "I'm doing" to "you're doing", and a
    diary line with no subject ("Went to the range") given its "you"."""
    text = realise.shift_person(text)
    if _DOING_NOW.match(text):
        #: "thinking of buying the mouse": what the writer was doing then,
        #: or still is when the note is recent.
        return ("you're " if _fresh(written) else "you were ") + text[0].lower() + text[1:]
    first = re.match(r"[A-Za-z]+", text)
    if first and first.group(0).lower() in _WEATHER_VERBS:
        #: "Rained all day, baked banana bread": the weather did the first, the
        #: writer the rest (audit 1031 C13).
        head, comma, rest = text.partition(",")
        rest = rest.strip()
        text = "it " + head[0].lower() + head[1:] + (f", and you {rest[0].lower() + rest[1:]}" if comma and rest and not rest.lower().startswith(("and ", "but ")) else (", " + rest if rest else ""))
    elif first and _did(first.group(0)):
        text = _as_you(text)
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
#: The stems of what the question is about, so a to-do or an offer from a note
#: that only shares the notebook is not tacked on (audit 1030 Z8).
_SUBJECT_STEMS: ContextVar[frozenset] = ContextVar("digest_subject_stems", default=frozenset())
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
    gone: list[str] = []

    def said(m: re.Match) -> str:
        step = {"next": 1, "this": 0, "last": -1}[m.group("which").lower()]
        pre, unit = m.group("pre") or "", m.group("unit").lower()
        if unit == "month":
            index = written.month - 1 + step
            year, month = written.year + index // 12, index % 12 + 1
            name = composer_ask._MONTHS[month - 1] + (f" {year}" if year != today.year else "")
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
        first = _week_first()
        if first:
            #: The person's own first day of the week (Settings, or the
            #: browser's locale): "last week" in a note of Sunday 26 July is
            #: the week of 19 July where weeks start on a Sunday (INBOX 1461).
            monday = written - timedelta(days=(written.weekday() - first) % 7) + timedelta(days=7 * step)
        if pre.strip().lower() in ("before", "by", "until"):
            return f"{pre}{_day(monday, today)}"
        if not pre and monday + timedelta(days=7) <= today:
            #: A week gone by: its date and how far back (INBOX 1461).
            gone.append(_when_gone(f"in the week of {_day(monday, today)}", monday, today, week=True))
            return gone[-1]
        return f"{pre}the week of {_day(monday, today)}"

    text = _PIN.sub(said, text)
    #: "Trimmed my first bowl today", written 2 September, is "on 2
    #: September"; under that day's own label the day is dropped (`_lines`).
    for found in reversed(_spans(text, written)):
        if _in_a_title(text, found):
            continue
        if found.kind in ("date", "datetime") and (found.text.lower() in _DEICTIC or (written != today and _RELATIVE_TIME.match(found.text))):
            day = found.value.date() if isinstance(found.value, datetime) else found.value
            if day == today and written == today:
                #: Today's "today" and "tonight" are still true (INBOX 1461).
                continue
            #: "Tomorrow at 3pm" keeps its clock time: "on 6 October at 3pm" (L94).
            at = re.search(r" at .+$", found.text, re.I) if found.kind == "datetime" else None
            on = f"on {_day(day, today)}{at.group(0) if at else ''}"
            if day < today:
                gone.append(_when_gone(on, day, today))
                on = gone[-1]
            text = f"{text[:found.start].rstrip()} {on}{text[found.end:]}"
    return _said_gone(_pin_weekdays(text, written, today, gone), gone)


def _in_a_title(text: str, found) -> bool:  # noqa: ANN001
    """A capitalised "Tomorrow" in the middle of a list is a title ("Tomorrow and
    Tomorrow and Tomorrow"), not the day (R9-5)."""
    before = text[: found.start].rstrip()
    return found.text[:1].isupper() and bool(before) and before[-1] not in ".!?:;-([*\n"


#: A weekday said alone ("moved to Friday", "on Monday", "next Tuesday"):
#: the note's week tells which, so it is said with its date once read.
_WEEK_SAID = re.compile(r"\s*,?\s*(?:(?:in )?the week of|back in|[\w-]+ (?:weeks?|months?|years?) ago|(?:mornings|afternoons|evenings|nights)\b|(?:next|this|last) week|\d|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b)", re.I)
_WEEKDAY_ALONE = re.compile(r"^(?P<pre>on )?(?:(?:this|next|last) )?(?P<day>(?:mon|tues|wednes|thurs|fri|satur|sun)day)$", re.I)


def _pin_weekdays(text: str, written: date, today: date, gone: list[str]) -> str:
    """"Group project meeting moved to Friday", written Thursday 10
    September, is "moved to Friday 11 September": pinned to the note's own
    week, read back from its day when the sentence tells what happened
    ("handed in on Monday" is the Monday before), past tense once gone
    (composer-1031, item 4). A note of today keeps its weekday as said."""
    #: "My uni days are Tuesday and Thursday": two weekdays are a schedule,
    #: every week's, never one week's days.
    if written == today or len(re.findall(r"\b(?:mon|tues|wednes|thurs|fri|satur|sun)days?\b", text, re.I)) > 1:
        return text
    tense = "past" if recognise_questions.told_as_past(text) else None
    for found in reversed(_spans(text, written, tense)):
        alone = _WEEKDAY_ALONE.match(found.text) if found.kind == "date" else None
        #: "Thursday next week", "Friday 11 September": its week or date is said already.
        if not alone or _WEEK_SAID.match(text[found.end:]):
            continue
        #: "On Tuesday", said by `_when_gone` for a "today" of this week, is
        #: the note's day already, never read again as another week's.
        if any(found.text.lower() in g.lower() for g in gone):
            continue
        day = found.value.date() if isinstance(found.value, datetime) else found.value
        said = f"{alone.group('pre') or ''}{alone.group('day').capitalize()} {_day(day, today)}"
        if day < today:
            gone.append(said)
        text = f"{text[:found.start]}{said}{text[found.end:]}"
    return text


_COPULA_PAST = {"is": "was", "are": "were", "am": "was", "'s": " was", "'re": " were"}


def _said_gone(text: str, gone: list[str]) -> str:
    """A sentence about a time gone by in the past tense ("your uni days ...
    were Tuesday and Thursday"), its one time said first when the sentence
    is the person's own ("Back in July, your uni days were ...", "Three
    weeks ago, on 8 October, you missed the bus"), as the owner wrote it
    (INBOX 1461, 1483)."""
    if not gone:
        return text
    text = re.sub(r"\b(is|are|am)\b", lambda m: _COPULA_PAST[m.group(1).lower()], text)
    phrase = gone[0]
    if len(gone) == 1 and re.match(r"(?:you|your)\b", text, re.I) and phrase in text:
        rest = re.sub(r"\s{2,}", " ", text.replace(f" {phrase}", "", 1)).strip(" ,")
        return f"{phrase}, {rest[:1].lower()}{rest[1:]}"
    for phrase in gone:
        if ", " in phrase:
            #: An aside closes before the words go on: "three weeks ago, on
            #: 8 October, for prototyping".
            text = re.sub(rf"{re.escape(phrase)}(?= \w)", f"{phrase},", text, count=1)
    return text


#: The words for the day a note was written, said as that day once read:
#: the recogniser gives the day each means from the note's own date.
#: "Tomorrow" is said as its day too once that day is past (INBOX 1357).
_DEICTIC = frozenset(("today", "tonight", "yesterday"))
#: Time words true only on the day written: "tomorrow (at 3pm)", "in 3 days", "two weeks ago" (L94).
_RELATIVE_TIME = re.compile(r"(?:tomorrow|yesterday)(?: at .+)?$|in \w+ (?:days?|weeks?)$|\w+ (?:days?|weeks?) ago$", re.I)


@lru_cache(maxsize=4096)
def _spans_at(text: str, written: date, tense: str | None = None) -> tuple:
    """The recogniser's first reading of each span in `text`, anchored at
    noon on the day the note was written (the one reader of date words and
    units, CHAT_PLAN decision 46)."""
    return tuple(s for s in recogniser.recognise(text, now=datetime.combine(written, time(12)), tense=tense) if not s.rank)


def _spans(text: str, written: date | None, tense: str | None = None) -> tuple:
    return _spans_at(text, written or _UNDATED, tense) if text else ()


#: The anchor for text with no day of its own: units and figures do not
#: depend on it, and a day read against it is never said.
_UNDATED = date(2000, 1, 1)


_DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _clause_list(said: str) -> str:
    """A sentence of three or more `;` clauses, each a few words, as bullets
    (audit 1028 E63): one run-on line of 12 to 20 words a clause reads as a
    wall. "" for a sentence that is not that."""
    clauses = [c.strip() for c in said.rstrip(". ").split("; ")]
    if len(clauses) < 3 or any(len(c.split()) < 3 for c in clauses):
        return ""
    return "\n".join(f"- {c[:1].upper() + c[1:]}" for c in clauses)


_WHEN_ASK: ContextVar[bool] = ContextVar("composer_when_ask", default=False)
