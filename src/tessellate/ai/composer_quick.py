"""The small no-model answers that need neither a note nor a search: a pick
from options (`composer_chance`), the calendar off the clock
(`composer_clock`, `composer_epoch`), a transform of pasted text
(`composer_text`), the calculator's spoken shorthand
(`composer_sums`). One door for `composer_extra`, so the route's reader list
stays short.

Each reader takes a `Ctx` and returns a `Reply` or None; only the counter's reads a note (its own, "Counter: coffee").
"""

from __future__ import annotations

from tessellate.ai import composer_chance, composer_clock, composer_counter, composer_epoch, composer_sums, composer_text
from tessellate.ai.composer_study import Ctx, Reply


def answer(ctx: Ctx) -> Reply | None:
    return composer_chance.answer(ctx) or composer_clock.answer(ctx) or composer_epoch.answer(ctx) or composer_text.answer(ctx) or composer_sums.answer(ctx) or composer_counter.answer(ctx)
