"""Two more animations the compositor refused, and what that cost (L138, L176, L231).

`test_atlas_composite_1101.py` records the rule: one animation off the compositor makes
the page restyle every animated element every frame. Found 2026-11-14 with a trace
(`compositeFailed` on `Animation` events, restarting every loop under the trace), the
feminine Atlas at rest, median of three 20 s runs in headless Chromium 153 on a loaded
four-core container:

- `translate` and `rotate` loops on an `svg` root (her wisps and glints, eight loops)
  fail with bit 19; moved to a span box around the drawing they composite;
- an empty box (`width: 0; height: 0`: the orbit and ring pivots, 16 loops) fails with
  bit 17; a 1px box composites and moves nothing (`transform-origin: 0 0`, set inline: the boot sheet is at its byte cap).

Style recalcs a minute 3,075 to 2,019, layouts 3,027 to 1,989, main thread 18.6 s to
13.1 s (`scratchpad/ui-sweeps/companionperf.js` IDLE=1 and an A/B of the same look).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAZY = (ROOT / "frontend" / "css" / "atlas-lazy.css").read_text(encoding="utf-8")
CONS = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
ATLAS = (ROOT / "frontend" / "js" / "atlas.js").read_text(encoding="utf-8")


def _rules(css: str) -> list[tuple[str, str]]:
    return re.findall(r"([^{}/]+?)\{([^{}]*)\}", re.sub(r"/\*.*?\*/", "", css, flags=re.S))


def test_no_loop_runs_on_an_svg_root() -> None:
    bad = [sel.strip() for sel, body in _rules(LAZY + CONS) if re.search(r">\s*svg\s*$", sel.strip()) and re.search(r"\banimation(-name)?\s*:", body)]
    assert not bad, f"an animation on an svg root is refused by the compositor (bit 19): {bad}"


def test_the_wisps_drift_on_a_box_around_the_drawing() -> None:
    assert '.startsWith("wisps")' in ATLAS and "atl-lw-drift-box" in ATLAS
    assert re.search(r"\.atl-lw-pose-wisps > \.atl-lw-drift-box \{ animation: atl-lw-drift", LAZY)
    assert 'Object.assign(wrap.style, { position: "absolute", left: "0", top: "0", width: "64px", height: "92px" });' in ATLAS


def test_a_looping_pivot_is_never_an_empty_box() -> None:
    assert 'arm.style.width = arm.style.height = "1px";' in ATLAS and 'frame.style.width = frame.style.height = "1px";' in ATLAS
    assert "place(frame, 0, 0, 1, 1)" in ATLAS
