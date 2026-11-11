"""A note's "now" is its own day's now (INBOX 1767 b, d). "Now I am spending the
weekend relaxing", written on 1 November and told on 11 November, is not today's
news: the line says the day it was written ("On 1 November, you mentioned that you
were spending the weekend relaxing"), the time word that no longer holds is
dropped, and the app's own retelling is made natural ("for gym" at the end of
"done legs" is "at the gym", a dropped apostrophe is put back). The person's
own quoted words are never touched."""

from __future__ import annotations

import re
from datetime import date

from tessellate.ai.recognise_questions import AT_THE_TIME_WORD as _AT_THE_TIME
from tessellate.ai.recognise_questions import DROPPED_NOW_WORD as _DROPPED
from tessellate.ai.recognise_questions import STALE_TIME_WORD as _STALE
from tessellate.ai.recognise_questions import THAT_TIME_WORD as _THAT_WORDS
from tessellate.core.lazyre import lazy_compile

_THAT = {"tonight": "that night", "this morning": "that morning", "this afternoon": "that afternoon",
         "this evening": "that evening", "this weekend": "that weekend", "this week": "that week", "this month": "that month"}
_NT = lazy_compile(r"\b(have|has|had|do|does|did|was|were|is|are|would|could|should|ca|wo)nt\b|\b(cant|wont)\b", re.I)
_QUOTED = lazy_compile(r"“[^”]*”")
_FOR_GYM = lazy_compile(r"(\b(?:done|did|do|doing|trained)\b[^“”]*?) for (?:the )?gym(?=\.?$)", re.I)


def _day_said(written: date, today: date) -> str:
    year = f" {written.year}" if written.year != today.year else ""
    return f"{written.day} {written.strftime('%B')}{year}"


def _unstale(body: str) -> str:
    body = _THAT_WORDS.sub(lambda m: _THAT[m.group(0).lower()], body)
    body = _AT_THE_TIME.sub("at the time", body)
    return _DROPPED.sub("", body).strip()


def _apostrophes(text: str) -> str:
    """"you havent been" is "you haven't been" in the app's own retelling."""
    def fix(m: re.Match) -> str:
        word = m.group(0)
        return word[:-2] + "n't" if word.lower() not in ("cant", "wont") else {"cant": "can't", "wont": "won't"}[word.lower()]

    return "".join(part if part.startswith("“") else _NT.sub(fix, part) for part in re.split(r"(“[^”]*”)", text))


def natural(text: str) -> str:
    """The retelling `text`, outside any quote, as a person would say it."""
    return _apostrophes(_FOR_GYM.sub(r"\1 at the gym", text)) if not _QUOTED.fullmatch(text.strip()) else text


def dated(lead: str, body: str, written: date | None, today: date | None, say, shift) -> tuple[str, str]:  # noqa: ANN001
    """(lead, line) for a note's `body` told on `today`: when it holds a time
    word and was written before, its own day leads, the word goes and the
    clause is one tense back (`shift`), whatever its age (a month-old note
    says \"you need\" only when it is not dated)."""
    if written and today and (today - written).days >= 1 and _STALE.search(body):
        body = shift(_unstale(body))
        lead = lead or f"on {_day_said(written, today)}, "
    return lead, natural(say(body))
