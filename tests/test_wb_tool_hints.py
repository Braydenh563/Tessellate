"""L-whiteboard-10: the first time a board tool is held on this device, one line says what it does; the
dismissal is remembered per tool in prefs (`wb-tool-hint-<tool>`). Runs the module in node."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests._app_js import frontend_text

INDEX = Path(__file__).resolve().parent.parent / "frontend" / "index.html"


def _run(calls: list[str], stored: dict | None = None) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = f"""
const saved = {json.dumps(stored or {})};
const toasts = [];
const document = {{ getElementById: () => null }};
const onSurface = () => {{}};
const prefs = {{ get: (k, d) => saved[k] ?? d, set: (k, v) => (saved[k] = v) }};
const toast = (t, kind) => toasts.push([t, kind]);
const wbFmtState = {{}};
{frontend_text("whiteboard-hints.js")}
const shown = {json.dumps(calls)}.map((t) => wbFmtState.hints.toolHint(t));
console.log(JSON.stringify({{ shown, toasts, saved }}));
"""
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


def test_a_tool_is_hinted_once_and_remembered_per_tool():
    got = _run(["draw", "draw", "eraser"])
    assert got["shown"][0] and got["shown"][1] == "" and got["shown"][2]
    assert got["saved"] == {"wb-tool-hint-draw": "seen", "wb-tool-hint-eraser": "seen"}
    assert [t[1] for t in got["toasts"]] == ["info", "info"]


def test_a_remembered_dismissal_stays_quiet():
    got = _run(["draw"], {"wb-tool-hint-draw": "seen"})
    assert got["shown"] == [""] and got["toasts"] == []


def test_every_tool_button_has_a_hint_in_plain_copy():
    tools = sorted(set(re.findall(r'data-tool="([a-z0-9-]+)"', INDEX.read_text(encoding="utf-8"))))
    got = _run(tools)
    assert all(got["shown"]), [t for t, s in zip(tools, got["shown"]) if not s]
    for line in got["shown"]:
        assert chr(8212) not in line and "!" not in line and line.endswith(".")


def test_the_tool_switch_asks_for_the_hint():
    assert "wbFmtState.hints?.toolHint(tool)" in frontend_text("whiteboard.js")
