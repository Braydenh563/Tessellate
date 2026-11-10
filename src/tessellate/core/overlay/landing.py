"""How a thrown companion comes to rest (INBOX 1683 k). The owner: it "often lands on its head and just stays at a 45
degree angle for a couple seconds before it instant resets". A body that meets the floor settles to a stable angle: on
its feet (0), or lying on its back or belly (a quarter turn); upside down is not stable, it topples. These are pure
policies (angle, rate and a roll of the dice in, a decision out) so the engine only moves the figure and the tests can
read every outcome with a fixed clock."""

from __future__ import annotations

import math
import random

TAU = 2 * math.pi
QUARTER = math.pi / 2
#: Within this much of upright (rad, about 40 degrees) a landing is on the feet; past it the body goes down.
FEET_WITHIN = 0.7
#: Rest on the floor before it gets up (s), the get-up spring and the thump spring (rad/s of a critically damped turn).
LIE_REST = (0.5, 1.0)
OVER_CHANCE = 0.4
GETUP_W = 6.0
#: A body that lands on its feet turns upright in one eased move this long (s), the owner's "it keeps turning even after it
#: lands" (INBOX 1683 v): upright and still within it, whatever it landed with.
FEET_FOR = 0.5
GROUND_RAMP = 0.08
#: Rising to a ceiling it would take hold of: it turns upright for the catch, this strongly, this far ahead (s).
REACH_W = 9.0
REACH_AHEAD = 0.5
THUMP_W = 9.0
#: Ground friction on a skid on its back or belly, and on a stumble onto the feet (per second).
SKID_K = 2.6
STUMBLE_K = 6.0
#: A wall hit is a smack above this speed (px/s at 96 dpi); a smack slides with this chance, passes through with this
#: chance when harder still, otherwise it bounces. The slide is capped at `WALL_SLIDE` px/s and bleeds gravity.
SMACK_SPEED = 750.0
SMACK_SLIDES = 0.7
THROUGH_SPEED = 2000.0
THROUGH_CHANCE = 0.3
WALL_SLIDE = 520.0
WALL_GRIP = 0.45
#: The scrabble while it slides (rad, Hz) and the flail of a long drop (rad, Hz), drawn on top of the true angle.
SCRABBLE = (0.1, 6.0)
FLAIL = (0.2, 3.0)
FLAIL_AFTER = 0.5


def wrap(angle: float) -> float:
    """The angle's distance from the nearest upright, -pi to pi."""
    return angle - round(angle / TAU) * TAU


def decide(angle: float, omega: float, facing: int, hard: bool = False, rng: random.Random | None = None) -> tuple[str, float]:
    """(outcome, rest angle) for a body meeting the floor tilted `angle`: ("feet", 0) near upright, otherwise
    ("belly" or "back", +-pi/2); a hard hit may carry it over the other way. Past 135 degrees (head first) it topples the way it was turning. A belly is
    the front down: a clockwise quarter turn of a figure facing right, an anticlockwise one of a figure facing left."""
    err = wrap(angle)
    if abs(err) <= FEET_WITHIN:
        return "feet", 0.0
    side = (1.0 if err > 0 else -1.0) if abs(err) < 2.4 else (1.0 if omega >= 0 else -1.0)
    if hard and rng is not None and rng.random() < OVER_CHANCE:  # a hard hit rebounds: it goes over the other way
        side = -side
    return ("belly" if (side > 0) == (facing > 0) else "back"), side * QUARTER


def hermite(a0: float, w0: float, elapsed: float, d: float = FEET_FOR) -> tuple[float, float]:
    """(angle, rate) `elapsed` s into the eased move from angle `a0` and rate `w0` to upright and still over `d` s: a cubic
    Hermite, so the rate is continuous at the start and the end and changes by little in between."""
    u = min(1.0, elapsed / d)
    angle = a0 * (2 * u**3 - 3 * u**2 + 1) + d * w0 * (u**3 - 2 * u**2 + u)
    rate = a0 * (6 * u**2 - 6 * u) / d + w0 * (3 * u**2 - 4 * u + 1)
    return angle, rate


def rest_for(rng: random.Random) -> float:
    return rng.uniform(*LIE_REST)


def smack(speed: float, scale: float, rng: random.Random) -> str:
    """What a wall hit at `speed` does: "bounce", "slide" (stick, scrabble and slide down) or "through" (out of the
    edge and in at the far one)."""
    if speed < SMACK_SPEED * scale:
        return "bounce"
    if speed >= THROUGH_SPEED * scale and rng.random() < THROUGH_CHANCE:
        return "through"
    return "slide" if rng.random() < SMACK_SLIDES else "bounce"


def wobble(kind: str | None, t: float, ramp: float = 0.25) -> float:
    """The angle added on top of the true one: a scrabble against a wall or the flail of a long drop, eased in."""
    if kind is None:
        return 0.0
    amp, hz = SCRABBLE if kind == "scrabble" else FLAIL
    return amp * min(1.0, t / ramp) * math.sin(TAU * hz * t)
