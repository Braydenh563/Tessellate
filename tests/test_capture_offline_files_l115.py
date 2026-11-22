"""L-world-class-115: Capture holds staged pictures and files while the server is gone.

Before, a save with a staged picture or file while offline kept the words in
the box and said the server was not answering. Now the bytes go into IndexedDB
beside the outbox item (keyed by its client_key) and are sent on reconnect:
pictures upload first and their `staged:` urls are rewritten, the note is
posted, then the files attach to it. Driven with Playwright
`context.setOffline(true)` on :8870 (2026-11-14); the numbers are in the CHANGELOG line.
"""

import re
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _src(name):
    return (JS / name).read_text(encoding="utf-8")


def test_the_staged_bytes_are_held_with_the_note_not_refused():
    text = _src("capture-ask.js")
    block = text[text.index("async function heldOffline"):]
    block = block[: block.index("\nasync function saveEntry")]
    # no longer a refusal for staged pictures and files
    assert "captureStagedImages.length || captureStagedFiles.length ||" not in block
    assert "noteOutboxAdd(body, { images: captureStagedImages, files: captureStagedFiles })" in block
    # the staged copies are let go only once the bytes are held, then the form resets
    assert block.index("noteOutboxAdd(") < block.index("clearStagedImages()") < block.index("resetCaptureForm(")
    assert "captureStagedFiles = []" in block
    # a failed hold (no IndexedDB, quota) keeps the words and says so, as before
    assert "The server is not answering. Your note is kept here; save again when it is back." in block


def test_the_outbox_stores_blobs_in_indexeddb_and_flushes_them_in_order():
    text = _src("quick-note.js")
    assert 'indexedDB.open("noteOutboxFiles", 1)' in text
    add = text[text.index("function noteOutboxAdd"):]
    add = add[: add.index("\n  }\n")]
    assert "held" in add and "noteFilesPut(key, held)" in add
    flush = text[text.index("function flushNoteOutbox"):]
    flush = flush[: flush.index("function returnNoteToCapture")]
    # pictures first (rewriting the staged urls), then the note, then the bytes are dropped and the files attach from memory (a failure toasts per file, as online)
    order = [flush.index(s) for s in ('"/media/upload"', "rewriteStagedUrls(", 'apiJson("/entries", { method: "POST"', "noteFilesDrop(", "/files`")]
    assert order == sorted(order)
    # a network failure mid-way keeps both the item and the bytes for the next try
    assert "noteServerGone(error)" in flush
    # the pending row names the held pictures and files instead of a broken staged url
    assert "stripStagedUrls(body)" in text and "Files kept with it" in text


def test_the_item_sent_never_carries_the_blob_marker():
    flush = _src("quick-note.js")
    flush = flush[flush.index("function flushNoteOutbox"):]
    assert re.search(r"queued_at: _queuedAt, [^}]*blobs: hasFiles, [^}]*\.\.\.payload", flush)
