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
    assert "select, tell:" in BUILDER
