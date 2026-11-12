"""INBOX 1723, the owner: "Im iffy about the blue ring that surrounds hovered
over nodes in the graph ... it just feels a little out of place".

Measured with a sweep on a 30px node at zoom 2 (dark): before, a pointer hover
laid a solid 4px #78a8ff ring on the node's edge. After, a pointer hover is a
soft halo in the node's own colour plus a 1.5px hairline 2px clear of the edge
(no accent pixel in the crop), and the keyboard's note keeps a 2px accent ring
3px clear of the dot, 5.0:1 (dark) and 4.8:1 (light) against the ground beside
it. These read the source, since the canvas hides the marks from the lints."""

from __future__ import annotations

import re
from pathlib import Path
from tests._js_scope import gc_frame, unwrapped

ROOT = Path(__file__).resolve().parent.parent
CANVAS = unwrapped((ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8"))


def _fn(name: str) -> str:
    found = re.search(rf"^function {name}\(.*?^\}}", CANVAS, re.S | re.M)
    assert found, name
    return found.group(0)


def _mark() -> str:
    found = re.search(r"^const gcHoverMark = \{.*?^\};", CANVAS, re.S | re.M)
    assert found
    return found.group(0)


def _method(name: str) -> str:
    body = _mark()
    start = body.index(f"  {name}(")
    return body[start:body.index("\n  },", start)]


def test_a_pointer_hover_takes_no_accent_ring():
    draw = gc_frame(CANVAS)
    # Only the keyboard's note, the open card's and the search's current hit
    # are ringed; the hovered id alone is not in that test.
    assert "const marked = node.id === gcKeyboardId(s) || node.id === openId || node.id === hl.current;" in draw
    assert "ringed.push({ node, focused: marked || leaving," in draw
    assert "focused: focused || leaving" not in draw
    # The old flat accent stroke on the node's own edge is gone.
    assert "ctx.lineWidth = 3.5 / k;\n    } else if (item.matched)" not in draw


def test_the_hover_is_the_nodes_own_halo_and_hairline():
    draw = gc_frame(CANVAS)
    assert "gcHoverMark.draw(ctx, hot.node, hot.heat * gcSmooth(hot.node._lit), k, pixelScale);" in draw
    halo = _method("draw")
    # The hairline is the node's colour drawn toward the ink, never the accent.
    assert "ctx.strokeStyle = sprite.line;" in halo and "accent" not in halo
    assert "this.lineGap + this.lineW / 2" in halo and "lineW: 1.5," in _mark()
    # A focused note skips the hairline: two lines would be the ring again.
    assert "if (node._marked) return;" in halo
    assert "(ink[i] - v) * 0.3" in _method("sprite")


def test_the_halo_is_cached_not_built_per_frame():
    sprite = _method("sprite")
    assert "this.cache.get(key)" in sprite and "this.cache.set(key, sprite)" in sprite
    # Keyed on the node's base size, so the ease scales one sprite.
    assert "this.sprite(node.colour, node.r * pixelScale)" in _method("draw")
    assert "createRadialGradient" not in _method("draw")


def test_keyboard_focus_keeps_an_offset_accent_ring():
    draw = gc_frame(CANVAS)
    assert "ringGap: 3," in _mark() and "ringW: 2," in _mark()
    branch = draw[draw.index("} else if (item.focused) {"):draw.index("} else if (item.matched) {")]
    assert "gcHoverMark.ringGap + gcHoverMark.ringW / 2" in branch
    assert "ctx.strokeStyle = gcTokens.accent;" in branch
    assert "ctx.lineWidth = gcHoverMark.ringW / k;" in branch
