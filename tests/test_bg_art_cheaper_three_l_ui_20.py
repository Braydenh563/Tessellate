"""Source text: L-ui-modernisation-20, the cheaper-equivalent pass over
aurora, microbes and mycelium. Each draws 15 frames a second where it drew
30, and keeps its on-screen speed by standing each draw for the old frames
it replaces: aurora scales its clock and its motes by `k`, microbes and
mycelium run their physics or growth step once per old frame (`owe`), so the
picture at a given moment is the same (scratchpad bgdiff, under 2 percent of
pixels in both themes)."""

from __future__ import annotations

import re
from pathlib import Path

BG_ART = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "bg-art.js").read_text()
OLD_FRAMES = "Math.min(30, bgArtFrameRate()) / Math.min(15, bgArtFrameRate())"


def _style(name: str) -> str:
    start = BG_ART.index(f"    {name}(p, ctx) {{")
    end = re.compile(r"\n    [a-z]+\(p, ctx\) \{").search(BG_ART, start + 10)
    return BG_ART[start : end.start() if end else len(BG_ART)]


def test_the_three_styles_ask_for_fifteen_frames():
    for name in ("aurora", "microbes", "mycelium"):
        assert "fps: 15," in _style(name), name


def test_aurora_scales_its_clock_and_motes_by_the_old_frames():
    body = _style("aurora")
    frame = body[body.index("frame(t) {") :]
    assert f"const k = {OLD_FRAMES};" in frame
    assert "t *= k;" in frame
    assert "my[i] -= (0.12 + z * 0.25) * k;" in frame
    assert "* 0.8 * k;" in frame


def test_microbes_and_mycelium_step_once_per_old_frame():
    micro = _style("microbes")
    assert f"owe += {OLD_FRAMES};" in micro
    assert "for (; owe >= 1; owe--) step();" in micro
    myc = _style("mycelium")
    assert f"owe += {OLD_FRAMES};" in myc
    assert "for (; owe >= 1; owe--) this.tick();" in myc
    # The step count, not the draw count, drives the growth clocks.
    tick = myc[myc.index("tick() {") :]
    assert tick.index("phaseFrame++;") < tick.index("grow(g);")
