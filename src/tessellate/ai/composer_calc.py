"""What needs no model and no note: more arithmetic, dates, word counts and a
small study glossary (INBOX 1351).

`utilities.py` already answers a sum, a unit, the time, a plain "15% of 240",
the mean of a list. This adds the next rung of what a student asks:

- percentages the other way round and the change between two ("what percent
  is 30 of 120", "percentage change from 80 to 100"), a price after a discount
  or a rise ("20% off 80", "add 15% to 50"), a tip and a split;
- the mark still needed ("I have 65 on coursework worth 40%, what do I need on
  the exam to get 50 overall");
- date arithmetic ("what day is 3 weeks from friday", "100 days ago", "days
  between 1 november and 25 december");
- word counts of a named note or of pasted text;
- `define X` for a study term the notes do not hold, from `data/study_terms.json`
  (the person's own notes always come first).

Every answer is worked here by rule and says how the question was read. The
numbers are ours; the only words are the app's (the composer's `computed` kind).
"""

from __future__ import annotations

import functools
import json
import re
from datetime import date, datetime, time
from pathlib import Path

from tessellate.ai import arithmetic, recognise, study, utilities
from tessellate.core import cjk
from tessellate.ai import composer_compose as compose
from tessellate.ai.composer_study import Ctx, Reply, topic_notes

_NUM = r"(-?\d+(?:[.,]\d+)?)"
_LEAD = r"^(?:(?:so|ok|okay|hey|please|pls|can you|could you|quick question|tell me)[, ]+)*"
_PCT_OF_WHAT = re.compile(rf"{_LEAD}(?:what|how much)(?:'s| is)? (?:percent(?:age)?|%) (?:is |of )?{_NUM}(?: out)? (?:of|out of|in|over|from) {_NUM}\W*$|"
                          rf"{_LEAD}(?:what(?:'s| is) )?{_NUM} (?:out of|over|/) {_NUM} (?:as|is what|in) (?:a )?(?:percent(?:age)?|%)\W*$|"
                          rf"{_LEAD}(?:what )?percent(?:age)? (?:is|was) {_NUM} (?:of|out of|over) {_NUM}\W*$|"
                          rf"{_LEAD}{_NUM}\s*/\s*{_NUM} as a (?:percent(?:age)?|%)\W*$", re.I)
_PCT_CHANGE = re.compile(rf"{_LEAD}(?:what(?:'s| is) )?(?:the )?(?:percent(?:age)?|%)(?: (?:change|increase|decrease|difference|rise|drop|growth))? (?:change )?(?:from|between) {_NUM} (?:to|and) {_NUM}\W*$|"
                         rf"{_LEAD}(?:how much)? (?:percent(?:age)? )?(?:did|has|have) .{{0,30}}?(?:go|gone|grow|grown|rise|risen|fall|fallen|drop|dropped|change|changed|increase|increased|decrease|decreased) from {_NUM} to {_NUM}\W*$", re.I)
_DISCOUNT = re.compile(rf"{_LEAD}(?:what(?:'s| is) )?(?:{_NUM}\s*%\s*(?:off|discount(?:ed)?(?: from| on| off)?)\s*(?:of |on |from )?\$?£?€?{_NUM}|{_NUM} with (?:a )?{_NUM}\s*%\s*(?:off|discount)|"
                       rf"\$?£?€?{_NUM}\s*(?:minus|less|-)\s*{_NUM}\s*%|(?:take|knock|reduce|discount)\s*{_NUM}\s*%\s*(?:off|from|of)\s*\$?£?€?{_NUM})\W*$", re.I)
_RISE = re.compile(rf"{_LEAD}(?:what(?:'s| is) )?(?:(?:add|plus|increase|raise)\s*{_NUM}\s*%\s*(?:to|on|onto)\s*\$?£?€?{_NUM}|\$?£?€?{_NUM}\s*(?:plus|\+|with)\s*{_NUM}\s*%|\$?£?€?{_NUM} increased by {_NUM}\s*%|increase \$?£?€?{_NUM} by {_NUM}\s*%)\W*$", re.I)
_TIP = re.compile(rf"{_LEAD}(?:what(?:'s| is) )?(?:a |the )?{_NUM}\s*%\s*tip (?:on|for|of)\s*\$?£?€?{_NUM}\W*$|{_LEAD}tip (?:of )?{_NUM}\s*%\s*(?:on|for)\s*\$?£?€?{_NUM}\W*$", re.I)
_SPLIT = re.compile(rf"{_LEAD}(?:split|divide|share)\s*\$?£?€?{_NUM}\s*(?:between|among|by|across|into|over)\s*(\d+)(?: people| ways)?\W*$|{_LEAD}\$?£?€?{_NUM}\s*(?:split|divided|shared)\s*(?:between|among|by|across)\s*(\d+)(?: people| ways)?\W*$", re.I)
_NEED = re.compile(
    rf"{_LEAD}(?:what|how much|how many|which)\b.*\b(?:need|require|have to (?:get|score|make)|must (?:get|score))\b.*?(?:to (?:get|reach|pass with|score|make|finish with|end with|hit)|for|so that i (?:get|have|end up with))\s*{_NUM}\s*%?\s*(?:overall|in total|total|for the (?:module|unit|course|class)|in the (?:module|unit|course|class)|final|on average)?"
    rf".*?(?:if|when|given|with|and)\s+(?:i(?:'ve| have| got| scored)?|my\b.*?\bis|so far)?\s*(?:got|scored|have|on|of|is)?\s*{_NUM}\s*%?\s*(?:so far|already)?.*?(?:worth|weighted|weighting|counts? for|which is|being|is)\s*{_NUM}\s*%", re.I)

_DAYQ = re.compile(
    rf"{_LEAD}what(?:'s| is| was| will be| would be)? (?:the )?(?P<kind>day|date|weekday)(?: of the week)?"
    rf"(?: is| was| will it be| would it be| will| would| is it going to be)?(?: it| that)?\s*(?:in |on )?(?P<rest>.+?)\W*$", re.I)
_BETWEEN = re.compile(rf"{_LEAD}(?:how many |how much )?(?P<unit>days|weeks|months|nights)?\s*(?:are there |is there |have i got |do i have )?(?:between|from)\s+(?P<a>.+?)\s+(?:and|to|until|till)\s+(?P<b>.+?)\W*$", re.I)
_COUNTDOWN = re.compile(
    rf"{_LEAD}(?:how (?:many|much) (?P<u>days|weeks|months|sleeps)(?: (?:are there|is there|do i have|have i got|are left|is left|left|to go|remain|remaining))?|how long|(?P<u2>days|weeks|months|sleeps)(?: left| to go)?)"
    r"\s+(?:until|till|'til|before|to|to go until|left until|left till)\s+(?P<d>.+?)\W*$", re.I)
_OFFSET_Q = re.compile(rf"{_LEAD}(?:what(?:'s| is| was)|when is|when was) (?P<rest>(?:\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten|twelve|a couple of|a few) (?:days?|weeks?|fortnights?|months?|years?) .+?)\W*$", re.I)
_WORDS = re.compile(rf"{_LEAD}(?:how many (?:words|characters|letters|sentences)(?: are| is| long)?(?: there)?|what(?:'s| is) the (?:word|character) count|word count|char(?:acter)? count|how (?:long|big) is(?= (?:this|that|my|the) (?:note|doc(?:ument)?|text|essay|draft|page)\b| [\x22\u201c'])|count (?:the )?words)\s*(?:in|of|for|is|on)?\s*(?P<t>.*)$", re.I)
_QUOTED = re.compile(r"[\"“](.+)[\"”]|:\s*(.{12,})$", re.S)
_DEFINE = re.compile(
    rf"{_LEAD}(?:define\s+(?P<c>.+)|what does (?P<a>.+?) mean|(?:what(?:'s| is| are) (?:the )?(?:meaning|definition) of|meaning of|definition of)\s+(?P<d>.+)|"
    rf"what(?:'s| is| are) (?:a |an |the )?(?P<b>.+)|what do you mean by (?P<e>.+)|explain (?P<f>.+))$", re.I)


def _n(raw: str) -> float:
    return float(raw.replace(",", ""))


def _said(value: float) -> str:
    return arithmetic.spoken(value) if value == int(value) or abs(value) >= 1e6 else f"{round(value, 2):g}"


def _computed(text: str, read: str) -> Reply:
    return Reply(f"{text}\n\n_Read as {read}._")


def _percent(match: re.Match) -> Reply | None:
    a, b = [float(g.replace(",", "")) for g in match.groups() if g][:2]
    if b == 0:
        return Reply("A share of zero is not a number, so there is no percentage to give.")
    return _computed(f"{_said(a)} is {_said(a / b * 100)}% of {_said(b)}.", f"{_said(a)} divided by {_said(b)}, times 100")


def _change(match: re.Match) -> Reply | None:
    a, b = [float(g.replace(",", "")) for g in match.groups() if g][:2]
    if a == 0:
        return Reply("A change from zero has no percentage: there is nothing to measure it against.")
    pct = (b - a) / abs(a) * 100
    word = "an increase" if pct > 0 else "a decrease" if pct < 0 else "no change"
    return _computed(f"From {_said(a)} to {_said(b)} is {word}" + (f" of {_said(abs(pct))}%." if pct else "."), f"({_said(b)} minus {_said(a)}) divided by {_said(a)}, times 100")


def _priced(match: re.Match, up: bool) -> Reply | None:
    nums = [float(g.replace(",", "")) for g in match.groups() if g]
    if len(nums) < 2:
        return None
    text = match.group(0).lower()
    #: Which of the two is the price: the one with the percent sign after it is the rate.
    first, second = nums[0], nums[1]
    rate, price = (first, second) if re.search(rf"{re.escape(str(int(first)) if first == int(first) else str(first))}\s*%", text) and not re.search(rf"{re.escape(str(int(second)) if second == int(second) else str(second))}\s*%", text) else (second, first)
    result = price * (1 + rate / 100) if up else price * (1 - rate / 100)
    amount = price * rate / 100
    word = "plus" if up else "less"
    return _computed(f"{_said(price)} {word} {_said(rate)}% is {_said(result)}.", f"{_said(rate)}% of {_said(price)} is {_said(amount)}, {'added to' if up else 'taken off'} the {_said(price)}")


def _tip(match: re.Match) -> Reply:
    nums = [float(g.replace(",", "")) for g in match.groups() if g]
    rate, bill = nums[0], nums[1]
    tip = bill * rate / 100
    return _computed(f"A {_said(rate)}% tip on {_said(bill)} is {_said(round(tip, 2))}, so {_said(round(bill + tip, 2))} in all.", f"{_said(rate)}% of {_said(bill)}")


def _split(match: re.Match) -> Reply | None:
    groups = [g for g in match.groups() if g]
    total, people = float(groups[0].replace(",", "")), int(groups[1])
    if people < 1:
        return None
    return _computed(f"{_said(total)} split {people} ways is {_said(round(total / people, 2))} each.", f"{_said(total)} divided by {people}")


def _needed(match: re.Match) -> Reply | None:
    target, have, weight = [float(g.replace(",", "")) for g in match.groups() if g][:3]
    if not 0 < weight < 100:
        return None
    rest = 100 - weight
    need = (target - have * weight / 100) / (rest / 100)
    if need > 100:
        text = f"You would need {_said(round(need, 1))}% on the rest, which is more than the 100% available, so {_said(target)} overall is out of reach on those numbers."
    elif need <= 0:
        text = f"You already have {_said(target)} overall, whatever the rest scores: your {_said(have)}% on the {_said(weight)}% already gets there."
    else:
        text = f"You need {_said(round(need, 1))}% on the remaining {_said(rest)}% to finish on {_said(target)}% overall."
    return _computed(text, f"{_said(have)}% on work worth {_said(weight)}%, aiming for {_said(target)}% overall, so ({_said(target)} minus {_said(round(have * weight / 100, 2))}) divided by {_said(rest / 100)}")


# --- dates ------------------------------------------------------------------------------

def _long(day: date) -> str:
    return f"{day:%A} {day.day} {day:%B %Y}"


def _resolve(phrase: str, today: date) -> date | None:
    phrase = phrase.strip(" ,.?")
    if not phrase or phrase in ("now", "today", "this day"):
        return today
    got = recognise.resolve(phrase, datetime.combine(today, time(10)))
    return got.date() if got else None


def _offset_reply(moved: dict, today: date) -> Reply:
    n, unit, target = moved["n"], moved["unit"], moved["target"]
    what = f"{n} {unit}{'s' if n != 1 else ''}"
    said, anchor = moved["said"], moved["anchor"]
    own = said in ("ago", "from now", "from today", "hence", "later", "earlier", "in", "away") and not anchor
    when = {"in": "from today", "hence": "from today", "away": "from today", "later": "from today"}.get(said, said) if own else f"{said} {anchor}"
    based = f" ({_long(moved['base'])})" if anchor and anchor.lower() not in ("today", "now") else ""
    verb = "was" if target < today else "is"
    return _computed(f"{what.capitalize()} {when}{based} {verb} {_long(target)}.", f"{what} {'before' if moved['sign'] < 0 else 'after'} {_long(moved['base'])}")


def _day_question(text: str, today: date) -> Reply | None:
    found = _DAYQ.match(text)
    if not found:
        return None
    rest = found["rest"].strip()
    moved = recognise.day_offset(rest, today)
    if moved:
        return _offset_reply(moved, today)
    if rest.lower() in ("it", "today", "now", "this"):
        return None
    target = _resolve(rest, today)
    if target is None:
        return None
    return _computed(f"{rest.capitalize()} {'was' if target < today else 'is'} {_long(target)}.", f"{rest} as {_long(target)}")


def _between(text: str, today: date) -> Reply | None:
    found = _BETWEEN.match(text)
    if not found or not re.search(r"\b(?:days|weeks|months|nights|many|much)\b", text, re.I):
        return None
    a, b = _resolve(found.group("a"), today), _resolve(found.group("b"), today)
    if a is None or b is None:
        return None
    low, high = sorted((a, b))
    words = _gap_words(low, high, (found.group("unit") or "days").lower())
    return _computed(f"From {_long(low)} to {_long(high)} is {words}.", f"the days from {_long(low)} to {_long(high)}")


def _gap_words(low: date, high: date, unit: str) -> str:
    """The gap between two days in the unit asked: days with their weeks,
    weeks to a decimal, or whole months and the days left over."""
    days = (high - low).days
    weeks, rest = divmod(days, 7)
    if unit.startswith("week"):
        return f"{days / 7:.1f} weeks ({days} days)"
    if unit == "months":
        months = (high.year - low.year) * 12 + high.month - low.month - (1 if high.day < low.day else 0)
        return f"{months} month{'s' if months != 1 else ''} and {(high - recognise.shift_day(low, months, 'month', 1)).days} days ({days} days)"
    tail = f" ({weeks} week{'s' if weeks != 1 else ''}" + (f" and {rest} day{'s' if rest != 1 else ''}" if rest else "") + ")" if days >= 14 else ""
    return f"{days} day{'s' if days != 1 else ''}{tail}"


def _countdown_words(today: date, target: date, unit: str) -> str:
    low, high = sorted((today, target))
    return _gap_words(low, high, "days" if unit == "sleeps" else unit)


def _countdown(text: str, today: date, mood: compose.Mood) -> Reply | None:
    """"How many days until 12 Dec", "weeks until christmas": the dates are
    read by the recogniser; a subject it does not know (an exam) is left to
    the notes."""
    found = _COUNTDOWN.match(text)
    if not found:
        return None
    unit = (found.group("u") or found.group("u2") or "days").lower()
    target = _resolve(found.group("d"), today)
    if target is None:
        return None
    key = "today" if target == today else "until" if target > today else "until_past"
    words = _countdown_words(today, target, unit)
    line = compose.say(key, mood, when=_long(target), words=words)
    return _computed(line, f"the days from today to {found.group('d').strip()}")


def _since(text: str, today: date, mood: compose.Mood) -> Reply | None:
    asked = recognise.since_question(text)
    if not asked:
        return None
    unit, phrase = asked
    ago = recognise.days_since(phrase, datetime.combine(today, time(10)))
    if ago is None:
        return None
    target = date.fromordinal(today.toordinal() - ago)
    words = _countdown_words(today, target, unit)
    line = compose.say("since", mood, when=_long(target), words=words)
    return _computed(line, f"the days from {phrase} to today")


def _offset_question(text: str, today: date) -> Reply | None:
    """"What is 3 weeks before 12 dec": the recogniser's offset, no "day" word needed."""
    found = _OFFSET_Q.match(text)
    moved = recognise.day_offset(found["rest"].strip(), today) if found else None
    return _offset_reply(moved, today) if moved else None


# --- word counts and definitions ---------------------------------------------------------

def _pasted_count(text: str, mood: compose.Mood) -> Reply | None:
    quoted = _QUOTED.search(text)
    body = ((quoted.group(1) or quoted.group(2)) if quoted else "") or ""
    if not body.strip():
        return None
    words = cjk.word_count(body)
    return _computed(compose.say("count_text", mood, words=f"{words} word{'s' if words != 1 else ''}", chars=f"{len(body)} characters",
                                 read=utilities.reading_time(words) or "a few seconds"), "the text you gave")


def _note_count(ctx: Ctx, topic: str) -> Reply | None:
    if re.match(r"^(?:my notes|all my notes|everything|the notebook|my notebook)$", topic, re.I) or not topic and not ctx.open_ids:
        return None
    notes = topic_notes(topic, ctx)
    if not notes:
        return None
    body = str(notes[0].get("content") or "")
    counted = utilities.counts(body)
    sents = len(study.sentences(body))
    words = counted["words"]
    read = f", {'' if counted['read'].startswith('under') else 'a '}{counted['read']}" if counted["read"] else ""
    detail = f"{counted['chars']} characters and about {sents} sentence{'s' if sents != 1 else ''}{read}"
    return Reply(compose.say("count_note", ctx.mood, link=f"[**{study.title_of(body)}**](#/notes/{notes[0]['id']})",
                             words=f"{words} word{'s' if words != 1 else ''}", detail=detail))


def _word_count(ctx: Ctx, text: str) -> Reply | None:
    found = _WORDS.match(text)
    if not found:
        return None
    return _pasted_count(text, ctx.mood) or _note_count(ctx, (found.group("t") or "").strip(" .?"))


@functools.lru_cache(maxsize=1)
def glossary() -> dict[str, dict]:
    path = Path(__file__).parent / "data" / "study_terms.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    table: dict[str, dict] = {}
    for row in rows:
        table[row["term"].lower()] = row
        for alias in row.get("aliases", []):
            table[alias.lower()] = row
    return table


def _define(ctx: Ctx, text: str) -> Reply | None:
    found = _DEFINE.match(text)
    if not found:
        return None
    term = next((g for g in found.groups() if g), "").strip(" ?.!")
    term = re.sub(r"^(?:a|an|the)\s+", "", term, flags=re.I).strip()
    if not term or len(term.split()) > 4:
        return None
    row = glossary().get(term.lower())
    if row is None:
        return None
    needle = term.lower()
    if any(needle in str(n.get("content") or "").lower() for n in ctx.notes):
        return None
    mood = ctx.mood
    return Reply(compose.head("define", mood, term=f"**{row['term']}**", meaning=row["meaning"]) + "\n\n" + compose.frame("define_src", mood, asked=term))


def answer(ctx: Ctx) -> Reply | None:
    text = " ".join((ctx.question or "").split())
    if not text or len(text) > 240:
        return None
    today = ctx.now.date()
    for pattern, work in ((_PCT_OF_WHAT, _percent), (_PCT_CHANGE, _change), (_TIP, _tip), (_SPLIT, _split), (_NEED, _needed)):
        found = pattern.match(text)
        if found:
            return work(found)
    found = _DISCOUNT.match(text)
    if found:
        return _priced(found, up=False)
    found = _RISE.match(text)
    if found:
        return _priced(found, up=True)
    return (_word_count(ctx, text) or _day_question(text, today) or _between(text, today) or _countdown(text, today, ctx.mood)
            or _since(text, today, ctx.mood) or _offset_question(text, today) or _define(ctx, text))
