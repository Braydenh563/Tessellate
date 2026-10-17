"""A key in a long note does not rebuild the hidden textarea (BACKLOG, the owner 2026-10-12).

"Backspace and delete are laggy in the editor." Measured (1500-word note,
1440x900, a trace of 25 Backspaces in the capture box with the invalidation
tracker on): each key wrote the whole note into the hidden mirror textarea
(`noteSurfaceMirror`: `host.value = text`), which makes the browser rebuild
the textarea's inner text, one text node and one <br> per line, and restyle
them: 10,962 <br> and 6,309 text-node insertions in 25 keys (the stack of
every one of them ends in that `set`), and 141 style recalculations of 1,764
elements, 33 to 69 ms each. The mirror is now written once the typing pauses
(`NOTE_MIRROR_MS`) or when a caller touches the textarea's own selection or
text; reads of `value`, `selectionStart` and `selectionEnd` come live from the
view, so a handler of the `input` event sees the same text as before.
"""

from __future__ import annotations

import re

from tests._app_js import JS_DIR

DOCS = (JS_DIR / "documents.js").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    start = DOCS.index(f"function {name}(")
    return DOCS[start : DOCS.index("\n}\n", start) + 2]


def test_a_keystroke_does_not_write_the_hidden_textarea():
    mirror = _fn("noteSurfaceMirror")
    assert "host.value = " not in mirror and "setSelectionRange" not in mirror and "doc.toString()" not in mirror
    assert "NOTE_MIRROR_MS" in mirror
    assert int(re.search(r"const NOTE_MIRROR_MS = (\d+);", DOCS).group(1)) >= 100


def test_the_box_reads_live_from_the_view():
    own = _fn("noteSurfaceOwnValue") + _fn("noteSurfaceMirrorTools")
    assert "return view.state.doc.toString();" in own
    assert "view.state.selection.main" in own


def test_anything_that_touches_the_textarea_itself_finds_it_current():
    own = _fn("noteSurfaceOwnValue") + _fn("noteSurfaceMirrorTools")
    for name in ("setSelectionRange", "setRangeText", "select"):
        assert name in own
    assert own.count("host.noteMirrorFlush()") >= 3
    # A script setting `.value` is not announced as a typed change.
    assert "host.noteSettingValue = true" in own
    assert "host.noteSettingValue" in _fn("noteSurfaceMirror")
