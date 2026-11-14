"""A presence spell's beats (L-ui-modernisation-99, INBOX 1832): inside a spell's long act it looks up, or settles with
its eyes shut, for a few seconds every 20 to 40 s, and goes back to what it does. Between two spells (INBOX 1834) comes a
short act at the spell's own spot, never a walk home and back, and a kind past its share of the while waits.

`BeatsMixin` holds what `Engine` inherits for them; it comes before `FramesMixin` so its `_state_frame` draws the beat
and hands every other picture on. Drawn from `var_rng`, so the choices the seeded `rng` makes stay what they were."""

from __future__ import annotations

import math

from . import behaviour as bh
from . import presence as pr
from .engine_consts import AWAY
from .presence import SPELL_BEAT_EVERY, SPELL_BEATS


class BeatsMixin:
    #: The beat under way, (picture, until), and when the next falls.
    spell_beat: tuple[str, float] | None = None
    spell_beat_at = math.inf
    #: The start of the spell act the beats were armed for: a new one arms them on its first tick.
    beats_for = -math.inf

    #: A spell was the last thing chosen: the next is a short act where it is, not another spell nor a walk home first.
    spell_gap = False

    def _spell_shut(self, now: float) -> bool:
        """No spell now: none can be had (`_no_spell`), one has just been (its gap comes first), or every kind that suits
        the hour is past its share."""
        return self._no_spell() or self.spell_gap or not pr.open_spells(self.hour, pr.used_by_kind(self.spells, now))

    #: The spells taken away from home lately, (start, seconds) (`_far_ok`).
    far_log: tuple[tuple[float, float], ...] = ()

    def _far_ok(self, now: float) -> bool:
        """A spell may go to the far edge while far spells fill less than `SPELL_FAR_SHARE` of the while: INBOX 1692 keeps
        it by its home most of the time (away at most 0.25 of an hour), and more, shorter spells took more far trips."""
        far = pr.used_by_kind([("far", t, n) for t, n in self.far_log], now).get("far", 0.0)
        return far < pr.SPELL_FAR_SHARE * pr.SPELL_KIND_WINDOW

    def _note_far(self, spot: tuple[float, float] | None, now: float) -> None:
        if spot is not None and self.home_x is not None and abs(spot[0] - self.home_x) > 2 * AWAY * self._scale():
            self.far_log = (*self.far_log[-15:], (now, self.spell["len"]))

    def _gap_or_home(self, now: float) -> bool:
        """Before a new pick: the short act after a spell, else the walk home when it is away and not perched."""
        if self._spell_gap_act(now):
            return True
        if self._away() and self.perch is None:
            self._go_home(now)
            return True
        return False

    def _spell_gap_act(self, now: float) -> bool:
        """After a spell, a short act at the spell's own spot before anything else (no added standing or time away). A
        spell away from home needs none: the walk home is the seen move between two, and an act there first kept the
        walker away 0.26 of a seeded hour (INBOX 1692: at most 0.25)."""
        if not self.spell_gap or self.perch is not None:
            return False
        if self._away():
            self.spell_gap = False
            return False
        self._perform("idle", now)
        return True

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
