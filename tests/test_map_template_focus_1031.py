"""A map template leaves the keyboard somewhere real (blind test 1031, friction 1).

Clicking "Trip plan" on a new map hid the offer with the pressed tile still
focused, so `document.activeElement` fell to BODY while the centre topic read
as selected and typing "Lisbon trip" met the global chords: `t` then `r` went
to Reminders, and Enter made a reminder. Two causes, two guards: the template
opens the centre topic's editor (real focus), and the global key handler
treats a topic whose editor is open as a text field whether or not it holds
the focus.
"""
import re
from pathlib import Path

from tests._app_js import app_js_text

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
BOARD = {n: (JS / n).read_text(encoding="utf-8") for n in ("whiteboard-templates.js", "whiteboard-map.js")}


def _body(js: str, signature: str) -> str:
    start = js.index(signature)
    return js[start : js.index("\n}\n", start)]


def test_the_template_opens_the_centre_topic_after_the_offer_is_hidden():
    body = _body(BOARD["whiteboard-templates.js"], "async function wbApplyMapTemplate(")
    assert body.index("wbDismissMapTemplates()") < body.index("wbMapEditRootAfterTemplate")


def test_the_root_edit_is_skipped_where_a_keyboard_would_cover_the_canvas():
    body = _body(BOARD["whiteboard-templates.js"], "function wbMapEditRootAfterTemplate(")
    assert "(pointer: fine)" in body
    assert "wbMapEditNode(" in body
    assert 'selectWbItem("object"' in body


def test_the_global_key_handler_counts_a_shown_editor_as_typing():
    js = app_js_text()
    assert "const mapEditorShown = " in js
    assert re.search(r"const typing = [^;]*mapEditorShown\(\)", js)


def test_a_template_does_not_toast_the_layout_it_just_chose():
    assert "wbMapSetLayout(entry.layout, { quiet: true })" in BOARD["whiteboard-templates.js"]
    assert "if (quiet) return;" in BOARD["whiteboard-map.js"]
