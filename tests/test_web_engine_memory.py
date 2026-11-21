"""The web panel's engine control is drawn from the last known state, not after the status call.

The owner (2026-10-10): the "Start SearXNG" button "doesnt appear for a while". With
a slow Docker the status call takes seconds and the menu had nothing to draw
from on a fresh page load (driven: 4017 ms with the call held 4000 ms)."""

from __future__ import annotations

from pathlib import Path

from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]


def _chat_js() -> str:
    text = app_js_text()
    start = text.index("let webEngineInfo = prefs.json(")
    return text[start : start + 4000]


def test_the_engine_starts_from_the_remembered_state():
    body = _chat_js()
    assert body.startswith('let webEngineInfo = prefs.json("webEngine");')


def test_a_settled_status_is_remembered():
    body = (ROOT / "frontend" / "js" / "web-results.js").read_text(encoding="utf-8")
    refresh = body[body.index("async function refreshWebSearxngStrip()") :]
    assert 'prefs.setJSON("webEngine", webEngineInfo)' in refresh
