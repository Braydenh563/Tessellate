"""The body's own rhythms, as both companions draw them (INBOX 1719 b: "more life and biological design").

One table, `vitals` in `frontend/companion-catalogue.json`, read here and by the app (atlas-vitals.js): how a mood and
tiredness change the blink (how often, how long the lid stays down) and how exertion and a mood change the breath.
A tired or sleepy figure blinks more often and slower; a curious or startled one holds its gaze and blinks less; a
figure that has just walked, hopped or been carried breathes quicker and eases back over `half_s` seconds. A missing
or broken table is `DEFAULTS`, the same numbers, so nothing changes when the file is gone.
"""

from __future__ import annotations

import math
from typing import Any

from . import catalogue

#: blink: per mood `[gap scale, length scale]`, and `tired`, the scale reached at a full rest need (from `tired_from` up).
#: breath: per mood a period scale; `exert` the most the rate rises after exertion; `half_s` its half-life.
DEFAULTS: dict[str, Any] = {
    "blink": {
        "mood": {
            "happy": [1.0, 1.0], "content": [1.0, 1.05], "proud": [1.1, 1.0], "bored": [0.85, 1.25],
            "curious": [1.35, 0.95], "focus": [1.5, 0.95], "startled": [1.45, 0.8], "sleepy": [0.7, 1.7],
        },
        "tired": [0.8, 1.35],
        "tired_from": 0.5,
    },
    "breath": {
        "mood": {"sleepy": 1.2, "bored": 1.08, "content": 1.04, "happy": 0.96, "curious": 0.97, "startled": 0.78},
        "exert": 0.55,
        "half_s": 14.0,
    },
}


def table() -> dict[str, Any]:
    """The catalogue's `vitals`, section by section over `DEFAULTS` (a malformed section is the default)."""
    got = catalogue.load().get("vitals")
    out = {k: dict(v) for k, v in DEFAULTS.items()}
    if isinstance(got, dict):
        for k in out:
            if isinstance(got.get(k), dict):
                out[k].update(got[k])
    return out


def _tired(rest: float, start: float) -> float:
    """0 below `start`, 1 at a full rest need."""
    return 0.0 if rest <= start else min(1.0, (rest - start) / max(1e-6, 1.0 - start))


def blink(mood: str, rest: float) -> tuple[float, float]:
    """`(gap scale, length scale)` for the next blink: the mood's, leaned toward the tired scale by the rest need."""
    b = table()["blink"]
    try:
        gap, length = (float(v) for v in b["mood"].get(mood, (1.0, 1.0)))
        tg, tl = (float(v) for v in b["tired"])
        k = _tired(rest, float(b["tired_from"]))
    except (TypeError, ValueError, KeyError):
        return 1.0, 1.0
    return gap * (1.0 + (tg - 1.0) * k), length * (1.0 + (tl - 1.0) * k)


def exertion(since: float) -> float:
    """How out of breath, 0 to 1, `since` seconds after the last exertion ended (halved each `half_s`)."""
    if since < 0:
        return 1.0
    half = float(table()["breath"].get("half_s", 14.0)) or 14.0
    return math.pow(0.5, since / half)


def breath(mood: str, exert: float) -> float:
    """The breath's period scale: under 1 is quicker (exertion, a startle), over 1 slower (sleepy)."""
    b = table()["breath"]
    try:
        m = float(b["mood"].get(mood, 1.0))
        rise = float(b["exert"]) * max(0.0, min(1.0, exert))
    except (TypeError, ValueError, KeyError, AttributeError):
        return 1.0
    return m / (1.0 + rise)
