"""INBOX 1670, row C: the companion's menu asks the figure for things (wave, come here, go somewhere
else, nap, wake, sit on a window, stay, roam) and can hide it for ten minutes. The engine on a fixed
clock and the shipped frames, the runner and the coordinator on fakes; nothing here runs on Windows."""

# ruff: noqa: F811  (pytest fixtures are used by name)
from __future__ import annotations

import math
from pathlib import Path

import pytest

pytest.importorskip("PIL")

from tessellate.core import desk_companion as dc  # noqa: E402
from tessellate.core.overlay import engine as eng  # noqa: E402
from tessellate.core.overlay.engine import Perch  # noqa: E402
from tests.test_desk_companion import prefs  # noqa: E402, F401
from tests.test_desk_overlay_wiring import FakeRunner, over  # noqa: E402, F401
from tests.test_overlay_life_1670 import calm, run  # noqa: E402
from tests.test_overlay_ride_1670 import make  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def ready(gait="walk"):
    e, s = make("masculine", gait)
    calm(e)
    e.x, e.home_x = 200.0, 200.0
    e.last_active = 0.0
    e.update(0.1, (1500, 900))
    return e, s


# --- the engine's half ----------------------------------------------------------------------------


def test_wave_waves_and_returns_to_standing() -> None:
    e, _ = ready()
    assert e.command("wave", 1.0) and e.state == "wave"
    run(e, 1.0, eng.WAVE_FOR + 0.5, step=0.05)
    assert e.state != "wave"


def test_nap_sleeps_and_wake_stretches_awake() -> None:
    e, _ = ready()
    assert e.command("nap", 1.0) and e.state == "sleep"
    assert e.command("wake", 2.0)
    assert e.state == "act" and e.act == "stretch"


def test_a_nap_on_a_window_comes_down_first() -> None:
    e, _ = ready("walk")
    e.perch = Perch(1, 300, 300, 1200)
    e.y = 300 - e.size[1]
    assert e.command("nap", 1.0)
    assert e.perch is None and e.state == "fall" and e.nap_after_land
    run(e, 1.0, 3.0, step=0.033)
    assert e.state == "sleep" and e.y == pytest.approx(e.floor_y(), abs=1)


def test_come_here_walks_to_the_pointer_and_stops_close() -> None:
    e, _ = ready()
    k = e._scale()
    # Intent moved (INBOX 1683 t): the menu is opened on the figure, so it first waits for the pointer to leave.
    assert e.command("come", 1.0) and e.come["phase"] == "wait"
    run(e, 1.0, 14.0, pointer=(1500, 900), step=0.033)
    near = abs((e.x + e.size[0] / 2) - 1500)
    assert near <= (eng.COME_GAP + 40) * k + e.size[0] / 2, near
    assert near < 240 * k  # closer than the polite following distance


def test_come_here_without_a_pointer_says_no() -> None:
    e, _ = make("masculine", "walk")
    assert e.pointer is None and e.command("come", 1.0) is False


def test_go_somewhere_else_goes_far_and_makes_it_home() -> None:
    e, _ = ready()
    start = e.x
    assert e.command("wander", 1.0)
    run(e, 1.0, 60.0, step=0.033)
    assert abs(e.x - start) >= eng.WANDER_MIN - 1 and e.state in ("stand", "act")
    assert e.home_x == pytest.approx(e.x, abs=2)


def test_sit_on_a_window_needs_one_to_sit_on() -> None:
    e, _ = ready()
    e.roam_windows = True
    assert e.command("perch", 1.0) is False
    e.set_windows([Perch(9, 500, 400, 1300)], 1.0)
    assert e.command("perch", 1.5) is True
    run(e, 1.5, 12.0, step=0.033)
    assert e.perch is not None and e.perch.key == 9


def test_stay_stops_the_wandering_and_roam_starts_it_again() -> None:
    e, _ = ready()
    e.big_ready = e.trip_ready = 0.0
    assert e.command("stay", 1.0) and e.roam is False
    _, t = run(e, 1.0, 120.0, step=0.5)
    assert abs(e.x - 200.0) < 1
    assert e.command("roam", t) and e.roam is True


def test_a_carried_figure_is_not_interrupted() -> None:
    e, _ = ready()
    e.state = "held"
    assert e.command("wave", 1.0) is False and e.state == "held"


def test_reduced_motion_waves_by_sitting_and_never_walks() -> None:
    e, _ = ready()
    e.reduced = True
    assert e.command("wave", 1.0) and e.state == "sit"
    assert e.command("come", 2.0) is False and e.command("wander", 2.0) is False


def test_every_command_the_menu_names_exists() -> None:
    assert set(dc.FIGURE_COMMANDS) <= set(eng.Engine.COMMANDS)
    assert not math.isnan(eng.COME_GAP)


# --- the coordinator's half -----------------------------------------------------------------------


def test_the_page_may_ask_the_figure_only_for_the_known_commands(over) -> None:
    over.set_main_hidden(True)
    runner = FakeRunner.started[0]
    api = dc.DeskApi(over)
    assert api.figure_do("wave") and api.figure_do("perch")
    assert not api.figure_do("rm -rf") and not api.figure_do(None) and not api.figure_do("stay")
    assert runner.commands == ["wave", "perch"]


def test_stay_is_saved_and_given_to_the_figure(over, prefs) -> None:
    over.set_main_hidden(True)
    runner = FakeRunner.started[0]
    assert dc.DeskApi(over).set_stay(True) and prefs[dc.STAY_PREF] is True and runner.stay_calls == [True]
    assert over.panel_motion()["stay"] is True
    over.set_stay(False)
    assert prefs[dc.STAY_PREF] is False


def test_a_new_figure_starts_staying_when_that_was_the_choice(over, prefs) -> None:
    prefs[dc.STAY_PREF] = True
    over.set_main_hidden(True)
    assert FakeRunner.started[0].stay is True


def test_hide_for_ten_minutes_hides_now_and_returns_by_itself(over, prefs) -> None:
    clock = {"t": 1000.0}
    over._now = lambda: clock["t"]
    over.set_main_hidden(True)
    assert over.shown
    assert dc.DeskApi(over).snooze()
    assert not over.shown and "hide" in FakeRunner.started[0].calls
    over._snooze_timer.cancel()
    clock["t"] += 599
    over.sync()
    assert not over.shown
    clock["t"] += 2
    over.sync()
    assert over.shown
    assert prefs[dc.PREF] is True  # snoozing never turns it off


def test_closing_cancels_the_snooze_timer(over) -> None:
    over.set_main_hidden(True)
    over.snooze()
    timer = over._snooze_timer
    over.close()
    timer.join(1.0)
    assert not timer.is_alive()


def test_the_panel_reports_sleep_and_the_stay_choice(over) -> None:
    over.set_main_hidden(True)
    runner = FakeRunner.started[0]
    runner.engine = type("E", (), {"state": "sleep"})()
    info = over.panel_motion()
    assert info["asleep"] is True and info["figure"] is True and info["stay"] is False


# --- the page ------------------------------------------------------------------------------------

JS = (ROOT / "frontend" / "js" / "desk-companion.js").read_text(encoding="utf-8")


def test_the_menus_list_the_new_choices_each_wired_to_a_call() -> None:
    for label, call in (
        ("Wave", '"wave"'), ("Come here", '"come"'), ("Go somewhere else", '"wander"'),
        ("Take a nap", '"nap"'), ("Wake up", '"wake"'), ("Sit on a window", '"perch"'),
        ("Hide for 10 minutes", 'ask("snooze")'), ("Turn off", 'ask("hide_companion")'),
        ("New reminder", 'ask("open_app", "reminder")'), ("Open today", 'ask("open_app", "today")'),
    ):
        assert f'"{label}"' in JS and call in JS, label
    assert '"Stay here"' in JS and '"Roam"' in JS and 'ask("set_stay"' in JS and 'ask("figure_do"' in JS


def test_the_python_scripts_for_the_new_menu_rows_are_guarded_by_the_lock() -> None:
    for script in (dc.NEW_REMINDER_SCRIPT, dc.TODAY_SCRIPT):
        assert "lock-overlay" in script and "classList.contains('hidden')" in script
    assert "switchTab('reminders')" in dc.NEW_REMINDER_SCRIPT and "reminder-magic" in dc.NEW_REMINDER_SCRIPT
    assert "switchTab('dashboard')" in dc.TODAY_SCRIPT


@pytest.mark.parametrize("where, script", [("reminder", "NEW_REMINDER_SCRIPT"), ("today", "TODAY_SCRIPT")])
def test_open_app_takes_only_the_named_places(over, where, script) -> None:
    seen: list[str] = []
    over._open_main = seen.append
    api = dc.DeskApi(over)
    assert api.open_app(where) and seen == [getattr(dc, script)]
    assert api.open_app("alert(1)") and seen[-1] == ""


# --- the runner's half ---------------------------------------------------------------------------


def test_the_runner_queues_a_request_and_the_engine_takes_it_on_its_next_tick() -> None:
    from tests.test_overlay_roam_runner import started, tick

    r, _fake, clock, _clicks = started()
    assert r.command("wave") and r.command("nope") is False
    assert r.engine.state != "wave"  # not on the caller's thread
    tick(r, clock, 0.1)
    assert r.last_command == ("wave", True) and r.engine.state == "wave"
    r.set_stay(True)
    tick(r, clock, 0.1)
    assert r.engine.roam is False and r.stay is True
    r.stop()


def test_sit_on_a_window_reads_the_window_list_at_once() -> None:
    from tests.test_overlay_roam_runner import scans, started, tick

    r, fake, clock, _clicks = started()
    fake.window_list = {5: {"rect": (300, 700, 1100, 900), "title": "Notes"}}
    before = scans(fake)
    r.command("perch")
    tick(r, clock, 0.1)
    assert scans(fake) > before and r.last_command[0] == "perch"
    r.stop()


def test_a_failed_search_refits_the_window_for_its_status_line() -> None:
    """The error line adds a row to the panel; the overlay window must be asked to grow with it."""
    js = (ROOT / "frontend" / "js" / "desk-companion.js").read_text(encoding="utf-8")
    body = js[js.index("async function runSearch()") :]
    catch = body[body.index("} catch (error) {") : body.index("// --- the companion itself")]
    assert "if (overlay) fit();" in catch


def test_the_context_menu_offers_small_medium_and_large_as_the_apps_steps() -> None:
    for label, name in (("Small", "small"), ("Medium", "medium"), ("Large", "large")):
        assert f'"{label}"' in JS and name in JS, label
    assert 'ask("set_figure_size"' in JS and "motion.size" in JS
