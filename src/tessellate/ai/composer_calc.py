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
from datetime import date, datetime, time, timedelta
from pathlib import Path

from tessellate.ai import arithmetic, recognise, study, utilities
from tessellate.ai.composer_study import Ctx, Reply, pick, topic_notes

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

_UNIT = r"(?P<unit>days?|weeks?|fortnights?|months?|years?)"
_AMOUNT = r"(?P<n>\d{1,4}|a|an|one|two|three|four|five|six|seven|eight|nine|ten|twelve|a couple of|couple of)"
_WORD_N = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twelve": 12,
           "a couple of": 2, "couple of": 2}
_DAYDATE = re.compile(
    rf"{_LEAD}what(?:'s| is| was| will be| would be)? (?:the )?(?P<kind>day|date|weekday)(?: of the week)?(?: is| was| will it be| would it be| will| would)?(?: it| that)?\s*(?:in |on )?"
    rf"(?:{_AMOUNT}\s*{_UNIT}\s*(?P<dir>from now|from today|from|after|before|ago|since|later|earlier|hence|prior to|before|away)\s*(?P<anchor>.*)|(?P<abs>.+))\W*$", re.I)
_DAYS_OF = re.compile(rf"{_LEAD}(?:what|which) (?P<kind>day|date)(?: of the week)?(?: will it be| is it going to be| would it be| is it| is| will be)? ?(?:in )?{_AMOUNT}\s*{_UNIT}(?: from now| from today| away| time)?\W*$", re.I)
_BETWEEN = re.compile(rf"{_LEAD}(?:how many |how much )?(?P<unit>days|weeks|months|nights)?\s*(?:are there |is there |have i got |do i have )?(?:between|from)\s+(?P<a>.+?)\s+(?:and|to|until|till)\s+(?P<b>.+?)\W*$", re.I)
_WORDS = re.compile(rf"{_LEAD}(?:how many (?:words|characters|letters|sentences)(?: are| is| long)?(?: there)?|what(?:'s| is) the (?:word|character) count|word count|char(?:acter)? count|how long is|how big is|count (?:the )?words)\s*(?:in|of|for|is|on)?\s*(?P<t>.*)$", re.I)
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

def _shift(base: date, n: int, unit: str, sign: int) -> date:
    unit = unit.rstrip("s")
    if unit == "day":
        return base + timedelta(days=sign * n)
    if unit == "week":
        return base + timedelta(weeks=sign * n)
    if unit == "fortnight":
        return base + timedelta(weeks=2 * sign * n)
    months = n * (12 if unit == "year" else 1) * sign
    index = base.year * 12 + base.month - 1 + months
    year, month = divmod(index, 12)
    month += 1
    last = [31, 29 if year % 4 == 0 and (year % 100 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    return date(year, month, min(base.day, last))


def _long(day: date) -> str:
    return f"{day:%A} {day.day} {day:%B %Y}"


def _resolve(phrase: str, today: date, future: bool = True) -> date | None:
    phrase = phrase.strip(" ,.?")
    if not phrase or phrase in ("now", "today", "this day"):
        return today
    got = recognise.resolve(phrase, datetime.combine(today, time(10)))
    return got.date() if got else None


def _day_question(text: str, today: date) -> Reply | None:
    found = _DAYS_OF.match(text)
    if found:
        n = _WORD_N.get(found.group("n").lower()) or int(found.group("n"))
        unit = found.group("unit")
        target = _shift(today, n, unit, 1)
        return _computed(f"{n} {unit.rstrip('s')}{'s' if n != 1 else ''} from today is {_long(target)}.", f"{n} {unit} after {_long(today)}")
    found = _DAYDATE.match(text)
    if not found:
        return None
    if found.group("n"):
        n = _WORD_N.get(found.group("n").lower()) or int(found.group("n"))
        unit, direction = found.group("unit"), found.group("dir").lower()
        anchor_text = (found.group("anchor") or "").strip(" ,.?")
        base = _resolve(anchor_text, today) if anchor_text else today
        if base is None:
            return None
        sign = -1 if direction in ("before", "ago", "earlier", "prior to") else 1
        target = _shift(base, n, unit, sign)
        what = f"{n} {unit.rstrip('s')}{'s' if n != 1 else ''}"
        rel = {"ago": "ago", "from now": "from now", "from today": "from today", "hence": "from now", "later": "later", "earlier": "earlier"}.get(direction, direction)
        anchor_words = f" {anchor_text}" if anchor_text and direction not in ("ago", "from now", "from today") else ""
        tail = f" ({_long(base)})" if anchor_text and not recognise.resolve(anchor_text, datetime(2026, 1, 1)) is None and anchor_text.lower() not in ("today", "now") else ""
        verb = "was" if target < today else "is"
        return _computed(f"{what.capitalize()} {rel}{anchor_words}{tail} {verb} {_long(target)}.", f"{what} {'before' if sign < 0 else 'after'} {_long(base)}")
    absolute = (found.group("abs") or "").strip(" ,.?")
    if not absolute or re.search(r"\b(?:it|the time|my|your)\b", absolute, re.I) and absolute.lower() in ("it", "it today", "today?"):
        return None
    target = _resolve(absolute, today)
    if target is None or absolute.lower() in ("today", "it"):
        return None
    verb = "was" if target < today else "is" if target > today else "is"
    return _computed(f"{absolute.strip().capitalize()} {verb} {_long(target)}.", f"{absolute.strip()} as {_long(target)}")


def _between(text: str, today: date) -> Reply | None:
    found = _BETWEEN.match(text)
    if not found or not re.search(r"\b(?:days|weeks|months|nights|many|much)\b", text, re.I):
        return None
    a, b = _resolve(found.group("a"), today), _resolve(found.group("b"), today)
    if a is None or b is None:
        return None
    low, high = sorted((a, b))
    days = (high - low).days
    weeks, rest = divmod(days, 7)
    unit = (found.group("unit") or "days").lower()
    words = f"{days} day{'s' if days != 1 else ''}" + (f" ({weeks} week{'s' if weeks != 1 else ''}" + (f" and {rest} day{'s' if rest != 1 else ''}" if rest else "") + ")" if days >= 14 else "")
    if unit == "weeks":
        words = f"{days / 7:.1f} weeks ({days} days)"
    elif unit == "months":
        months = (high.year - low.year) * 12 + high.month - low.month - (1 if high.day < low.day else 0)
        words = f"{months} month{'s' if months != 1 else ''} and {(high - _shift(low, months, 'months', 1)).days} days ({days} days)"
    return _computed(f"From {_long(low)} to {_long(high)} is {words}.", f"the days from {_long(low)} to {_long(high)}")


# --- word counts and definitions ---------------------------------------------------------

def _word_count(ctx: Ctx, text: str) -> Reply | None:
    found = _WORDS.match(text)
    if not found:
        return None
    topic = (found.group("t") or "").strip(" .?")
    quoted = _QUOTED.search(text)
    if quoted and (quoted.group(1) or quoted.group(2)):
        body = (quoted.group(1) or quoted.group(2)).strip()
        words = len(body.split())
        return _computed(f"That text has {words} word{'s' if words != 1 else ''} and {len(body)} characters, about {utilities.reading_time(words) or 'a few seconds'} to read.", "the text you gave")
    if re.match(r"^(?:my notes|all my notes|everything|the notebook|my notebook)$", topic, re.I) or not topic and not ctx.open_ids:
        return None
    notes = topic_notes(topic, ctx)
    if not notes:
        return None
    note = notes[0]
    body = str(note.get("content") or "")
    counted = utilities.counts(body)
    sents = len(study.sentences(body))
    title = study.title_of(body)
    return Reply(
        f"[**{title}**](#/notes/{note['id']}) has {counted['words']} word{'s' if counted['words'] != 1 else ''}, {counted['chars']} characters and about {sents} sentence{'s' if sents != 1 else ''}"
        + (f", a {counted['read']}." if counted["read"] else ".")
    )


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
    return Reply(
        f"**{row['term']}**: {row['meaning']}\n\nNone of your notes mention “{term}”, so that is from the app's short study glossary, not from you. "
        "Write it in a note in your own words and I will quote that next time."
    )


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
    return _word_count(ctx, text) or _day_question(text, today) or _between(text, today) or _define(ctx, text)
