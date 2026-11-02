"""Undo histories survive a reload (INBOX 553(b), the owner's decision;
WHITEBOARD_PLAN decision 17 as amended).

The round trip is driven in a browser by
`scratchpad/ui-sweeps/mmdoc1005-undoreload.js` (a map's two typed topics and
a document's edit, reloaded, then Ctrl+Z); these pin the wiring the sweep
relies on and the two rules that keep it safe.
"""

from __future__ import annotations

import re
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
STORE = (JS / "undo-store.js").read_text(encoding="utf-8")
APP = (JS / "app.js").read_text(encoding="utf-8")
WB = (JS / "whiteboard.js").read_text(encoding="utf-8")
DOCS = (JS / "documents.js").read_text(encoding="utf-8")


def test_the_store_loads_first_in_the_library_bundle():
    bundle = re.search(r"library: \[(.*?)\]", APP, re.S).group(1)
    files = re.findall(r'"(/js/[^"]+)"', bundle)
    assert files[0] == "/js/undo-store.js"


def test_it_keeps_a_hundred_steps_on_this_device():
    assert "const UNDO_STORE_MAX = 100;" in STORE
    assert "indexedDB.open(" in STORE
    assert "fetch(" not in STORE and "apiJson(" not in STORE


def test_a_board_writes_only_after_its_stored_history_was_read():
    """Otherwise an open quicker than the read would store an empty history
    over the real one."""
    update = WB[WB.index("function wbUpdateUndoRedoButtons()"):][:600]
    assert "wbHistoryRead.has(wbHistoryBoard)" in update
    assert "undoStorePut(`board:${wbHistoryBoard}`" in update


def test_a_document_history_comes_back_only_over_its_own_text():
    restore = DOCS[DOCS.index("function docHistoryRestore("):][:900]
    assert "stored.doc !== text" in restore
    #: The editor's text is read through `docStr` since audit 1028 D19 (7add0bf,
    #: joined once per version); the check itself is unchanged.
    assert "docStr(docCmView.state.doc) !== text" in restore


def test_the_lock_empties_the_store():
    watch = DOCS[DOCS.index("function docWatchLock()"):][:1500]
    assert "undoStoreClear()" in watch
