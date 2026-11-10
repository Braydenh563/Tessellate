"""The web panel's engine control is drawn from the last known state, not after the status call.

The owner (2026-10-10): the "Start SearXNG" button "doesnt appear for a while". With
a slow Docker the status call takes seconds and the menu had nothing to draw
from on a fresh page load (driven: 4017 ms with the call held 4000 ms)."""

from __future__ import annotations

from tests._app_js import app_js_text


def _chat_js() -> str:
    text = app_js_text()
    start = text.index("let webEngineInfo = (() => {")
    return text[start : start + 4000]


def test_the_engine_starts_from_the_remembered_state():
    body = _chat_js()
    seed = body[: body.index("})();")]
    assert 'prefs.json("webEngineLast"' in seed
    # Only settled states are drawn from memory; installing and starting pass.
    assert '["running", "stopped", "absent"]' in seed


def test_a_settled_status_is_remembered_and_a_missing_backend_forgets_it():
    body = _chat_js()
    refresh = body[body.index("async function refreshWebSearxngStrip()") :]
    assert refresh.index('prefs.setJSON("webEngineLast", {})') < refresh.index('prefs.setJSON("webEngineLast", { state })')
