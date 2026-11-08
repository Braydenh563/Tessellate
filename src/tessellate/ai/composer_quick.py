"""The small no-model answers that need neither a note nor a search: a pick
from options (`composer_chance`). One door for `composer_extra`, so the
route's reader list stays short.

Each reader takes a `Ctx` and returns a `Reply` or None; none reads a note.
"""

from __future__ import annotations

from tessellate.ai import composer_chance
from tessellate.ai.composer_study import Ctx, Reply


def answer(ctx: Ctx) -> Reply | None:
    return composer_chance.answer(ctx)
