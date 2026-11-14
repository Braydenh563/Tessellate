"""INBOX 659: a double-click on a top-bar tab goes back to its first sub-tab."""

from tests._app_js import frontend_text
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_a_top_tab_double_click_selects_its_first_sub_tab():
    shell = (ROOT / "frontend" / "js" / "phone-shell.js").read_text(encoding="utf-8")
    assert 'button.addEventListener("dblclick"' in shell
    assert "$(`${button.dataset.tab}-subtabs`)?.querySelector('[role=\"tab\"]:not([hidden])')" in shell
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    for tab in ("notes", "library"):
        assert f'id="{tab}-subtabs"' in html and f'data-tab="{tab}"' in html


def test_map_bend_undo_snapshot_is_the_old_line():
    src = frontend_text("whiteboard-map.js")
    done = src[src.index("if (patch.edge_bend === before.edge_bend"):]
    assert done.index("child.data = { ...child.data, ...before };") < done.index("await wbMapSetNodeStyle(child, patch);")
