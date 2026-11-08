"""The calculator's spoken shorthand with no model and no note (CHAT_PLAN T1):
"5 factorial", "half of 90", "double 45", "sqrt 144".

`utilities.py` and `composer_calc.py` read a sum, a percentage and "the square
root of N"; this adds the words people use when they do not write a sum. Each
answer states the number and says how it was read ("_Read as ..._"). Text is
read lower case with blanks collapsed to single spaces and no group starts at
a blank, so every pattern is linear.
"""

from __future__ import annotations

import math
import re

from tessellate.ai import arithmetic
from tessellate.ai.composer_clock import computed
from tessellate.ai.composer_study import Ctx, Reply

#: The largest factorial said in full (20! is the last that is exact in a float).
MAX_FACTORIAL = 20
_NUM = r"-?\d{1,12}(?:\.\d{1,9})?"
_ASK = r"(?:what is |calculate |work out |tell me )?"
_FACTORIAL = re.compile(rf"^{_ASK}(?:(?:the )?factorial of (?P<a>\d{{1,4}})|(?P<b>\d{{1,4}}) factorial|(?P<c>\d{{1,4}})!)$")
_PART = re.compile(rf"^{_ASK}(?P<w>half|a half|quarter|a quarter|a third|third) of (?P<n>{_NUM})$")
_MULTIPLE = re.compile(rf"^{_ASK}(?P<w>double|twice|triple|treble) (?P<n>{_NUM})$")
_SQRT = re.compile(rf"^{_ASK}(?:(?:the )?sqrt|√) ?(?:of )?(?P<n>{_NUM})$")
_DIVISORS = {"half": 2, "a half": 2, "quarter": 4, "a quarter": 4, "third": 3, "a third": 3}
_FACTORS = {"double": 2, "twice": 2, "triple": 3, "treble": 3}


def _clean(question: str) -> str:
    """Lower case and single-spaced; a closing "?" or "." goes but a "!" stays
    ("5!" is a factorial); "what's" is "what is"."""
    text = " ".join((question or "").lower().split()).rstrip(" ?.")
    return re.sub(r"^(?:what's|whats) ", "what is ", text)


def _num(raw: str) -> float:
    return float(raw)


def _say(value: float) -> str:
    return arithmetic.spoken(value)


def _factorial(n: int) -> Reply | None:
    if n > MAX_FACTORIAL:
        return None
    steps = " x ".join(str(i) for i in range(n, 0, -1)) if 1 < n <= 10 else f"the product of the whole numbers from 1 to {n}"
    return computed(f"{n} factorial is {_say(math.factorial(n))}.", steps if n > 1 else "the product of no numbers, which is 1")


def _part(word: str, raw: str) -> Reply:
    by = _DIVISORS[word]
    value = _num(raw)
    name = word if word.endswith("half") else f"a {word.removeprefix('a ')}"
    return computed(f"{name.removeprefix('a ').capitalize() if word.endswith('half') else name.capitalize()} of {_say(value)} is {_say(round(value / by, 2))}.", f"{_say(value)} divided by {by}")


def _multiple(word: str, raw: str) -> Reply:
    by = _FACTORS[word]
    value = _num(raw)
    name = "double" if by == 2 else "triple"
    return computed(f"{name.capitalize()} {_say(value)} is {_say(value * by)}.", f"{_say(value)} times {by}")


def _sqrt(raw: str) -> Reply | None:
    value = _num(raw)
    if value < 0:
        return None
    return computed(f"The square root of {_say(value)} is {_say(math.sqrt(value))}.", f"the square root of {_say(value)}")


def answer(ctx: Ctx) -> Reply | None:
    text = _clean(ctx.question)
    if not text or len(text) > 80:
        return None
    found = _FACTORIAL.match(text)
    if found:
        return _factorial(int(found["a"] or found["b"] or found["c"]))
    found = _PART.match(text)
    if found:
        return _part(found["w"], found["n"])
    found = _MULTIPLE.match(text)
    if found:
        return _multiple(found["w"], found["n"])
    found = _SQRT.match(text)
    return _sqrt(found["n"]) if found else None
