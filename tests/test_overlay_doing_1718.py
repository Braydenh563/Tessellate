"""What the figure is doing is said, and a prop act starts only on a surface (INBOX 1718 b, owner screenshot: Atlas
holding a light gridded panel in front of a dark window, "what is it doing here"). The panel is the map of `read_map`
(cream with lilac grid lines and a teal route). The figure stood on the work area floor, in front of a window: a
prop act is only picked while grounded or perched, measured over six seeded hours per gait by a probe (33 starts, 0 off a surface; the test runs three).
The menu's first line names the act. Fixed clock."""

from __future__ import annotations

import random
from pathlib import Path

from tessellate.core.overlay import props
from tessellate.core.overlay.engine import Engine, Monitor

ONE = [Monitor((0, 0, 1920, 1040), 96)]
ROOT = Path(__file__).resolve().parents[1]


def hour(gait: str, seed: int, starts: list[tuple[str, float, bool]]) -> None:
    e = Engine((100, 120), ONE, rng=random.Random(seed), home=(800, 920), gait=gait, hang_top=0.195)
    e.hour = 13
    t, last = 1.0, None
    while t < 3600:
        t += 0.05
        e.update(t)
        if e.state == "act" and e.act != last and props.spec_of(e.act) is not None:
            starts.append((e.act, e.y - e.ground_y(e.current_monitor()), e.perch is not None))
        last = e.act if e.state == "act" else None


def test_a_prop_act_starts_only_on_the_floor_or_a_window_top() -> None:
    starts: list[tuple[str, float, bool]] = []
    for gait in ("walk", "float"):
        for seed in range(3):
            hour(gait, seed, starts)
    assert len(starts) >= 6
    assert all(abs(dy) <= 4 or perched for _a, dy, perched in starts), [s for s in starts if abs(s[1]) > 4 and not s[2]]


def test_every_prop_and_spell_act_has_words_for_the_menu() -> None:
    for name in (*props.PROP_ACTS, *props.SPELL_ACTS):
        assert name in props.DOING and props.DOING[name], name
    assert props.DOING["read_map"] == "reading a map"


def test_the_engine_says_it_while_the_act_runs_and_nothing_otherwise() -> None:
    e = Engine((100, 120), ONE, rng=random.Random(1), home=(800, 920))
    e.update(1.0)
    assert e.doing() == ""
    e._start_act("read_map", 2.0)
    e.update(2.1)
    assert e.state == "act" and e.doing() == "reading a map"


def test_the_menu_shows_the_line() -> None:
    js = (ROOT / "frontend" / "js" / "desk-companion.js").read_text(encoding="utf-8")
    assert "Right now: ${motion.doing}." in js
    py = (ROOT / "src" / "tessellate" / "core" / "desk_companion.py").read_text(encoding="utf-8")
    assert 'out["doing"] = said' in py
