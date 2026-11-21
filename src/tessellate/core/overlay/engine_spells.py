"""Spells on a window's top (D5, L152), moved out of engine.py (which is at its line cap) as a mixin.

A walker standing on another app's window may do a presence spell there (`presence.PERCH_SPELLS`: tea, a book, a journal,
fishing, the stars, knitting) at an edge spot, a few px in from the end of the top, and keeps the perch for as long as the spell
runs. A floater rests on a window for a dangle and never stays on it, so it does its spells on the floor as before. Also the
counts of how each far move was made (`warp_counts`, the log's last line)."""

from __future__ import annotations

from collections import Counter

from . import presence as pr
from .engine_consts import SPELL_MOVE

#: The perch is kept this long after a spell ends (s), so the figure does not hop off the moment its prop is put away.
SPELL_TAIL = 20.0


class SpellsMixin:
    perch_spells = 0

    def _perch_spell_ok(self) -> bool:
        """A walker on a window top that may stay: not a floater, not still (reduced motion shows no props)."""
        return self.perch is not None and self.gait == "walk" and not self.reduced

    def _spell_blocked(self, up: bool) -> bool:
        """A spell cannot start: up on a window it must be a walker's perch spell, and never without presence."""
        return (up and not self._perch_spell_ok()) or self._no_spell()

    def _perch_spell(self, now: float) -> bool:
        """`_begin_spell` on a window top: pick a spell that can be done up there, walk to the edge spot of the top and start it.
        False (the floor's spell instead) when it is not on a top or no spell suits the hour."""
        if not self._perch_spell_ok():
            return False
        name = pr.pick_perch_spell(self.rng, self.hour, self.mind.mood(now, self.hour), [s[0] for s in self.spells[-2:]])
        if name is None:
            return False
        p, k = self.perch, self._scale()
        area = self.current_monitor().area
        x = pr.perch_edge_x(max(p.left, area[0]), min(p.right, area[2]), self.size[0], k, self.x)
        length = pr.length_of(self.rng, name)
        self.spell = {"name": name, "act": pr.SPELLS[name].act, "start": now, "len": length}
        self.perch_until = max(self.perch_until, now + length + SPELL_TAIL)
        self.perch_spells += 1
        if abs(x - self.x) > SPELL_MOVE * k * 0.1:
            self._go((x, self.y), "spell", now, plain=True)
        else:
            self._start_spell(now)
        return True

    def warp_counts(self) -> dict[str, int]:
        """How many legs went by each way so far (walk, run, portal, puff, edge...), for the log and the sweeps."""
        return dict(Counter(self.modes))
