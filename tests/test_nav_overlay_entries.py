"""The manual and Statistics are places in the nav history (INBOX 1335), and no
row of the history list is crushed when the list scrolls (the owner, 2026-10-19).

Measured in Chromium at 1440x900 (untracked sweeps, scratchpad is at its cap):
with 8 rows the list scrolls (clientHeight 382, scrollHeight 543) and the
current row was 32px with scrollHeight 42 (subtitle clipped) against 52.5px for
the others; with `.nav-history-menu > * { flex: none }` every row is 52.5px.
The manual and Statistics each add one entry (stack 4 to 5), the list names
them, Back closes them, Forward reopens Statistics, the X steps back off.
These are the shapes the suite can see.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"


def _read(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def test_the_manual_and_statistics_record_a_visit_when_they_open():
    assert 'recordTabVisit("manual")' in _read("manual.js")
    assert 'recordTabVisit("statistics")' in _read("statistics.js")


def test_overlay_entries_are_named_routed_and_restorable():
    nav = _read("navigation.js")
    assert "ROUTE_VIEW_NAMES[name]" in nav
    # The labels are added by the lazy file, so the boot pays nothing for them.
    assert 'Object.assign(ROUTE_VIEW_NAMES, { manual: "Manual", statistics: "Statistics" })' in _read("router-overlays.js")
    # Overlays close before the settings branch returns, so Back from the
    # manual to a Settings entry closes the manual.
    restore = nav[nav.index("async function openHistoryEntry") :]
    assert restore.index("overlayGo(entry)") < restore.index('entry.tab === "settings"')
    lazy = _read("router-overlays.js")
    assert "async function overlayGo(" in lazy
    assert 'entry.tab === "manual"' in lazy and 'entry.tab === "statistics"' in lazy


def test_closing_an_overlay_steps_back_unless_it_is_leaving_for_somewhere():
    assert "function overlayClosed(" in _read("router-overlays.js")
    assert 'overlayClosed("manual"' in _read("manual.js")
    assert 'overlayClosed("statistics"' in _read("statistics.js")
    assert "close?.({ stay: true })" in _read("manual.js")
    assert "close?.({ stay: true })" in _read("statistics.js")


def test_browser_back_does_not_swallow_the_overlay_step():
    assert "OVERLAY_TABS[tabHistory.stack[tabHistory.index]?.tab]" in _read("router-overlays.js")


def test_history_rows_have_icons_for_the_overlays():
    assert 'manual: "book-open-text"' in _read("nav-history.js")
    assert 'statistics: "chart-bar"' in _read("nav-history.js")


def test_no_history_row_shrinks_when_the_list_scrolls():
    css = (ROOT / "frontend" / "css" / "nav-history-lazy.css").read_text(encoding="utf-8")
    assert ".nav-history-menu > * {\n  flex: none;\n}" in css
