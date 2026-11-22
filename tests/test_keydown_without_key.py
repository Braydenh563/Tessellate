"""A keydown with no `key` string reaches the document (the owner's log,
2026-10-10: "Uncaught TypeError: Cannot read properties of undefined (reading
'startsWith')" at whiteboard.js's ring handler, from the desktop webview).
Every document-level keydown handler in the whiteboard that reads `e.key` as
a string returns first when it is not one."""

from tests._app_js import frontend_text
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_whiteboard_document_keydown_handlers_guard_a_missing_key():
    text = frontend_text("whiteboard.js")
    heads = [m.end() for m in re.finditer(r'^\s*document\.addEventListener\("keydown", \(e\) => \{\n', text, re.M)]
    assert len(heads) >= 2
    for start in heads:
        body = text[start:start + 6000]
        reads = re.search(r"\be\.key\.(startsWith|toLowerCase|length)\b", body)
        if not reads:
            continue
        guard = body.find('if (typeof e.key !== "string") return;')
        assert 0 <= guard < reads.start(), text[start:start + 200]
