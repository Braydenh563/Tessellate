"""Roam, carry and mixed-dpi placement in the desktop companion (owner, 2026-11-04):
`DeskCompanion` with a fake runner. The Windows calls themselves cannot run here."""

# ruff: noqa: F811  (pytest fixtures are used by name)
from __future__ import annotations

from tessellate.core import desk_companion as dc
from tests.test_desk_companion import prefs  # noqa: F401
from tests.test_desk_overlay_wiring import FakeRunner, over  # noqa: F401

LEFT = ((-1920, 0, 0, 1000), 96)     # a 100 percent monitor left of the primary (negative x)
PRIMARY = ((0, 0, 1920, 1040), 144)  # the 150 percent primary
MONITORS = [PRIMARY, LEFT]


# --- placement, pure ---------------------------------------------------------------------------

def test_the_panel_uses_the_dpi_of_the_monitor_it_lands_on_100_and_150_percent() -> None:
    on_left, dpi_left = dc.panel_placement((-600, 880, 100, 120), (208, 168), MONITORS)
    assert dpi_left == 96 and on_left[2:] == (208, 168)
    assert on_left[:2] == (-600 - dc.PANEL_GAP - 208, 1000 - 168)  # left of the figure, bottoms level
    on_main, dpi_main = dc.panel_placement((1200, 800, 150, 180), (208, 168), MONITORS)
    assert dpi_main == 144 and on_main[2:] == (312, 252)
    assert on_main[:2] == (1200 - 12 - 312, 980 - 252)


def test_a_dpi_from_windows_wins_over_the_monitor_list() -> None:
    box, dpi = dc.panel_placement((1200, 800, 150, 180), (208, 168), MONITORS, dpi=192)
    assert dpi == 192 and box[2:] == (416, 336)


def test_the_panel_is_kept_inside_the_monitor_it_is_on_at_the_negative_edge() -> None:
    # Against the left monitor's left edge: it goes to the figure's right, never past the edge.
    box, dpi = dc.panel_placement((-1900, 700, 100, 120), (208, 168), MONITORS)
    assert dpi == 96 and box[0] == -1900 + 100 + dc.PANEL_GAP and box[0] >= -1920
    # Against the primary's bottom: held inside the work area.
    box, _ = dc.panel_placement((1000, 1000, 150, 180), (208, 168), MONITORS)
    assert box[1] + box[3] <= 1040 and box[0] >= 0


def test_a_point_off_every_monitor_takes_the_nearest() -> None:
    assert dc.monitor_for((-5000, 400), MONITORS) == LEFT
    assert dc.monitor_for((9000, 400), MONITORS) == PRIMARY


# --- wired ---------------------------------------------------------------------------------------

def _runner(over):  # noqa: F811
    over.set_main_hidden(True)
    runner = FakeRunner.started[0]
    runner.monitors = [type("M", (), {"area": a, "dpi": d})() for a, d in MONITORS]
    runner.sprites = type("S", (), {"size": staticmethod(lambda dpi: (round(100 * dpi / 96), round(120 * dpi / 96)))})()
    runner.dpi_at = lambda x, y: next((d for a, d in MONITORS if a[0] <= x < a[2] and a[1] <= y < a[3]), 96)
    return runner


def test_a_click_places_the_panel_at_the_scale_of_the_monitor_under_the_figure(over) -> None:
    runner = _runner(over)
    runner.on_click("left", (-600, 880, 100, 120), 96)
    box, dpi = over.panel_box
    # INBOX 1683: intent kept (the scale of the monitor under the figure); the opening size is now the measured
    # menu height (`PANEL_SIZES`), not the old 168 guess, so the numbers come from it.
    mw, mh = dc.PANEL_SIZES["menu"]
    assert dpi == 96 and box == (-600 - dc.PANEL_GAP - mw, 1000 - mh, mw, mh)
    runner.on_click("left", (-600, 880, 100, 120), 96)  # closes
    runner.on_click("left", (1200, 800, 150, 180), 144)
    box, dpi = over.panel_box
    assert dpi == 144 and box[2:] == (round(mw * 1.5), round(mh * 1.5))


def test_a_drop_on_another_monitor_re_places_the_open_panel_with_that_monitors_dpi(over) -> None:
    runner = _runner(over)
    runner.on_click("left", (-600, 880, 100, 120), 96)
    assert over.panel_box[1] == 96
    runner.on_settle(1200, 700)  # carried over to the 150 percent monitor and dropped
    box, dpi = over.panel_box
    assert dpi == 144
    assert over._pet_phys == (150, 180, 144)  # the figure's own size at that scale
    assert box == dc.panel_placement((1200, 700, 150, 180), dc.PANEL_SIZES["menu"], MONITORS)[0]  # 1683: the measured size, not 168
    runner.on_settle(-700, 800)  # and back to the 100 percent one
    assert over.panel_box[1] == 96 and over._pet_phys[2] == 96


def test_the_page_asking_for_a_height_re_places_the_panel_physically(over) -> None:
    runner = _runner(over)
    runner.on_click("left", (1200, 800, 150, 180), 144)
    over.resize(248, 120)
    box, dpi = over.panel_box
    assert dpi == 144 and box[2:] == (372, 180)


def test_with_no_monitor_list_the_logical_corner_still_places_it(over) -> None:
    over.set_main_hidden(True)
    FakeRunner.started[0].on_click("left", (1000, 800, 200, 240), 96)
    assert over.panel_box is None and over.corner == (1000 - dc.PANEL_GAP, 1040)


# --- roam switch ----------------------------------------------------------------------------------

def test_roam_is_on_by_default_and_the_menu_switch_is_a_pref_the_runner_follows(over, prefs) -> None:  # noqa: F811
    over.set_main_hidden(True)
    runner = FakeRunner.started[0]
    assert runner.roam_windows is True
    assert dc.DeskApi(over).panel_motion()["roam"] is True
    assert dc.DeskApi(over).set_roam(False) is True
    assert prefs[dc.ROAM_PREF] is False and runner.roam_calls == [False]
    assert dc.DeskApi(over).panel_motion()["roam"] is False
    assert dc.DeskApi(over).set_roam("yes") is True  # only a real true turns it on
    assert prefs[dc.ROAM_PREF] is False
    dc.DeskApi(over).set_roam(True)
    assert prefs[dc.ROAM_PREF] is True and runner.roam_calls[-1] is True


def test_a_runner_made_after_the_switch_is_off_starts_with_it_off(over, prefs) -> None:  # noqa: F811
    prefs[dc.ROAM_PREF] = False
    over.set_main_hidden(True)
    assert FakeRunner.started[0].roam_windows is False


# --- reminders --------------------------------------------------------------------------------------

def test_a_due_reminder_goes_to_the_figure_only_while_it_shows(over) -> None:
    assert over.carry_reminder("r1") is False  # no overlay yet
    over.set_main_hidden(True)
    runner = FakeRunner.started[0]
    assert over.carry_reminder("r1") is True and runner.cards == ["r1"]
    over.set_main_hidden(False)  # the app is open: the figure is away
    assert over.carry_reminder("r2") is False and runner.cards == ["r1"]


def test_a_click_on_the_card_opens_the_reminders_tab_in_the_app(over) -> None:
    opened: list[str] = []
    over._open_main = lambda script="": opened.append(script)  # noqa: SLF001
    over.set_main_hidden(True)
    FakeRunner.started[0].on_card("r1")
    assert opened == [dc.REMINDERS_SCRIPT]
    assert "switchTab('reminders')" in dc.REMINDERS_SCRIPT and "lock-overlay" in dc.REMINDERS_SCRIPT


def test_the_card_windows_fallback_ignores_reminders(prefs) -> None:  # noqa: F811
    from tests.test_desk_companion import FakeWebview, FakeWindow

    companion = dc.DeskCompanion(FakeWebview(), FakeWindow(), lambda s="": None, lambda: "http://x/", transparent=False)
    assert companion.carry_reminder("r1") is False


def test_the_notifier_hook_hands_each_due_reminder_to_the_showing_companion(over) -> None:
    from tessellate.core.reminder_notifier import Due

    over.set_main_hidden(True)
    runner = FakeRunner.started[0]
    assert dc.carry_due([Due("k1", 7, "Stretch", False), Due("k2", 9, "Call", False)]) == 2
    assert runner.cards == [7, 9]
    over.set_main_hidden(False)
    assert dc.carry_due([Due("k3", 11, "x", False)]) == 0


def test_with_no_companion_the_hook_does_nothing(monkeypatch) -> None:
    monkeypatch.setattr(dc, "_active", None)
    assert dc.carry_due([]) == 0
