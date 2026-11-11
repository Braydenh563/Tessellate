"""Research DG5: how lively the desk companion is can be chosen from its menu (Calm, Usual, Lively): how often it
goes on a trip, how readily it climbs, hangs or peeks, and whether it may take a long walk. Engine on a fixed clock
and seeded rng; the coordinator and the page on fakes (nothing here runs on Windows)."""

# ruff: noqa: F811  (pytest fixtures are used by name)
from __future__ import annotations

from tests._help_text import help_more_text
import random
from pathlib import Path

import pytest

pytest.importorskip("PIL")

from tessellate.core import desk_companion as dc  # noqa: E402
from tessellate.core.overlay import engine as eng  # noqa: E402
from tests.test_desk_companion import prefs  # noqa: E402, F401
from tests.test_desk_overlay_wiring import FakeRunner, over  # noqa: E402, F401

ROOT = Path(__file__).resolve().parent.parent
ONE = [eng.Monitor((0, 0, 1920, 1040), 96)]


def make(level: str) -> eng.Engine:
    e = eng.Engine((100, 120), ONE, rng=random.Random(4), home=(800, 920))
    e.roam = True
    e.set_lively(level)
    e.update(0.1)
    e.trip_ready = 100.0
    return e


def trip_weight(e: eng.Engine, now: float = 100.0) -> float:
    return dict(e._act_table(now, 0.0))["trip"]


def test_the_levels_are_calm_usual_and_lively_and_anything_else_is_usual() -> None:
    assert set(eng.LIVELY) == {"calm", "usual", "lively"}
    e = make("lively")
    e.set_lively("rm -rf")
    assert e.lively == "usual"


def test_a_livelier_figure_goes_on_trips_more_readily_and_sooner() -> None:
    calm, usual, lively = (trip_weight(make(n)) for n in ("calm", "usual", "lively"))
    assert calm < usual < lively
    gaps = {}
    for name in ("calm", "usual", "lively"):
        e = make(name)
        e._start_trip(1000.0)
        gaps[name] = e.trip_ready - 1000.0
    assert gaps["calm"] > gaps["usual"] > gaps["lively"]


def test_a_calm_figure_takes_no_long_walk() -> None:
    e = make("lively")
    e.mind.needs.update(rest=0.1, curiosity=0.8)
    e.last_long_walk = -1e9
    assert e._long_walk_ok(5000.0) is True
    e.set_lively("calm")
    assert e._long_walk_ok(5000.0) is False


def test_the_choice_is_saved_given_to_the_figure_and_shown_in_the_menu(over, prefs) -> None:
    over.set_main_hidden(True)
    runner = FakeRunner.started[0]
    api = dc.DeskApi(over)
    assert api.set_lively("lively") and prefs[dc.LIVELY_PREF] == "lively" and runner.lively_calls == ["usual", "lively"]
    assert over.panel_motion()["lively"] == "lively"
    assert not api.set_lively("wild") and not api.set_lively(None) and prefs[dc.LIVELY_PREF] == "lively"


def test_a_new_figure_starts_as_lively_as_was_chosen(over, prefs) -> None:
    prefs[dc.LIVELY_PREF] = "calm"
    over.set_main_hidden(True)
    assert FakeRunner.started[0].lively_calls == ["calm"]


def test_the_menu_has_one_row_that_steps_through_the_levels_and_the_help_names_them() -> None:
    js = (ROOT / "frontend" / "js" / "desk-companion.js").read_text(encoding="utf-8")
    assert '"Activity: ' in js or "`Activity: " in js
    for label in ('"Calm"', '"Usual"', '"Lively"'):
        assert label in js
    assert 'ask("set_lively"' in js
    help_text = help_more_text()
    assert "Activity (Calm, Usual or Lively;" in help_text
