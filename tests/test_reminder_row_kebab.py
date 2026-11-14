"""The Reminders row's date and its ⋯ never share pixels, and the ⋯ takes a
plain click (the owner, 2026-10-27: both right edges measured 1230 and a plain
Playwright click was intercepted until the row was hovered).

Measured by `scratchpad/ui-sweeps/remkebab.js` at 1280: date 1045..1230 and
kebab 1202..1230 with the element at the kebab's centre the date, before; date
1010..1195, kebab 1202..1230 (a 6px gap) and the kebab the hit, after.
"""

from __future__ import annotations

from pathlib import Path
from tests._css_paths import FORMER_08, sheets

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "frontend" / "css"


def _rule(css: str, selector: str) -> str:
    start = css.index(selector + " {")
    return css[start : css.index("}", start)]


def test_the_time_stops_short_of_the_kebab_by_a_gap_token() -> None:
    css = sheets(*FORMER_08)
    rule = _rule(css, "  #reminder-groups li .entry-meta > .entry-date")
    # The kebab's own size, `--target-min`: it is 44px under 820 and a fixed
    # 1.75rem left it 10px over the time at 768 (wrapzoom sweep).
    assert "margin-inline-end: calc(var(--target-min) + var(--space-2))" in rule


def test_on_hover_the_strip_takes_the_times_place_rather_than_a_slice_of_it() -> None:
    """wrapzoom sweep, every width: the 222px strip lay over the 250px time, so
    29px of "Wed," showed beside "+1h"; a short time let it run over the words.
    The time leaves the row on hover and the strip joins the row's flow."""
    css = sheets(*FORMER_08)
    hover = "  #reminder-groups li:is(:hover, :focus-within) .entry-meta > "
    assert "display: none" in _rule(css, hover + ".entry-date")
    strip = _rule(css, hover + ".entry-actions")
    assert "position: static" in strip and "transform: none" in strip


def test_the_kebab_takes_presses_at_rest_and_only_the_other_actions_wait_for_hover() -> None:
    wide = sheets(*FORMER_08)
    assert "pointer-events: auto" in _rule(wide, "  #reminder-groups li .entry-meta > .entry-actions > .menu-wrap")
    strip = _rule(wide, "  #reminder-groups li .entry-meta > .entry-actions")
    assert "pointer-events: none" in strip and "background" not in strip
    base = (CSS / "03-dashboard-widgets.css").read_text(encoding="utf-8")
    assert "#tab-reminders .entry-actions > :not(.menu-wrap) {\n  opacity: 0;" in base
    assert "#tab-reminders .entry-actions {\n  opacity: 0" not in base
