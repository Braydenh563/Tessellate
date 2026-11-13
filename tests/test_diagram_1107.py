"""1107 diagram builder build list (docs/roadmap/agent-remaining/diagram-dive-1107.md): DD-3, DD-7, DD-8, DD-9, DD-14.

Read for what the code must hold; the browser numbers (keys, clicks, rects) are in each commit and in
docs/roadmap/agent-remaining/diagbuild-1107.md.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"


def _js(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


BUILDER = _js("diagram-builder.js")
EMBED = _js("diagram-embed.js")
MERMAID = _js("documents-mermaid.js")
STYLE = _js("diagram-style.js")


BAR = _js("diagram-bar.js")
KINDBAR = _js("diagram-kindbar.js")
SHELL = _js("phone-shell.js")


def test_tab_adds_a_joined_box_only_on_the_last_box_and_never_traps_and_f6_leaves_the_blocks():
    # DD-3a: first connected 3-box diagram without a drag. The flowchart's handler only; the mind map keeps its own Tab.
    # Review 1107 moved the code to diagram-bar.js (the builder is at its size cap) and made Tab a chain only on the last box:
    # Tab on every box added boxes without end and Shift+Tab on the first box swallowed the key (WCAG 2.1.2).
    body = BUILDER[BUILDER.index("  function onKey(S, event)") :]
    assert "diagramModel.bar.chain(event, S, key, block, addBlock)" in body
    chain = BAR[BAR.index("  function chain(") : BAR.index("  diagramModel.bar = ")]
    assert 'event.key !== "Tab" || key[0] !== "n") return false' in chain and "add(S, { after: key, from: id })" in chain
    assert "S.m.edges.find((e) => e.to === id)?.from" in chain
    # diagramOps is the builder's private name (an IIFE const); the bar file reads the model's. Review sweep: a ReferenceError on every Tab.
    assert "diagramModel.ops" in chain and "diagramOps" not in chain
    # Only the last box chains; any other Tab, and Shift+Tab with no parent, is left to the browser (no preventDefault before the return false).
    assert "if (block !== [...S.tree.querySelectorAll(\".dgm-block\")].at(-1)) return false;" in chain
    assert "if (!up) return false;" in chain and chain.index("if (!up) return false;") < chain.index("event.preventDefault()", chain.index("if (!up)"))
    # F6 is the way out of the blocks to the picture, Shift+F6 to the toolbar.
    assert 'event.key === "F6"' in chain and "S.fig" in chain
    for row in ('["Tab", "Add a box after the last one, joined to it"]', '["Shift + Tab", "Select the box that points at this one"]', '["F6"', '["Ctrl + Enter", "Keep the diagram (Done)"]'):
        assert row in STYLE, row
    # The first-run line, the Keys chip and the blocks hint all name the way out.
    assert "F6 leaves the blocks" in EMBED and "F6 leaves the blocks" in _js("diagram-steps.js")


def test_clear_starts_the_kind_the_pane_is_not_always_a_flowchart():
    # Review 1107: Clear on a sequence, mind map or timeline switched the kind silently.
    assert "STARTS[diagramModel.builder.kindOf(history[at])]" in EMBED and "io.set(`${STARTS.flowchart}\\n`)" not in EMBED
    assert 'makeMenuItem("ph:eraser Clear"' in EMBED


def test_ctrl_enter_keeps_the_diagram_from_anywhere_in_the_dialog():
    # Review 1107: the only keyboard route to Done was 15 Tabs.
    assert '(event.ctrlKey || event.metaKey) && event.key === "Enter"' in EMBED and "finish(true)" in EMBED[EMBED.index('event.key === "Enter"') :][:200]
    assert "Ctrl + Enter" in STYLE


def test_the_keys_sheet_closes_on_escape_over_the_diagram_window():
    # Review 1107: the sheet's early return counted the host dialog's own .confirm-overlay, so Escape did nothing and sheets stacked.
    assert 'document.querySelector(".confirm-overlay")) return;' not in SHELL
    assert "DOCUMENT_POSITION_FOLLOWING" in SHELL[SHELL.index("One Escape, one sheet") :][:900]


def test_a_press_on_a_kind_puts_focus_back_on_the_kind_bar():
    # Review 1107: the pane was rebuilt and focus fell to BODY.
    assert "pending" in KINDBAR and "button.focus()" in KINDBAR[KINDBAR.index("if (pending === here)") :][:80]


def test_the_door_opens_on_a_drawn_starter_with_its_first_box_selected_and_clear_in_the_menu():
    # DD-3b: the blank walkthrough was a lesson next to an empty picture.
    door = MERMAID[MERMAID.index("async function diagramDoor") : MERMAID.index("diagramModel.starter =")]
    #: Intent moved (R12, owner 2026-11-12): a text box asks first and New diagram opens an empty builder; the starter stays for the palette door.
    assert door.count("source: diagramModel.starter") == 1 and door.count('source: "",') == 1
    assert 'source: "flowchart TD"' not in door
    assert 'makeMenuItem("ph:eraser Clear"' in EMBED
    assert "diagramModel.builder.select(S, firstBox.dataset.key, true)" in EMBED
    assert "kindOf, select, styleDo," in BUILDER


def test_the_dialog_has_a_keys_chip_a_question_mark_anywhere_and_a_help_popover_with_the_guide_offer():
    # DD-7: help in reach. `?` from anywhere but a field; a block's own `?` is not opened twice.
    assert 'smallButton("ph:keyboard Keys"' in EMBED and "foot.append(seg, ...(live ? [chip, back] : [...(known ? [known] : []), chip, cancel, go]))" in EMBED  # 2026-11-11: an expanded diagram has Collapse for Cancel and Done
    ask = EMBED[EMBED.index('event.key !== "?"') :][:260]
    assert "event.defaultPrevented" in ask and 'input, textarea, select, [contenteditable]' in ask and "keys();" in EMBED
    assert 'data-help-for", "dgm-dialog-help"' in EMBED and "initHelpToggles(dialog)" in EMBED
    assert 'atlasSuggestion("How do I make a diagram?"' in EMBED
    # An open help popover takes its own Escape before the dialog closes.
    assert ".help-popover:not(.hidden)" in EMBED
    assert 'diagramModel.builder.styleDo(pane, "shortcuts")' in EMBED


def test_a_dock_tooltip_names_its_key():
    bar = _js("diagram-bar.js")
    touch = _js("diagram-touch.js")
    assert "Choose a shape to add (1 to 9, or ? for every key)" in bar
    assert "Choose a shape to add as a block (N, or ? for every key)" in touch
    assert 'main.title = `Add a ${name.toLowerCase()} (${hintOf(shape)})`' in bar and '"Undo, Ctrl+Z"' in bar and '"Redo, Ctrl+Y"' in bar


def test_a_click_on_a_hover_handle_grows_a_joined_block_and_asks_for_its_words():
    """DD-14: a press that never moved on a handle adds a joined block and opens its words; a drag still connects."""
    edges = (JS / "diagram-edges.js").read_text(encoding="utf-8")
    assert "function grow(from, group)" in edges and "else grow(from, " in edges
    assert "else arm(from, side)" not in edges
    assert "if (moved) connect(from, event.clientX, event.clientY)" in edges
    # the keyboard path (Enter on a handle) still arms, so a block can be joined to an existing one without a pointer
    assert "event.detail === 0 && arm(current(), side)" in edges
    assert "Click for a new joined block, or drag it to a block to connect them" in edges


def test_the_kind_is_one_tab_stop_in_the_title_row():
    """DD-8, moved by 1661 k: the kinds were four buttons crossed as one roving stop; they are now one Kind button, so
    the stop is that button, in the Title row before the dock, and the dialog's views are still the foot's."""
    bar = (JS / "diagram-kindbar.js").read_text(encoding="utf-8")
    assert "wireToolbarRoving(seg)" not in bar and 'h.el("button", "ghost small dgm-kindbtn")' in bar
    assert "row.append(word, button)" in bar
    embed = (JS / "diagram-embed.js").read_text(encoding="utf-8")
    assert "foot.append(seg" in embed


def test_new_diagram_is_a_palette_row_and_the_coarse_dock_buttons_are_44_px():
    """DD-9 (small part): "diagram" in Ctrl+K finds New diagram first, and at (pointer: coarse) every dock button is 2.75rem."""
    features = (ROOT / "frontend" / "js" / "app-features.js").read_text(encoding="utf-8")
    assert 'label: "ph:flow-arrow New diagram"' in features and "diagramModel.door({ doc: true })" in features
    css = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")
    block = css[css.index("@media (pointer: coarse) {\n  .dgm-dirs,") :]
    block = block[: block.index("\n}\n")]
    assert ".dgm-dock .dock-actions button:not(.dgm-add)" in block and "min-block-size: 2.75rem" in block


def test_a_note_card_asks_for_the_documents_once_so_its_diagram_embed_resolves():
    # Review 1107: "Embedded: Diagram ..." then "Nothing called ... yet" on the Notes tab, also after a reload: the documents
    # list was empty there. Measured (port 8821): the card now reads "<name>: open the diagram".
    notes = _js("notes-list.js")
    assert "if (!docList.length) loadEmbedDocuments();" in notes
    ask = notes[notes.index("function loadEmbedDocuments()") :][:520]
    assert "embedDocumentsAsked" in ask and 'apiPagedList("/documents", DOCUMENTS_PAGE_SIZE)' in ask and "renderEntries();" in ask
