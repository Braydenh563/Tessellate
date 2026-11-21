"""`box.readOnly = true` on a note box reaches the editor mounted over it.

The Write with AI desk sets `#draft-text.readOnly` while a pass streams into
the draft (`setDraftBusy`, chat-agent.js). Once the note-surface editor has
mounted, the textarea is a hidden mirror and the flag lived only on it: a
person could type into the draft while it was arriving. Measured in Chromium
with `scratchpad/ui-sweeps/draftreadonly.js` (typing during the pass changed
the draft; contenteditable stayed true). The fix is a compartment driven by an
own `readOnly` accessor, the same hook `value` uses; script writes still go
through, so the stream itself is not blocked.
"""

from pathlib import Path

from tests._app_js import documents_text

DOCUMENTS = Path(__file__).resolve().parent.parent / "frontend" / "js" / "documents.js"


def _between(text: str, start: str, end: str) -> str:
    head = text.index(start)
    return text[head : text.index(end, head)]


def test_the_mounted_editor_has_a_read_only_compartment():
    text = documents_text()
    extensions = _between(text, "function noteSurfaceExtensions", "function noteSurfaceName")
    assert "noteReadOnlySlot.of(host.noteReadOnlyExtensions(host.readOnly))" in extensions
    # Both halves: `readOnly` refuses the keymap and commands, `editable`
    # makes the contenteditable itself inert so the caret and IME stay out.
    assert "EditorState.readOnly.of(true)" in extensions
    assert "EditorView.editable.of(false)" in extensions


def test_assigning_read_only_on_the_box_reconfigures_the_editor():
    text = documents_text()
    own = _between(text, "function noteSurfaceOwnValue", "async function mountNoteSurface")
    assert 'getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "readOnly")' in own
    assert "noteReadOnlySlot.reconfigure(" in own
