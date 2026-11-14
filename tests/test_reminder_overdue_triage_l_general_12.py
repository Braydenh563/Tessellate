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
    # One Undo per batch, never one per reminder: every choice, Delete all
    # too (restore back, drop again), goes through run()'s one pushUndo, so
    # Ctrl+Z reaches a binned batch (L-ui-modernisation-89, undo coverage); the node
    # test below drives it.
    assert body.count("pushUndo(") == 1
    assert "run((m) => `Moved ${m} to the bin`, drop, restore," in body
    assert "kebabMenu(" in body and "confirmDialog(" in body


def _run_in_node(choice: str) -> dict:
    """Run `overdueRun` in node with stand-ins; the reminder with id 2 is refused by the server."""
    import json
    import shutil
    import subprocess

    import pytest

    if not shutil.which("node"):
        pytest.skip("node is not installed")
    lazy = frontend_text("reminder-edit.js")
    start = lazy.index("loadReminders.overdueRun = function (choice, items) {")
    import re

    fn = lazy[start : re.compile(r"return choices\[choice\]\(\);\s*\};").search(lazy, start).end()]
    script = """
const log = { calls: [], reloads: 0, toasts: [], undo: null, actionToast: null };
const loadReminders = () => { log.reloads += 1; };
const apiJson = async (url, opts) => { log.calls.push(opts.method + " " + url); if (url.startsWith("/reminders/2")) throw new Error("refused"); return {}; };
const pushUndo = (label, undo, redo) => (log.undo = { label, undo, redo });
const toast = (text, error) => log.toasts.push([text, !!error]);
const toastAction = (text) => (log.actionToast = text);
const settleUndoFromToast = () => {};
const confirmDialog = async () => true;
const presetDate = () => new Date(2026, 10, 14, 9);
""" + fn + """
(async () => {
  await loadReminders.overdueRun(%s, [1, 2, 3].map((id) => ({ id, due_at: "2026-11-01T09:00:00Z", done: false })));
  const forward = log.calls.length;
  await log.undo.undo();
  process.stdout.write(JSON.stringify({ ...log, forward, back: log.calls.slice(forward), undo: log.undo.label }));
})();
""" % json.dumps(choice)
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, timeout=30).stdout
    return json.loads(out)


def test_one_refused_reminder_does_not_stop_the_batch_or_its_undo():
    # Review 5899359161 (2): Promise.all stopped at the first refusal, skipped the reload and the
    # Undo, though the other rows had changed. Every row is tried, the list always reloads, the
    # failures are counted in an error toast, and Undo reaches the rows that did change.
    for choice, verb in (("tomorrow", "PUT"), ("done", "PUT"), ("bin", "DELETE")):
        log = _run_in_node(choice)
        assert log["forward"] == 3, choice
        assert ["Couldn't change 1 of 3 overdue reminders.", True] in log["toasts"], choice
        assert log["undo"] and "2 overdue reminders" in log["undo"], choice
        assert log["back"] and all("/reminders/2" not in c for c in log["back"]) and len(log["back"]) == 2, choice
        assert log["reloads"] == 2, choice
        assert log["calls"][0].startswith(verb), choice


def test_the_menu_toasts_when_its_handlers_cannot_load():
    # Review 5899359161 (3): a failed lazy load of reminder-edit.js was an unhandled rejection.
    menu = frontend_text("shell-reminders.js")
    start = menu.index("loadReminders.overdueTriage = function (items) {")
    go = menu[start : menu.index("return kebabMenu(", start)]
    assert ".catch((e) => toast(" in go
