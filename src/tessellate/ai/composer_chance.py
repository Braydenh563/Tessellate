"""A pick from options the person typed (CHAT_PLAN T10): "pick one of pizza,
sushi, tacos", "choose between tea and coffee".

`utilities.py` rolls dice, flips a coin and picks a number in a range; this is
the same chance, over words. The pick is seeded by the chat's seed and the
question, so asking again in the same chat gives the same pick and a new chat
gives a new one. It reads only the question: no note is read or quoted, and a
question about "my notes" is left to the ordinary answer. The answer says it
was picked at random (a computed value, not a judgement).

Patterns read text with its blanks collapsed to single spaces, and every group
starts at a non-blank, so the match is linear.
"""

from __future__ import annotations

import re

from tessellate.ai import utilities
from tessellate.ai.composer_study import Ctx, Reply

#: Most options and longest option read; a longer list is a paragraph.
MAX_OPTIONS = 20
MAX_OPTION = 60

_PICK = re.compile(
    r"^(?:please |can you |could you |help me )*(?:pick|choose|select|decide)(?: one| something)?(?: of| from| between| among)? (?P<list>\S.*)$",
    re.I,
)
_SPLIT = re.compile(r", or |, and |, | or | and |/")
_NOT_OPTIONS = re.compile(r"\b(?:notes?|number|numbers|entries|entry|reminders?|tasks?|todo|todos)\b", re.I)


def options_in(text: str) -> list[str]:
    """The distinct options in "a, b or c", in the order given."""
    seen: dict[str, str] = {}
    for raw in _SPLIT.split(text.strip(" .?!")):
        word = raw.strip(" .?!\"'")
        if word:
            seen.setdefault(word.casefold(), word)
    return list(seen.values())


def _spoken(options: list[str]) -> str:
    return options[0] if len(options) == 1 else ", ".join(options[:-1]) + " and " + options[-1]


def answer(ctx: Ctx) -> Reply | None:
    text = " ".join((ctx.question or "").split())
    if not text or len(text) > 400:
        return None
    found = _PICK.match(text)
    if not found or _NOT_OPTIONS.search(found["list"]):
        return None
    options = options_in(found["list"])
    if not 2 <= len(options) <= MAX_OPTIONS or any(len(o) > MAX_OPTION for o in options):
        return None
    chosen = options[utilities._salted(ctx.seed, text, 0, len(options) - 1)]
    return Reply(f"I pick {chosen}.\n\n_Read as one pick at random from {_spoken(options)}._")
