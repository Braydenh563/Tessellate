"""Turn a natural-language reminder into structured fields (Magic Add).

Reuses the local utility model, the same one the digest/janitor use, so
nothing leaves the machine. Parsing is best-effort: if the model is unavailable
or returns something unusable, callers get a sensible fallback (the raw text,
due tomorrow at 9am, normal priority) rather than an error.

The `now` handed in is the user's local wall-clock time, not the server's UTC:
"this evening" is meaningless against the wrong clock, and getting it wrong put
every relative reminder hours out.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta

from tessellate.ai import recognise

_PRIORITIES = ("low", "normal", "high")

# --- clock-level phrases, resolved without asking a model ------------------------
#
# "in half an hour" is a lookup, not a language problem: the common "in ..."
# shapes are read by rule first and the model is the fallback, so Magic Add
# works with Ollama off. The reading is `ai/recognise.py`'s (CHAT_PLAN
# decision 46: one reader); `relative_delta` is kept here by name for callers.
# Wall-clock phrases ("tomorrow morning") are `when.parse_reminder_text`'s,
# which every caller tries next.

relative_delta = recognise.relative_delta


def _tidy(text: str, phrase: str) -> str:
    """The reminder text with the time phrase, and the "remind me (to)" it
    stranded, taken out: "remind me in 20 minutes to check the oven" fires as
    "Check the oven"."""
    without = recognise.strip_lead(" ".join(text.replace(phrase, " ").split()).strip(" ,.;:-"))
    if not without:
        return text.strip() or "Reminder"
    return without[0].upper() + without[1:]


def _with_clock(text: str, phrase: str, due: datetime, now: datetime) -> tuple[datetime, str]:
    """"In 2 days at 3pm": the offset lands on a day and the time said beside
    it is the time. Only a day-sized offset takes one ("in 20 minutes at 3pm"
    is not a sentence)."""
    if due - now < timedelta(days=1):
        return due, phrase
    for span in recognise.recognise(text, now=now, tense="future", bare_hours=True):
        if span.rank == 0 and span.kind == "datetime" and phrase in span.text and len(span.text) > len(phrase):
            return span.value, span.text
    return due, phrase


def parse_relative(text: str, now: datetime) -> dict | None:
    """A reminder from an "in ..." phrase ("in 20 minutes", "in 1.5 hours",
    "in 6 months"), with no model involved."""
    found = relative_delta(text)
    if found is not None:
        due, phrase = now + found[0], found[1]
    else:
        months = recognise.relative_months(text, now)
        if months is None:
            return None
        due, phrase = months
    due, phrase = _with_clock(text, phrase, due, now)
    return {
        "text": _tidy(text, phrase)[:500],
        "due_at": due,
        "priority": "normal",
        "source": "rule",
    }

_SYSTEM = (
    "You convert a short natural-language reminder into JSON. "
    "The current date and time is {now}. "
    'Reply with ONLY a JSON object of the form '
    '{{"text": string, "due_at": ISO-8601 date-time, "priority": one of '
    '"low"/"normal"/"high"}}. '
    "That time is the user's own local clock, answer on the same clock, and "
    "resolve relative times (tomorrow, this evening, next week, in 2 hours) "
    "against it. If a time of day is given but no date, choose the next time "
    "that is still in the future. If no time at all is given, use 9am the "
    "following morning. If no priority is given, use normal. Keep the reminder "
    "text short and imperative."
)


def read_by_rule(text: str, now: datetime) -> dict | None:
    """Magic Add's reading with no model: the sentence as heard (misspellings
    and hedges put right), by the "in ..." reader, then the wall-clock reader,
    and the words made a task. None when no rule finds a time. The route and
    the table of hard phrasings (`tests/test_reminder_magic_hard_2210.py`) both
    read through this."""
    from tessellate.ai import when

    heard_text = heard(text)
    parsed = parse_relative(heard_text, now)
    if parsed is None:
        parsed = when.parse_reminder_text(heard_text, now)
    if parsed is None:
        return None
    parsed["text"] = worded(parsed["text"])
    return parsed


def _fallback(text: str, now: datetime) -> dict:
    due = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    return {"text": text.strip() or "Reminder", "due_at": due, "priority": "normal"}


def _extract_json(content: str) -> dict | None:
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        parsed = json.loads(content[start : end + 1])
    except (ValueError, TypeError, RecursionError):
        return None
    return parsed if isinstance(parsed, dict) else None


def parse_reminder(text: str, ollama, model_manager, now: datetime) -> dict:
    """Return {text, due_at: datetime, priority} parsed from natural language.

    An "in …" phrase is resolved here, before the model is asked. It is
    arithmetic, the answer does not vary with which model is installed, and it
    is the shape people actually type into Magic Add.
    """
    ruled = parse_relative(text, now)
    if ruled is not None:
        return ruled

    messages = [
        {"role": "system", "content": _SYSTEM.format(now=now.isoformat())},
        {"role": "user", "content": text},
    ]
    try:
        reply = ollama.chat(model_manager.utility_model(), messages)
    except Exception:  # noqa: BLE001  # any model failure degrades gracefully
        return _fallback(text, now)

    parsed = _extract_json(reply.get("content", "") if isinstance(reply, dict) else "")
    if not parsed:
        return _fallback(text, now)

    result = _fallback(text, now)
    if isinstance(parsed.get("text"), str) and parsed["text"].strip():
        result["text"] = parsed["text"].strip()[:500]
    priority = str(parsed.get("priority", "")).lower()
    if priority in _PRIORITIES:
        result["priority"] = priority
    due_raw = parsed.get("due_at")
    if isinstance(due_raw, str):
        try:
            result["due_at"] = datetime.fromisoformat(due_raw.replace("Z", "+00:00"))
        except ValueError:
            pass  # keep the fallback due time
    return result


# --- the wording, through the composer (O8; INBOX 904 B03) -------------------------
#
# The owner, 2026-10-17: "Use composer to refine magic add on reminders like
# with bad sentence grammar and spelling mistakes and intent etc". Measured
# the same day on /reminders/parse with no model: "remnd me to cal mum tmrw at
# 5pm" was saved as "Remnd me to cal mum tmrw" due today, the day unread;
# "dont forget to water the plants every sunday" as "Dont forget to water
# the plants"; "pay the rent friday plz" as "Pay the rent plz". The rule (what
# a reminder's words are: the thing to do, said as a task) lives here; the
# engine (the speller, the proofreader) is the composer's.

#: How a sentence asks for a reminder, not what it is about.
_ASKING = re.compile(
    r"^(?:(?:can you |could you |please )?remind me (?:to |that |about )?|(?:do not|don'?t|dont) forget (?:to |that |about )?"
    r"|remember (?:to |that )?|note to self:? ?|todo:? ?|to do:? ?)?"
    r"(?:i (?:need|have|must|should|want|ought) to |i'?ve got to |i gotta |need to |have to |must )?",
    re.I,
)
_PLEASE_WORDS = ("thank you", "thanks", "please", "pls", "plz", "ty")


def _drop_please(said: str) -> str:
    """A closing "please" / "thanks" off the end, with the comma or space
    before it. A suffix check, not a regex over the whole line, so a long
    run of spaces cannot make it slow (CodeQL)."""
    tail = said.rstrip()
    tail = tail[:-1] if tail.endswith(".") else tail
    for word in _PLEASE_WORDS:
        if tail.lower().endswith(word):
            head = tail[: -len(word)]
            if head and (head[-1] == "," or head[-1].isspace()):
                return head.rstrip(", \t\n\r\f\v")
    return said
#: Real-word slips the speller cannot see: "too buy milk", "cal mum".
_TOO_VERB = re.compile(
    r"\btoo (buy|call|get|pay|go|do|see|make|take|send|book|finish|start|check|ask|pick|clean|cook|write|read|water|feed|"
    r"walk|email|text|ring|visit|fix|order|return|renew|cancel|prepare|bring|collect|post|print|sign|submit)\b",
    re.I,
)
_CAL = re.compile(r"\b([Cc])al (mum|mom|dad|nan|nana|gran|grandma|grandad|him|her|them|back|the|[A-Z]\w*)\b")


#: Hedges around a time ("probably around 7pm", "say 7:30", "at about 8"): the
#: time is the same without them, and they strand in the title if left. Only
#: "around/about/say" that sit right before a clock are dropped, so "remind me
#: about 3 things" keeps its "about".
_HEDGE = re.compile(r"\b(?:probably|maybe|perhaps|possibly|approximately|roughly)\b,?[ \t]*|\b(\w+)ish\b(?=\s*\d)", re.I)
_APPROX = re.compile(
    r"(?<=\bat )(?:around|about|approximately|roughly|say)\s+|(?<=\bby )(?:around|about|approximately|roughly|say)\s+|"
    r"(?<=\bin )(?:about|around|approximately|roughly)\s+(?=\d|an? |half|one|two|three|four|five|six|seven|eight|nine|ten)|"
    r"(?<=[,;] )(?:around|about|approximately|roughly|say)\s+(?=\d|noon\b|midnight\b|half\b|quarter\b)|"
    r"(?<=\s)(?:around|about|approximately|roughly|say)\s+(?=\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)|\d{1,2}:\d{2}|noon\b|midnight\b|half past\b|quarter (?:past|to)\b)",
    re.I,
)


def heard(text: str) -> str:
    """The sentence as the reminder readers should read it: misspellings
    and shorthand put right ("tmrw" is tomorrow, so the day is read), and the
    hedges around a time taken off."""
    from tessellate.ai import question_noise

    tidy = question_noise.tidy(text or "") or (text or "")
    return unhedged(question_noise.repair(tidy) or tidy)


def unhedged(text: str) -> str:
    """`text` without the hedges around a time ("probably around 7pm" is 7pm)."""
    said = _APPROX.sub("", _HEDGE.sub(lambda m: m.group(1) or "", text or ""))
    return " ".join(said.split()).replace(" ,", ",")


#: A place or a moment the sentence waits on ("when I get home", "once I'm in",
#: "before bed"): not a clock, so it is not kept in the title. The reminder
#: fires at the time said; the owner's example was "Do my tax return".
_CONDITION = re.compile(
    r"[,;]?(?<!\s)\s*\b(?:when|once|as soon as|after)\s+(?:i|we)(?:'m|\u2019m|\s+am|\s+get|\s+got|\s+come|\s+came|\s+arrive|\s+arrived|\s+reach|\s+reached|\s+wake up)"
    r"(?:\s+(?:back\s+)?(?:home|in|there|here|up|to work|to the office|at work|at home|in work|in the office|from work)|\s+back)?\b"
    r"|[,;]?(?<!\s)\s*\b(?:before bed|after work|after dinner|after lunch|after breakfast|when i wake up)\b",
    re.I,
)
_STRAY = re.compile(r"(?<![\s,;])(?:[\s,;]+(?:probably|maybe|perhaps|possibly|around|about|roughly|approximately|say|later|then))+\s*$", re.I)
_LEAD_TO = re.compile(r"^\s*(?:to|that)\s+", re.I)
_FORGET = re.compile(r"^(?:please\s+)?(?:don'?t|do not|dont) let me forget\s+(?:to |that |about )?|^(?:please\s+)?make sure (?:that )?i\s+", re.I)


def without_conditions(text: str) -> str:
    """A reminder's words without the place or moment it waits on ("when I
    get home") and the hedges a cut time stranded."""
    said = text
    if _CONDITION.search(said):
        said = _LEAD_TO.sub("", " ".join(_CONDITION.sub(" ", said).split()))
        said = _ASKING.sub("", said)
    return _STRAY.sub("", said).replace(" ,", ",").strip(" ,;:")


def worded(text: str) -> str:
    """A reminder's words as a task: the asking taken off ("remind me to",
    "don't forget to", "I need to"), the please, real-word slips and
    misspellings put right, the first letter raised."""
    from tessellate.ai import proofread

    said = " ".join((text or "").split())
    said = _TOO_VERB.sub(lambda m: f"to {m.group(1)}", said)
    said = _FORGET.sub("", said)
    said = _ASKING.sub("", said)
    said = without_conditions(said)
    said = _drop_please(said)
    said = _CAL.sub(lambda m: f"{m.group(1)}all {m.group(2)}", said)
    said = proofread.proofread(said)[0].strip(" ,;:")
    return said[:1].upper() + said[1:] if said else (text or "")
