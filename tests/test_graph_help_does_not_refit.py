"""Opening the graph's help moves nothing (owner, 2026-10-12: "the graph still
shifts when I open that tooltip dropdown"). The help panel was watched like a
side panel, so the map refitted around it: measured, the camera moved 215px.
It is a menu over the map, like the gear's options and the dock."""

from pathlib import Path
from tests._js_scope import unwrapped

JS = unwrapped((Path(__file__).resolve().parent.parent / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8"))


def test_the_help_panel_is_a_menu_not_a_panel_for_the_refit():
    line = next(ln for ln in JS.splitlines() if ln.startswith("const GC_FIT_MENUS"))
    assert "#graph-help-panel" in line


def test_the_help_panel_still_keeps_a_fit_clear_of_itself():
    block = JS[JS.index("const GC_FIT_OVERLAYS"):JS.index("const GC_FIT_MENUS")]
    assert "#graph-help-panel" in block
