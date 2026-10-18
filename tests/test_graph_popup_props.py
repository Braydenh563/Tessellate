"""INBOX 1300 C27: "The ui structure and formatting and placement of this
properties button in the graph node popup needs to be fixed, redesigned and
improved".

Measured before (`d2/probe-popup.js`, 1440x900, a note with no properties): a
lone ghost "Properties" button, 117x32, its icon indented past the popup's
text edge, between the topic chip and the note's text with 0px between it and
the text field, so it read as a heading for the text. Now the properties are a
section: a small-caps "Properties" head with its count and the action (Add
when there are none, Edit when there are) at the row's end, the table under
it, and the section spaced off the text field.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAPH = (ROOT / "frontend" / "js" / "graph.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "graph-lazy.css").read_text(encoding="utf-8")


def _function(text: str, name: str) -> str:
    start = re.search(rf"\nfunction {name}\(", text).start() + 1
    return text[start : text.index("\n}\n", start) + 2]


def _rule(selector: str) -> str:
    at = CSS.index(selector + " {")
    return CSS[at : CSS.index("}", at)]


def test_the_properties_are_a_section_with_a_head_and_its_action_at_the_end() -> None:
    body = _function(GRAPH, "renderGraphPopupProps")
    assert "graph-popup-props-head" in body and "graph-popup-props-label" in body
    assert '"ph:plus Add"' in body and '"ph:pencil-simple Edit"' in body
    # The action names what it does to a screen reader, not only "Add".
    assert "aria-label" in body
    head = _rule(".graph-popup-props-head")
    assert "justify-content: space-between" in head
    label = _rule(".graph-popup-props-label")
    assert "text-transform: uppercase" in label and "var(--text-xs)" in label


def test_the_section_stands_off_the_notes_text() -> None:
    box = _rule(".graph-popup-props")
    assert "align-items: stretch" in box
    assert "margin-bottom: var(--space-" in box


def test_the_guide_names_the_new_action() -> None:
    chat = (ROOT / "src" / "tessellate" / "ai" / "help_chat.py").read_text(encoding="utf-8")
    assert "with a Properties button" not in chat
    assert "Add or Edit beside its Properties heading" in chat
