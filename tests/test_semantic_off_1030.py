"""Audit 1030 Y2: search by meaning that was never allowed to download (the
one-time question still open, or answered no) showed as an error in three
places: a red "Search AI didn't load" chip, a "not working" toast and a bell
row. It is a choice, not a fault: the server says `semantic_off` and the
chip, toast and bell read it. An install that was allowed and failed is
still an error. No clock is read: the functions run with stubs."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tessellate.core import deps

ROOT = Path(__file__).resolve().parent.parent
STATUS = (ROOT / "frontend" / "js" / "status.js").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _function(text: str, name: str) -> str:
    start = re.search(rf"\n(?:async )?function {name}\(", text).start() + 1
    return text[start : text.index("\n}\n", start) + 2]


def _run(status: dict) -> dict:
    script = (
        "let statusEverAnswered = true; let embeddingNudgeSaid = ''; const said = [];"
        "function recordNotification(n) { said.push(['bell', n.title]); }"
        "function toastAction(t) { said.push(['toast', t]); }"
        "function embeddingToastDue() { return true; }"
        "function embeddingProblemDetail(e) { return e; }"
        "function openSettingsModal() {}"
        f"let modelStatus = {json.dumps(status)};"
        + _function(STATUS, "aiStatusState")
        + _function(STATUS, "nudgeEmbeddingProblem")
        + "nudgeEmbeddingProblem(); console.log(JSON.stringify({chip: aiStatusState(), said}));"
    )
    run = subprocess.run([shutil.which("node"), "-e", script], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


NOT_INSTALLED = "Search by meaning is not installed yet; search uses keywords until you allow the download."


@needs_node
def test_search_by_meaning_off_by_choice_is_neutral_everywhere():
    out = _run({"ollama_running": False, "embedding_ready": False, "embedding_error": NOT_INSTALLED, "semantic_off": True})
    assert out["chip"]["level"] == "off", out
    assert "didn't load" not in out["chip"]["title"]
    assert out["said"] == [], out


@needs_node
def test_an_allowed_install_that_failed_is_still_an_error():
    out = _run({"ollama_running": False, "embedding_ready": False, "embedding_error": "The model files would not load.", "semantic_off": False})
    assert out["chip"]["level"] == "error", out
    assert [kind for kind, _ in out["said"]] == ["bell", "toast"], out


def test_the_status_says_when_search_by_meaning_is_off(client, monkeypatch):
    monkeypatch.setattr(deps.get_embeddings(), "awaiting_consent", True, raising=False)
    assert client.get("/models/status").json()["semantic_off"] is True
