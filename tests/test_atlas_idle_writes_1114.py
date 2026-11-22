"""What the in-app Atlas writes and reads at idle, per frame (L176, L138, L231).

Measured 2026-11-14 (headless, feminine Atlas on the dashboard, mains setting, 20 s; every
style write, `getComputedStyle` and `setAttribute` counted by caller): no `getComputedStyle`
and no custom-property write runs per frame. The reads are 99 a minute, all in a task after a
drawn frame (`atlasPropsFrame`, `atlasRigWake.afterPaint`); the custom properties are the gaze
(`--nmb-ex`, `--nmb-ey`, `--nmb-hx`), 258 a minute. What wrote every frame was path geometry:
the lower body's morph (`d` 10,285 a minute at 10 Hz) and the tail. And the one loop that kept
every animated element restyling each frame was the torso's breath, a Web Animation on an svg
`<g>` (never composited); it is now written in the morph's own task (test_atlas_breath_687.py).
These guards keep the per-frame paths free of reads and custom-property writes.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parents[1]
LIFE = unwrapped((ROOT / "frontend" / "js" / "atlas-life.js").read_text(encoding="utf-8"))
READS = ("getComputedStyle", "getBoundingClientRect", "getAnimations", "offsetWidth", "offsetHeight", "getBBox")


def _block(start: str) -> str:
    i = LIFE.index(start)
    m = re.compile(r"^\};?$", re.M).search(LIFE, i)
    return LIFE[i : m.end()]


def test_the_per_frame_draws_read_no_style_and_write_no_custom_property() -> None:
    for start in ("function atlasTailDraw(", "atlasRigLower.morph.draw = ", "atlasRigLower.morph.run = ", "atlasBreathFrame.put = "):
        body = _block(start)
        for read in READS:
            assert read not in body, f"{start} reads {read} on its frame"
        assert not re.search(r"setProperty\(\s*[\"'`]--", body), f"{start} writes a custom property on its frame"


def test_no_web_animation_runs_on_an_element_inside_an_atlas_drawing_at_idle() -> None:
    # An svg child's animation is never composited (a `<g>`'s `transform`: 3,150 "Style changed" a minute in a trace).
    assert not re.search(r"atlasTorsos\.map\(\(el\) => \{\s*const anim = el\.animate", LIFE)
