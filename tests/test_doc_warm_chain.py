"""The idle warm-up chains on warmDocumentEngine's result, not on its closure's private flag.

library.js read `docWarmed`, which lives only inside documents-cm-load.js, so every idle warm-up
threw a ReferenceError and the document editor was never pre-built."""
from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"


def test_warm_chain_uses_the_return_value():
    lib = (JS / "library.js").read_text(encoding="utf-8")
    assert "docWarmed" not in lib
    assert "window.warmDocumentEngine() && window.loadCodeMirror()" in lib
    js = (JS / "documents-cm-load.js").read_text(encoding="utf-8")
    body = js[js.index("function warmDocumentEngine("):]
    body = body[:body.index("\n  }\n")]
    assert "return docWarmed;" in body and "return true;" in body


def test_an_open_runs_the_prose_pass_in_idle():
    # L-world-class-40: the whole-document prose walk left the post-paint task (two frames 251 to 240 ms).
    surface = (JS / "documents-surface.js").read_text(encoding="utf-8")
    panel = (JS / "documents-suggest-panel.js").read_text(encoding="utf-8")
    assert "renderDocTools(() => seq === docOpenSeq)" in surface
    assert "requestIdleCallback(() => stillOpen() && renderDocProse()" in panel
