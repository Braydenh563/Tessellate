"""One typed reading per input (CHAT_PLAN "The deterministic foundation",
module 2; decisions 47 to 49).

`read(text, *, now, context)` is the one parse chat, search, quick add and the
palette share: the `Reading` says what the words are (an act with its slots, a
utility, a question with its window, small talk, nothing), the spans
`recognise` read in them, how sure the reading is, and which reader decided.
No surface parses twice; `GET /read` serves it to the page (Brief 66's chips).

Confidence decides behaviour (decision 48), by the bands in `BANDS`:

- sure: act, or answer;
- likely: act, and say what was read (`Reading.said`);
- unsure: ask one question naming both readings, or the one missing slot
  ("Remind you when?"), never a guess (`Reading.question`);
- none: the repair ladder (`repair`, decision 49).

Nothing here reads a date or a unit itself: every such word is a span from
`ai/recognise.py` (decision 46; `tests/test_one_reader.py`).
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass, field
from datetime import date, datetime

from tessellate.ai import act_registry
from tessellate.ai import recognise as rec

#: The bands of decision 48, highest first: a reading is in the first band
#: whose floor its confidence reaches. Set 2026-10-10 by the eval
#: `tests/fixtures/composer/reading_1010.json` (42 rows, each with the band a
#: person would expect; `tests/test_reading.py`): at these floors every row
#: lands in its band (42 of 42). The scores in `SCORES` sit 0.1 or more from
#: every floor, so a score moved by one step of `SCORES` cannot change band
#: by accident.
BANDS: tuple[tuple[str, float], ...] = (("sure", 0.85), ("likely", 0.6), ("unsure", 0.3), ("none", 0.0))

#: What each kind of reading scores. One table, so the policy reads in one
#: place: an act or utility with every slot filled is sure; a question that
#: names a window is likely (the window is said back); a missing slot or two
#: readings of one phrase is unsure; a key-mash or empty input is none.
SCORES: dict[str, float] = {
    "act": 0.95,
    "utility": 0.95,
    "about_app": 0.95,
    "smalltalk": 0.95,
    "question": 0.95,
    "question_window": 0.75,
    "act_read_by_locale": 0.75,
    "ambiguous": 0.45,
    "missing_slot": 0.45,
    "no_content": 0.15,
    "unknown": 0.1,
    "empty": 0.0,
}

_TIME_KINDS = frozenset({"date", "datetime", "time", "range", "recurrence"})
#: Spans that say a time of day as well as a day (a repeat always has one: 9:00 unless said).
_CLOCKED = frozenset({"datetime", "time", "recurrence"})
#: Fields where the whole input is one dated thing (quick add, decision 50):
#: read as the item's words and its time, and the one question each asks
#: when no time was said. Other surfaces ("note", "palette") read as chat does.
DATED_SURFACES = {"reminder": "Remind you when?", "meeting": "When is it?", "timeline": "When was it?"}


def band_of(confidence: float) -> str:
    for name, floor in BANDS:
        if confidence >= floor:
            return name
    return "none"


@dataclass
class Reading:
    """What one input says: `intent` (an act's name such as "reminder" or
    "tag", or "utility", "question", "about_app", "smalltalk", "unknown",
    "empty"), its `slots`, the `spans` read in it, `confidence` (0 to 1),
    and `source`, the reader that decided ("commands", "reminder",
    "utilities", "intent", "query", "none"). `question` is the one question
    an unsure reading asks; `said` is what a likely one says it read."""

    intent: str
    slots: dict = field(default_factory=dict)
    spans: list = field(default_factory=list)
    confidence: float = 0.0
    source: str = "none"
    question: str | None = None
    said: str | None = None
    #: The tool in `ai/tools` this reading reaches with no model (decision 59,
    #: step 1): an act's own tool, a utility's, or the one its words name.
    tool: str | None = None

    @property
    def band(self) -> str:
        return band_of(self.confidence)

    def json(self) -> dict:
        return {
            "intent": self.intent,
            "slots": {k: _plain(v) for k, v in self.slots.items()},
            "spans": [s.json() for s in self.spans],
            "confidence": self.confidence,
            "band": self.band,
            "source": self.source,
            "question": self.question,
            "said": self.said,
            "tool": self.tool,
        }


def _plain(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat(timespec="minutes")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def _known(context: dict, now: datetime) -> dict:
    """Dates the context names, as `recognise` takes them: the next birthday
    from a stored one ("on my birthday" was None everywhere: engine probe)."""
    out = {}
    born = context.get("birthday")
    if born:
        try:
            day = date.fromisoformat(str(born))
        except ValueError:
            day = None
        if day is not None:
            for year in (now.year, now.year + 1):
                try:
                    candidate = day.replace(year=year)
                except ValueError:
                    candidate = date(year, 2, 28)
                if candidate >= now.date():
                    out["my birthday"] = candidate
                    break
    return out


def _ambiguity(spans: list, chosen: list) -> tuple | None:
    """(the reading, the other) when a span the reading uses has a second reading."""
    for span in chosen:
        other = next((s for s in spans if s.rank > 0 and (s.start, s.end) == (span.start, span.end)), None)
        if other is not None:
            return span, other
    return None


def _weigh(reading: Reading, used: list, context: dict) -> Reading:
    """Lower a complete reading whose time words read two ways: likely when
    the person's locale settled it (and say so), unsure otherwise (ask)."""
    two = _ambiguity(reading.spans, used)
    if two is None:
        return reading
    first, other = two
    if context.get("locale"):
        reading.confidence = min(reading.confidence, SCORES["act_read_by_locale"])
        reading.said = f"Read as {first.read_as}."
    else:
        reading.confidence = min(reading.confidence, SCORES["ambiguous"])
        reading.question = f"Do you mean {first.read_as} or {other.read_as}?"
    return reading


def _reminder_slots(text: str, spans: list, now: datetime, locale: str | None, known: dict,
                    tense: str = "future") -> tuple[dict, list]:
    """Slots for a reminder read from a whole sentence (quick add), and the spans they used."""
    parsed = rec.parse_reminder_text(text, now, locale=locale, known=known, tense=tense)
    used = [s for s in spans if s.rank == 0 and s.kind in _TIME_KINDS]
    if parsed is None:
        return {"text": rec.strip_lead(text.strip()) or text.strip(), "due_at": None}, used
    slots = {"text": parsed["text"], "due_at": parsed["due_at"], "priority": parsed["priority"]}
    return slots, used


def _repeat_slots(slots: dict, spans: list) -> None:
    """The repeat a reminder carries, as the store says it, and a monthly
    offer for a bare day of the month ("pay rent on the 1st", engine probe)."""
    repeat = next((s for s in spans if s.kind == "recurrence" and s.rank == 0), None)
    if repeat is not None:
        slots["repeat"] = repeat.value
        stored = rec.stored_repeat(repeat.value)
        if stored:
            slots["recurring"] = stored
        return
    if any(s.rank == 0 and rec.day_of_month(s) for s in spans):
        slots["offer_recurring"] = "monthly"


def tool_of(text: str, reading: Reading) -> str | None:
    """The tool a sentence reaches with no model (decision 59, step 1): the
    words that name one tool (`act_registry.TOOL_CUES`), else the act's own
    tool, else the utility's, else a question's search or the Guide's."""
    if reading.intent == "empty":
        return None
    low = " ".join(text.lower().split())
    for tool, pattern in act_registry.TOOL_CUES:
        if re.search(pattern, low):
            return tool
    if reading.intent in act_registry.ACT_TOOLS:
        return act_registry.ACT_TOOLS[reading.intent]
    if reading.intent == "utility":
        return act_registry.UTILITY_TOOLS.get(str(reading.slots.get("kind")), "calculate")
    if reading.intent == "about_app":
        return "search_help"
    if reading.intent == "question":
        return "search_notes"
    return None


def _resolving(body):  # noqa: ANN001, ANN202
    """`body` (the one reading), with the tool the reading reaches named
    (`tool_of`). With `context["turns"]` (the chat's last turns, {"text",
    "objects"?}), a spoken follow-up ("and delete it", "same for Tuesday",
    "the other one") is read as the sentence it stands for (`follow`), and
    says so (decision 59, steps 1 and 3)."""

    @functools.wraps(body)
    def resolved_read(text: str, *, now: datetime, context: dict | None = None) -> Reading:
        turns = (context or {}).get("turns")
        resolved = follow(str(text or ""), turns, now) if turns else None
        said = resolved[0] if resolved else text
        reading = body(said, now=now, context=context)
        if resolved is not None:
            reading.slots["follows"] = resolved[1]
            reading.said = reading.said or f"Read as \u201c{said}\u201d."
        reading.tool = tool_of(str(said or ""), reading)
        return reading

    return resolved_read


@_resolving
def read(text: str, *, now: datetime, context: dict | None = None) -> Reading:
    """The one reading of `text` on the person's clock `now`. `context` may
    carry `locale` (the date order, the temperature scale), `surface`
    (a key of `DATED_SURFACES` reads the whole input as one dated item, as
    quick add does),
    `tense` and `birthday`."""
    context = dict(context or {})
    raw = str(text or "").strip()
    if not raw:
        return Reading("empty", confidence=SCORES["empty"])
    locale = context.get("locale") or "en-GB"
    known = _known(context, now)
    surface = context.get("surface")
    #: A timeline entry is something that happened: "on 3 october" is the one before.
    tense = context.get("tense") or ("past" if surface == "timeline" else None)
    dated = surface in DATED_SURFACES
    spans = rec.recognise(raw, now=now, locale=context.get("locale"), tense=tense, known=known, bare_hours=dated)

    if dated:
        return _read_dated(raw, surface, spans, now, locale, known, tense or "future", context)

    from tessellate.ai import commands, intent, utilities

    act = commands.read(raw, now, context.get("locale"))
    if act is not None:
        return _read_act(act, spans, context)

    kind = utilities.kind_of(raw)
    if kind and kind != "until_note":
        return Reading("utility", {"kind": kind}, spans, SCORES["utility"], "utilities")

    routed = intent.classify(raw)
    if routed == intent.SMALLTALK:
        if intent.is_mash(raw):
            return Reading("unknown", {}, spans, SCORES["unknown"], "intent")
        return Reading("smalltalk", {}, spans, SCORES["smalltalk"], "intent")
    if routed == intent.ABOUT_APP:
        return Reading("about_app", {}, spans, SCORES["about_app"], "intent")

    return _read_question(raw, spans, now, locale, context)


def _read_dated(raw: str, surface: str, spans: list, now: datetime, locale: str, known, tense: str, context: dict) -> Reading:
    """A line on a surface that dates what it holds (quick add, the timeline): one reminder-shaped reading."""
    slots, used = _reminder_slots(raw, spans, now, locale, known, tense)
    _repeat_slots(slots, spans)
    if slots["due_at"] is None:
        return Reading(surface, slots, spans, SCORES["missing_slot"], "reminder", question=DATED_SURFACES[surface])
    if surface != "timeline" and not any(s.rank == 0 and s.kind in _CLOCKED for s in spans):
        #: A day with no time is asked, never filled with 9:00 (decision 50).
        day = slots["due_at"]
        return Reading(surface, slots, spans, SCORES["missing_slot"], "reminder",
                       question=f"What time on {rec._WEEKDAY_NAMES[day.weekday()]} {day.day} {rec._MONTH_NAMES[day.month - 1]}?")
    return _weigh(Reading(surface, slots, spans, SCORES["act"], "reminder"), used, context)


def _read_act(act: dict, spans: list, context: dict) -> Reading:
    """A command the app can carry out, with the slots it named."""
    slots = {k: v for k, v in act.items() if k != "intent"}
    if act["intent"] == "reminder":
        _repeat_slots(slots, spans)
        if not act.get("time_given"):
            slots["due_at"] = None
            return Reading("reminder", slots, spans, SCORES["missing_slot"], "commands", question="Remind you when?")
    used = [s for s in spans if s.rank == 0 and s.kind in _TIME_KINDS]
    return _weigh(Reading(act["intent"], slots, spans, SCORES["act"], "commands"), used, context)


def _read_question(raw: str, spans: list, now: datetime, locale: str, context: dict) -> Reading:
    """Anything else is a question about the notes."""
    from tessellate.search import query

    understood = query.understand(raw, now, locale)
    slots = {
        "subject": understood.subject,
        "since": understood.since,
        "until": understood.until,
        "when_phrase": understood.when_phrase,
        "time_only": understood.time_only,
        "filters": {k: v for k, v in understood.filters.items() if v},
        "phrases": understood.phrases,
        "excluded": understood.excluded,
    }
    if not query.search_terms(understood.subject) and not understood.has_range and not understood.has_operators:
        return Reading("question", slots, spans, SCORES["no_content"], "query")
    reading = Reading("question", slots, spans, SCORES["question"], "query")
    if understood.has_range:
        reading.confidence = SCORES["question_window"]
        if understood.since and understood.until and understood.since != understood.until:
            reading.said = f"Read as notes from {rec._day_words(understood.since)} to {rec._day_words(understood.until)}."
        elif understood.since:
            reading.said = f"Read as notes from {rec._day_words(understood.since)}."
    used = [s for s in spans if s.rank == 0 and s.kind in _TIME_KINDS]
    return _weigh(reading, used, context)


# --- the repair ladder (decision 49): one contract for every surface ----------------


@dataclass(frozen=True)
class Repair:
    """What a surface does when a reading is not sure enough to act on.

    `step`: "ask" (one question), "no_match" (the closest thing and what can
    be done), "no_input" (wait: say nothing), "error" (the model stopped:
    keep the composed answer on screen and say so). `line` is the one line
    to show, None for "no_input"; `keep` is the answer that stays."""

    step: str
    line: str | None
    keep: str | None = None


NO_MATCH = "I could not read that as a question or something to do."
MODEL_STOPPED = "The model stopped. The answer above is the one the app worked out itself."


def repair(reading: Reading | None, *, error: str | None = None, composed: str | None = None,
           closest: str | None = None) -> Repair | None:
    """The ladder's step for `reading`, or None when it is sure or likely
    enough to act on. Chat, Ask, quick add, search and the palette all call
    this, so the same miss is handled the same way everywhere."""
    if error:
        return Repair("error", MODEL_STOPPED, composed)
    if reading is None or reading.intent == "empty":
        return Repair("no_input", None)
    band = reading.band
    if band in ("sure", "likely"):
        return None
    if band == "unsure" and reading.question:
        return Repair("ask", reading.question)
    from tessellate.ai import commands

    lead = f"The closest I have is {closest}. " if closest else f"{NO_MATCH} "
    return Repair("no_match", lead + commands.CAPABILITY_LINE)


#: The reading without the follow-up step, for the turns a follow-up leans on.
_read = read.__wrapped__


# --- spoken follow-ups over the last turns (decision 59, step 3; decision 58's context) ----

#: How many turns back a follow-up may lean (decision 58: the last five).
FOLLOW_TURNS = 5

_AGAIN = r"^(?:and |ok |okay )?(?:same again|again|do (?:that|it) again|one more time|repeat that)[.?]*$"
#: `follow` folds whitespace and strips the trailing mark first, so single
#: spaces and an unqualified tail keep these linear (CodeQL).
_SAME_FOR = r"^(?:and |ok |okay |now |then )?(?:(?:the )?same (?:for|on)|what about|how about|and for|and on) (?P<x>.+)$"
_PRONOUN = (r"^(?:and |then |now |ok |okay |also |please )*(?P<verb>delete|bin|pin|unpin|open|summarise|summarize|rename|move|tag)"
            r"\s+(?:that one|this one|the note|it|that)\b(?P<rest>.*)$")
_OTHER = r"\bthe other(?: one| note)?\b"
_TOO = r"^(?:and |also )?(?:the )?(?P<x>.+?)(?: note)? (?:too|as well)$"


def _turn_object(turn: dict, now: datetime) -> str | None:
    """What a turn was about: the object its words named (an act's note or a
    question's subject), else the first object its answer named."""
    got = _read(str(turn.get("text") or ""), now=now)
    about = got.slots.get("about") or got.slots.get("subject")
    if about:
        return str(about)
    objects = turn.get("objects") or []
    return str(objects[0]) if objects else None


def _swap_object(text: str, old: str, new: str) -> str:
    return re.sub(re.escape(old), new, text, count=1, flags=re.I) if re.search(re.escape(old), text, re.I) else text


def _day_phrase(new, old) -> str:  # noqa: ANN001
    """`new` (a date span) said so `recognise` reads it back exactly, keeping
    the clock of `old` when the old span had one ("same for Tuesday" after
    "on Friday at 9" is Tuesday at 9)."""
    if new.kind != "date" or not isinstance(new.value, date):
        return new.text
    day = new.value
    said = f"on {rec._WEEKDAY_NAMES[day.weekday()]} {day.day} {rec._MONTH_NAMES[day.month - 1]}"
    if old.kind in _CLOCKED and isinstance(old.value, datetime):
        said += f" at {old.value:%H:%M}"
    return said


def follow(text: str, turns: list[dict] | None, now: datetime) -> tuple[str, str] | None:
    """A spoken follow-up resolved against the last `FOLLOW_TURNS` turns
    (each {"text", "objects"?}, oldest first): (the sentence it stands for,
    the kind: "again", "other", "pronoun", "date", "subject"), or None for a
    sentence that stands on its own. Dates are `recognise` spans, never read
    here (decision 46)."""
    turns = _leaned_on(turns, now)
    raw = " ".join(str(text or "").split())
    if not turns or not raw:
        return None
    low = raw.lower().rstrip("?.")
    slot = _follow_slot(raw, turns[-1], now)
    if slot:
        return slot, "slot"
    if re.match(_AGAIN, low):
        return str(turns[-1]["text"]), "again"
    if re.search(_OTHER, low):
        return _follow_other(raw, low, turns, now)
    pronoun = re.match(_PRONOUN, low)
    if pronoun:
        return _follow_pronoun(raw, pronoun, turns, now)
    same = re.match(_SAME_FOR, low) or re.match(_TOO, low)
    return _follow_same(raw[same.start("x"):same.end("x")], turns, now) if same else None


def _leaned_on(turns: list[dict] | None, now: datetime) -> list[dict]:
    """The last turns with words, less small talk: "thanks" between is not a
    turn to lean on (INBOX 741's rule)."""
    turns = [t for t in (turns or []) if str(t.get("text") or "").strip()][-FOLLOW_TURNS:]
    return [t for t in turns if _read(str(t["text"]), now=now).intent not in ("smalltalk", "unknown")]


def _follow_slot(raw: str, turn: dict, now: datetime) -> str | None:
    """"Friday at 3" after "remind me to call the dentist", which was asked
    for its time (decision 50): the reminder with the time said, when the
    reply is a time and nothing else."""
    from tessellate.ai import commands

    before = str(turn["text"])
    waiting = commands.read(before, now)
    if not waiting or waiting["intent"] != "reminder" or waiting.get("time_given"):
        return None
    #: Rebuilt from what is to be done, so a time already gone ("tonight at
    #: 8", said at ten) does not ride along with the new one.
    joined = f"remind me to {waiting.get('said') or ''} {raw}"
    filled = commands.read_typed(joined, now)
    if filled and filled.get("time_given") and filled.get("said") == waiting.get("said"):
        return joined
    return None


def _follow_other(raw: str, low: str, turns: list[dict], now: datetime) -> tuple[str, str] | None:
    """"The other one": the object a turn's answer named that the turn did not."""
    for turn in reversed(turns):
        objects = [str(o) for o in turn.get("objects") or []]
        named = _turn_object(turn, now)
        #: The chat sends whole titles ("Passport renewal") where the turn
        #: named a subject ("passport"): a title holding it is the named one.
        others = [o for o in objects if not named or named.lower() not in o.lower()]
        if len(objects) < 2 or not others:
            continue
        standing = re.sub(r"^(?:and |what about |how about )?" + _OTHER + r"[?.]*$", "", low).strip()
        if not standing:
            return (_swap_object(str(turn["text"]), named, others[0]) if named else str(turn["text"])), "other"
        return re.sub(_OTHER, f"the {others[0]} note", raw, count=1, flags=re.I), "other"
    return None


def _follow_pronoun(raw: str, pronoun: re.Match, turns: list[dict], now: datetime) -> tuple[str, str] | None:
    """"Delete it": the act on the newest turn's object."""
    for turn in reversed(turns):
        obj = _turn_object(turn, now)
        if obj:
            return f"{pronoun['verb']} the {obj} note{raw[pronoun.start('rest'):]}", "pronoun"
    return None


def _follow_same(said: str, turns: list[dict], now: datetime) -> tuple[str, str] | None:
    """"Same for Tuesday" (a new day for the newest dated turn) or "the gym
    note too" (a new object for the newest turn that named one)."""
    dated = any(s.rank == 0 and s.kind in _TIME_KINDS for s in rec.recognise(said, now=now))
    for turn in reversed(turns):
        before = str(turn["text"])
        if dated:
            redated = _redate(before, said, now)
            if redated:
                return redated, "date"
            continue
        obj = _turn_object(turn, now)
        if obj and obj.lower() in before.lower():
            return _swap_object(before, obj, re.sub(r"^the | note$", "", said, flags=re.I)), "subject"
    return None


def _redate(before: str, said: str, now: datetime) -> str | None:
    """`before` with its day replaced by the day in `said`, read in the old
    day's tense: "what about Tuesday" after "what did I write on Monday" is
    the Tuesday past."""
    old = [s for s in rec.recognise(before, now=now) if s.rank == 0 and s.kind in _TIME_KINDS]
    if not old:
        return None
    then = old[0].value.date() if isinstance(old[0].value, datetime) else old[0].value
    tense = "past" if isinstance(then, date) and then < now.date() else None
    new = [s for s in rec.recognise(said, now=now, tense=tense) if s.rank == 0 and s.kind in _TIME_KINDS]
    if not new:
        return None
    return before[: old[0].start] + _day_phrase(new[0], old[0]) + before[old[0].end:]


act_registry.reader = read
