"""L742: the lower body's stipple of stars, both looks (the owner 2026-11-12: "the lower body gets texture").

Measured 2026-11-21 in the running companion (`stippleprobe.js`, port 8803): one stipple path inside `.atl-lw-lower` per
look, feminine 45 by 55 px over her dress, masculine 25 by 56 px over his trail, at opacity 0.5, each pointing at its
own look's tile of seven dots painted in the rig's highlight. A pattern, so the texture costs one path and one tile and
moves with the lower body's morph: no new loop (the motion stays gated by `atlasTailCalm.rest`)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ATLAS = (ROOT / "frontend" / "js" / "atlas.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "atlas-lazy.css").read_text(encoding="utf-8")


def test_one_tile_per_look_of_uneven_specks() -> None:
    m = re.search(r'atlasMake\("pattern", \{ id: `\$\{id\}-stipple`, patternUnits: "userSpaceOnUse", width: ([0-9.]+), height: ([0-9.]+) \}, defs\);\n  for \(const \[x, y, r\] of (\[\[.*?\]\])\) atlasMake\("circle", \{ class: "atl-stipple-dot"', ATLAS)
    assert m, "the tile is in the look's defs"
    dots = [[float(v) for v in d.split(",")] for d in re.findall(r"\[([0-9., ]+)\]", m.group(3))]
    assert 5 <= len(dots) <= 12
    w, h = float(m.group(1)), float(m.group(2))
    assert all(0 <= x <= w and 0 <= y <= h for x, y, _r in dots)
    assert len({r for _x, _y, r in dots}) >= 4, "uneven sizes, not a grid of one dot"
    assert max(r for *_xy, r in dots) <= 0.4, "specks, not spots"


def test_both_looks_lower_bodies_take_it() -> None:
    uses = re.findall(r'atlasMake\("path", \{ class: "atl-lower-stipple", d: ([\w.]+), fill: `url\(#\$\{id\}-stipple\)` \}', ATLAS)
    assert sorted(uses) == ["part.fill", "spec.sower.fill"], "her dress and his trail (the ribbon)"


def test_it_is_painted_in_the_rig_and_kept_faint() -> None:
    assert ".atl-stipple-dot { fill: var(--atl-hi); }" in CSS
    op = re.search(r"\.nm-atlas \.atl-lower-stipple \{ opacity: ([0-9.]+);", CSS)
    assert op and 0.3 <= float(op.group(1)) <= 0.6
    assert not re.search(r"atl-lower-stipple[^{]*\{[^}]*animation", CSS), "no loop of its own"
