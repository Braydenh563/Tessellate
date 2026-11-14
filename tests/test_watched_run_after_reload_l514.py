"""L514: a run its own page watches (a transcription) that is still running
on the first poll after a reload has no page watching it any more, so its
ending is announced. One started on this page stays quiet."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

STATUS = Path(__file__).resolve().parents[1] / "frontend" / "js" / "status.js"


def _run(script: str) -> dict:
    src = STATUS.read_text(encoding="utf-8")
    start = src.index("function noticeTaskTransitions(")
    end = src.index("\n}\n", src.index("function noticeTaskTransitions(")) + 3
    harness = (
        "const notices = [];\n"
        "const seenRunningTasks = new Map(); const backgroundRunRows = new Map();\n"
        "const QUIET_TASK_KINDS = new Set();\n"
        "const taskKey = (t) => `${t.kind}:${t.name}`;\n"
        "const renderAgentRunSummary = () => {}; const endAgentRun = () => {};\n"
        "const addAgentRun = () => ({}); const openPanelForRun = () => {};\n"
        "const recordNotification = () => 'n'; const settleNotification = () => {};\n"
        "const taskEndingWords = () => ({});\n"
        "const agentActivityNotice = (m) => notices.push(m);\n"
        + src[start:end]
        + script
        + "\nconsole.log(JSON.stringify({ notices }));\n"
    )
    out = subprocess.run(["node", "-e", harness], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

T = "{ kind: 'transcribe', name: 'r1', label: 'Transcribing a recording', watched: true, run_id: 'x' }"
DONE = "[{ run_id: 'x', kind: 'transcribe', outcome: 'done', label: 'Transcribing a recording' }]"


def test_a_watched_run_left_over_from_before_a_reload_says_it_finished():
    got = _run(f"noticeTaskTransitions([{T}], []); noticeTaskTransitions([], {DONE});")
    assert got["notices"] == ["Finished: Transcribing a recording"]


def test_a_watched_run_started_on_this_page_stays_quiet():
    got = _run(f"noticeTaskTransitions([], []); noticeTaskTransitions([{T}], []); noticeTaskTransitions([], {DONE});")
    assert got["notices"] == []
