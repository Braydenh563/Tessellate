"""A nap (INBOX 1683 u; L-ui-modernisation-104), moved out of engine.py whole: asked for from the menu, or taken on its own trip.

`NapMixin` holds what `Engine` inherits for it. Every sleep it settles into here is a nap with an end of its own
(`nap_req`, then `Engine._arm_nap` gives `nap_until`): a nap trip's sleep without one held until a touch, and slept 40 to
68% of a seeded hour with the person about."""

from __future__ import annotations

from . import travel as tv


class NapMixin:
    def _nap(self, now: float) -> None:
        if self.perch is not None and not self.reduced and self.gait == "walk":
            self.nap_after_land = True  # it never sleeps on a window: down first, then to sleep
            self._leave_perch(now, hop=False)
            return
        self.perch = None
        self.spell = None
        self.follow_until = self.follow_close_until = 0.0
        self.relocate_at = None
        if self.reduced:
            self._enter("sit", now)
            return
        spot = self._nap_spot()
        if spot is not None and self.gait == "walk":
            self._go(spot, "nap", now, plain=True)  # to a corner first, on foot
            return
        self._settle_to_sleep(now)

    def _nap_spot(self) -> tuple[float, float] | None:
        """Where a nap is taken: out of the middle third, by the nearer edge; None when it is there already."""
        m = self.current_monitor()
        x = tv.out_of_middle(self.x, m.area, self.size[0])
        if abs(x - self.x) < 12 * self._scale():
            return None
        return x, self.ground_y(m)

    def _settle_to_sleep(self, now: float) -> None:
        """A turn (to face the way it came, tail to the room) and a curl, then a nap with an end of its own."""
        if self.metrics:
            self._face(-self.facing, now)
        self.nap_req = True
        self._enter("sleep", now)
