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


def test_tab_on_a_box_adds_a_joined_box_and_names_it_and_shift_tab_selects_the_one_that_points_here():
    # DD-3a: first connected 3-box diagram without a drag. The flowchart's handler only; the mind map keeps its own Tab.
    body = BUILDER[BUILDER.index("  function onKey(S, event)") :]
    tab = body[body.index('event.key === "Tab"') : body.index('event.key === "F6"')]
    assert 'key[0] === "n"' in tab and "addBlock(S, { after: key, from: id })" in tab
    assert "S.m.edges.find((e) => e.to === id)?.from" in tab
    # Tab stays in the blocks, so F6 is the way out (a key trap otherwise).
    assert 'event.key === "F6"' in body and "S.fig" in body[body.index('event.key === "F6"') :][:200]
    for row in ('["Tab", "Add a box after the selected one, joined to it"]', '["Shift + Tab"', '["F6"'):
        assert row in STYLE


def test_the_door_opens_on_a_drawn_starter_with_its_first_box_selected_and_clear_in_the_menu():
    # DD-3b: the blank walkthrough was a lesson next to an empty picture.
    door = MERMAID[MERMAID.index("async function diagramDoor") : MERMAID.index("diagramModel.starter =")]
    assert door.count("source: diagramModel.starter") == 2
    assert 'source: "flowchart TD"' not in door
    assert 'makeMenuItem("ph:eraser Clear"' in EMBED and "io.set(`${STARTS.flowchart}\\n`)" in EMBED
    assert "diagramModel.builder.select(S, firstBox.dataset.key, true)" in EMBED
    assert "kindOf, select, keys:" in BUILDER


def test_the_dialog_has_a_keys_chip_a_question_mark_anywhere_and_a_help_popover_with_the_guide_offer():
    # DD-7: help in reach. `?` from anywhere but a field; a block's own `?` is not opened twice.
    assert 'smallButton("ph:keyboard Keys"' in EMBED and "foot.append(seg, ...(known ? [known] : []), chip, cancel, go)" in EMBED
    ask = EMBED[EMBED.index('event.key !== "?"') :][:260]
    assert "event.defaultPrevented" in ask and 'input, textarea, select, [contenteditable]' in ask and "keys();" in EMBED
    assert 'data-help-for", "dgm-dialog-help"' in EMBED and "initHelpToggles(dialog)" in EMBED
    assert 'atlasSuggestion("How do I make a diagram?"' in EMBED
    # An open help popover takes its own Escape before the dialog closes.
    assert ".help-popover:not(.hidden)" in EMBED
    assert "keys: (S) => styleDo(S, \"shortcuts\")" in BUILDER


def test_a_dock_tooltip_names_its_key():
    bar = _js("diagram-bar.js")
    touch = _js("diagram-touch.js")
    assert "Choose a shape to add (1 to 7, or ? for every key)" in bar
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


def test_the_kind_bar_is_one_tab_stop_resting_on_the_chosen_kind():
    """DD-8: Tab crosses the four kind buttons as one stop (arrows move between them) and the dialog's DOM order is
    head, kinds, dock, panes, footer, so Add box comes right after the kinds."""
    bar = (JS / "diagram-kindbar.js").read_text(encoding="utf-8")
    assert "wireToolbarRoving(seg)" in bar and "button.tabIndex = button.dataset.kind === here ? 0 : -1" in bar
    assert bar.index("wireToolbarRoving(seg)") < bar.index("S.root.prepend(seg)")
    embed = (JS / "diagram-embed.js").read_text(encoding="utf-8")
    assert "foot.append(seg" in embed
