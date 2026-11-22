"""The Quick sketch's brush ring follows the ink colour (owner bug).

Measured before (1440x900, scratchpad/ui-sweeps/sketchring.js): the ring's
border computed to the theme's ink (rgb(31, 36, 48) light, rgb(231, 233, 238)
dark) whatever colour was picked. After: the ring's border is the picked ink,
its width is the brush size times the zoom, and a halo in a theme token that
stands off the paper keeps it seen when the ink matches the paper.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAD = (ROOT / "frontend" / "js" / "sketch-pad.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "sketch-pad.css").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    start = PAD.index(f"function {name}(")
    return PAD[start : PAD.index("\n  }\n", start)]


def test_ring_is_tinted_on_every_move() -> None:
    assert "tintRing(ring)" in _fn("moveRing")


def test_ring_border_takes_the_ink_and_halo_a_token() -> None:
    body = _fn("tintRing")
    assert "ring.style.borderColor" in body and "S.ink" in body
    assert '"--ink"' in body and '"--modal-bg-opaque"' in body and "ring.style.boxShadow" in body
    assert "getComputedStyle(ring).color" in body, "tokens are read resolved, never parsed as text"
    assert "S.paper" in body, "the halo is chosen against the paper, not the theme"
    assert "#" not in body.replace("`#", "")


def test_ring_css_keeps_the_theme_ink_and_halo_as_its_default() -> None:
    start = CSS.index("\n.sp-ring {\n  position") + 1
    rule = CSS[start : CSS.index("}", start)]
    assert "border: 1px solid var(--ink)" in rule
    assert "box-shadow: 0 0 0 1px var(--modal-bg-opaque)" in rule


def test_ring_size_still_follows_the_brush() -> None:
    body = _fn("moveRing")
    assert "brushWidth(e) * S.zoom" in body
