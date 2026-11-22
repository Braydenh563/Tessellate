"""Source text: the Activity panel (Agent runs, bottom right) floats and takes no room (the owner, 2026-11-22).

With it open, every tab's scroller gained 18rem of padding: the dashboard's scroll height went 1459 to 1747 px at
1440x900 and 3663 to 3951 at 390x844, and shrank back on close. After: equal open and closed on Dashboard,
Reminders, Notes, Timeline and Library at both widths (scratchpad/lag/panelroom.js, BEFORE_DIR for the old files).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_no_rule_gives_room_for_the_open_activity_panel() -> None:
    css = "".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "frontend" / "css").glob("*.css")))
    assert "has-agent-monitor" not in css


def test_opening_the_panel_does_not_mark_the_page() -> None:
    js = (ROOT / "frontend" / "js" / "agent-activity.js").read_text(encoding="utf-8")
    assert "has-agent-monitor" not in js
