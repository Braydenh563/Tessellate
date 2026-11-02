"""Audit 1031 Z20: the destructive space delete says so, asks for the name, and is explicit."""
from __future__ import annotations

from pathlib import Path

from tests._app_js import app_js_text

HTML = (Path(__file__).resolve().parents[1] / "frontend" / "index.html").read_text(encoding="utf-8")


def test_dialog_names_the_bin_skip_and_asks_for_the_name():
    assert "This skips the bin and cannot be undone." in HTML
    assert 'id="space-delete-confirm"' in HTML
    js = app_js_text()
    assert "?purge=1" in js and "spaceDeleteNeedsName" in js


def test_the_wipe_is_never_sent_without_the_explicit_flag():
    js = app_js_text()
    body = js[js.index("async function spaceDeleteSubmit"):]
    assert '"?purge=1"' in body and 'moveTo ? `?move_to=' in body
