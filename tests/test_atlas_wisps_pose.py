"""The feminine Atlas's astral wisps and tail, after INBOX 535's follow-ups.

Measured with scratchpad/ui-sweeps/atlaswisps.js (6x, animations stopped):
- the waist and tail wisps ignored the pose: lying down, the tail turns -42deg
  about the hips and the wisps stayed put, their offset from the tail's centre
  falling from 14.0 units standing to 7.6 (they floated beside the body); now
  the same 14.0 in every lying pose;
- on a light page the wisps were barely there: median contrast 1.13 against
  what is behind them, 90th percentile 1.40 (dark: 1.20, 3.25); now 1.33 and
  3.28;
- the body's edge glow stopped at the hips; the tail now carries it.
The masculine look is pixel-identical in six poses and both themes
(scratchpad/ui-sweeps/atlasdepth2.js atlasstill).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
#: atlas.js and its lazy half, atlas-life.js (the living tail and the
#: rings' loops, out of the boot for the gzip budget), read as one.
ATLAS = "\n".join((ROOT / "frontend" / "js" / name).read_text(encoding="utf-8") for name in ("atlas.js", "atlas-life.js"))
CSS = (ROOT / "frontend" / "css" / "characters-lazy.css").read_text(encoding="utf-8")


def _rule(selector: str) -> str:
    match = re.search(re.escape(selector) + r" \{([^}]*)\}", CSS)
    assert match, selector
    return match.group(1)


def test_the_waist_and_tail_wisps_take_the_tail_s_pose():
    assert ATLAS.count("low: true },") == 2, "the waist and the tail wisps, not the shoulder's"
    assert 'atlasGroup(atlasGroup(wisps, "atl-astral-hips", [31, 57]), "atl-lower", spec.lowerPivot)' in ATLAS
    # INBOX 619 (the owner: "when sleeping etc, her lower body actually
    # rotates halfway off her upperbody which stays mostly upright"): lying
    # and curled, neither the lower layer nor the wisps' group turns off the
    # torso; the figure lies down as one chain.
    assert not re.search(r'#nm-buddy\[data-pose="[\w-]+"\] \.atl-layer-lower \{ rotate:', CSS)
    assert not re.search(r'#nm-buddy\[data-pose="[\w-]+"\] \.atl-astral-hips \{', CSS)


def test_the_wisps_stand_out_on_a_light_page_and_keep_their_starlight_in_the_dark():
    # INBOX 550: each wisp is painted along its run by its own gradient
    # (`wisp<i>`), so the theme's difference is in the stops: the nebula's
    # deeper violet on a light page, starlight mixed with white in the dark.
    for k in "012":
        assert "white" not in _rule(f".nm-atlas .atl-st-wisp{k}"), k
        assert re.search(r"& \.atl-st-wisp" + k + r" \{ stop-color: color-mix\(.*white\); \}", CSS), k
    assert "fill: paint" in ATLAS and "url(#${id}-wisp${i})" in ATLAS
    for cls in ("atl-astral-glow", "atl-astral-core", "atl-astral-edge"):
        assert "stroke" not in _rule(f".nm-atlas .{cls}"), cls


def test_the_body_s_edge_glow_carries_down_the_tail_as_a_fill():
    assert "glow: atlasStem(seg, (t) => width(t) + 1.3" in ATLAS
    assert 'atlasMake("path", { class: "atl-sower-glow", d: spec.sower.glow }, glow);' in ATLAS
    rule = _rule(".nm-atlas .atl-sower-glow")
    assert "stroke" not in rule
    edge = _rule(".nm-atlas .atl-edge")
    assert "var(--atl-glow-c)" in rule and "opacity: 0.26" in rule and "opacity: 0.26" in edge
