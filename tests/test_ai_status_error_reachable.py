"""The status dot's red error state can be reached (L-world-class-184, IDEAS.md
"check that the status dot's error state in the top bar can be reached").
`aiStatusState` runs in node over the two ways it says "error": the server
stops answering after it has answered once, and the search model fails to
load when meaning search was allowed. The poll's catch must drop the status
for those to show, and the CSS must paint the level."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parent.parent
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _function(src: str, name: str) -> str:
    start = src.index(f"function {name}(")
    depth, i = 0, src.index("{", start)
    while True:
        depth += {"{": 1, "}": -1}.get(src[i], 0)
        i += 1
        if depth == 0:
            return src[start:i]


def _state(model_status, ever_answered: bool) -> dict:
    body = _function(app_js_text(), "aiStatusState")
    script = (
        f"let modelStatus = {json.dumps(model_status)}; let statusEverAnswered = {json.dumps(ever_answered)};\n"
        f"{body}\nprocess.stdout.write(JSON.stringify(aiStatusState()));"
    )
    run = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(run.stdout)


@needs_node
def test_the_first_unanswered_poll_is_quiet_not_red():
    assert _state(None, False)["level"] == "idle"


@needs_node
def test_a_server_that_stops_answering_turns_the_dot_red():
    state = _state(None, True)
    assert state["level"] == "error"
    assert state["title"] == "Can't reach Tessellate"


@needs_node
def test_a_search_model_that_failed_to_load_turns_the_dot_red():
    status = {"ollama_running": True, "embedding_ready": False, "embedding_error": "model file is damaged", "semantic_off": False}
    assert _state(status, True)["level"] == "error"
    status["semantic_off"] = True
    assert _state(status, True)["level"] == "off"


def test_a_failed_poll_drops_the_status_so_the_red_state_shows():
    src = app_js_text()
    catch = src[src.index("A slow answer keeps the last good status") :][:900]
    #: Only a server that does not answer drops it (L70, L79): a failed poll while it answers keeps the last status.
    assert re.search(r"if \(!up\) modelStatus = null;", catch), catch
    assert "button.dataset.level = state.level;" in _function(src, "renderAiPill")


def test_the_red_state_is_painted_with_its_glyph():
    css = (ROOT / "frontend/css/00-tokens-shell.css").read_text(encoding="utf-8")
    assert re.search(r'\.ai-status\[data-level="error"\]\s*\{[^}]*color', css)
    assert 'error: "✕"' in app_js_text()
