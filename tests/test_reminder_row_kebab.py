"""The Reminders row's date and its ⋯ never share pixels, and the ⋯ takes a
plain click (the owner, 2026-10-27: both right edges measured 1230 and a plain
Playwright click was intercepted until the row was hovered).

Measured by `scratchpad/ui-sweeps/remkebab.js` at 1280: date 1045..1230 and
kebab 1202..1230 with the element at the kebab's centre the date, before; date
1010..1195, kebab 1202..1230 (a 6px gap) and the kebab the hit, after.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "frontend" / "css"


def _rule(css: str, selector: str) -> str:
    start = css.index(selector + " {")
    return css[start : css.index("}", start)]


def test_the_time_stops_short_of_the_kebab_by_a_gap_token() -> None:
    css = (CSS / "08-consistency.css").read_text(encoding="utf-8")
    rule = _rule(css, "  #reminder-groups li .entry-meta > .entry-date")
    assert "margin-inline-end: calc(1.75rem + var(--space-2))" in rule


def test_the_kebab_takes_presses_at_rest_and_only_the_other_actions_wait_for_hover() -> None:
    wide = (CSS / "08-consistency.css").read_text(encoding="utf-8")
    assert "pointer-events: auto" in _rule(wide, "  #reminder-groups li .entry-meta > .entry-actions > .menu-wrap")
    strip = _rule(wide, "  #reminder-groups li .entry-meta > .entry-actions")
    assert "pointer-events: none" in strip and "background" not in strip
    base = (CSS / "03-dashboard-widgets.css").read_text(encoding="utf-8")
    assert "#tab-reminders .entry-actions > :not(.menu-wrap) {\n  opacity: 0;" in base
    assert "#tab-reminders .entry-actions {\n  opacity: 0" not in base
