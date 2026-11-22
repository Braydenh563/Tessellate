"""The whiteboard context bar's "More" menu opens against the bar.

The owner (2026-09-23): "its kebab menu lands away from the bar". In a short
window neither side of the bar holds the whole menu, and the app-wide
placement pins such a menu to the last position that fits, which put it over
the bar it came from (measured at 947x608: menu 267 to 600, bar 316 to 354).
`wbKeepMenuBesideBar` takes the side with more room and caps the height
instead. Run in node against its own source with stand-in elements; the
browser half is `scratchpad/ui-sweeps/wbtextbar.js`.
"""

from tests._app_js import frontend_text
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = frontend_text("whiteboard.js")


def _function(name: str) -> str:
    start = SOURCE.index(f"function {name}(")
    return SOURCE[start : SOURCE.index("\n}\n", start) + 3]


def _place(window_h: int, bar_top: int, bar_bottom: int, natural: int) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = (
        f"globalThis.window = {{ innerHeight: {window_h} }};\n"
        + _function("wbKeepMenuBesideBar")
        + f"""
const menu = {{
  _escapedHome: {{}},
  style: {{}},
  getBoundingClientRect() {{
    const top = parseFloat(this.style.top || "0");
    const cap = parseFloat(this.style.maxHeight);
    const h = Number.isFinite(cap) ? Math.min({natural}, cap) : {natural};
    return {{ top, bottom: top + h, height: h }};
  }},
}};
const bar = {{ getBoundingClientRect: () => ({{ top: {bar_top}, bottom: {bar_bottom}, width: 480, height: {bar_bottom - bar_top} }}) }};
wbKeepMenuBesideBar(menu, bar);
const box = menu.getBoundingClientRect();
console.log(JSON.stringify({{ top: box.top, bottom: box.bottom, cap: menu.style.maxHeight }}));
"""
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip())


def test_a_short_window_puts_the_menu_above_the_bar_not_over_it():
    box = _place(608, 316, 354, 333)
    assert box["bottom"] <= 316 and 316 - box["bottom"] <= 8, box
    assert box["top"] >= 8, box


def test_a_menu_that_fits_below_opens_just_under_the_bar():
    box = _place(760, 316, 354, 333)
    assert 354 <= box["top"] <= 354 + 8, box
    assert box["bottom"] <= 760 - 8, box


def test_the_side_with_more_room_wins_and_the_menu_scrolls_in_it():
    box = _place(608, 150, 188, 600)
    assert 188 <= box["top"] <= 196, box
    assert box["bottom"] <= 600, box


def test_the_bar_menu_toggle_calls_it():
    # Since INBOX 396 every board menu hangs from its opener; the context
    # bar's menu still takes the bar as its opener, which is what this pins.
    assert 'const edge = menu.id === "wb-context-menu" ? document.getElementById("wb-context") : toggle;' in SOURCE
    assert "wbKeepMenuBesideBar(menu, edge);" in SOURCE
