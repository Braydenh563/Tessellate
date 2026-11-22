"""The board's help is a sheet whose rows cannot overlap (INBOX 566, UX-03).

The owner: "the whiteboard help popup is still cooked and needs a redesign".
Measured on the old card: labels set `nowrap` and pushed apart from their keys
by flex ran under the keys, and the right column ran out of the card. The
sheet is the dialog recipe with a search field, and a row is three grid
tracks (icon, words, a fixed key column whose caps wrap inside it). The
browser half, the geometry at 1440, 1024 and 390 in both themes, is
`scratchpad/ui-sweeps/wb1005-help.js`.
"""

import re
from pathlib import Path
from tests._app_js import index_html_text

ROOT = Path(__file__).resolve().parents[1]
INDEX = index_html_text()
COMMANDS = (ROOT / "frontend" / "js" / "whiteboard-commands.js").read_text(encoding="utf-8")
CSS = "\n".join((ROOT / "frontend" / "css" / name).read_text(encoding="utf-8") for name in ("07-whiteboard-misc.css", "library-lazy.css"))


def _rule(selector: str) -> str:
    start = CSS.index(selector + " {")
    return CSS[start : CSS.index("}", start)]


def test_the_sheet_is_the_dialog_recipe() -> None:
    sheet = INDEX[INDEX.index('id="wb-help-overlay"') :]
    sheet = sheet[: sheet.index('id="wb-help-none"')]
    assert 'class="dialog-head"' in sheet and 'id="wb-help-close"' in sheet
    assert "dialog-head-btn" in sheet and 'data-help-for="wb-help-about"' in sheet
    assert 'class="search-field' in sheet and 'id="wb-help-search"' in sheet


def test_a_row_has_a_fixed_key_column_and_words_that_wrap() -> None:
    row = _rule(".wb-help-row")
    assert "grid-template-columns:" in row and "minmax(0, 1fr) var(--wb-help-keys-w)" in row
    assert "overflow-wrap: anywhere" in _rule(".wb-help-row-label")
    keys = _rule(".wb-help-row-keys")
    assert "flex-wrap: wrap" in keys and "min-width: 0" in keys
    assert "nowrap" not in _rule(".wb-help-row-label")


def test_the_list_scrolls_inside_the_card() -> None:
    assert "overflow-y: auto" in _rule(".wb-help-sections")
    assert "min-height: 0" in _rule(".wb-help-sections")


def test_every_command_row_names_a_command_with_a_key() -> None:
    table = dict(re.findall(r'\{ id: "([\w-]+)",[^\n]*?keys: "([^"]*)"', COMMANDS))
    block = COMMANDS[COMMANDS.index("const WB_HELP_SECTIONS = [") :]
    block = block[: block.index("\n];\n")]
    named = re.findall(r'cmd: "([\w-]+)"', block)
    assert len(named) >= 30
    missing = [c for c in named if c not in table or not table[c]]
    assert not missing, f"help rows naming a command with no key: {missing}"


def test_the_empty_board_card_no_longer_carries_the_key_list() -> None:
    card = INDEX[INDEX.index('id="wb-empty-hint"') :]
    card = card[: card.index('id="wb-empty-hint-dismiss"')]
    assert "<kbd>" not in card
    assert 'id="wb-empty-hint-keys"' in card
