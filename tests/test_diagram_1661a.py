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
    assert "flex-wrap: nowrap" in CSS.split(".dgm-dock {", 1)[1].split("}", 1)[0]
    build = BAR.split("function build(", 1)[1]
    order = build.index("bar.append(split, S.dirs, actions)")
    assert order > 0
    # Eight now: the blocks-list button sits before the menu (1661 review: the list can be hidden).
    assert "actions.append(suggest, ...hist, outline, h.more(S))" in build
    assert 'bar.dataset.dockName = "diagram"' in build and 'setAttribute("role", "toolbar")' in build
    # The eight tiles and the four direction buttons are not built any more.
    assert "library.build(" not in BUILDER and "for (const [dir, arrow, name] of DIRS)" not in BUILDER


def test_add_is_a_split_whose_main_half_is_the_last_used_shape_saved_in_prefs():
    assert 'const LAST = "diagram.lastShape"' in BAR
    assert "prefs.set(LAST, shape)" in BAR and 'prefs.get(LAST, "rect")' in BAR
    assert "dgm-addmain" in BAR and "dgm-addcaret" in BAR and 'aria-haspopup", "menu"' in BAR


def test_direction_is_one_cycling_button_that_shift_reverses():
    assert "DIRS.length - 1 : 1" in BAR
    assert "Direction: ${WORD[dir]}. Press to turn it." in BAR
    assert 'const WORD = { TD: "Down", LR: "Right", BT: "Up", RL: "Left" }' in BAR


def test_one_key_table_feeds_the_menu_hints_and_the_handler():
    table = re.search(r"const KEYS = \{([^}]*)\}", BAR).group(1)
    keys = dict(re.findall(r'(\w+): "(\w+)"', table))
    assert [keys[str(n)] for n in range(1, 8)] == ["rect", "round", "stadium", "circle", "diamond", "hexagon", "note"]
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
