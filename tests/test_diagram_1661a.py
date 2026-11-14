"""INBOX 1661 step A (first slice): the flowchart's one-row toolbar, diagram-bar.js."""

import gzip
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"
BAR = (JS / "diagram-bar.js").read_text(encoding="utf-8")
BUILDER = (JS / "diagram-builder.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")


def test_the_toolbar_is_one_nowrap_dock_with_the_controls_in_order():
    # Intent moved (DD-2, 1107): one row is the flowchart dock's, so the nowrap is scoped to it; the kinds' docks wrap.
    assert "flex-wrap: nowrap" in CSS.split(".dgm-dock:has(> .dgm-addsplit) {", 1)[1].split("}", 1)[0]
    build = BAR.split("function build(", 1)[1]
    order = build.index("bar.append(split, S.dirs, actions)")
    assert order > 0
    # Eight now: the blocks-list button sits before the menu (1661 review: the list can be hidden).
    # 1661 m: the list button left for the panel's own fold. Intent moved (the owner, 2026-11-11): Expand joined the toolbar's end, made by the
    # kind bar (a diagram in a document only), so the buttons are the same and one control sits before the menu.
    assert "actions.append(suggest, ...hist, ...[diagramModel.kindbar?.expand(S)].filter(Boolean), h.more(S))" in build
    assert 'bar.dataset.dockName = "diagram"' in build and 'setAttribute("role", "toolbar")' in build
    # The eight tiles and the four direction buttons were removed.
    assert "library.build(" not in BUILDER and "for (const [dir, arrow, name] of DIRS)" not in BUILDER


def test_add_is_a_split_whose_main_half_is_the_last_used_shape_saved_in_prefs():
    assert 'const LAST = "diagram.lastShape"' in BAR
    assert "prefs.set(LAST, shape)" in BAR and 'prefs.get(LAST, "rect")' in BAR
    assert "dgm-addmain" in BAR and "dgm-addcaret" in BAR and 'aria-haspopup", "menu"' in BAR


def test_direction_is_a_menu_of_the_four_and_shift_still_cycles_back():
    # 1679 slice 7 (was: one cycling button, "Press to turn it"): a press opens the four with their arrows; Shift keeps the cycle.
    assert "event.shiftKey) return S.turn(DIRS[(at + DIRS.length - 1) % DIRS.length][0])" in BAR
    assert "Direction: ${WORD[dir]}. Choose a direction." in BAR
    assert "openMenuAtPoint(DIRS.map(" in BAR and 'S.dirs.setAttribute("aria-haspopup", "menu")' in BAR and "S.turn = " in BAR
    assert 'const WORD = { TD: "Down", LR: "Right", BT: "Up", RL: "Left" }' in BAR


def test_one_key_table_feeds_the_menu_hints_and_the_handler():
    table = re.search(r"const KEYS = \{([^}]*)\}", BAR).group(1)
    keys = dict(re.findall(r'(\w+): "(\w+)"', table))
    assert [keys[str(n)] for n in range(1, 10)] == ["rect", "round", "stadium", "circle", "diamond", "hexagon", "note", "cylinder", "parallelogram"]
    assert keys["n"] == "rect" and keys["g"] == "group"
    # The menu hint is read from the table (hintOf), and the handler reads the same table.
    assert "Object.keys(KEYS).find" in BAR and "KEYS[event.key]" in BAR
    assert "diagramModel.bar.key(event)" in BUILDER


def test_the_lazy_file_is_registered_and_the_builder_stays_under_its_cap():
    assert 'diagramBar: ["/js/diagram-bar.js"]' in (JS / "documents-mermaid.js").read_text(encoding="utf-8")
    assert 'ensureModule("diagramBar")' in BUILDER
    assert len(gzip.compress((JS / "diagram-builder.js").read_bytes(), 9)) <= 12000
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "diagram-bar.js" not in html


def test_the_phone_keeps_44_px_targets_on_the_new_controls():
    coarse = CSS[CSS.index("(pointer: coarse)", CSS.index("@container (max-width: 599.98px)")) :]
    for name in (".dgm-dirs", ".dgm-addmain", ".dgm-addcaret"):
        assert name in coarse.split("}", 1)[0], name
