"""DOCUMENTS_PLAN 24 row 1 (Brief 76): every act on a document is one undo step.

Each act that reaches the server goes through `offerUndo` or `pushUndo`
(status.js, rule 1.8) with the server's own inverse as its undo, and on an
open document Ctrl+Z walks whichever history holds the newer step
(`appStackIsNewer`). Driven for real by `scratchpad/ui-sweeps/docacts76.js`.
"""

from __future__ import annotations

import re

from tests._app_js import JS_DIR, app_js_text

APP = app_js_text() + (JS_DIR / "documents.js").read_text(encoding="utf-8")


def _body(name: str) -> str:
    match = re.search(rf"^(?:async\s+)?function\s+{name}\s*\(", APP, re.M)
    assert match, f"{name} is missing"
    rest = APP[match.end():]
    end = re.search(r"^(?:async\s+)?function\s", rest, re.M)
    return rest[: end.start() if end else len(rest)]


ACTS = {
    "renameDocumentWithUndo": "() => put(before)",
    "archiveDocumentWithUndo": "/unarchive",
    "offerCreateUndo": "/restore",
    "unlinkDocNoteWithUndo": "docSetNoteLink(docId, note.id, true)",
    "docBookmarkWithUndo": "docSetBookmark(docId, bookmarkId, !attached)",
    "restoreDocVersionWithUndo": "docPutFields(docId, before)",
    "docDictionaryAdd": "without",
    "deleteDocumentWithUndo": "/restore",
}


def test_every_document_act_goes_through_the_one_stack():
    for name, inverse in ACTS.items():
        body = _body(name)
        assert "offerUndo(" in body or "pushUndo(" in body, name
        assert inverse in body, f"{name}: its undo is not the server's inverse"


def test_the_handlers_call_the_acts():
    for call in (
        "renameDocumentWithUndo(doc, next)",
        "archiveDocumentWithUndo(doc)",
        "offerCreateUndo(doc)",
        "unlinkDocNoteWithUndo(note)",
        "docBookmarkWithUndo(bookmark.id, false)",
        "docBookmarkWithUndo(Number(select.value), true)",
        "restoreDocVersionWithUndo(entry)",
    ):
        assert call in APP, call


def test_a_restore_is_one_step_not_a_confirm():
    body = _body("docHistoryRow")
    assert "restoreDocVersionWithUndo(entry)" in body
    assert "Restore it" not in body
    #: Outside the editor's history, so Ctrl+Z does not undo it twice.
    assert "addToHistory.of(false)" in _body("docWriteOutsideHistory")


def test_a_fix_is_its_own_step_in_the_editor():
    for name in ("docProseFix", "docProseFixAll"):
        body = _body(name)
        assert body.index("docUndoBreak()") < body.index("box.value =")


def test_ctrl_z_walks_the_newer_history_on_a_document():
    body = _body("appStackIsNewer")
    assert "window.docUndoAt" in body and "window.docRedoAt" in body
    assert "!appStackIsNewer(dir)" in _body("surfaceHistory")
    assert "docHistoryStamp(update);" in _body("docCmUpdate")
    # performUndo/performRedo queue their *Now bodies (historyQueue), which hold the logic.
    assert 'surfaceHistory("redo")' in _body("performRedoNow")
    assert "action.undoneAt = Date.now();" in _body("performUndoNow")


def test_version_history_names_versions_and_compares_side_by_side():
    """DOCUMENTS 24 row 4: named versions (one undo step each), a Named
    filter, the diff side by side on the rows `docRenderDiff` drew, and the
    prompt that names one reachable from inside the modal history."""
    assert "offerUndo(" in _body("docSetVersionName")
    assert "offerUndo(" in _body("docNameCurrentVersion")
    assert "docDiffSplitLayout(host, opts.split)" in _body("docRenderDiff")
    assert 'docHistoryFilter === "named"' in _body("renderDocHistoryList")
    assert "docIdeCompareWith(entry.id" in _body("docHistoryRowMenu")
    assert "modal.appendChild(overlay)" in _body("docPromptInModal")
    assert "docPromptInModal(" in _body("docNameCurrentVersion")
    from tests._app_js import INDEX_HTML

    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="doc-history-name"' in html and 'data-history-filter="named"' in html


def test_the_open_paints_the_text_before_the_panels():
    """DOCUMENTS 25 row 7: no reconfigure that changes nothing, and the outline,
    prose check and side panels a frame after the text (measured open of a
    241-line file: 1,679 to 1,981ms at 390 before, 367 to 782 after)."""
    opener = _body("openDocument")
    assert "docAfterFirstPaint(seq, () => {" in opener
    deferred = opener[opener.index("docAfterFirstPaint(seq"):]
    assert "renderDocOutline();" in deferred and "renderDocTools();" in deferred
    assert "if (seq === docOpenSeq) paint();" in _body("docAfterFirstPaint")
    assert "docCmPartIs(docCmParts.live, on)" in _body("docSetLiveDecorations")
    assert "docCmPartIs(docCmParts.gutter, docFenceGutterOn())" in _body("docCmSyncGutter")
    #: The findings are repainted once, by the deferred prose check.
    assert "docResetDocument(doc.content, doc.id, { repaint: false });" in opener
    assert "syncDocFileType({ prose: false });" in opener
