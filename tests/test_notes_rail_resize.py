"""The Connections column can be resized (INBOX 1443, owner 2026-10-29).

The clamp and key maths of frontend/js/notes-rail-spy.js run in node; the rest
are source checks, since a drag needs a pointer (measured with Playwright,
numbers in the commit).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPY = ROOT / "frontend" / "js" / "notes-rail-spy.js"

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not available")

HARNESS = r"""
const vm = require("node:vm");
const fs = require("node:fs");
const ctx = { Math, Number, Set, $: () => null, notesRailWide: { matches: false } };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + "\n;globalThis.api = { notesRailClamp, notesRailKeyWidth };", ctx);
const a = ctx.api;
console.log(JSON.stringify({
  low: a.notesRailClamp(10, 900),
  high: a.notesRailClamp(5000, 900),
  mid: a.notesRailClamp(333.4, 900),
  roomBound: a.notesRailClamp(500, 380),
  roomBelowMin: a.notesRailClamp(500, 100),
  left: a.notesRailKeyWidth("ArrowLeft", 300),
  right: a.notesRailKeyWidth("ArrowRight", 300),
  home: a.notesRailKeyWidth("Home", 300),
  other: a.notesRailKeyWidth("a", 300) === undefined,
}));
"""


@node
def test_clamp_and_keys_run_in_node() -> None:
    out = json.loads(subprocess.run(["node", "-e", HARNESS, str(SPY)], capture_output=True, text=True, check=True).stdout)
    assert out["low"] == 240 and out["high"] == 560 and out["mid"] == 333
    assert out["roomBound"] == 380, "the list keeps its reading width"
    assert out["roomBelowMin"] == 240
    assert (out["left"], out["right"]) == (316, 284), "the handle is on the left edge: left widens, 16px a press"
    assert out["home"] is None and out["other"] is True


def test_the_handle_is_a_keyboard_reachable_separator_on_fine_pointers_only() -> None:
    js = SPY.read_text(encoding="utf-8")
    assert 'setAttribute("role", "separator")' in js and 'setAttribute("tabindex", "0")' in js
    assert "(pointer: fine) and (min-width: 600px)" in js
    assert "prefs.set(NOTES_RAIL_W_KEY" in js and "catch" in js, "kept per device, storage may be blocked"
    assert "setPointerCapture" in js and "ResizeObserver" not in js.split("wireNotesRailResize")[1]


def test_the_width_is_the_grid_track_and_the_handle_follows_the_rail() -> None:
    css = (ROOT / "frontend" / "css" / "04-chat-dock-appearance.css").read_text(encoding="utf-8")
    assert "grid-auto-columns: clamp(17rem, 21vw, 20rem)" in css, "the stylesheet's own width is what Home restores"
    js = SPY.read_text(encoding="utf-8")
    assert "layout.style.gridAutoColumns" in js and "gridArea" in js
    assert "notesRailHandle.hidden = !entry" in js, "no handle without the rail (no empty track)"


def test_the_recipe_and_the_guide_say_it() -> None:
    design = (ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8")
    assert "`notesRailResize`" in design and "INBOX 1443" in design
    topics = (ROOT / "src" / "tessellate" / "ai" / "help_topics_more.py").read_text(encoding="utf-8")
    assert "Drag its left edge" in topics and "Home puts it back" in topics
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "Drag its left edge" in html
