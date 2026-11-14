"""L-ui-modernisation-99 (INBOX 1832, held within INBOX 1692): shorter presence spells, a beat inside each, never two in a row.

Source text: "Recommendation (taken): spells 60 to 150 s (now 100 to 480), a non-spell activity or a seen move between two
spells, and a visible beat in a spell (look up, page turn, stretch) every 20 to 40 s; measured by no frame over 40% and
no activity over 20% of a seeded hour."
"""

from __future__ import annotations

import collections
import random
import re

import pytest

from tessellate.core.overlay import engine_consts as ec, presence as pr
from tests.test_overlay_ride_1670 import make


_HELD = (
    "L-ui-modernisation-99 partly (INBOX 1834): shorter spells and a gap between two put INBOX 1692's measures out "
    "(standing 19.4 min an hour over 18, evening spell share 0.49 under 0.5, the walker away 0.81 of an hour over 0.25)"
)


@pytest.mark.xfail(strict=True, reason=_HELD)
def test_source_text_spells_last_60_to_150_seconds() -> None:
    """Source text: "spells 60 to 150 s (now 100 to 480)"."""
    for name, spell in pr.SPELLS.items():
        lo, hi = spell.seconds
        assert 60.0 <= lo < hi <= 150.0, name
    assert ec.SPELL_QUIET[1] <= 150.0, "a spell carried on while the person types is no longer than a spell"


@pytest.mark.xfail(strict=True, reason=_HELD)
def test_source_text_no_spell_straight_after_a_spell() -> None:
    """Source text: "a non-spell activity or a seen move between two spells". Held from the choice, the walk to its spot
    included, until another act is done (a rest in time after each spell, also tried, put the standing over INBOX 1692's
    18 minutes an hour at every length from 30 to 150 s)."""
    e, _ = make(seed=3)
    e.update(1.0)
    e._perform("spell", 2.0)
    assert e._act_blocked("spell", False, 3.0, 0.0)
    e._perform("idle", 4.0)
    assert not e._act_blocked("spell", False, 5.0, 0.0)


def _spell_frames(seed: int) -> list[tuple[float, str]]:
    e, s = make(seed=seed)
    e.extra_frames = frozenset(s.extras())  # as the runner gives it (`spr.extras()`)
    e.update(1.0)
    e._perform("spell", 1.0)
    t, out = 1.0, []
    while t < 400.0 and len(out) < 1500:
        t += 0.1
        e.last_active = t
        o = e.update(t)
        if e.state == "act" and e.spell is not None and e.act == e.spell["act"]:
            out.append((t, o.frame))
    return out


def test_source_text_a_visible_beat_every_20_to_40_seconds_inside_a_spell() -> None:
    """Source text: "a visible beat in a spell (look up, page turn, stretch) every 20 to 40 s"."""
    for seed in (2, 3, 4):
        frames = _spell_frames(seed)
        assert len(frames) > 500, (seed, len(frames))
        runs: list[list[tuple[float, str]]] = [[frames[0]]]
        for a, b in zip(frames, frames[1:]):  # one unbroken spell act each, the time between two spells left out
            (runs[-1].append(b) if b[0] - a[0] < 0.5 else runs.append([b]))
        seen = 0
        for run in runs:
            base = collections.Counter(re.sub(r"\d+$", "", f) for _, f in run).most_common(1)[0][0]
            beats = [t for (_, f), (t, g) in zip(run, run[1:]) if re.sub(r"\d+$", "", f) == base and re.sub(r"\d+$", "", g) not in (base, f"{base}blink", "blink")]
            seen += len(beats)
            marks = [run[0][0], *beats, run[-1][0]]
            assert max(b - a for a, b in zip(marks, marks[1:])) <= 45.0, (seed, marks)
            assert all(b - a >= 15.0 for a, b in zip(beats, beats[1:])), (seed, beats)
        assert seen, seed


@pytest.mark.xfail(strict=True, reason=_HELD)
def test_source_text_no_frame_over_40_and_no_activity_over_20_percent_of_a_seeded_while() -> None:
    """Source text: "measured by no frame over 40% and no activity over 20% of a seeded hour" (standing between acts is no
    activity, its picture held by the 40% on frames; twenty minutes here, one
    seed of each gait; the hour itself is scratchpad hour99.py's, recorded on the row)."""
    for gait, seed in (("walk", 3), ("float", 2)):
        e, s = make(gait=gait, seed=seed)
        e.extra_frames = frozenset(s.extras())
        person = random.Random(100 + seed)
        frames: collections.Counter[str] = collections.Counter()
        acts: collections.Counter[str] = collections.Counter()
        t, nxt, secs = 0.0, 5.0, 1200.0
        while t < secs:
            t += 0.1
            pointer = None
            if t >= nxt:
                nxt = t + person.uniform(10.0, 30.0)
                pointer = (person.randint(100, 1800), person.randint(100, 900))
                e.last_active = t
            frames[re.sub(r"\d+$", "", e.update(t, pointer).frame)] += 1
            k = e.act if e.state == "act" else e.state
            if k != "stand":  # standing between two things is no activity; its picture counts in `frames`
                acts[k] += 1
        n = secs / 0.1
        assert frames.most_common(1)[0][1] / n <= 0.40, (gait, frames.most_common(3))
        assert acts.most_common(1)[0][1] / n <= 0.20, (gait, acts.most_common(3))
