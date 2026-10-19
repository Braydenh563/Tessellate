"""INBOX 430: "Ask all notes" must not depend on the lazy Questions view.

The scope variable lives in capture-ask.js (eager); the Clear button's listener
lived in questions-view.js, which loads on first open of the Questions view.
Measured 2026-10-19 on port 8796 at 1440: with the scope set, a click on
`#ask-scope-clear` hid `#ask-scope`.
"""
from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"


def test_the_ask_scope_clear_button_is_wired_by_the_eager_ask_script():
    ask = (JS / "capture-ask.js").read_text(encoding="utf-8")
    view = (JS / "questions-view.js").read_text(encoding="utf-8")
    assert '$("ask-scope-clear").onclick' in ask
    assert "ask-scope-clear" not in view
