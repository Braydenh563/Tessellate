"""TIMELINE_PLAN rows L474/L476/L480/L484 and L-timeline-3: the Reminders tab on a phone, the closed presets menu, Done in the bell.

Measured in Chromium (390x844, 8 rows): scrolled to the foot the last row ends
at y 683 and the floating + starts at y 730 (47px clear); the + opens a sheet
whose sentence box is at y 398-442, inside the window; at 1440 the closed
Quick set list is display none, 0x0, with 0 overlaps.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._css_paths import css_text

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = re.sub(r"/\*.*?\*/", "", css_text(), flags=re.S)
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def test_the_phone_add_row_is_the_floating_plus_and_its_sheet():
    assert '"reminders-new"' in (JS / "phone-shell.js").read_text(encoding="utf-8")
    assert re.search(r"@media \(max-width: 1099\.98px\)\s*\{\s*#tab-reminders > #reminder-compose\s*\{\s*display: none;", CSS)
    wiring = (JS / "wiring.js").read_text(encoding="utf-8")
    assert 'const REMINDER_SHEET = "(max-width: 1099.98px)";' in wiring
    assert "function openReminderCompose()" in wiring


def test_the_floating_plus_leaves_the_last_row_clear():
    rule = re.search(r"@media \(max-width: 599\.98px\)\s*\{\s*#tab-reminders:has\(> \.dock-fab\)\s*\{([^}]*)\}", CSS)
    assert rule and "padding-bottom: calc(var(--target-min) + var(--space-5) + var(--space-3))" in rule.group(1)


def test_the_closed_quick_set_menu_is_not_laid_out():
    menu = re.search(r'<details class="doc-dock-menu dock-menu" id="reminder-presets-menu">', INDEX)
    assert menu, "the presets menu is a closed details, which the browser does not lay out"
    for block in re.findall(r"#reminder-presets\s*\{([^}]*)\}", CSS):
        assert "display" not in block, "a display on the list would lay it out while the details is closed"


def test_a_reminder_row_in_the_bell_can_be_completed():
    bell = (JS / "notifications.js").read_text(encoding="utf-8")
    status = (JS / "status.js").read_text(encoding="utf-8")
    assert "reminderId: reminder.id," in bell
    assert "reminderId: reminder.early ? null : reminder.id," in status
    body = bell.split("function reminderDoneButton(item) {", 1)[1].split("\n}\n", 1)[0]
    assert "/reminders/${item.reminderId}/complete?tz_offset_minutes=" in body
    assert "row.reminderDone = true" in body
    assert 'item.kind === "reminder" && item.reminderId && !item.reminderDone' in bell
    # Review on #222: Done names the occurrence it was raised for, so a repeat ticked elsewhere
    # since is refused (409) rather than rolled twice, and the row says where it is now.
    assert "expected_due_at=${encodeURIComponent(item.reminderDue)}" in body
    assert "error?.status === 409" in body and "error.detail?.reminder" in body
    # Focus lands on the row's new line (the button is gone) and the live region says it.
    assert "announce(detail)" in body and "meta.focus()" in body
    assert "land(said)" in body and "land(detail)" in body
