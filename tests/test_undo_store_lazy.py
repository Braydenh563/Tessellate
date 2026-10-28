"""A costly undo snapshot is taken once per pause, not per keystroke (audit 1028 D6).

`docHistoryPersist` serialised the document's whole CodeMirror history on
every change; the store's write was debounced but the snapshot was not.
`undoStorePut` now takes a function and calls it only when the write runs.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

STORE = Path(__file__).resolve().parent.parent / "frontend" / "js" / "undo-store.js"
DOCS = Path(__file__).resolve().parent.parent / "frontend" / "js" / "documents.js"


def _function(source: str, head: str) -> str:
    start = source.index(head)
    return source[start : source.index("\n}\n", start) + 3]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_a_function_value_is_called_once_after_many_puts():
    put = _function(STORE.read_text(encoding="utf-8"), "function undoStorePut(")
    script = (
        "const undoStoreTimers = new Map(); const UNDO_STORE_DELAY_MS = 5; const written = [];\n"
        "function undoStoreRequest(mode, fn) { fn({ put: (v, k) => written.push([k, v]) }); }\n"
        + put
        + "\nlet calls = 0;\nfor (let i = 0; i < 50; i++) undoStorePut('doc:1', () => { calls++; return { n: i }; });\n"
        "setTimeout(() => console.log(JSON.stringify({ calls, written })), 30);\n"
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True)
    assert out.stdout.strip() == '{"calls":1,"written":[["doc:1",{"n":49}]]}'


def test_the_document_history_is_handed_over_as_a_function():
    body = _function(DOCS.read_text(encoding="utf-8"), "function docHistoryPersist(")
    assert "() => state.toJSON(" in body
