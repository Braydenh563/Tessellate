"""The desk figure's micro-saccades (INBOX 1719 b, E3): while it holds its eyes on something, the eyes take a small step now and
then, so the held gaze is never a still picture. The in-app side is `atlasBlink.saccade` (atlas-motion.js).

Attention is a look: the `look` picture held between two blinks, or an act drawn on the `look` frame (look around, ponder,
glance at the pointer, scan the horizon, peer at the cursor, peek down). A step comes every `STEP_EVERY` seconds from its own
seeded stream, to one of `faces.GAZE`'s places (never the one it is on), and the eyes stay there until the next. The step rides the face
layer as `kind~n` (`faces.draw`), so a look with an expression keeps its expression. No wake of its own: a held look is redrawn at the
streams' tick (`FLOW_TICK_MS`) anyway, and a step is a picture the tick finds.
"""

from __future__ import annotations

import random

from . import behaviour as bh
from . import faces

#: Seconds between two steps of the eyes in a held gaze (a fixation is a few tenths of a second to a couple of seconds).
STEP_EVERY = (0.6, 1.8)

#: The acts that hold a gaze: those drawn on the `look` frame at any point.
ATTEND_ACTS = frozenset(
    name for name, a in bh.ACTIVITIES.items() if a.frame == "look" or (not isinstance(a.frame, str) and any(f == "look" for _at, f in a.frame))
)


class Saccade:
    """The place the eyes are at in a held gaze: `None` until the first step, then an index into `faces.GAZE`."""

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        self.at: int | None = None
        self.next_at = -1.0

    def tick(self, now: float, attending: bool) -> int | None:
        """Advance to `now`; the eyes' place (an index of `faces.GAZE`) while `attending`, else None (the gaze is let go)."""
        if not attending:
            self.at, self.next_at = None, -1.0
            return None
        if self.next_at < 0.0:  # a gaze has just begun: the first step is not at once
            self.next_at = now + self.rng.uniform(*STEP_EVERY)
        elif now >= self.next_at:
            places = [i for i in range(len(faces.GAZE)) if i != self.at]
            self.at = self.rng.choice(places)
            self.next_at = now + self.rng.uniform(*STEP_EVERY)
        return self.at


def worn(face: tuple[str, int] | None, step: int | None) -> tuple[str, int] | None:
    """`face` with the eyes at `step` of `faces.GAZE`; the eyes alone (a look with no expression) where there is none."""
    if step is None:
        return face
    if face is None:
        return (f"gaze~{step}", len(faces.LEVELS) - 1)
    return (f"{face[0]}~{step}", face[1])
