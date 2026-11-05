"""The right-click menu is as tall on its first open after start as on every later one (INBOX 1683, owner: "the
desktop companion menu is quote short (edit: it was only short the first time I right clicked it after startup)").

Cause, measured in the code: the panel window is placed and shown at `PANEL_SIZES[kind]` before the page has measured
anything, and the page's first height report was only stored "for the next open" (INBOX 1658, so the window would not
flip between heights). The guess was 124 for the right-click menu whose six rows measure 306 (11 rows of the left-click
menu: 516, guessed 168), so the first open showed three rows and a clipped fourth. Now the guess is the measured
height, and a first report that still differs from what was placed (a larger font scale, another set of rows) refits the
window once; every later report is kept and places nothing."""

from __future__ import annotations

import pytest

from tessellate.core import desk_companion as dc
from tests.test_desk_companion import prefs  # noqa: F401
from tests.test_desk_overlay_wiring import FakeRunner, over  # noqa: F401

RECT = (1000, 800, 200, 240)
#: Measured in Chromium at 96 dpi (desk-1670.md, Row C): 11 rows of 38 px and 2 separators, and 6 rows.
MEASURED = {"menu": 516, "context": 306}


def _resizes(panel) -> list[tuple[int, int]]:
    return [(c[1], c[2]) for c in panel.calls if c[0] == "resize"]


def test_the_guess_the_first_open_is_placed_at_is_the_measured_height() -> None:
    for kind, height in MEASURED.items():
        assert dc.PANEL_SIZES[kind][1] == height, kind


@pytest.mark.parametrize("kind,button", [("menu", "left"), ("context", "right")])
def test_the_first_open_is_as_tall_as_the_later_ones(over, kind, button) -> None:  # noqa: F811
    over.set_main_hidden(True)
    runner = FakeRunner.started[0]
    panel = over.webview.made[0]
    api = dc.DeskApi(over)
    runner.on_click(button, RECT, 96)
    first = over.size
    api.set_size(dc.PANEL_SIZES[kind][0], MEASURED[kind], kind)  # the page measured its rows
    assert over.size == first == (dc.PANEL_SIZES[kind][0], MEASURED[kind])
    runner.on_click("left", RECT, 96) if button == "left" else over._hide_panel_window()  # noqa: SLF001
    panel.calls.clear()
    runner.on_click(button, RECT, 96)
    assert over.size == first and _resizes(panel)[-1] == first


def test_a_first_report_taller_than_the_guess_refits_the_open_window_once(over) -> None:  # noqa: F811
    """A 150 percent font scale or one more row: the first open is refitted, never left clipped."""
    over.set_main_hidden(True)
    runner = FakeRunner.started[0]
    panel = over.webview.made[0]
    api = dc.DeskApi(over)
    runner.on_click("right", RECT, 96)
    placed = len(_resizes(panel))
    api.set_size(248, 352, "context")
    assert over.size == (248, 352) and len(_resizes(panel)) == placed + 1
    for h in (352, 306, 352, 306, 352, 306, 352):  # the 1658 flip-flop: reports after the first place nothing
        api.set_size(248, h, "context")
    assert over.size == (248, 352) and len(_resizes(panel)) == placed + 1
    runner.on_click("left", RECT, 96)  # a left click while the context panel is up closes it
    panel.calls.clear()
    runner.on_click("right", RECT, 96)
    assert _resizes(panel)[-1] == (248, 352)  # the last report is what the next open uses


def test_a_first_report_within_a_few_pixels_places_nothing(over) -> None:  # noqa: F811
    over.set_main_hidden(True)
    runner = FakeRunner.started[0]
    panel = over.webview.made[0]
    runner.on_click("right", RECT, 96)
    placed = list(panel.calls)
    dc.DeskApi(over).set_size(248, MEASURED["context"] + 6, "context")
    assert panel.calls == placed
