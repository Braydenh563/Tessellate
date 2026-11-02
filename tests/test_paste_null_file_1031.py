"""The owner's log, 2026-10-31: a paste threw `Cannot read properties of null
(reading 'type')` in settings-wiring.js, because `DataTransferItem.getAsFile`
answers null for a file item the browser will not hand over."""

from __future__ import annotations

from tests._app_js import app_js_text


def test_a_null_file_item_is_skipped():
    js = app_js_text()
    start = js.index('document.addEventListener("paste"')
    body = js[start : start + 900]
    assert "files.push(item.getAsFile())" not in body
    assert "if (file) files.push(file);" in body
