"""The warm-up after boot reads whether the editor engine warmed from `warmDocumentEngine`'s own answer.

documents-cm-load.js is wrapped whole (L-documents-116), so its `docWarmed` is no longer a global: library.js's
idle warm-up read it bare and threw `ReferenceError: docWarmed is not defined` a second after every boot (seen
in the Capture sweep at 1440 on the merged tree), and the code editor was never pre-loaded.
"""

from __future__ import annotations

import re

from tests._app_js import frontend_text


def test_library_does_not_read_the_wrapped_flag() -> None:
    assert not re.search(r"(?<![\w.])docWarmed\b", frontend_text("library.js"))


def test_warm_document_engine_answers_whether_it_warmed() -> None:
    src = frontend_text("documents-cm-load.js")
    body = src[src.index("function warmDocumentEngine()") :]
    body = body[: body.index("\n}\n")]
    assert "if (docWarmed) return true;" in body and body.rstrip().endswith("return true;")
