"""INBOX 1111: the companion's menu is placed between the top bar and the dock, not over them (390 wide).

Measured at 390x844 on the Notes list (Atlas on a card, right-click on its face): the menu, 11 rows and 416px tall,
was clamped to the window's 8px margin and landed at top 8, over the top bar (bottom edge 58), though 58 to 786
holds it. `room` takes the bars' edges when the menu fits between them and the window otherwise.
"""

from __future__ import annotations

import json
import shutil
import subprocess

from pathlib import Path

import pytest
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parents[1]
SRC = unwrapped((ROOT / "frontend" / "js" / "companion-menu.js").read_text(encoding="utf-8"))
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

START = SRC.index("  const margin = 8;\n  const room = ")
END = SRC.index("  const place = at ? inside : beside;")
PLACEMENT = SRC[START:END]

HARNESS = """
globalThis.innerWidth = 390;
globalThis.innerHeight = %(vh)d;
const nameMarkBuddyLedges = () => ({ top: %(top)s, bottom: %(bottom)s });
const at = %(at)s;
const menu = {
  style: { translate: "", maxHeight: "" },
  getBoundingClientRect() {
    const [x, y] = (this.style.translate || "0px 0px").split(" ").map(parseFloat);
    const h = Math.min(%(h)s, this.style.maxHeight ? parseFloat(this.style.maxHeight) : Infinity);
    return { left: 100 + x, right: 348 + x, top: 300 + y, bottom: 300 + y + h, width: 248, height: h };
  },
};
const face = { getBoundingClientRect: () => ({ left: 200, right: 264, top: %(face)s, bottom: %(face)s + 92 }) };
%(code)s
(at ? inside : beside)();
const r = menu.getBoundingClientRect();
process.stdout.write(JSON.stringify({ top: r.top, bottom: r.bottom, cap: menu.style.maxHeight }));
"""


def _place(at: bool, face_top: float, menu_h: float, top_bar: float | None = 58, dock_top: float | None = 786, vh: int = 844) -> dict:
    script = HARNESS % {
        "vh": vh,
        "top": json.dumps({"bottom": top_bar} if top_bar is not None else None),
        "bottom": json.dumps({"top": dock_top} if dock_top is not None else None),
        "at": "true" if at else "false",
        "h": menu_h,
        "face": face_top,
        "code": PLACEMENT,
    }
    run = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-2000:]
    return json.loads(run.stdout)


@needs_node
@pytest.mark.parametrize("at", [False, True])
def test_a_tall_menu_that_fits_between_the_bars_lands_between_them(at: bool) -> None:
    out = _place(at, face_top=40, menu_h=416)
    assert out["top"] >= 66, "under the top bar's 58 and the 8px margin, not at the window's 8"
    assert out["bottom"] <= 778, "over the dock's 786 less the margin"


@needs_node
@pytest.mark.parametrize("at", [False, True])
def test_a_menu_low_on_the_page_stays_above_the_dock(at: bool) -> None:
    out = _place(at, face_top=700, menu_h=416)
    assert out["bottom"] <= 778 and out["top"] >= 66


@needs_node
def test_a_menu_taller_than_the_gap_is_capped_to_it_and_scrolls_inside() -> None:
    # 150% zoom at 390 wide: a 563px window, bars to 55 and from 505, the menu 522px tall (over the top bar at 8 before).
    out = _place(False, face_top=0, menu_h=522, top_bar=55, dock_top=505, vh=563)
    assert out["cap"] == "434px" and out["top"] == 63 and out["bottom"] == 497, "the gap less a margin each side"


@needs_node
def test_a_gap_too_small_to_read_in_keeps_the_window() -> None:
    out = _place(False, face_top=0, menu_h=400, top_bar=55, dock_top=200, vh=563)
    assert out["cap"] == "" and out["top"] == 8, "145px of gap: the window's margins, the menu's own max-height as before"


@needs_node
def test_a_page_without_bars_is_as_before() -> None:
    out = _place(False, face_top=0, menu_h=300, top_bar=None, dock_top=None)
    assert out["top"] == 8


def test_both_placements_ask_room() -> None:
    inside = SRC.split("const inside = () => {", 1)[1].split("const beside", 1)[0]
    assert "const { lo, hi, now } = room();" in inside
    assert "const top = Math.min(Math.max(lo, box.top), hi - now.height);" in SRC
