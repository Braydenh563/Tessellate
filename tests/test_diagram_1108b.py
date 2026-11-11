"""INBOX 1661 (j), first round: quick ways to build. Measured in the browser by the sweeps named in `diagram-1108.md`."""

from __future__ import annotations

from tests._help_text import help_more_text
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"


def _js(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def test_quick_keys_live_in_the_multi_module_and_do_not_steal_text_fields():
    multi = _js("diagram-multi.js")
    quick = multi[multi.index("diagramModel.quick") - 4500 :]
    for needle in ('low === "d"', 'low === "f"', 'event.key === "/"', "event.shiftKey", "event.altKey", "Delete|Backspace", "dblclick"):
        assert needle in quick, needle
    # Typing, a menu and a field are left alone; Delete and Ctrl+A act only from the picture itself.
    assert "input, textarea, select, .menu-wrap" in quick and "isContentEditable" in quick
    assert "event.target === S.fig" in quick
    assert "diagramModel.quick.wire(S, h" in multi


def test_double_press_on_empty_picture_checks_node_arrow_and_group_first():
    multi = _js("diagram-multi.js")
    start = multi.index('S.fig.addEventListener("dblclick"')
    body = multi[start : start + 900]
    assert "nodeAt" in body and "groupAt" in body and "edgeAt" in body


def test_reverse_direction_is_in_the_connector_menu_and_refuses_a_duplicate():
    joins = _js("diagram-joins.js")
    assert "Reverse direction" in joins and "already points that way" in joins


def test_the_overlay_is_made_once_per_figure():
    # A picture that went away (all blocks deleted) took the layer out and the next draw made a second one: 6 boxes for 3 blocks.
    overlay = _js("diagram-overlay.js")
    assert 'fig.dataset.overlay' in overlay and 'fig.querySelector(":scope > .dgm-overlay")) return' not in overlay


def test_the_shortcuts_sheet_and_guide_list_the_new_keys():
    style = _js("diagram-style.js")
    for needle in ("Shift + Enter", "Alt + Enter", "Ctrl + D", "Ctrl + F, /", "Double press on empty picture"):
        assert needle in style, needle
    topics = help_more_text()
    assert "Shift+Enter adds a joined box" in topics and "Ctrl+F or / finds by name" in topics
