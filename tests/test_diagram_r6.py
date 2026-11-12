"""DOCUMENTS_PLAN 22.4 R6 (the blind-tester's list, R6.1 to R6.13): one test per item.

The pure half (`diagramOps.needsLabel`) runs in node; the rest is read for what it must hold. Each item's browser
numbers (390 and 1440 wide, light and dark) are named in docs/roadmap/HISTORY.md.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.test_diagram_builder import NESTED, _script

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")
BUILDER = (JS / "diagram-builder.js").read_text(encoding="utf-8")
EMBED = (JS / "diagram-embed.js").read_text(encoding="utf-8")
JOINS = (JS / "diagram-joins.js").read_text(encoding="utf-8")
# `kebabMenu.beside` (the menu hung from a whole row) lives in diagram-library.js since the boot-bundle ratchet; sheets-selects.js only calls it.
SELECTS = (JS / "sheets-selects.js").read_text(encoding="utf-8") + (JS / "diagram-library.js").read_text(encoding="utf-8")
TOUCH = (JS / "diagram-touch.js").read_text(encoding="utf-8")
STEPS = (JS / "diagram-steps.js").read_text(encoding="utf-8")
MERMAID_JS = (JS / "documents-mermaid.js").read_text(encoding="utf-8")
LIBRARY = (JS / "library.js").read_text(encoding="utf-8")


def _rule(selector: str) -> str:
    """The body of the first rule whose selector list contains `selector` (outside any at-rule is not required)."""
    for match in re.finditer(r"(?:(?<=[{}])|\A)([^{}]+)\{([^{}]*)\}", re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)):
        if selector in [s.strip() for s in match.group(1).split(",")]:
            return match.group(2)
    raise AssertionError(f"no rule for {selector}")


def test_r6_1_the_phone_picture_is_taller_and_the_zoom_bar_sits_under_it():
    narrow = CSS[CSS.index("@container (max-width: 599.98px)") :]
    assert re.search(r"\.dgm-picture,\s*\.dgm-stage\s*\{[^}]*block-size: (3[6-9]|4\d)dvh", narrow), "the stage is no taller than 26vh"
    assert "26vh" not in CSS
    # The bar is a row under the picture, not a layer over its lower node.
    assert re.search(r"\.dgm-stage\s*\{[^}]*flex-direction: column", narrow)
    assert re.search(r"\.dgm-zoom\s*\{[^}]*position: static", narrow)


def test_r6_2_a_node_in_the_picture_is_not_text_to_select_and_a_move_redraws_the_picture():
    assert "user-select: none" in _rule(".dgm-picture .md-mermaid-img") or "user-select: none" in _rule(".dgm .dgm-picture")
    # Moving a row prints the source and draws it again: the picture follows the list (commit ends in drawPicture).
    assert re.search(r"function commit\(S, said\) \{.*?drawPicture\(S\);\n  \}", BUILDER, re.S)
    got = _script("flowchart TD\n  A[One]\n  B[Two]\n  A --> B\n", "o.step(m, 'n:A', 1); return m.nodes.map((x) => x.id);")
    assert got["result"] == ["B", "A"] and got["src"].index("B[") < got["src"].index("A[")


def test_r6_3_a_second_arrow_next_to_a_yes_is_already_labelled_no_and_the_other_arrows_still_ask():
    # Renamed in review 1108: the old name said "asks for its words" while the body asserts the second branch is NOT asked.
    # Its stated intent (a decision's branches get words) moved with dgmfix2; the asserts below are unchanged.
    src = "flowchart TD\n  D{Ready?}\n  Y[Ship]\n  N[Fix]\n  D -->|yes| Y\n"
    # dgmfix2: a second branch next to a "yes" now arrives already labelled "no", so it no longer needs asking.
    got = _script(src, "const e = o.join(m, 'D', 'N'); return [e.label, o.needsLabel(m, e), o.needsLabel(m, m.edges[0])];")
    assert got["result"] == ["no", False, False]
    box = _script("flowchart TD\n  A[One]\n  B[Two]\n  C[Three]\n  A --> B\n", "const e = o.join(m, 'A', 'C'); return o.needsLabel(m, e);")
    assert box["result"] is False  # only a decision's branches are asked about
    # INBOX 1679 moved the intent: the FIRST arrow out of a decision asks too (it was "one arrow out is not a branch yet", and
    # a six-block task ended with one silent branch and a user who did not know it needed words).
    first = _script("flowchart TD\n  D{Q}\n  Y[Ship]\n", "const e = o.join(m, 'D', 'Y'); return o.needsLabel(m, e);")
    assert first["result"] is True
    word = _script(src, "const e = o.join(m, 'D', 'N'); return [o.branchWord(m, e), o.branchWord(m, m.edges[0])];")
    assert word["result"] == ["no", "yes"]  # yes is taken by the first branch, so the second is offered no; the first is offered yes
    bare = _script("flowchart TD\n  D{Q}\n  Y[Ship]\n", "const e = o.join(m, 'D', 'Y'); return o.branchWord(m, e);")
    assert bare["result"] == "yes"
    assert "needsLabel" in JOINS and "promptDialog" in JOINS


def test_r6_4_the_connector_menu_hangs_from_its_row_and_each_line_has_its_own_glyph():
    assert '{ anchor: line }' in BUILDER and "openMenuAtPoint(rows" not in BUILDER
    # Hung from the row's right edge by the recipe (`kebabMenu`'s `anchor`), each kind's glyph riding on its item (`lead`), not matched by index.
    assert "row.right - box.width" in SELECTS and "lead: () =>" in JOINS and 'querySelectorAll(":scope > .menu-item")' not in JOINS
    assert ".dgm-link" in CSS
    for style in ("dotted", "thick"):
        assert f'.dgm-link[data-style="{style}"]' in CSS, style
    assert '.dgm-link[data-arrow="true"]::after' in CSS
    # Six rows, six glyphs: the style and the arrow head are the two things that tell them apart.
    assert re.search(r'LINKS = \[\s*\["solid", true, "Arrow"\], \["solid", false, "Line"\], \["dotted", true, "Dotted arrow"\]', JOINS)


def test_r6_5_the_dialog_takes_focus_when_it_opens():
    after = EMBED[EMBED.index("view(\"canvas\");") :]
    assert "await show();" in after and ".dgm-steps button" in after and "dialog).focus" in after


def test_r6_6_arrow_keys_walk_the_create_dialog():
    start = LIBRARY.index("function openLibraryCreatePicker")
    body = LIBRARY[start : LIBRARY.index("function updateLibraryCreateButton")]
    assert "ArrowDown: 1" in body and "ArrowUp: -1" in body
    assert 'list.querySelectorAll("button")' in body


def test_r6_7_the_empty_library_text_names_diagrams():
    line = re.search(r'freshText\.textContent = fresh \? "([^"]+)"', LIBRARY).group(1)
    assert "diagram" in line and chr(0x2014) not in line and "!" not in line


def test_r6_8_a_new_diagram_from_create_opens_the_walkthrough_and_offers_an_example():
    door = MERMAID_JS[MERMAID_JS.index("async function diagramDoor") : MERMAID_JS.index("diagramModel.starter =")]
    anywhere = door[door.index("if (!box)") : door.rindex("return openDiagramBuilder({\n      source: \"\"")]
    # Intent moved (DD-3b, 1107): the door opens on the drawn starter, not the blank walkthrough; the walkthrough still shows for
    # a blank page (Clear in the ... menu, a document with no blocks), and it still offers the example.
    assert "source: diagramModel.starter" in anywhere and 'source: "flowchart TD"' not in anywhere
    # The text-box path keeps the starter: a fence is pasted into prose and wants something to show.
    assert "source: diagramModel.starter" in door
    assert "Start from an example" in STEPS and "diagramModel.starter" in STEPS
    assert "commit" in STEPS and "commit," in BUILDER[BUILDER.index("steps.build") : BUILDER.index("steps.build") + 120]


def test_r6_9_the_connect_picker_draws_each_blocks_shape_and_does_not_raise_a_phones_keyboard():
    for icon in ("ph:square", "ph:rectangle", "ph:pill", "ph:circle", "ph:diamond", "ph:hexagon"):
        assert icon in JOINS, icon
    assert 'about: "Block"' not in JOINS
    assert "(pointer: coarse)" in JOINS and "shell.card.focus(" in JOINS


def test_r6_10_the_phone_controls_are_44_px_and_a_row_names_its_connect_button():
    coarse = CSS[CSS.index("(pointer: coarse)", CSS.index("@container (max-width: 599.98px)")) :]
    assert re.search(r"\.dgm-dirs,[^{]*\{[^}]*min-inline-size: 2\.75rem", coarse)  # 1661 D2: Direction is one button, Add is a split
    assert 'connect.setAttribute("aria-label", `Connect to…, from ${text}`)' in BUILDER
    assert "Draw an arrow from this block to another" in BUILDER


def test_r6_11_the_add_sheet_gives_every_glyph_the_same_slot():
    assert "dgm-add-glyph" in TOUCH
    rule = _rule(".dgm-add-glyph")
    assert "inline-size: 1.5rem" in rule and "place-items: center" in rule


def test_r6_12_the_hint_stays_in_view_and_the_library_counts_lines_as_the_status_bar_does(client):
    rule = _rule(".dgm-next")
    # Intent moved (the owner, 2026-11-11): the hint stays in view because the foot is no longer over the list, not because it sticks;
    # a sticky hint inside the scroller was the other half of the overlap. It is a plain line at the end of the list now.
    assert "position: sticky" not in rule and "inset-block-end" not in rule
    # "flowchart TD\n  A\n  B\n" is three lines in the status bar (a last newline ends a line, it does not start one).
    made = client.post("/documents", json={"title": "Flow", "content": "flowchart TD\n  A --> B\n  B --> C\n", "file_type": "mmd"}).json()
    row = next(d for d in client.get("/documents").json() if d["id"] == made["id"])
    assert row["lines"] == 3
    bare = client.post("/documents", json={"title": "Bare", "content": "one\ntwo", "file_type": "mmd"}).json()
    assert next(d for d in client.get("/documents").json() if d["id"] == bare["id"])["lines"] == 2


def test_r6_13_n_adds_a_box_and_shift_n_repeats_the_last_shape_added():
    # Revised by 1661 D2: Shift+N adds the LAST-USED shape (what the Add button shows), not the selected block's shape,
    # so the button and the key say the same thing. 1 to 7 add a shape; diagram-bar.js owns the table.
    keys = BUILDER[BUILDER.index("const plain = {") : BUILDER.index("if (!plain ||")]
    assert 'shape: "rect"' in keys and "diagramModel.bar.key(event)" in keys
    bar = (JS / "diagram-bar.js").read_text(encoding="utf-8")
    assert 'event.key === "N" ? last()' in bar and "diagramModel.keys = KEYS" in bar
    # The pane with no block: N is a Box too, not the shape the last palette press left behind.
    pane = BUILDER[BUILDER.index("S.pane.addEventListener(\"keydown\""):]
    assert 'shape: "rect"' in pane[:500]
    assert NESTED  # the fixture is shared with the other diagram tests
