"""Source text: the overdue triage menu is a heading kebab in shell-reminders.js
(handlers in the lazy reminder-edit.js) whose bulk moves need a browser to press; the source pins its shape (L-general-12).

Overdue reminders pile up; the Overdue heading carries one menu that moves
them all on (tomorrow, next week), ticks them all off or bins them, each with
one Undo for the whole batch.
"""

from __future__ import annotations

from tests._app_js import frontend_text


def _triage() -> str:
    # The menu is built at boot (shell-reminders.js); its handlers moved to the
    # lazy reminder-edit.js for the boot gzip ratchet, so the shape spans both.
    source = frontend_text("shell-reminders.js")
    start = source.index("loadReminders.overdueTriage = function (items) {")
    menu = source[start : source.index("\n};\n", start)]
    lazy = frontend_text("reminder-edit.js")
    start = lazy.index("loadReminders.overdueRun = function (choice, items) {")
    return menu + lazy[start : lazy.index("return choices[choice]();", start)]


def test_the_overdue_heading_carries_a_triage_menu():
    source = frontend_text("shell-reminders.js")
    assert 'label === "Overdue" && items.length > 1' in source
    assert "loadReminders.overdueTriage(items)" in source


def test_the_menu_moves_ticks_or_bins_them_all_with_one_undo():
    body = _triage()
    for label in ("Move all to tomorrow 9am", "Move all to next Monday 9am", "Mark all done", "Delete all"):
        assert label in body
    # One Undo per batch, never one per reminder: the moves and ticks share
    # run()'s, and Delete all pushes its own (restore back, drop again), so
    # Ctrl+Z reaches a binned batch too (L-general-63, undo coverage).
    assert body.count("pushUndo(") == 2
    assert "pushUndo(`Moved ${n} to the bin`, restore, drop)" in body
    assert "kebabMenu(" in body and "confirmDialog(" in body
