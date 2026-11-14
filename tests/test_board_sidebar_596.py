"""The board's sidebar on a board and on a map (INBOX 596).

The owner: the Library's menu "is a little off position", the side dock of
the tool bar "clashes with the side panel", "the height of this side bar
changes on the whiteboard and mindmap", a map wants "mind map specific stuff
in that sidebar" because layers and the element library do not apply there,
and "preset whiteboard and mind map templates that are draggable from the
library". Measured by `scratchpad/ui-sweeps/bm1005-sidebar.js` on the base:
the menu's right edge 20px left of its button's and 15px under it; with the
tools docked at the side, the sidebar drawn over them (58,854px² at 1440)
and 341px tall on a board against 443px on a map; a map's rail Library,
Notes, Layers and Outline; no templates in either Library. The sweep is the
measurement; this pins the shape.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from tests._app_js import frontend_text
from tests._css_paths import FORMER_10, sheets

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


def _body(file: str, name: str) -> str:
    text = frontend_text(file)
    start = re.search(rf"\n(?:async )?function {name}\(", text).start()
    nxt = re.search(r"\n(?:async )?function ", text[start + 10 :])
    return text[start : start + 10 + (nxt.start() if nxt else len(text))]


def test_the_library_menu_hangs_from_its_button_right_edge():
    lib = frontend_text("whiteboard-library.js")
    wire = lib[lib.index('getElementById("wb-lib-more")?.addEventListener') :]
    wire = wire[: wire.index("\n  });")]
    assert '"Library actions", r.right, r.bottom' in wire and "r.left" not in wire
    # Corrected by the difference once it has escaped to <body>.
    assert "r.right - got.right" in wire and "r.bottom + 4 - got.top" in wire


def test_a_side_dock_moves_the_sidebar_beside_it_not_under_it():
    wb = frontend_text("whiteboard.js")
    assert 'viewHost?.setAttribute("data-wb-dock", dock)' in wb
    css = (FRONTEND / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    rule = css[css.index('[data-wb-dock="side"] .wb-sidebar {') :]
    rule = rule[: rule.index("}")]
    # Beside the column, and its height no longer the column's.
    assert "var(--wb-w-tools)" in rule and "--wb-h-tools" not in rule


def test_a_map_has_its_own_tab_and_not_the_boards():
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert 'data-side-tab="map"' in html and 'data-side-panel="map"' in html
    lib = frontend_text("whiteboard-library.js")
    assert 'const WB_SIDE_TABS_BY_KIND = { map: ["library", "map", "outline"], board: ["library", "notes", "layers", "pages"] };' in lib
    assert "WB_SIDE_TABS_BY_KIND[" in _body("whiteboard-library.js", "wbSyncSidebarKind")
    assert "wbRenderSideMap()" in _body("whiteboard-library.js", "wbOpenSidebar")
    # The facts are the stats dialog's own list, one builder for both.
    assert "wbMapStatsList(" in _body("whiteboard-library.js", "wbRenderSideMap")
    assert "wbMapStatsList(" in _body("whiteboard-map.js", "wbShowMapStats")


def test_templates_of_each_kind_are_built_in_sets():
    index = json.loads((FRONTEND / "board-library" / "index.json").read_text(encoding="utf-8"))
    keys = [s["key"] for s in index["sets"]]
    assert keys[:2] == ["templates", "maps"]
    boards = json.loads((FRONTEND / "board-library" / "templates.json").read_text(encoding="utf-8"))
    maps = json.loads((FRONTEND / "board-library" / "maps.json").read_text(encoding="utf-8"))
    assert all(i["template"] == "board" and i["kind"] == "element" for i in boards["items"])
    assert all(i["template"] == "map" and i["kind"] == "branch" for i in maps["items"])
    # The four the empty map offers are in the Library too, with its words.
    offered = re.findall(r'key: "([a-z-]+)",\n    label:', frontend_text("whiteboard-map.js"))
    assert set(offered) <= {i["key"] for i in maps["items"]}
    tile = _body("whiteboard-library.js", "wbLibTile")
    assert "tile.dataset.libTemplate = entry.template" in tile
    place = _body("whiteboard-library.js", "wbLibPlace")
    assert "onto" in place and 'entry.template === "map"' in place


def test_the_side_column_is_one_width_and_one_grid_and_a_phone_has_no_side():
    """596, the rest: the side column measured 173px on a board and 225px on
    a map (the layout select set it), each row centred on its own count, so
    no icon lined up; at 390 the open sidebar's sheet covered the collapsed
    picker (7,554px²). Now the column is `--wb-w-tools` on both, every row
    four cells, and below 600 a side dock is the bottom strip."""
    css = (FRONTEND / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    col = css[css.index('.whiteboard-floating-panel.bottom-center[data-dock="side"] {\n  width: var(--wb-w-tools);') :]
    grid = col[col.index('[data-dock="side"] .wb-tool-section-row {') :]
    grid = grid[: grid.index("}")]
    assert "display: grid" in grid and "repeat(4, 2.25rem)" in grid and "width: 100%" in grid
    assert "grid-column: 1 / -1" in col[: col.index("}", col.index("> .select-shell"))]
    phone = sheets(*FORMER_10)
    # One phone block until UI plan 13b moved each rule beside its own; now any phone block counts.
    band = "\n".join(re.findall(r"@media \(max-width: 599\.98px\) \{\n(.*?)\n\}\n", phone, flags=re.S))
    assert '.whiteboard-floating-panel.bottom-center[data-dock="side"] {\n    inset: auto 0 0;' in band
    assert "#wb-dock-toggle {\n    display: none;" in band


def test_the_library_and_notes_tabs_wait_on_skeletons():
    """596, the rest: "some skeleton loaders are missing like on the
    dashboard". The Library's first open drew nothing until its index and
    sets came (bm1005-sidebar.js, the index held 1.5s: 0 skeletons before,
    6 after); the Notes tab drew an empty list before the notebook's first
    page. Both draw `showSkeletons` and clear them when the list lands."""
    load = _body("whiteboard-library.js", "wbLoadLibrary")
    assert load.index("showSkeletons(") < load.index('apiJson("/board-library")')
    render = _body("whiteboard-library.js", "wbRenderLibrary")
    assert render.index("clearSkeletons(list)") < render.index("list.replaceChildren()")
    notes = _body("whiteboard.js", "renderWbLibrary")
    assert "if (!entriesEverLoaded)" in notes and 'showSkeletons(list, 5, "li")' in notes
    assert "entriesEverLoaded && renderWbLibrary()" in notes
