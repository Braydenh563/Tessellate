"""The desk's pictures of acts the app drew first (W31 E1, E2; INBOX 1710, 1711), moved out of engine.py whole.

`DeskActsMixin` holds what `Engine` inherits for the five optional frames (`sprites.EXTRA_FRAMES`): the legs-over-the-edge acts
(`dangle`, `kick_legs`, only on a window's top with room for the hem), the hang with one hand let go (`hang_one_hand`, played inside a
hang) and the fallbacks a look without the pictures draws. Behaviour and lengths come from `behaviour.ACTIVITIES` and the catalogue."""

from __future__ import annotations

import math

from . import behaviour as bh
from .sprites import EXTRA_FALLBACK

#: How long a long hang holds on with both hands between the times it lets one go (`bh.ACTIVITIES["hang_one_hand"]`).
HANG_ONE_EVERY = (20.0, 55.0)
#: The tricks played inside a hang: (the picture, its activity, its weight; the app's `onehand`, `sloth` and `feet`).
HANG_TRICKS = (("hang_one", "hang_one_hand", 3), ("hang_sloth", "sloth", 2), ("hang_feet", "hang_by_feet", 1))
#: The pictures placed as the sit is: its seat on the rest line, whatever hangs below it (a dangle's hem, a kick's) is drawn under it.
SIT_REGISTERED = ("dangle", "kick0", "kick1", "meditate")
#: Never begin the one-handed hold in the last seconds of a hang: both hands are on the edge when it ends.
HANG_ONE_CLEAR = 9.0


class DeskActsMixin:
    #: Both hands on, and no letting go until a hang begins (`_hang_one_reset`).
    hang_one_until = 0.0
    hang_one_at = math.inf
    #: The picture the hang is drawn with while `hang_one_until` runs (`HANG_TRICKS`).
    hang_alt = "hang_one"

    def _extra_name(self, name: str, now: float) -> str:
        """The picture to draw for `name`: the hang is the one-handed one while the hand is let go, and a look without the
        picture of an act draws the pose it is a variation of (`sprites.EXTRA_FALLBACK`)."""
        if name == "hang" and now < self.hang_one_until:
            name = self.hang_alt
        return name if name not in EXTRA_FALLBACK or name in self.extra_frames else EXTRA_FALLBACK[name]

    def _hem_room(self) -> bool:
        """The hem of a dangle or a kick is drawn below the seat (a sit's line is the window's top), so the legs-over-the-edge
        acts are only chosen where that hem stays above the monitor's bottom: a window near the bottom is not dangled from."""
        if not self.metrics or self.perch is None:
            return True
        seat = self._box("sit", False)[3]
        hem = max((self._box(f, False)[3] for f in ("dangle", "kick0", "kick1") if f in self.extra_frames), default=seat) - seat
        return self.perch.top + hem <= self.current_monitor().area[3]

    def _rested_on_perch(self) -> bool:
        """On a window top, with room for the legs over its edge, when the act was chosen."""
        return self.perch is not None and self._hem_room()

    def _hang_one_reset(self, now: float) -> None:
        """A hang begins with both hands on: the hand is let go first after a while, and never without the picture or in reduced motion."""
        self.hang_one_until = 0.0
        self.hang_one_at = now + self.var_rng.uniform(*HANG_ONE_EVERY) if any(t[0] in self.extra_frames for t in HANG_TRICKS) and not self.reduced else math.inf

    def _let_one_go(self, now: float) -> None:
        """The app's `onehand`: one hand lets go of the edge for a few seconds and the other holds, then it takes hold again. Only
        while the hang is calm: not on a slip, a pull up, a swing, a release or a turn, and never in the last seconds of the rest."""
        if now < self.hang_one_at:
            return
        if self.pulling is not None or self.swing_to is not None or self.releasing or self.turn_to or self.reduced or now >= self.state_until - HANG_ONE_CLEAR:
            self.hang_one_at = now + 2.0 if now < self.state_until - HANG_ONE_CLEAR else math.inf
            return
        have = [t for t in HANG_TRICKS if t[0] in self.extra_frames]
        self.hang_alt, act, _w = self.var_rng.choices(have, weights=[t[2] for t in have])[0]
        lo, hi = bh.ACTIVITIES[act].seconds
        self.hang_one_until = now + min(self.var_rng.uniform(lo, hi), self.state_until - now - 2.0)  # a long trick still ends before the hang
        self.hang_one_at = self.hang_one_until + self.var_rng.uniform(*HANG_ONE_EVERY)
        self.mind.did(act, now)
