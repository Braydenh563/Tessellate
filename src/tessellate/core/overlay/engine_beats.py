"""A presence spell's beats (L-ui-modernisation-99, INBOX 1832): inside a spell's long act it looks up, or settles with
its eyes shut, for a few seconds every 20 to 40 s, and goes back to what it does.

`BeatsMixin` holds what `Engine` inherits for them; it comes before `FramesMixin` so its `_state_frame` draws the beat
and hands every other picture on. Drawn from `var_rng`, so the choices the seeded `rng` makes stay what they were."""

from __future__ import annotations

import math

from . import behaviour as bh
from .presence import SPELL_BEAT_EVERY, SPELL_BEATS


class BeatsMixin:
    #: The beat under way, (picture, until), and when the next falls.
    spell_beat: tuple[str, float] | None = None
    spell_beat_at = math.inf
    #: The start of the spell act the beats were armed for: a new one arms them on its first tick.
    beats_for = -math.inf

    def _in_spell_act(self) -> bool:
        return self.spell is not None and self.act == self.spell["act"] and not self.reduced

    def _spell_beat_wake(self, now: float) -> float:
        """When a beat next starts or ends; never, outside the spell's own act or once the time has passed (a stale time
        would wake every tick)."""
        if not self._in_spell_act():
            return math.inf
        at = self.spell_beat[1] if self.spell_beat else self.spell_beat_at
        return at if at > now else math.inf

    def _spell_beat_due(self, now: float) -> None:
        """Inside a spell's act: a beat ends, or the next one starts."""
        if not self._in_spell_act():
            self.spell_beat = None
            return
        if self.beats_for != self.act_started:  # a spell has begun: its first beat falls 20 to 40 s on
            self.beats_for, self.spell_beat = self.act_started, None
            self.spell_beat_at = now + self.var_rng.uniform(*SPELL_BEAT_EVERY)
        if self.spell_beat is not None and now >= self.spell_beat[1]:
            self.spell_beat = None
        if self.spell_beat is None and now >= self.spell_beat_at and now < self.state_until - 2.0:
            base = bh.activity_frame(bh.ACTIVITIES[self.act], (now - self.act_started) / max(0.01, self.act_len))
            beats = SPELL_BEATS.get(base, ())
            if beats:
                frame, lo, hi = beats[self.var_rng.randrange(len(beats))]
                self.spell_beat = (frame, now + self.var_rng.uniform(lo, hi))
            self.spell_beat_at = now + self.var_rng.uniform(*SPELL_BEAT_EVERY)

    def _state_frame(self, now: float) -> str:
        if self.state == "act" and self.spell_beat is not None and now < self.spell_beat[1]:
            return self._extra_name(self.spell_beat[0], now)  # a look without the picture draws its pose
        return super()._state_frame(now)
