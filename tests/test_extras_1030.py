"""Audit 1030 extras, the small rows.

- Y4: every space row's actions were "Delete this space", "Rename this
  space": nine of each with nine spaces. Each names its space.
- Y8: a space named "ALL" sat beside "All spaces" in the switcher. "All",
  "All spaces" and "Everything" are refused as names (a restore keeps its own).
- Y13: no file manager for the lock card's logs folder answered 500, a server
  fault in the log; it is 503.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from test_forgot_password import (  # noqa: F401  # the fixtures are autouse there
    _clean,
    _devices_already_allowed,
    _known_code,
    _local,
    _notebook,
)

ROOT = Path(__file__).resolve().parent.parent
SPACES_JS = (ROOT / "frontend" / "js" / "spaces-find.js").read_text(encoding="utf-8")


def test_each_space_action_names_its_space():
    assert "this space" not in SPACES_JS.split("function spaceMenuOption", 1)[1].split("\n}\n", 1)[0]
    for label in ("`Rename ${name}`", "`Delete ${name}`", "`Hide ${name} from All spaces`"):
        assert label in SPACES_JS


@pytest.mark.parametrize("name", ["ALL", "all spaces", " All  Spaces ", "Everything"])
def test_the_everything_view_names_are_not_space_names(client, name):
    response = client.post("/spaces", json={"name": name})
    assert response.status_code == 400, response.text
    assert "view of every space" in response.json()["detail"]


def test_an_ordinary_name_with_all_in_it_is_fine(client):
    response = client.post("/spaces", json={"name": "All hands"})
    assert response.status_code in (200, 201)


def test_a_reserved_name_cannot_come_in_by_rename(client):
    sid = client.post("/spaces", json={"name": "Garden plot"}).json()["id"]
    response = client.put(f"/spaces/{sid}", json={"name": "All"})
    assert response.status_code == 400


def test_no_file_manager_for_the_logs_folder_is_503(client, monkeypatch):
    from tessellate.api import routes_files

    _notebook(client)

    def refuse(folder, label):
        raise HTTPException(status_code=500, detail=f"no file manager for {folder}")

    monkeypatch.setattr(routes_files, "reveal_folder", refuse)
    response = _local(client).post("/auth/reset-code/open-logs")
    assert response.status_code == 503
    assert "/" not in response.json()["detail"]


def test_a_clip_with_no_text_makes_no_note(client):
    """Y12: a bookmarklet on a blank page made "# 127.0.0.1 / The page had no
    text to keep." notes."""
    before = len(client.get("/entries").json())
    response = client.post("/links/clip-page", json={"url": "https://blank.example/", "title": "", "html": "", "selection": ""})
    assert response.status_code == 422
    after = client.get("/entries").json()
    assert len(after) == before


@pytest.mark.parametrize(("name", "data", "status"), [
    ("a.png", b"not a png at all", 415),
    ("a.jpg", b"GIF89a fake", 415),
    ("a.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 8, 200),
    ("a.gif", b"GIF89a" + b"\x00" * 8, 200),
    ("a.pdf", b"%PDF-1.7\n", 200),
])
def test_a_picture_must_open_the_way_its_type_does(client, name, data, status):
    """Y15: 16 bytes of text named .png were kept and served as image/png."""
    response = client.post("/media/upload", files={"file": (name, data, "image/png")})
    assert response.status_code == status, response.text


def test_a_failed_space_name_is_marked_on_its_field():
    """Y14: the dialogs said the error but left the field unmarked; they use
    the lock card's failure helper (aria-invalid, aria-describedby, focus)."""
    for field in ("space-create-name", "space-edit-name"):
        assert f'const fail = (message) => lockFail(message, $("{field}"), error);' in SPACES_JS
    assert "error.textContent = err.message" not in SPACES_JS


def test_the_update_question_waits_for_open_dialogs():
    """Y17: it opened over a recording 5 s after boot and took its clicks."""
    js = (ROOT / "frontend" / "js" / "update-dialogs.js").read_text(encoding="utf-8")
    ask = js.split("async function askUpdateChoiceOnce", 1)[1]
    assert ask.index("await untilNoDialogOpen();") < ask.index("firstRunTurn(ask")
    assert 'document.querySelector("dialog[open], .modal-overlay:not(.hidden)")' in js


@pytest.mark.parametrize(("typed", "kept"), [
    ("<img src=x onerror=alert(1)> Ada", "img src=x onerror=alert(1) Ada"),
    ("  Ada‮  Lovelace\n", "Ada Lovelace"),
    ("Zoë", "Zoë"),
])
def test_the_display_name_is_a_name_not_markup(client, typed, kept):
    """Y9: markup and control characters showed in the greeting and the
    Profile heading as typed."""
    response = client.put("/preferences", json={"display_name": typed})
    assert response.status_code == 200, response.text
    assert response.json()["display_name"] == kept


def _node(script: str):
    import json
    import shutil
    import subprocess

    if not shutil.which("node"):
        pytest.skip("needs node")
    run = subprocess.run([shutil.which("node"), "-e", script], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def _js_function(path: str, name: str) -> str:
    import re

    text = (ROOT / path).read_text(encoding="utf-8")
    start = re.search(rf"\n(?:async )?function {name}\(", text).start() + 1
    return text[start : text.index("\n}\n", start) + 2]


def test_the_week_change_says_last_weeks_count_once():
    """Y10: "14 more than last week (0)"."""
    said = _node(_js_function("frontend/js/statistics.js", "statsChange")
                 + "console.log(JSON.stringify([statsChange(14, 0), statsChange(3, 5), statsChange(2, 2)]))")
    assert said == ["up from 0 last week", "down from 5 last week", "the same as last week"]


def test_not_used_lately_waits_for_a_ledger_older_than_its_window():
    """Y10: a day-old notebook listed 112 commands as not used lately."""
    script = (
        "async function ensureModule() {} function usageLabels() { return {a: 'A', b: 'B', c: 'C'}; }"
        + _js_function("frontend/js/statistics.js", "statsUnused")
        + "(async () => { const young = await statsUnused({unused_days: 90, features: [{name: 'a', first: '2026-10-29', last: '2026-10-30'}]}, '2026-10-30T12:00:00Z');"
        + " const old = await statsUnused({unused_days: 90, features: [{name: 'a', first: '2026-01-02', last: '2026-10-30'}]}, '2026-10-30T12:00:00Z');"
        + " console.log(JSON.stringify([young.unused, old.unused])); })();"
    )
    assert _node(script) == [None, ["b", "c"]]


def test_a_new_notebook_is_not_a_productive_week():
    """Y18: fourteen notes made seconds ago were "A productive week"."""
    from tessellate.ai import greeting_compose as g

    new = g._context_phrases(g.NotebookFacts(total=14, today=14, this_week=14), "morning")
    worked = g._context_phrases(g.NotebookFacts(total=40, today=2, this_week=12), "morning")
    assert ("A productive week", ".") not in new
    assert ("A productive week", ".") in worked


def test_a_timer_arms_a_one_shot_at_its_end():
    """Y6: only the one-second interval noticed the end, and a hidden tab runs
    it about once a minute, so "Time is up" came up to a minute late."""
    script = (
        "const utilityTick = { id: 0, end: 0 }; const armed = [];"
        "let utilityClocks = [{kind: 'timer', end: 1000 + 90000}, {kind: 'timer', end: 1000 + 30000}, {kind: 'stopwatch', start: 0}];"
        "Date.now = () => 1000; function paintUtilityChip() {}"
        "globalThis.setInterval = () => 7; globalThis.clearInterval = () => {}; globalThis.clearTimeout = () => {};"
        "globalThis.setTimeout = (fn, ms) => { armed.push(ms); return 9; };"
        + _js_function("frontend/js/utility-tools.js", "utilityEnsureTick")
        + "utilityEnsureTick(); utilityClocks = [{kind: 'stopwatch', start: 0}]; utilityEnsureTick();"
        + "console.log(JSON.stringify(armed));"
    )
    assert _node(script) == [30050]


def test_y7_upkeep_jobs_stay_out_of_the_bell_unless_they_fail():
    """Audit 1030 Y7: warming, housekeeping, re-dating and backups the app
    starts itself put a "Started:" row in the bell every launch."""
    from tessellate.core import jobs

    assert jobs.LABELS["warm"] == "Warming up"
    status = (ROOT / "frontend/js/status.js").read_text(encoding="utf-8")
    quiet = status.split("const QUIET_TASK_KINDS", 1)[1].split("]);", 1)[0]
    for kind in ("job-warm", "maintenance", "job-maintenance", "redate", "job-redate", "backup"):
        assert f'"{kind}"' in quiet, kind
    assert "if (!QUIET_TASK_KINDS.has(task.kind)) task.noticeId = recordNotification({" in status
    # A failure still reaches the bell, through agentActivityNotice.
    assert 'agentActivityNotice(`Failed: ${ended.label || task.label}`, { isError: true });' in status
    for path in ("src/tessellate/ai/spelling.py", "src/tessellate/search/search_manager.py"):
        assert 'name="warm the' not in (ROOT / path).read_text(encoding="utf-8"), path
