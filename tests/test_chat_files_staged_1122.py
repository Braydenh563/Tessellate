"""A file chosen in the chat is staged until the message is sent (the owner, 2026-11-22).

Source text: "Uploading a file (a .py) in chat adds it to the Documents library immediately, before
the message is sent. It must be staged: it shows as a removable chip in the composer, and it's
saved to the library only when sent. Removing the chip before sending leaves nothing behind."
Measured in the app (scratchpad/ui-sweeps/chatstage1122.js): attach 0 requests and 0 documents,
remove 0 and 0, send one `/documents/import` and the id on the chat request.
"""

from __future__ import annotations

import re

from tests._app_js import JS_DIR

DOCS = (JS_DIR / "chat-docs.js").read_text(encoding="utf-8")
TURN = (JS_DIR / "chat-turn.js").read_text(encoding="utf-8")


def _body(source: str, name: str) -> str:
    start = source.index(f"async function {name}(")
    end = source.find("\nasync function ", start + 1)
    return source[start:] if end == -1 else source[start:end]


def test_choosing_a_file_sends_nothing_to_the_server():
    stage = _body(DOCS, "importChatDocuments")
    assert "apiJson" not in stage and "fetch(" not in stage
    assert "file," in stage or "file }" in stage


def test_the_send_path_imports_what_is_staged_before_the_request_is_built():
    commit = TURN.index("commitStagedDocuments()")
    built = TURN.index("const sentDocuments =")
    assert commit < built
    assert re.search(r"attachedDocuments\.some\(\(d\) => d\.file\)\) await commitStagedDocuments\(\)", TURN)
    assert "/documents/import" in _body(DOCS, "commitStagedDocuments")


def test_the_guide_says_a_chip_is_saved_only_on_send():
    from tessellate.ai import help_topics_more

    text = repr(vars(help_topics_more))
    assert "adds files as chips, saved only when you send" in text
