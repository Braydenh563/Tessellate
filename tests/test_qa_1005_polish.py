"""The overnight quality pass's fixes (qa-1005), each pinned where it lives.

The numbers are measured in the browser by
`scratchpad/ui-sweeps/qa1005-polish.js` (one check per fix) and
`scratchpad/ui-sweeps/search1005-lazy.js` FIRST=1; these tests keep the
shapes those fixes depend on from being undone by a later edit.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = ROOT / "frontend" / "css"


def _rule(css: str, selector: str) -> str:
    start = css.index(selector + " {")
    return css[start : css.index("}", start)]


def test_a_note_cards_task_line_is_a_box_not_brackets():
    """'- [x] Beta invite list' was the card's own text, dash and brackets
    included (qa1005-polish.js `tasks`: 1 card, then 0, with 4 boxes)."""
    src = (JS / "notes-list.js").read_text(encoding="utf-8")
    body = src[src.index("function renderNoteText") : src.index("// The inline half")]
    assert r"/^\s*[-*+]\s+\[([ xX])\]\s+(.*)$/" in body
    assert 'item.className = "entry-task"' in body and "box.disabled = true" in body
    #: The break after the task stays in the text the next flush renders.
    assert 'buffer.push("");' in body
    css = (CSS / "01-forms-settings.css").read_text(encoding="utf-8")
    box = _rule(css, '#entry-list .entry-content .entry-task > input[type="checkbox"]:disabled')
    assert "min-height: 0" in box and "width: 1.1em" in box
    assert "line-through" in _rule(css, ".entry-task:has(> input:checked)")


def test_the_empty_states_atlas_offer_has_no_floating_rule():
    """Chat's, Notes' and Library's empty states drew `.help-atlas`'s popover
    rule as a short centred hairline (qa1005-polish.js `emptyrule`: 3 to 0)."""
    css = (CSS / "08-consistency.css").read_text(encoding="utf-8")
    rule = _rule(css, ":is(.chat-empty, #empty-message, #library-empty) > .help-atlas")
    assert "border-top: 0" in rule and "padding-top: 0" in rule


def test_a_reminders_actions_are_centred_on_its_first_line():
    """Centred on the whole row, the strip sat 11px low on a reminder with a
    linked note and the top of the time showed (qa1005-polish.js
    `reminders`: 6 rows to 0)."""
    css = (CSS / "08-consistency.css").read_text(encoding="utf-8")
    block = css[css.index("@media (hover: hover) and (min-width: 600px) {\n  /* The strip is centred") :]
    block = block[: block.index("\n}\n")]
    assert re.search(r"#reminder-groups li \.entry-meta \{\s*position: relative;", block)
    assert "right: 0;" in _rule(block, "  #reminder-groups li .entry-meta > .entry-actions")


def test_the_library_draws_its_view_switch_and_board_placeholders_before_data():
    """With `/library` and the boards' bundle held 3s, the Cards/Rows well had
    neither pressed and Boards & maps was blank (qa1005-polish.js `library`:
    0 and 0, then 1 pressed and 4 placeholders; dockgrammar621.js had read
    the unpressed well as a second segment style, skeletons.js the sub-tab as
    BLANK at 390)."""
    src = (JS / "library.js").read_text(encoding="utf-8")
    load = src[src.index("async function loadLibrary()") :]
    assert load.index("renderLibraryView();") < load.index('apiJson("/library")')
    assert 'showSkeletons($("library-boards-grid"), 4);\n            wbShowBoardsLanding();' in src


def test_the_notes_find_zone_is_never_narrower_than_its_controls():
    """Its 8rem basis let the zone shrink to 133px round 188px of controls:
    between 1100 and 1170 wide the Filter menu lay 40px under the sort select
    (qa1005-polish.js `dockoverlap`: 1 to 0; one row still at 1184 and 1200,
    the packaged window)."""
    css = (CSS / "08-consistency.css").read_text(encoding="utf-8")
    rule = _rule(css, '[data-dock-name="notes"] .dock-find')
    assert "flex: 1 1 8rem" in rule and "min-width: min-content" in rule


def test_an_empty_settings_status_line_takes_no_room():
    """Nine Settings cards ended on an empty `p.status` that kept 27px of
    paragraph margin (qa1005-polish.js `settingspad`: 9 to 0). The margin
    goes, the element stays, so a live region is in the tree before it
    speaks."""
    css = (CSS / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    rule = _rule(css, "#settings-modal .settings-group > p.status:empty")
    assert "margin: 0" in rule and "display" not in rule


def test_a_settings_text_field_wraps_rather_than_shrinks():
    """`.row input`'s zero basis squeezed a field rather than wrapping it: the
    server address was 62px wide at 390 and six placeholders were cut off
    (qa1005-polish.js `placeholders`: 1 at 1440 and 5 at 390, then 0)."""
    css = (CSS / "01-forms-settings.css").read_text(encoding="utf-8")
    rule = _rule(css, '#settings-modal .settings-section .row > input:is([type="text"], [type="search"], [type="password"], [type="url"])')
    assert "min-width: min(100%, 15rem)" in rule
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'placeholder="What it\'s for (optional)"' in html


def test_a_note_cards_connection_pill_is_one_line():
    """At 390 a card's connection pills wrapped their words to two 12px lines
    inside a one-line pill; Ask's results had the fix, the note list did not
    (qa1005-polish.js `linkpills`: 112 of 112 at 390, then 0)."""
    css = (CSS / "08-consistency.css").read_text(encoding="utf-8")
    chip = _rule(css, "#entry-list .link-connection > .chip.link")
    #: `clip visible`, not `hidden` (audit 1029 rank 46): the words are still cut
    #: across, but the chip keeps the hit overhang above and below.
    assert "white-space: nowrap" in chip and "overflow: clip visible" in chip
    assert "text-overflow: ellipsis" in _rule(css, "#entry-list .link-connection > .chip.link > .ph-text")


def test_a_note_being_opened_for_editing_holds_its_place_while_the_form_loads():
    """With note-edit-panels.js held 3s the card fell from 188px to a 15px
    empty strip, then rose to the form: every note under it jumped twice.
    The stand-in's promise now puts placeholders up (133px, aria-busy)."""
    src = (JS / "note-cards.js").read_text(encoding="utf-8")
    block = src[src.index("if (editingId === entry.id && options.actions) {") :][:900]
    assert "const drawn = renderEditForm(li, entry);" in block
    assert "if (drawn instanceof Promise)" in block and "showSkeletons(li, 2)" in block
    assert "drawn.finally(() => clearSkeletons(li))" in block


def test_the_parchment_muted_ink_clears_4_5_on_the_settings_cards():
    """Manuscript's muted ink was 4.33 to 4.47:1 on the Settings cards' tint
    (contrast.js LOOK=manuscript, 17 texts in four sections, hidden until the
    sweep stopped crashing before Settings); #655949 is 4.89 to 5.05:1."""
    css = (CSS / "05-sidebars-themes.css").read_text(encoding="utf-8")
    block = css[css.index(':root[data-palette="parchment"] {') :]
    block = block[: block.index("}")]
    assert "--muted: #655949;" in block
