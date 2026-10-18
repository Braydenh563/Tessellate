"""The live view's table menu survives its own press (INBOX 290).

The owner, 2026-09-21: "when I click on a header row in a table on the live
view in documents page, another row appears below it until I click off, and I
cant click the meatball button on the end of the row".

Measured before the fix with `scratchpad/ui-sweeps/doctable290.js`: one press
on the kebab left `.cm-editor.cm-focused` gone, the widget unmounted, and the
`.action-menu` standing under the header row with no opener. Two causes, both
in `DocTableMenuWidget`:

* `openActionMenu` shows the popup, measures it and reparents it to `<body>`
  when it would be clipped. Those are mutations inside the widget, and a
  widget that does not claim them makes CodeMirror re-read the content DOM,
  which rebuilds the view and blurs the editor.
* The decoration that draws the menu is computed from `view.hasFocus`, so the
  blur then removed the button that had just been pressed.

Neither is visible to a test that cannot run a browser, so this file holds the
two shapes rather than the behaviour: the widget claims its mutations, and the
decoration has a second reason to draw the menu besides focus. The behaviour
itself is `doctable290.js`, 10 of 10.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "frontend" / "js" / "documents.js").read_text(encoding="utf-8")


def _widget_body() -> str:
    match = re.search(
        r"class DocTableMenuWidget extends WidgetType \{.*?\n  \}\n", SOURCE, re.S
    )
    assert match, "DocTableMenuWidget not found in documents.js"
    return match.group(0)


def test_the_table_menu_widget_claims_its_own_mutations():
    body = _widget_body()
    assert "ignoreMutation()" in body, (
        "DocTableMenuWidget must declare ignoreMutation. Without it CodeMirror "
        "reads openActionMenu's show, measure and reparent as the document "
        "changing under it, rebuilds the view and blurs the editor, which is "
        "INBOX 290's 'I cant click the meatball button'."
    )
    claim = re.search(r"ignoreMutation\(\)\s*\{\s*return\s+(\w+)", body)
    assert claim and claim.group(1) == "true", (
        "ignoreMutation must return true, or the mutations are not claimed."
    )


def test_the_table_menu_widget_closes_a_menu_it_is_taking_with_it():
    body = _widget_body()
    assert "destroy(" in body and "closeActionMenus" in body, (
        "A widget removed while its menu is open leaves the menu floating over "
        "the document with no opener, which is INBOX 290's 'another row "
        "appears below it'."
    )


def test_an_open_menu_holds_the_kebab_on_screen():
    assert "const menuHeld =" in SOURCE, (
        "The table menu decoration must have a reason to draw besides "
        "view.hasFocus, or opening the menu removes the button that opened it."
    )
    held = re.search(r"const menuHeld =(.*?);\n", SOURCE, re.S)
    assert held, "menuHeld not found"
    assert 'aria-expanded="true"' in held.group(1), (
        "menuHeld must read the opener's aria-expanded, which openActionMenu "
        "sets before anything it does can move focus."
    )
    # The row is the one being edited since INBOX 425 i (`menuRow`, the header
    # when the caret is on the delimiter), no longer always the header; the
    # guard this test exists for is the `inTable || menuHeld` half.
    assert re.search(
        r"if \(r === menuRow && \(inTable \|\| menuHeld\)\)", SOURCE
    ), "the menu widget must be drawn when the caret is in the table OR its own menu is open"


def test_the_table_right_click_menu_carries_copy_cut_and_paste():
    """The right-click menu replaces the browser's, so it must keep the three
    clipboard rows (review note on PR 191); the behaviour is checked in a browser."""
    body = re.search(r"function docTableMenuAtPoint\(.*?\n\}\n", SOURCE, re.S).group(0)
    assert "docClipboardMenuItems(view)" in body
    rows = re.search(r"function docClipboardMenuItems\(.*?\n\}\n", SOURCE, re.S).group(0)
    for label in ("Copy", "Cut", "Paste"):
        assert f'label: "{label}"' in rows
