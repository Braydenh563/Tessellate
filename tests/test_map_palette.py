"""An open map's commands are in the command palette (audit FEAT-11), and a
laid-out map's topic menu offers no front-and-back order (FEAT-17).

Driven in a browser by `scratchpad/ui-sweeps/mmdoc1005-mapchecks.js`; these
pin the wiring and that every row's action is a function the map has.
"""

from __future__ import annotations

from tests._app_js import frontend_text, unwrapped
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
MAP_JS = frontend_text("whiteboard-map.js")
PANES = (JS / "settings-panes.js").read_text(encoding="utf-8") + (JS / "app-features.js").read_text(encoding="utf-8")
WB_JS = frontend_text("whiteboard.js")


def _body(source: str, signature: str) -> str:
    start = source.index(signature)
    return source[start:source.index("\n}\n", start)]


def test_the_palette_takes_the_maps_rows():
    assert "mapPaletteCommands()" in _body(PANES, "function paletteCommands(")


def test_every_row_calls_a_function_that_exists():
    body = _body(MAP_JS, "function mapPaletteCommands(")
    called = set(re.findall(r"=> (wb\w+)\(", body))
    assert called, "no rows"
    everything = "\n".join(unwrapped(p.read_text(encoding="utf-8")) for p in JS.glob("*.js"))
    for name in sorted(called):
        assert re.search(rf"^(async )?function {name}\(", everything, re.M), name


def test_the_rows_need_a_map_on_screen():
    body = _body(MAP_JS, "function mapPaletteCommands(")
    assert "wbIsMap()" in body and "getClientRects()" in body


def test_order_is_not_offered_on_a_laid_out_map():
    start = WB_JS.index('subItem("Order"')
    guard = WB_JS[start - 400:start]
    assert 'wbMapLayout() === "free"' in guard
