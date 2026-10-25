"""One door for what the app answers with no model and no search (INBOX 1351):
study help (`composer_study`), deadlines and plans (`composer_plan`), the next
rung of arithmetic, dates and counts (`composer_calc`), and "open it" on the
note the last answer named.

`answer(ctx)` returns a `Reply` or None; None leaves the question to the
older readers. The route builds the `Ctx` (`routes_chat._extra_events`).
"""

from __future__ import annotations

import re

from tessellate.ai import composer_calc, composer_plan, composer_study
from tessellate.ai.composer_study import Ctx, Reply

_OPEN_IT = re.compile(
    r"^(?:ok(?:ay)?[, ]+|please[, ]+|can you |could you )*(?:open|show|go to|take me to|pull up|bring up|jump to|let me see)\s+"
    r"(?:(?:it|that|this|that one|this one|that note|the note|the same one)|the (first|second|third|fourth|last|1st|2nd|3rd|top|latest|newest) (?:one|note|result|match))"
    r"\s*(?:please|for me|now)?\W*$", re.I)
_ORDINAL = {"first": 0, "1st": 0, "top": 0, "latest": 0, "newest": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2, "fourth": 3, "last": -1}
_LINKED = re.compile(r"\[\*{0,2}([^\]\n]+?)\*{0,2}\]\(#/notes/(\d+)\)")


def open_it(ctx: Ctx) -> Reply | None:
    """"Open it" after an answer that named notes: a link to the note, the
    first it named or the one the ordinal picks."""
    found = _OPEN_IT.match(" ".join((ctx.asked or ctx.question or "").split()))
    if not found or not ctx.history:
        return None
    named: list[tuple[str, str]] = []
    for title, ident in _LINKED.findall(ctx.last_answer):
        if ident not in [i for _t, i in named]:
            named.append((title, ident))
    if not named:
        return None
    index = _ORDINAL.get((found.group(1) or "first").lower(), 0)
    if index >= len(named) and index != -1:
        return Reply(f"My last answer named only {len(named)} note{'s' if len(named) != 1 else ''}.")
    title, ident = named[index]
    lead = composer_study.pick(ctx.seed, "openit", ("Here it is:", "Opening it:", "Right here:"))
    return Reply(f"{lead} [**{title}**](#/notes/{ident})")


def answer(ctx: Ctx) -> Reply | None:
    opened = open_it(ctx)
    if opened:
        return opened
    if composer_study.match(_plain(ctx)) is not None:
        return composer_study.answer(ctx)
    return composer_plan.answer(ctx) or composer_calc.answer(ctx) or composer_study.answer(ctx)


def _plain(ctx: Ctx) -> str:
    text = ctx.question
    if ctx.follow_kind == "length" and text.lower().startswith("briefly,"):
        text = text[8:].strip()
    return re.sub(r"\s+in detail\W*$", "", text, flags=re.I) if ctx.follow_kind == "length" else text
