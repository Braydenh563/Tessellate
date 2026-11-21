"""L-world-class-202: Ctrl+Z inside a dialog's text field, and what Ctrl+S says with nothing to save.

Driven at 1440 on :8870 (2026-11-14), promptDialog opened over a pushed app step:
typed "Old name extra words", Ctrl+Z gave "Old name", Ctrl+Shift+Z gave it
back, the app's own step ran 0 times (the field keeps its own undo). With no
initial text the same: " extra words" to "" and back. Ctrl+S answered
"Nothing to save yet." on Graph, Library, Timeline, Chat, Reminders and
Dashboard, where nothing is ever written first; now it names the tab.
"""

from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _src(name):
    return (JS / name).read_text(encoding="utf-8")


def test_a_text_field_keeps_its_own_undo_and_redo_in_every_dialog():
    text = _src("settings-wiring.js")
    assert 'if ((id === "undo" || id === "redo" || id === "pasteNote") && inTextField) continue;' in text
    assert "!inTextField && (e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey && e.key.toLowerCase() === \"y\"" in text


def test_ctrl_s_with_nothing_to_save_says_what_to_do_on_each_tab():
    text = _src("settings-wiring.js")
    body = text[text.index("function saveWhatIsInFront"):]
    body = body[: body.index("\n}\n")]
    assert 'toast("Nothing to save yet. Write a note first.")' in body
    assert 'toast("Nothing to save here. It saves as you go.")' in body
    assert 'toast("Nothing to save here.")' not in body
    # the composer's note is only saved from the Notes tab, not from a tab it is hidden behind
    assert '$("tab-notes")' in body
