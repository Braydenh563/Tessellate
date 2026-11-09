"""INBOX 1700 (the owner, 2026-11-09, Windows): "the desktop companion still doesnt seem to react to anything im doing on my
screen". Three causes, each pinned here on the fake win32 and a fixed clock: a screen event that came while the figure was
walking, hanging or typed over was thrown away (it is now held for `SCREEN_WAIT` s and played at the next free moment); a
window opening, closing or being dragged was read only when a climb was near (it is now read every `EVERY` s while the
figure is up); and the cooldowns (45 s the app changing) let one reaction in a minute. A reaction turns the figure toward
the window it is about, and each says so at INFO."""

from __future__ import annotations

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import extras, runner  # noqa: E402
from tests.test_overlay_roam_runner import started, tick  # noqa: E402

FAR_LEFT, FAR_RIGHT = (20, 100, 300, 500), (1500, 100, 1900, 500)


def _up():
    r, fake, clock, _ = started()
    fake.fg = 9
    fake._GetForegroundWindow = lambda: fake.fg
    fake.window_list = {7: {"rect": FAR_LEFT, "title": "Notes"}, 8: {"rect": FAR_RIGHT, "title": "Mail"}}
    r.engine.last_active = clock.t
    r.engine.trip_ready = r.engine.climb_ready = r.engine.big_ready = clock.t + 10_000  # no climb is near: no scan of its own
    tick(r, clock, 0.5, 8)  # the first reads are only remembered
    return r, fake, clock


def _answered(caplog, kind: str) -> bool:
    return any(f"it answered {kind}" in rec.getMessage() for rec in caplog.records)


def test_the_app_changing_is_answered_and_logged_and_it_looks_toward_that_window(caplog) -> None:
    caplog.set_level("INFO", logger=runner.logger.name)
    r, fake, clock = _up()
    e = r.engine
    e.facing = 1
    e.ex.cool.clear()
    fake.fg = 7  # the window on the far left comes forward
    tick(r, clock, 0.5, 10)
    assert "app_switched" in e.ex.last and _answered(caplog, "app_switched")
    assert e.facing == -1 or e.turn_to == -1, (e.facing, e.turn_to)
    assert any("screen event app_switched" in rec.getMessage() for rec in caplog.records)
    r.stop()


def test_it_looks_the_other_way_for_a_window_on_the_right() -> None:
    r, fake, clock = _up()
    e = r.engine
    e.facing = -1
    fake.fg = 8
    tick(r, clock, 0.5, 10)
    assert "app_switched" in e.ex.last and (e.facing == 1 or e.turn_to == 1), (e.facing, e.turn_to)
    r.stop()


def test_an_event_that_comes_while_it_is_busy_waits_and_is_answered_when_free(caplog) -> None:
    caplog.set_level("INFO", logger=runner.logger.name)
    r, fake, clock = _up()
    e = r.engine
    fake.last_input = (50_000, 50_000)  # keys are going in: no reaction is played over the person's typing
    fake.fg = 8
    tick(r, clock, 0.5, 6)
    assert e.quiet and "app_switched" not in e.ex.last, "held, not played over typing"
    fake.last_input = (100_000, 50_000)  # 50 s since the last key
    tick(r, clock, 0.5, 6)
    assert "app_switched" in e.ex.last and _answered(caplog, "app_switched")
    r.stop()


def test_an_event_nobody_could_answer_is_dropped_after_the_wait_and_said_so(caplog) -> None:
    caplog.set_level("INFO", logger=runner.logger.name)
    r, fake, clock = _up()
    e = r.engine
    fake.last_input = (50_000, 50_000)
    fake.fg = 8
    tick(r, clock, 0.5, int((runner.SCREEN_WAIT + 4) / 0.5))
    assert "app_switched" not in e.ex.last and not r._events
    assert any("screen event app_switched went unanswered" in rec.getMessage() for rec in caplog.records)
    r.stop()


def test_a_window_opening_is_read_with_no_climb_near_and_answered(caplog) -> None:
    caplog.set_level("INFO", logger=runner.logger.name)
    r, fake, clock = _up()
    e = r.engine
    assert not r._wants_scan(clock.t), "no trip is due: the climb scan is not what reads this"
    fake.window_list[9] = {"rect": (700, 200, 1100, 600), "title": "Calc"}
    tick(r, clock, 0.5, 10)
    assert "window_opened" in e.ex.last and _answered(caplog, "window_opened")
    r.stop()


def test_a_window_closing_and_a_window_dragged_are_answered_too() -> None:
    r, fake, clock = _up()
    e = r.engine
    del fake.window_list[8]
    tick(r, clock, 0.5, 10)
    assert "window_closed" in e.ex.last
    e.ex.cool.clear()
    e.ex.last.clear()
    for step in range(1, 5):  # 80 px a scan, the size unchanged: it is being dragged
        fake.window_list[7]["rect"] = (20 + 80 * step, 100, 300 + 80 * step, 500)
        tick(r, clock, 2.1, 1)
    tick(r, clock, 0.5, 6)
    assert "window_dragged" in e.ex.last, e.ex.last
    r.stop()


def test_the_cooldowns_let_a_reaction_through_every_few_seconds_not_once_a_minute() -> None:
    for kind in ("app_switched", "window_opened", "window_closed", "window_dragged", "window_maximised", "window_restored"):
        assert extras.REACTIONS[kind].cooldown <= 12.0, kind


def test_a_text_caret_in_the_foreground_window_does_not_silence_it(caplog) -> None:
    """A caret is reported by every editor, idle or not; only keys going in (`quiet`) holds a glance back."""
    r, fake, clock = _up()
    e = r.engine
    fake.caret = ((10, 10, 12, 30), (400, 400))
    fake.fg = 8
    tick(r, clock, 0.5, 10)
    assert e.busy and not e.quiet, "the caret was read, and nobody is typing"
    assert "app_switched" in e.ex.last
    r.stop()
