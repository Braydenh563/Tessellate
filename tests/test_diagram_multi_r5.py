"""DOCUMENTS_PLAN 22.4 R5 (INBOX 1615 a, b): several blocks picked at once, moved, copied or boxed together.

The pure half (`diagramOps.roots`, `moveMany`, `duplicate`, `wrap`) runs in node; the DOM half (diagram-multi.js,
lazy) and the grip drag are read for what they must hold. The Shift+click then drag is measured in a browser and named
in docs/roadmap/HISTORY.md.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.test_diagram_builder import NESTED, _script

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")
MULTI = (JS / "diagram-multi.js").read_text(encoding="utf-8")
POINTER = (JS / "diagram-pointer.js").read_text(encoding="utf-8")
BUILDER = (JS / "diagram-builder.js").read_text(encoding="utf-8")
MERMAID_JS = (JS / "documents-mermaid.js").read_text(encoding="utf-8")

FLAT = "flowchart TD\n  A[One]\n  B[Two]\n  C[Three]\n  D[Four]\n  A --> B\n  B --> C\n  C --> D\n"




def test_roots_keep_layout_order_and_drop_a_block_under_a_picked_group():
    got = _script(NESTED, "return o.roots(m, ['n:E', 'n:D', 'g:S1', 'n:B', 'n:A', 'k:0', 'n:nope']);")
    # D and B sit inside S1 (D inside S2 inside S1): they ride with the group and are not moved twice.
    assert got["result"] == ["g:S1", "n:A", "n:E"]


def test_roots_of_blocks_in_separate_groups_stay_separate():
    got = _script(NESTED, "return o.roots(m, ['n:D', 'n:C']);")
    assert got["result"] == ["n:D", "n:C"]  # the source prints a group ahead of its nodes


def test_a_group_move_keeps_the_picked_order_before_a_target():
    got = _script(FLAT, "const n = o.moveMany(m, ['n:D', 'n:B'], null, 'n:A'); return [n, m.nodes.map((x) => x.id)];")
    assert got["result"] == [2, ["B", "D", "A", "C"]]
    assert got["again"] == got["src"]


def test_a_group_move_to_the_end_and_before_one_of_themselves():
    end = _script(FLAT, "o.moveMany(m, ['n:A', 'n:B'], null, null); return m.nodes.map((x) => x.id);")
    assert end["result"] == ["C", "D", "A", "B"]
    # Dropped before a block that is itself picked: it lands before the next one that stays.
    same = _script(FLAT, "o.moveMany(m, ['n:B', 'n:C'], null, 'n:C'); return m.nodes.map((x) => x.id);")
    assert same["result"] == ["A", "B", "C", "D"]


def test_a_group_move_into_a_group_and_never_into_itself():
    into = _script(NESTED, "o.moveMany(m, ['n:A', 'n:E'], 'S2', null); return m.nodes.map((x) => [x.id, x.group]);")
    assert [g for i, g in into["result"] if i in "AE"] == ["S2", "S2"]
    for target in ("S1", "S2"):
        got = _script(NESTED, f"return [o.moveMany(m, ['g:S1', 'n:A'], '{target}', null), m.subgraphs.map((g) => g.parent)];")
        assert got["result"][0] == 0, target
        assert got["result"][1] == [None, "S1"]


def test_a_group_move_carries_a_picked_group_with_what_it_holds():
    got = _script(NESTED, "o.moveMany(m, ['g:S2', 'n:E'], null, null); return [m.subgraphs.find((g) => g.id === 'S2').parent, m.nodes.find((n) => n.id === 'D').group];")
    assert got["result"] == [None, "S2"]
    assert got["again"] == got["src"]


def test_duplicate_makes_fresh_ids_and_keeps_only_the_joins_inside_the_copy():
    got = _script(FLAT, "const r = o.duplicate(m, ['n:B', 'n:C']); return [r.keys, m.edges.map((e) => e.from + e.to)];")
    keys, edges = got["result"]
    assert keys == ["n:E", "n:F"]
    # B>C is inside the pick and is copied; A>B and C>D cross the edge of it and are not.
    assert sorted(edges) == ["AB", "BC", "CD", "EF"]
    assert got["again"] == got["src"]


def test_duplicate_of_a_group_copies_its_blocks_and_their_inner_joins():
    got = _script(NESTED, "const r = o.duplicate(m, ['g:S1']); return [r.keys, m.subgraphs.map((g) => [g.id, g.parent]), m.edges.length];")
    keys, groups, edges = got["result"]
    assert keys == ["g:G1"]
    assert ["G1", None] in groups and ["G2", "G1"] in groups
    # B>C is inside S1, C>D too; A>B enters it from outside and is not copied: 3 + 2.
    assert edges == 5
    assert got["again"] == got["src"]


def test_duplicate_stops_at_the_block_limit_and_changes_nothing():
    got = _script(FLAT, "while (m.nodes.length < o.MAX - 1) o.addNode(m); const before = m.nodes.length; const r = o.duplicate(m, ['n:A', 'n:B']); return [r, before, m.nodes.length];")
    assert got["result"][0] is None and got["result"][1] == got["result"][2]


def test_wrap_puts_the_pick_in_a_new_group_where_the_first_stood_in_order():
    got = _script(FLAT, "const id = o.wrap(m, ['n:C', 'n:B']); return [id, m.nodes.map((n) => [n.id, n.group]), m.subgraphs.map((g) => [g.id, g.parent])];")
    assert got["result"][0] == "G1"
    assert [i for i, g in got["result"][1] if g == "G1"] == ["B", "C"]
    assert got["result"][2] == [["G1", None]]
    assert got["again"] == got["src"]


def test_wrap_inside_a_group_goes_in_the_parent_of_the_first():
    got = _script(NESTED, "const id = o.wrap(m, ['n:B', 'n:C']); return [id, m.subgraphs.find((g) => g.id === id).parent];")
    assert got["result"] == ["G1", "S1"]


def test_wrap_of_nothing_makes_no_group():
    got = _script(FLAT, "return [o.wrap(m, []), o.wrap(m, ['k:0']), m.subgraphs.length];")
    assert got["result"] == [None, None, 0]


def test_the_group_functions_are_exported_on_the_ops_and_stay_in_the_pure_region():
    ops = (JS / "diagram-ops.js").read_text(encoding="utf-8")
    for name in ("roots", "moveMany", "duplicate", "wrap"):
        assert re.search(rf"\b{name}: ", ops), name
    assert ops.index("dgbMoveMany") < ops.index("DIAGRAM-OPS-END")


def test_the_picked_set_is_a_lazy_file_with_one_export_and_no_new_global():
    assert 'diagramMulti: ["/js/diagram-multi.js"]' in MERMAID_JS
    assert 'ensureModule("diagramMulti")' in BUILDER and "diagramModel.multi.wire(" in BUILDER
    assert "diagramModel.multi = " in MULTI and MULTI.rstrip().split("\n")[-1].strip() == "})();"
    assert re.search(r"^\(\(\) => \{", MULTI, re.M)
    # S.sel stays the one primary key; the rest is S.picked, an ordered Set.
    assert "S.picked = new Set()" in MULTI
    for needle in ("shiftKey", "ctrlKey", "metaKey", "Escape", "/^a$/i", "stopPropagation"):
        assert needle in MULTI, needle


def test_the_bar_is_the_library_selection_bar_with_the_named_actions():
    assert '"library-contextbar selectbar dgm-selectbar hidden"' in MULTI
    assert "selected" in MULTI
    for word in ("Delete", "Duplicate", "Shape", "Box them", "Undo", "Done"):
        assert word in MULTI, word
    assert "library-selected-count" in MULTI and "library-contextbar-end" in MULTI
    assert ".dgm-selectbar" in CSS


def test_the_grip_of_any_picked_row_carries_all_of_them():
    assert "moveMany(" in POINTER and "picked" in POINTER
    assert "within(" in POINTER


def test_builder_keeps_its_one_primary_key_and_marks_the_picked_rows():
    assert "S.picked?.has(" in BUILDER
    assert "S.picked?.clear()" in BUILDER


def test_the_bar_has_eight_buttons_with_colour_and_connect_over_the_picked_blocks():
    """1679 slice 10: Colour reuses the style sheet (K), Connect joins the first picked to the second and asks a decision's words."""
    labels = re.findall(r'(?:tool|smallButton)\("(?:ph:[\w-]+ )?([A-Za-z ]+)"', MULTI[MULTI.index("const shapeBtn") : MULTI.index("S.pane.prepend(bar)")])
    assert sorted(labels) == sorted(["Shape", "Colour", "Connect", "Undo", "Done", "Delete", "Duplicate", "Box them"]), labels
    assert 'ensureModule("diagramStyle")' in MULTI and "diagramModel.style.colour(S, h)" in MULTI
    assert "ops.join(S.m, from, to)" in MULTI and "diagramModel.joins.ask(S, edge, h)" in MULTI
