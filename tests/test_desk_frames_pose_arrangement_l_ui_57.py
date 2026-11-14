"""Source text: the capture runs in a headless browser render this suite does not start, so what it pins is read from the render script. L-ui-modernisation-57: the desk frames carry each pose's own lower-body and nebula arrangement, the same every run.

Source text: "Render the pose-keyed lower-body and nebula variants into the desk companion's frames (1683 B1, B3, B5, B6)"
(UI_MODERNISATION_PLAN.md "Decisions made" 7: one arrangement per pose, the app's first authored row of the pose's state,
what the app draws under reduced motion; the variation inside a pose stays live on `behaviour.Flow`). Before, the live rig
picked a random variant per capture and froze its drift paths at a random moment: two captures of one frame differed by
3,900 to 7,800 px below the waist.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RENDER = (ROOT / "scripts" / "render_desk_frames.js").read_text(encoding="utf-8")
LIFE = (ROOT / "frontend" / "js" / "atlas-life.js").read_text(encoding="utf-8")


def test_source_text_the_capture_pins_the_rig_to_its_still_path() -> None:
    """Source text: "one arrangement per pose ... what the app draws under reduced motion": the capture wraps the rig's
    lower-body call so it always runs not live (the first row, no drift path), and starts it afresh."""
    assert re.search(r"window\.atlasRigLower = Object\.assign\(\(rig, now, live, buddy\) => real\(rig, now, false, buddy\), real\)", RENDER)
    assert 'rig.lower.state = ""' in RENDER


def test_source_text_the_streams_redraw_is_held_at_its_drawn_shapes() -> None:
    """Source text: "the same every run": the streams' own redraw (`atlasRigLower.morph`, INBOX 1709) runs from a clock that
    starts at random, so the capture stops it and puts the drawn shapes back (1,800 to 4,400 px apart below the waist)."""
    assert "clearTimeout(m.timer); m.timer = 0;" in RENDER
    assert "real.morph.rest(rig.lower);" in RENDER
    assert "atlasRigLower.morph.rest = (low) => {" in LIFE


def test_source_text_the_still_path_is_the_first_row_and_no_drift() -> None:
    """Source text: "the app's first authored row": not live, the rig picks row 0 and runs no drift path; the wrap reaches
    the rig only through the window binding atlas-motion.js calls."""
    assert "const pick = live ? Math.floor(Math.random() * spec.v.length) : 0;" in LIFE
    assert "if (!live || !rig.box.isConnected || !rig.box.animate) {" in LIFE
    assert re.search(r"Object\.assign\(window, \{[^}]*\batlasRigLower\b", LIFE)
    motion = (ROOT / "frontend" / "js" / "atlas-motion.js").read_text(encoding="utf-8")
    assert "if (rig.lower) atlasRigLower(rig, now, live, buddy);" in motion


def test_source_text_every_capture_draws_the_figure_at_its_own_size() -> None:
    """Source text: "the same every run": the page shrinks the figure to fit a tight perch (`--nmb-scale` 0.75); the capture
    holds it at 1 (masculine stand came out 139 to 192 px tall over four runs)."""
    assert 'realSet.call(clone.style, "--nmb-scale", "1", "important");' in RENDER
    assert 'k !== "--nmb-scale"' in RENDER


def test_source_text_every_shipped_frame_has_a_capture() -> None:
    """Source text: "Render the ... variants into the desk companion's frames": a full render needs every frame the
    loader reads; `tumble` (the spin frames' base) fell out of the capture list in PR 216 and the render stopped at it."""
    from tessellate.core.overlay import sprites

    names = set(re.findall(r'name: "([a-z_0-9]+)"', RENDER))
    generated = re.compile(r"(walk|wave|idle)\d+")
    assert "...Array.from({ length: 12 }, (_, i) => ({ name: `walk${i}`" in RENDER
    missing = [n for n in sprites.FRAME_NAMES if n not in sprites.CARD_FRAMES and n not in names and not generated.fullmatch(n)]
    assert missing == []


def test_source_text_the_pose_boxes_keep_their_arrangement() -> None:
    """Source text: "no shipped PNG carries the variants": the per-frame reset clears the loop boxes, never the rig's pose boxes."""
    reset = next(line for line in RENDER.splitlines() if 'el.style.removeProperty("transform"); el.style.removeProperty("transform-origin")' in line)
    assert "atl-lw-pose" not in reset
