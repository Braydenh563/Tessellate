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
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal

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
_PRIME = re.compile(r"^(?:is |is the number )(?P<n>\d{1,9}) (?:a )?prime(?: number)?$")
_SQRT = re.compile(rf"^{_ASK}(?:(?:the )?sqrt|√) ?(?:of )?(?P<n>{_NUM})$")
#: round, floor, ceil as words, each with a number straight after ("round up my notes" has none, so it is left alone).
_ROUND = re.compile(
    rf"^{_ASK}(?:the )?(?P<f>round up|round down|round|floor|ceil|ceiling)(?: of)? (?P<n>{_NUM})(?: to (?P<p>\d{{1,2}}) (?:decimal places?|decimals?|places?|dp))?$"
    rf"|^{_ASK}(?P<n2>{_NUM}) (?P<g>rounded)$"
)
#: log and ln: "log 100", "log2 8", "log base 2 of 8", "natural log of 10". A number must follow.
_LOG = re.compile(
    rf"^{_ASK}(?:the )?(?P<f>ln|natural log(?:arithm)?|log(?:arithm)?|log10|log2)(?: base (?P<b>{_NUM}))?(?: of)? ?\(?(?P<n>{_NUM})\)?$"
)
#: powers as a function or in words; the plain "a to the power of b" is read first by utilities, and arrives here when its cap said no.
_POW = re.compile(
    rf"^{_ASK}(?:pow|power) ?\(?(?P<a>{_NUM})[, ] ?(?P<b>{_NUM})\)?$"
    rf"|^{_ASK}(?P<a2>{_NUM}) (?:to the power of|to the power|raised to the power of|raised to) (?P<b2>{_NUM})$"
)
#: "2(3+4)": a number or bracket straight against a bracket. Only digits, operators and brackets may be in it.
_IMPLICIT = re.compile(r"^[\d.+\-*/^() ]{3,60}$")
_JUXTA = re.compile(r"[\d)] ?\(|\) ?\d")
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


def _places(value: Decimal, places: int, mode: str) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-places), rounding=mode)


def _rounded(found: re.Match) -> Reply:
    raw = found["n"] or found["n2"]
    word = found["f"] or "round"
    mode = {"round up": ROUND_CEILING, "ceil": ROUND_CEILING, "ceiling": ROUND_CEILING, "round down": ROUND_FLOOR, "floor": ROUND_FLOOR}.get(word, ROUND_HALF_UP)
    places = int(found["p"] or 0) if found["p"] is not None else 0
    out = _places(Decimal(raw), places, mode)
    where = f"{places} decimal place{'s' if places != 1 else ''}" if places else "the nearest whole number"
    how = {ROUND_CEILING: "rounded up", ROUND_FLOOR: "rounded down"}.get(mode, "rounded")
    said = f"{raw} {how}{' to ' + where if places else ''} is {_say(float(out))}."
    return computed(said, f"{raw} {how} to {where}, halves going up" if mode == ROUND_HALF_UP else f"{raw} {how} to {where}")


def _log(found: re.Match) -> Reply:
    value = _num(found["n"])
    word = found["f"]
    natural = word == "ln" or word.startswith("natural")
    base = 2.0 if word == "log2" else 10.0 if word in ("log", "logarithm", "log10") else None
    if found["b"] is not None:
        base = _num(found["b"])
    name = "natural log" if natural else f"log (base {_say(base)})"
    if not natural and (base <= 0 or base == 1):
        return computed(f"A log needs a base above zero and not 1, so {_say(base)} cannot be used.", "a logarithm with the base you gave")
    if value <= 0:
        return computed(f"The {name} of {_say(value)} is not defined: a logarithm needs a number above zero.", f"the {name} of {_say(value)}")
    result = math.log(value) if natural else (math.log10(value) if base == 10 else math.log2(value) if base == 2 else math.log(value) / math.log(base))
    return computed(f"The {name} of {_say(value)} is {_say(round(result, 9))}.", f"the {name} of {_say(value)}")


def _power(found: re.Match) -> Reply:
    a, b = found["a"] or found["a2"], found["b"] or found["b2"]
    try:
        value = arithmetic.evaluate(f"({a}) ^ ({b})")
    except arithmetic.NotArithmetic:
        big = abs(_num(b)) > arithmetic.MAX_EXPONENT or abs(_num(a)) >= 10
        why = "is too large to write out here" if big else "cannot be worked out here: it divides by zero or is not a real number"
        return computed(f"{_say(_num(a))} to the power of {_say(_num(b))} {why}.", "the power you gave, with results kept under 1,000,000,000,000,000")
    return computed(f"{_say(_num(a))} to the power of {_say(_num(b))} is {_say(value)}.", f"{_say(_num(a))} multiplied by itself {_say(_num(b))} times")


def _implicit(text: str) -> Reply | None:
    if not _IMPLICIT.match(text) or not _JUXTA.search(text) or text.count("(") != text.count(")"):
        return None
    spaced = re.sub(r"(?<=[\d)]) ?(?=\()|(?<=\)) ?(?=\d)", "*", text)
    try:
        value = arithmetic.evaluate(spaced)
    except arithmetic.NotArithmetic:
        return None
    return computed(f"{text} is {_say(value)}.", f"{spaced.replace('*', ' x ')}, with the multiplication left out")


def _prime(n: int) -> Reply:
    """Trial division by the odd numbers up to the square root: exact, and quick at nine digits."""
    divisor = next((d for d in [2, *range(3, math.isqrt(n) + 1, 2)] if n % d == 0 and d < n), None) if n > 1 else 1
    said = f"{n:,} is a prime number." if divisor is None else (f"{n:,} is not a prime number: it is {divisor:,} times {n // divisor:,}." if n > 1 else f"{n} is not a prime number.")
    return computed(said, f"trial division of {n:,} by every number up to its square root")


def answer(ctx: Ctx) -> Reply | None:
    text = _clean(ctx.question)
    if not text or len(text) > 80:
        return None
    for pattern, reader in ((_ROUND, _rounded), (_LOG, _log), (_POW, _power)):
        found = pattern.match(text)
        if found:
            return reader(found)
    implicit = _implicit(text.removeprefix("what is ").removeprefix("calculate "))
    if implicit:
        return implicit
    found = _PRIME.match(text)
    if found:
        return _prime(int(found["n"]))
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
