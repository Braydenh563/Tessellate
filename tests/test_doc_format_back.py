"""A hidden formatting toolbar has a visible way back (INBOX 574, the owner:
"an easier way to open the formatting toolbar in the documents editor if it
is closed").

Driven in a browser by `scratchpad/ui-sweeps/mmdoc1005-formatback.js` (the
dock button, Ctrl+Shift+X in and out of the text, the ⋯ row, the palette
row, the shortcut sheet, the one-time toast, a code file); these pin the
wiring.
"""

from __future__ import annotations

from tests._help_text import help_chat_text

from pathlib import Path
from tests._app_js import documents_text

ROOT = Path(__file__).resolve().parents[1]
DOCS = documents_text()
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
HELP = help_chat_text()


def test_the_dock_has_a_labelled_formatting_button_with_its_key():
    start = HTML.index('id="doc-format-show"')
    tag = HTML[start:HTML.index("</button>", start)]
    assert "Ctrl+Shift+X" in tag and ">Formatting</span>" in tag


def test_the_key_the_menu_and_the_palette_all_toggle_it():
    assert '{ key: "Mod-Shift-x", run: () => { toggleDocToolbar(); return true; } }' in DOCS
    assert 'label: "Show or hide the formatting toolbar", keys: "Ctrl+Shift+X"' in DOCS
    assert 'id="doc-format-toggle-label">Show formatting toolbar<' in HTML


def test_the_first_hide_says_how_to_bring_it_back():
    assert "Formatting hidden. Bring it back from the Formatting button or Ctrl+Shift+X." in DOCS


def test_the_help_says_so():
    assert "Ctrl+Shift+X" in HELP and "Show formatting toolbar" in HELP
