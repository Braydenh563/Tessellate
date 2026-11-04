"""The overlay wired into the desktop companion (BACKLOG 16, O4): `DeskCompanion`
with a fake runner. Nothing here runs Windows; what is held is the logic: the
overlay replaces the card when due, a failed start falls back to the card, a click
opens the quick panel beside the figure, and Hide, the tray tick and sync work as
before."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tessellate.core import desk_companion as dc
from tests.test_desk_companion import FakeWebview, FakeWindow, prefs  # noqa: F401


class FakeRunner:
    started: list["FakeRunner"] = []

    def __init__(self, *, look, home, on_click, on_settle, on_died=None, ok=True):
        self.look, self.home, self.on_click, self.on_settle, self.on_died = look, home, on_click, on_settle, on_died
        self.ok = ok
        self.calls: list[str] = []
        FakeRunner.started.append(self)

    def start(self):
        self.calls.append("start")
        return self.ok

    def show(self):
        self.calls.append("show")

    def hide(self):
        self.calls.append("hide")

    def stop(self):
        self.calls.append("stop")


@pytest.fixture()
def over(prefs, monkeypatch):  # noqa: F811
    FakeRunner.started = []
    monkeypatch.setattr(dc, "monitor_areas", lambda: [(0, 0, 1920, 1040)])
    webview = FakeWebview()
    main = FakeWindow()
    main.evaluate_js = lambda script: "masculine"
    box = SimpleNamespace(ok=True)

    def factory(**kw):
        return FakeRunner(ok=box.ok, **kw)

    companion = dc.attach(webview, main, lambda s="": None, lambda: "http://x/desktop-companion.html", transparent=False, overlay_factory=factory)
    companion._dispatch = lambda name, fn: fn()  # noqa: SLF001
    companion.webview, companion.main_window, companion.box = webview, main, box
    prefs[dc.PREF] = True
    return companion


def test_panel_corner_is_left_of_the_figure_when_it_fits_else_right_and_always_inside():
    area = (0, 0, 1920, 1040)
    left = dc.panel_corner((1000, 800, 100, 120), (208, 160), area)
    assert left == (1000 - dc.PANEL_GAP, 920)
    right = dc.panel_corner((20, 800, 100, 120), (208, 160), area)
    assert right == (20 + 100 + dc.PANEL_GAP + 208, 920)
    low = dc.panel_corner((1000, 1000, 100, 120), (208, 160), area)
    assert low[1] == 1040 and low[0] - 208 >= 0


def test_when_due_the_overlay_is_shown_and_no_card_window_is_made(over):
    over.set_main_hidden(True)
    runner = FakeRunner.started[0]
    assert runner.calls == ["start", "show"] and runner.look == "masculine"
    assert over.window is None and over.shown
    over.set_main_hidden(False)
    assert runner.calls[-1] == "hide" and not over.shown


def test_a_failed_start_falls_back_to_the_card_window_with_a_warning(over, caplog):
    over.box.ok = False
    over.set_main_hidden(True)
    assert over.overlay_failed and over.window is not None and over.shown
    assert any("could not start" in r.getMessage() for r in caplog.records)
    over.set_main_hidden(True)
    assert len(FakeRunner.started) == 1  # not retried every sync


def test_the_look_is_read_from_the_app_window_and_a_change_restarts_the_runner(over):
    over.set_main_hidden(True)
    over.main_window.evaluate_js = lambda script: "feminine"
    over.set_main_hidden(False)
    over.set_main_hidden(True)
    first, second = FakeRunner.started
    assert "stop" in first.calls and second.look == "feminine"


def test_no_answer_from_the_app_window_keeps_the_last_look(over):
    def slow(script):
        raise RuntimeError("hidden")

    over.main_window.evaluate_js = slow
    over.set_main_hidden(True)
    assert FakeRunner.started[0].look == "masculine"


def test_a_click_opens_the_quick_panel_beside_the_figure_and_a_second_click_closes_it(over):
    over.set_main_hidden(True)
    runner = FakeRunner.started[0]
    runner.on_click("left", (1000, 800, 200, 240), 96)
    panel = over.webview.made[0]
    assert panel.options["url"].endswith("?card=1&overlay=1") and panel.options["focus"] is True
    assert ("show",) in panel.calls and over.panel_shown
    assert not any(c[0] == "js" for c in panel.calls)  # a new page opens its own menu
    runner.on_click("right", (1000, 800, 200, 240), 96)
    assert any(c[0] == "js" and "context" in c[1] for c in panel.calls)
    runner.on_click("left", (1000, 800, 200, 240), 96)
    assert not over.panel_shown and ("hide",) in panel.calls


def test_the_panel_is_placed_in_logical_pixels_on_a_scaled_screen(over):
    over.set_main_hidden(True)
    FakeRunner.started[0].on_click("left", (1500, 1200, 300, 360), 192)
    assert over.pet_rect == (750, 600, 150, 180)
    assert over.corner[0] == 750 - dc.PANEL_GAP


def test_the_page_asking_for_a_size_keeps_the_panel_beside_the_figure(over):
    over.set_main_hidden(True)
    FakeRunner.started[0].on_click("left", (1000, 800, 200, 240), 96)
    over.resize(320, 216)
    assert over.corner == (1000 - dc.PANEL_GAP, 1040)
    assert dc.DeskApi(over).hide_panel() is True and not over.panel_shown


def test_hide_turns_the_preference_off_and_the_overlay_away(over, prefs):  # noqa: F811
    over.set_main_hidden(True)
    assert over.turn_off()
    assert prefs[dc.PREF] is False
    assert FakeRunner.started[0].calls[-1] == "hide" and not over.shown


def test_a_drop_is_saved_and_close_stops_the_runner(over, prefs):  # noqa: F811
    over.set_main_hidden(True)
    FakeRunner.started[0].on_settle(640, 880)
    assert prefs[dc.OVERLAY_POS_PREF] == [640, 880]
    over.close()
    assert FakeRunner.started[0].calls[-1] == "stop"


def test_a_click_after_close_does_nothing(over):
    over.set_main_hidden(True)
    runner = FakeRunner.started[0]
    over.close()
    runner.on_click("left", (0, 0, 10, 10), 96)
    assert not over.webview.made


def test_off_windows_there_is_no_overlay_by_default(monkeypatch):
    monkeypatch.setattr(dc.sys, "platform", "linux")
    assert dc._default_overlay_factory() is None  # noqa: SLF001


def _open(over, kind="left"):
    over.set_main_hidden(True)
    runner = FakeRunner.started[0]
    runner.on_click(kind, (1000, 800, 200, 240), 96)
    return runner, over.webview.made[0]


def test_item1_losing_focus_to_something_else_closes_the_panel(over):
    _runner, panel = _open(over)
    assert dc.DeskApi(over).panel_blur() is True
    assert not over.panel_shown and ("hide",) in panel.calls


def test_item1_a_blur_caused_by_the_click_on_the_figure_does_not_reopen_it(over):
    runner, panel = _open(over)
    over._now = lambda: 10.0  # noqa: SLF001
    dc.DeskApi(over).panel_blur()
    over._now = lambda: 10.2  # noqa: SLF001
    runner.on_click("left", (1000, 800, 200, 240), 96)  # the same press that blurred it
    assert not over.panel_shown
    over._now = lambda: 20.0  # noqa: SLF001
    runner.on_click("left", (1000, 800, 200, 240), 96)  # a later, separate click opens it
    assert over.panel_shown


def test_item1_a_blur_with_no_panel_up_is_harmless(over):
    over.set_main_hidden(True)
    assert dc.DeskApi(over).panel_blur() is True


def test_item2_a_runner_that_died_brings_the_card_window_back(over, caplog):
    over.set_main_hidden(True)
    runner = FakeRunner.started[0]
    runner.on_click("left", (1000, 800, 200, 240), 96)
    panel = over.webview.made[0]
    runner.on_died()
    assert over.overlay_failed and over.runner is None
    assert ("destroy",) in panel.calls
    card = over.webview.made[-1]
    assert card is not panel and card.options["url"].endswith("?card=1") and ("show",) in card.calls
    assert over.shown and not over.panel_shown and not over.panel
    assert any("overlay stopped" in r.getMessage() for r in caplog.records)
    over.set_main_hidden(True)
    assert len(FakeRunner.started) == 1


def test_item2_a_death_while_the_companion_is_not_due_makes_no_card(over):
    over.set_main_hidden(True)
    runner = FakeRunner.started[0]
    over.set_main_hidden(False)
    runner.on_died()
    assert over.overlay_failed and over.window is None


def test_item2_a_death_after_close_or_from_a_replaced_runner_is_ignored(over):
    over.set_main_hidden(True)
    runner = FakeRunner.started[0]
    over.close()
    runner.on_died()
    assert not over.webview.made


def test_item3_a_drop_while_the_panel_is_open_moves_it_beside_the_figure(over):
    runner, panel = _open(over)
    before = over.corner
    runner.on_settle(300, 200)
    assert over.pet_rect[:2] == (300, 200) and over.corner != before
    assert over.corner == dc.panel_corner(over.pet_rect, over.size, (0, 0, 1920, 1040))
    assert ("move", *over.top_left()) in panel.calls or any(c[0] in ("move", "resize") for c in panel.calls[-3:])


def test_item3_a_drop_with_no_panel_only_saves_the_place(over, prefs):  # noqa: F811
    over.set_main_hidden(True)
    FakeRunner.started[0].on_settle(300, 200)
    assert prefs[dc.OVERLAY_POS_PREF] == [300, 200] and over.window is None


def test_item4_a_right_click_on_a_first_open_is_remembered_for_the_page_to_ask(over):
    _runner, panel = _open(over, "right")
    assert panel.options["url"].endswith("?card=1&overlay=1")
    api = dc.DeskApi(over)
    assert api.panel_kind() == "context"
    assert api.panel_kind() == "menu"  # asked once; a later load opens the menu


def test_item4_a_left_click_first_open_asks_for_the_menu(over):
    _open(over, "left")
    assert dc.DeskApi(over).panel_kind() == "menu"
