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

    def __init__(
        self, *, look, home, on_click, on_settle, on_died=None, on_card=None, roam_windows=True, stay=False, ok=True,
        reduced=None, reduced_reason="",
    ):
        self.look, self.home, self.on_click, self.on_settle, self.on_died = look, home, on_click, on_settle, on_died
        self.on_card, self.roam_windows = on_card, roam_windows
        self.monitors: list = []
        self.cards: list = []
        self.roam_calls: list = []
        self.stay, self.stay_calls, self.commands = stay, [], []
        self.reduced, self.reduced_reason = reduced, reduced_reason
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

    def bring_card(self, token):
        self.cards.append(token)

    def set_roam(self, on):
        self.roam_calls.append(on)

    def set_stay(self, on):
        self.stay_calls.append(on)

    def command(self, name):
        self.commands.append(name)
        return True


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
    # The quick panel is made ahead, hidden (INBOX 1658); there is no card window.
    assert over.window is not None and "overlay=1" in over.webview.made[0].options["url"] and not over.panel_shown and over.shown
    assert over.webview.made[0].options["hidden"] is True and ("show",) not in over.window.calls
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
    assert any(c[0] == "js" and "menu" in c[1] for c in panel.calls)  # the kept page is told which menu
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
    assert len(over.webview.made) == 1 and ("show",) not in over.webview.made[0].calls


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
    assert len(over.webview.made) == 1


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
    assert prefs[dc.OVERLAY_POS_PREF] == [300, 200] and not over.panel_shown


def test_item4_a_right_click_on_a_first_open_is_remembered_for_the_page_to_ask(over):
    _runner, panel = _open(over, "right")
    assert panel.options["url"].endswith("?card=1&overlay=1")
    api = dc.DeskApi(over)
    assert api.panel_kind() == "context"
    assert api.panel_kind() == "menu"  # asked once; a later load opens the menu


def test_item4_a_left_click_first_open_asks_for_the_menu(over):
    _open(over, "left")
    assert dc.DeskApi(over).panel_kind() == "menu"


# --- owner reports 2026-11-04 (a, b): the overlay follows Companion movement ----------------

import json  # noqa: E402


def _says(look="masculine", mode="full", reason=""):
    return lambda script: json.dumps({"look": look, "motion": {"mode": mode, "reason": reason}})


def test_the_overlay_follows_the_apps_resolved_motion_and_logs_it(over, caplog):
    caplog.set_level("INFO", logger=dc.logger.name)
    over.main_window.evaluate_js = _says(mode="fades", reason="app")
    over.set_main_hidden(True)
    runner = FakeRunner.started[0]
    assert runner.reduced is True and runner.reduced_reason == "app"
    assert any("overlay started" in r.getMessage() and "motion=still (app)" in r.getMessage() for r in caplog.records)
    assert dc.DeskApi(over).panel_motion() == {"still": True, "reason": "app", "roam": True, "stay": False, "size": 1.0, "asleep": False, "figure": True}


def test_a_full_answer_moves_and_no_answer_leaves_it_to_the_windows_flag(over):
    over.main_window.evaluate_js = _says(mode="full")
    over.set_main_hidden(True)
    assert FakeRunner.started[0].reduced is False
    assert dc.DeskApi(over).panel_motion() == {"still": False, "reason": "", "roam": True, "stay": False, "size": 1.0, "asleep": False, "figure": True}
    over.set_main_hidden(False)
    over.close()
    over.closing = False
    over.runner = None
    over.main_window.evaluate_js = lambda script: ""
    over.look, over.motion = "masculine", None  # no earlier answer: the Windows flag decides
    over.set_main_hidden(True)
    assert FakeRunner.started[-1].reduced is None


def test_a_change_of_motion_restarts_the_runner_where_it_stood(over):
    over.main_window.evaluate_js = _says(mode="fades", reason="setting")
    over.set_main_hidden(True)
    first = FakeRunner.started[0]
    first.engine = SimpleNamespace(x=700, y=900)
    over.main_window.evaluate_js = _says(mode="full")
    over.set_main_hidden(False)
    over.set_main_hidden(True)
    second = FakeRunner.started[1]
    assert "stop" in first.calls and second.reduced is False and second.home == (700, 900)


def test_let_it_walk_sets_the_apps_setting_and_restarts_the_figure_moving(over):
    seen = []

    def app(script):
        seen.append(script)
        if script == dc.WALK_SCRIPT:
            over.main_window.evaluate_js = _says(mode="full", reason="app-ignored")
            return True
        return _says(mode="fades", reason="os")(script)

    over.main_window.evaluate_js = app
    over.set_main_hidden(True)
    first = FakeRunner.started[0]
    assert first.reduced is True
    assert dc.DeskApi(over).let_it_walk() is True
    second = FakeRunner.started[1]
    assert dc.WALK_SCRIPT in seen and "avatar-buddy-motion" in dc.WALK_SCRIPT and "nameMarkBuddyMotionApply" in dc.WALK_SCRIPT
    assert "stop" in first.calls and second.reduced is False and second.calls == ["start", "show"]


def test_let_it_walk_holds_for_the_session_when_the_app_window_cannot_be_written(over):
    def app(script):
        if script == dc.WALK_SCRIPT:
            raise RuntimeError("hidden")
        return _says(mode="fades", reason="app")(script)

    over.main_window.evaluate_js = app
    over.set_main_hidden(True)
    assert dc.DeskApi(over).let_it_walk() is True
    assert FakeRunner.started[1].reduced is False


# --- owner report 2026-11-04 (c): the right click opens at its own size ----------------------


def test_a_right_click_makes_and_shows_the_panel_at_the_context_size_not_the_menus(over):
    over.set_main_hidden(True)
    FakeRunner.started[0].on_click("right", (1000, 800, 200, 240), 96)
    panel = over.webview.made[0]
    assert dc.PANEL_SIZES["context"][1] < dc.PANEL_SIZES["menu"][1]
    assert all(c[1:] == dc.PANEL_SIZES["context"] for c in panel.calls if c[0] == "resize")


def test_a_later_click_of_the_other_kind_is_sized_before_it_is_shown(over):
    over.set_main_hidden(True)
    runner = FakeRunner.started[0]
    runner.on_click("left", (1000, 800, 200, 240), 96)
    runner.on_click("left", (1000, 800, 200, 240), 96)  # closes
    panel = over.webview.made[0]
    panel.calls.clear()
    runner.on_click("right", (1000, 800, 200, 240), 96)
    shown_at = panel.calls.index(("show",))
    first_resize = next(i for i, c in enumerate(panel.calls) if c[0] == "resize")
    assert first_resize < shown_at and panel.calls[first_resize][1:] == dc.PANEL_SIZES["context"]


def test_every_panel_is_measured_by_its_content_not_a_fixed_height():
    # Widened 2026-11-04 from the menu alone to every panel (INBOX 1670: a fixed
    # 216 squashed Quick note, a fixed 280 left a band above Quick search).
    from pathlib import Path

    js = (Path(__file__).resolve().parent.parent / "frontend" / "js" / "desk-companion.js").read_text(encoding="utf-8")
    assert "function panelHeight(" in js and "getBoundingClientRect" in js.split("function panelHeight(")[1]
    fit = js.split("function fit()")[1].split("\n  }\n")[0]
    assert "panelHeight($(PANELS[state])" in fit and "fit();" in js.split("function show(next)")[1].split("\n  }\n")[0]


def test_an_unanswered_read_keeps_the_last_motion_answer(over):
    over.main_window.evaluate_js = _says(mode="full")
    over.set_main_hidden(True)
    assert over.motion == (False, "")
    over.main_window.evaluate_js = lambda script: ""
    over.set_main_hidden(False)
    over.set_main_hidden(True)
    assert len(FakeRunner.started) == 1 and over.motion == (False, "")


def test_hiding_the_panel_never_waits_on_its_page(over):
    import threading
    import time

    release = threading.Event()
    over.window = FakeWindow()
    over.window.evaluate_js = lambda script: release.wait(5)
    over.panel_shown = True
    t0 = time.monotonic()
    over._hide_panel_window()  # noqa: SLF001
    assert time.monotonic() - t0 < 0.5 and over.panel_shown is False
    release.set()


def test_the_menu_height_is_capped_and_walk_is_not_offered_when_locked():
    from pathlib import Path

    js = (Path(__file__).resolve().parent.parent / "frontend" / "js" / "desk-companion.js").read_text(encoding="utf-8")
    assert "screen.availHeight" in js.split("function panelHeight(")[1].split("\n  }\n")[0]
    assert "!locked && motion?.still" in js


# --- INBOX 1658: one writer for the panel's height, made once, no resize after show -------------


def _count(panel, name):
    return sum(1 for c in panel.calls if c[0] == name)


def test_1658_the_panel_is_made_once_ahead_and_a_click_shows_it_with_one_placement(over):
    over.set_main_hidden(True)
    panel = over.webview.made[0]
    assert len(over.webview.made) == 1 and panel.calls == []
    runner = FakeRunner.started[0]
    runner.on_click("left", (1000, 800, 200, 240), 96)
    assert len(over.webview.made) == 1
    assert _count(panel, "show") == 1 and _count(panel, "resize") == 1 and _count(panel, "move") == 1
    assert panel.calls.index(("show",)) > max(i for i, c in enumerate(panel.calls) if c[0] in ("resize", "move"))


# The menu window is 248 wide since the 1670 menu rows (long labels); read it from the source.
MENU_W = dc.PANEL_SIZES["menu"][0]


def test_1658_the_pages_height_report_after_show_places_nothing_and_is_kept_for_next_time(over):
    over.set_main_hidden(True)
    runner = FakeRunner.started[0]
    panel = over.webview.made[0]
    runner.on_click("left", (1000, 800, 200, 240), 96)
    api = dc.DeskApi(over)
    # Intent kept, one case moved (INBOX 1683, the first open was short): the page's FIRST height for a kind that
    # differs from the placed guess by more than REFIT_PX refits the window once; the flip-flop this test is about
    # (ten alternating placements in two seconds) is every report after it, which still places nothing.
    api.set_size(MENU_W, 154, "menu")
    placed = list(panel.calls)
    for _ in range(10):  # the owner's log: ten alternating placements in two seconds
        api.set_size(MENU_W, 154, "menu")
    assert panel.calls == placed and over.size == (MENU_W, 154)
    runner.on_click("left", (1000, 800, 200, 240), 96)  # closes
    panel.calls.clear()
    runner.on_click("left", (1000, 800, 200, 240), 96)
    assert [c[1:] for c in panel.calls if c[0] == "resize"] == [(MENU_W, 154)]
    assert _count(panel, "show") == 1 and _count(panel, "resize") == 1


def test_1658_a_note_opened_from_the_menu_is_still_a_real_resize_and_back(over):
    over.set_main_hidden(True)
    FakeRunner.started[0].on_click("left", (1000, 800, 200, 240), 96)
    panel = over.webview.made[0]
    api = dc.DeskApi(over)
    api.set_size(320, 376, "note")
    assert panel.calls[-2][1:] == (320, 376)
    api.set_size(MENU_W, 154, "menu")
    assert panel.calls[-2][1:] == (MENU_W, 154)


# INBOX 1666: at quit no web view is started, and one still starting gets a short deadline.
class _Loaded:
    def __init__(self, ok=True):
        self.ok, self.waited = ok, []

    def wait(self, timeout=None):
        self.waited.append(timeout)
        return self.ok


def test_1666_quit_hides_main_after_closing_so_no_panel_is_made(over):
    # Before: hide() -> set_main_hidden -> sync -> a new panel window created mid-quit.
    over.webview.made.clear()
    dc.shutdown()
    over.main_window.hide()
    over.set_main_hidden(True)
    assert over.webview.made == []


def test_1666_a_late_sync_after_close_makes_no_window(over):
    over.close()
    over._make_panel()  # noqa: SLF001
    assert over.webview.made == [] and over.window is None


def test_1666_close_waits_briefly_for_a_window_still_starting_then_destroys(over):
    # Intent moved (1666 review, 2026-11-07): the wait helps only a close off the GUI thread (the
    # /shutdown route, the tray), where the web view's start can still finish; so it runs on a worker here.
    import threading

    over.set_main_hidden(True)
    panel = over.webview.made[0]
    panel.events = SimpleNamespace(loaded=_Loaded(ok=False))
    worker = threading.Thread(target=over.close)
    worker.start()
    worker.join(5)
    assert panel.events.loaded.waited == [dc.LOADED_WAIT]
    assert ("destroy",) in panel.calls


def test_1666_a_close_on_the_gui_thread_does_not_wait_on_a_start_that_needs_that_thread(over):
    # The close X with close_to_tray off quits on the GUI thread: a start waits on that thread's loop, so
    # waiting there only froze the closing window for 1.5 s and the start aborted anyway (1666 review).
    over.set_main_hidden(True)
    panel = over.webview.made[0]
    panel.events = SimpleNamespace(loaded=_Loaded(ok=False))
    over.close()
    assert panel.events.loaded.waited == []
    assert ("destroy",) in panel.calls


def _closing_maker(over):
    """A `_make` that a quit overtakes: `close` (its lock wait timed out) sets closing mid-creation."""
    made = []

    def make():
        window = FakeWindow()
        made.append(window)
        over.closing = True
        return window

    over._make = make  # noqa: SLF001
    return made


def test_1666_a_panel_made_while_the_app_quits_is_destroyed_not_kept(over):
    made = _closing_maker(over)
    over._make_panel()  # noqa: SLF001
    assert over.window is None and ("destroy",) in made[0].calls


def test_1666_a_click_whose_panel_is_overtaken_by_quit_shows_nothing_and_keeps_nothing(over):
    over.set_main_hidden(True)
    over.window = None
    made = _closing_maker(over)
    over._overlay_click("left", (100, 100, 60, 90), 96)  # noqa: SLF001
    assert over.window is None and made[0].calls == [("destroy",)]


def test_1666_the_close_x_quit_closes_the_companion_on_the_same_teardown():
    from pathlib import Path

    src = (Path(dc.__file__).resolve().parents[1] / "__main__.py").read_text(encoding="utf-8")
    teardown = src.split("def _stop_background_work", 1)[1].split("\ndef ", 1)[0]
    assert "desk_companion.shutdown()" in teardown
    closing = src.split("def _on_closing", 1)[1].split("return True", 1)[0]
    assert "_stop_background_work()" in closing


def test_1666_a_window_without_a_loaded_event_is_still_destroyed(over):
    over.set_main_hidden(True)
    panel = over.webview.made[0]
    over.close()
    assert ("destroy",) in panel.calls


def test_1666_the_quit_handler_closes_the_companion_before_hiding_the_main_window():
    from pathlib import Path

    src = (Path(dc.__file__).resolve().parents[1] / "__main__.py").read_text(encoding="utf-8")
    body = src.split("def _quit_from_app", 1)[1].split("quit_hook.set_quit_handler", 1)[0]
    assert body.index("desk_companion.shutdown()") < body.index("hide()")


# INBOX 1690 d: "shown", "raised above the desktop: False", "hidden" every 3 to 8 s after a restart failed.
@pytest.mark.parametrize("how", ["restart", "sync"])
def test_1690d_a_failed_restart_drops_the_quick_panel_and_shows_a_real_card(over, how):
    # Before: the hidden quick panel (the overlay's page, menu sized, taking focus) stayed `self.window`,
    # so the fallback showed it as the card.
    over.set_main_hidden(True)
    panel = over.webview.made[0]
    assert "overlay=1" in panel.options["url"]
    over.box.ok = False
    over.main_window.evaluate_js = lambda script: "feminine"  # a new look: the runner is restarted
    if how == "restart":
        assert over._restart_shown("companion choice") is False  # noqa: SLF001
    else:
        over.set_main_hidden(False)
        over.set_main_hidden(True)
    assert over.overlay_failed and ("destroy",) in panel.calls and ("show",) not in panel.calls
    card = over.webview.made[-1]
    assert card is not panel and card.options["url"].endswith("?card=1") and ("show",) in card.calls
    assert over.shown and not over.panel and not over.panel_shown
def test_the_apps_companion_size_reaches_the_figure_and_a_pull_is_written_back(over):
    """The size handle (INBOX 1683 r): the look read carries Appearance's size, a changed one is passed to the
    running figure, and the figure's own pull is written through the page the way its handle writes it."""
    import json

    asked: list[str] = []

    def answer(script):
        asked.append(script)
        return json.dumps({"look": "masculine", "size": 1.3}) if "size:" in script else True

    over.main.evaluate_js = answer
    over.set_main_hidden(True)
    runner = FakeRunner.started[0]
    assert over.size_pref == 1.3 and "size:typeof nameMarkBuddyScaleSaved" in asked[0]
    runner.on_size = over._overlay_size  # noqa: SLF001 - what a real runner is given
    runner.scale = 1.3
    runner.set_scale = lambda v: runner.__dict__.setdefault("scaled", []).append(v)
    over.main.evaluate_js = lambda s: (asked.append(s), json.dumps({"look": "masculine", "size": 0.8}) if "size:" in s else True)[1]
    over._start_overlay()  # noqa: SLF001
    assert runner.scaled == [0.8]
    runner.on_size(1.4)
    assert over.size_pref == 1.4 and "nameMarkBuddySetSize(v,true)" in asked[-1] and "const v=1.4;" in asked[-1]


def _page(over, answers):
    """The app window: `answers` is what a size write returns; the look says what size the page holds."""
    import json

    asked: list[str] = []
    state = {"write": answers, "page": 1.0}

    def answer(script):
        asked.append(script)
        if "size:" in script:
            return json.dumps({"look": "masculine", "size": state["page"]})
        return state["write"]

    over.main.evaluate_js = answer
    return asked, state


def test_a_failed_write_back_keeps_the_pulled_size_and_is_retried_on_the_next_sync(over):
    asked, state = _page(over, False)
    over.set_main_hidden(True)
    runner = FakeRunner.started[0]
    runner.scale, runner.set_scale = 1.0, lambda v: runner.__dict__.setdefault("scaled", []).append(v)
    runner.on_size = over._overlay_size  # noqa: SLF001
    runner.on_size(1.4)
    assert over.size_pref == 1.4 and over._size_unsent == 1.4  # noqa: SLF001
    over._now = lambda: 1e9  # noqa: SLF001 - well past the hold
    runner.scale = 1.4
    before = len(asked)
    over._start_overlay()  # noqa: SLF001 - the page still says 1.0
    assert over.size_pref == 1.4 and not hasattr(runner, "scaled")  # the page's old value is not taken back
    assert any("const v=1.4;" in s for s in asked[before:])  # the write is tried again
    state["write"] = True
    over._start_overlay()  # noqa: SLF001
    assert over._size_unsent is None  # noqa: SLF001
    state["page"] = 0.8
    over._now = lambda: 2e9  # noqa: SLF001
    over._start_overlay()  # noqa: SLF001 - now Appearance may change it
    assert over.size_pref == 0.8


def test_the_menu_sizes_are_the_apps_three_steps_and_set_the_figure_and_the_page(over):
    asked, _ = _page(over, True)
    over.set_main_hidden(True)
    runner = FakeRunner.started[0]
    runner.scale, runner.set_scale = 1.0, lambda v: runner.__dict__.setdefault("scaled", []).append(v)
    api = dc.DeskApi(over)
    assert api.set_figure_size("large") is True and over.size_pref == 1.3 and runner.scaled == [1.3]
    assert "const v=1.3;" in asked[-1] and api.panel_motion()["size"] == 1.3
    assert api.set_figure_size("huge") is False and api.set_figure_size(None) is False and over.size_pref == 1.3
    assert api.set_figure_size("small") and runner.scaled == [1.3, 0.8]


def test_the_size_script_and_look_script_use_the_names_the_page_really_has():
    from pathlib import Path
    import re

    js = (Path(dc.__file__).resolve().parents[3] / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")
    setter = re.search(r"function nameMarkBuddySetSize\((\w+), (\w+) = true\)", js)
    assert setter and "nameMarkBuddySetSize(v,true)" in dc.SIZE_SCRIPT and "%s" in dc.SIZE_SCRIPT
    assert "function nameMarkBuddyScaleSaved()" in js and "nameMarkBuddyScaleSaved()" in dc.LOOK_SCRIPT
    assert 'prefs.get("avatar-buddy-size"' in js and "'avatar-buddy-size'" in dc.SIZE_SCRIPT
    steps = re.search(r"const NMB_SIZES = \{ small: ([\d.]+), medium: ([\d.]+), large: ([\d.]+) \}", js)
    assert steps and dc.SIZE_PRESETS == {"small": float(steps[1]), "medium": float(steps[2]), "large": float(steps[3])}


@pytest.mark.parametrize("bad", ["big", True, None, [1], {"a": 1}])
def test_a_size_that_is_not_a_number_is_ignored_when_the_look_is_read(over, bad):
    import json

    over.main.evaluate_js = lambda s: json.dumps({"look": "masculine", "size": bad})
    over.size_pref = 1.3
    over._read_look()  # noqa: SLF001
    assert over.size_pref == 1.3
