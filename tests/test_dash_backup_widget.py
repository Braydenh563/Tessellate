"""L591: the backup schedule and its last success on the dashboard, not only
in Settings, About and Health. `dashBackupWords` is pure and runs in node."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DAY = (ROOT / "frontend" / "js" / "dash-day.js").read_text(encoding="utf-8")
DASH = (ROOT / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")
ENTRIES = (ROOT / "frontend" / "js" / "lazy-entries.js").read_text(encoding="utf-8")

NOW = "2026-11-14T12:00:00+00:00"


def _words(run, newest):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    start = DAY.index("function dashBackupWords")
    end = DAY.index("//: end dashBackupWords")
    script = (
        "const parseServerTime = (s) => new Date(s);\n"
        "const relativeTime = (s) => 'REL(' + s + ')';\n"
        + DAY[start:end]
        + f"\nprocess.stdout.write(JSON.stringify(dashBackupWords({json.dumps(run)}, {json.dumps(newest)}, new Date('{NOW}'))));"
    )
    done = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_a_fresh_backup_says_when_and_when_the_next_is_due():
    got = _words({"ran": True, "status": "ok", "schedule": "Once a day."}, {"created_at": "2026-11-14T08:00:00+00:00"})
    assert got["state"] == "ok"
    assert "REL(2026-11-14T08:00:00+00:00)" in got["big"]
    assert "Once a day." in got["sub"]
    assert "Next due" in got["sub"]


def test_an_old_backup_is_due_at_the_next_start():
    got = _words({"ran": True, "status": "ok"}, {"created_at": "2026-11-10T08:00:00+00:00"})
    assert "Due at the next start" in got["sub"]


def test_a_failed_last_try_is_said_not_hidden_behind_an_older_success():
    got = _words({"ran": True, "status": "failed", "error": "disk full"}, {"created_at": "2026-11-13T08:00:00+00:00"})
    assert got["state"] == "failed"
    assert "disk full" in got["sub"]
    assert "REL(" in got["big"]


def test_no_backup_yet_is_its_own_state():
    got = _words(None, None)
    assert got["state"] == "none"


def test_the_widget_is_registered_opt_in_and_stands_in_lazily():
    assert "backups: { title:" in DASH
    assert "renderBackupsWidget" in DASH
    assert '"backups"' in DASH.split("const DASH_OPT_IN")[1].split("\n")[0]
    assert "renderBackupsWidget" in ENTRIES
    assert "renderBackupsWidget" in DAY
