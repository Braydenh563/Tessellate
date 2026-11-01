"""One lane per kind of work, from the server (audit 1031 HR4, HR6, SH3, AR6).

Three client lists said which jobs are "turns a person asked for" (`WATCHED_RUN_KINDS`,
`TASK_TURN_KINDS`, `routes_tasks.WATCHED_KINDS`) and they had drifted: a kind in one was
missing from another. The server now names the lane on every running and finished row
(`jobruns.lane_of`), and the panel, the history fold and the bell read that one field.
"""

from __future__ import annotations

from pathlib import Path

from tessellate.core import jobruns

ROOT = Path(__file__).resolve().parents[1]


def _js(name: str) -> str:
    return (ROOT / "frontend" / "js" / name).read_text(encoding="utf-8")


def test_the_lane_table():
    for kind in ("generation", "ai-call", "model-info", "transcription", "ocr", "run"):
        assert jobruns.lane_of(kind) == "user", kind
    for kind in ("backup", "reindex", "import", "maintenance", "job-ocr", "autonomous", ""):
        assert jobruns.lane_of(kind) == "background", kind


def test_a_finished_row_carries_its_lane():
    jobruns.clear_finished()
    run = jobruns.Run("ai-call", None, title="Draft title", origin="you")
    run.start()
    run.finish()
    other = jobruns.Run("backup", None, title="Backup", origin="you")
    other.start()
    other.finish()
    rows = {row["kind"]: row for row in jobruns.merged_history([])}
    assert rows["ai-call"]["lane"] == "user"
    assert rows["backup"]["lane"] == "background"
    jobruns.clear_finished()


def test_a_history_entry_from_taskhistory_carries_its_lane():
    rows = jobruns.merged_history(
        [{"kind": "generation", "label": "Chat", "outcome": "completed", "at": "2026-10-31T10:00:00+00:00"}]
    )
    assert rows[0]["lane"] == "user"


def test_a_running_row_carries_its_lane_and_watched_follows_it():
    from tessellate.api import routes_tasks

    jobruns.clear_live()
    run = jobruns.Run("generation", None, title="Answering 'hello'", origin="you")
    run.start()
    try:
        rows = routes_tasks.collect()
        mine = [row for row in rows if row.get("run_id") == run.id]
        assert mine and mine[0]["lane"] == "user" and mine[0]["watched"] is True
        assert all("lane" in row for row in rows)
    finally:
        run.finish()
        jobruns.clear_live()


def test_the_client_keeps_no_copy_of_the_lists():
    tools = _js("ai-tools.js")
    tasks = _js("chat-tasks.js")
    assert "WATCHED_RUN_KINDS" not in tools + tasks
    assert "TASK_TURN_KINDS" not in tools + tasks
    assert 'item.lane === "user"' in tasks
    assert not hasattr(__import__("tessellate.api.routes_tasks", fromlist=["x"]), "WATCHED_KINDS")


def test_the_history_fold_and_the_bell_read_the_lane():
    """Run the real `renderTaskHistory` with a tiny DOM: user-lane rows fold, background rows list."""
    import json
    import shutil
    import subprocess

    import pytest

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    source = _js("chat-tasks.js")
    start = source.index("function taskEndingIsUpkeep(")
    end = source.index("function taskHistoryRow(")
    script = r"""
const log = { bell: [], rows: [] };
class El {
  constructor(tag) { this.tag = tag; this.children = []; this.className = ""; this.open = false; this.textContent = ""; this.classList = { toggle() {} }; }
  appendChild(c) { this.children.push(c); return c; }
  append(...c) { this.children.push(...c); }
  replaceChildren(...c) { this.children = c; }
  querySelector() { return null; }
}
const els = { "task-history-box": new El("div"), "task-history": new El("ul") };
globalThis.$ = (id) => els[id];
globalThis.document = { createElement: (t) => new El(t), getElementById: (id) => els[id] };
globalThis.QUIET_TASK_KINDS = new Set();
globalThis.settleStartedNotification = () => false;
globalThis.recordNotification = (n) => log.bell.push(n.title);
globalThis.taskHistoryRow = (item) => { log.rows.push(item.label); return new El("li"); };
""" + source[start:end] + r"""
renderTaskHistory([
  { kind: "generation", label: "Answering hello", outcome: "completed", origin: "you", lane: "user", at: "a" },
  { kind: "ai-call", label: "Draft title", outcome: "completed", origin: "app", lane: "user", at: "b" },
  { kind: "backup", label: "Backup", outcome: "completed", origin: "you", lane: "background", at: "c" },
  { kind: "import", label: "Import failed", outcome: "failed", origin: "you", lane: "background", at: "d" },
]);
const fold = els["task-history"].children.find((c) => c.children[0] && c.children[0].tag === "details");
console.log(JSON.stringify({ bell: log.bell, rows: log.rows, folded: Boolean(fold) }));
"""
    done = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    result = json.loads(done.stdout.strip().splitlines()[-1])
    # The answer you watched and the app's own draft call are not announced; a backup you started
    # and a failure are.
    assert result["bell"] == ["Backup", "Import failed"]
    # Background rows are the list; the two user-lane rows sit in the fold (drawn by taskHistoryRow too).
    assert result["rows"].count("Backup") == 1 and result["rows"].count("Import failed") == 1
    assert result["folded"] is True
