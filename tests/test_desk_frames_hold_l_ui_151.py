"""Source text: the capture runs in a headless browser render this suite does not start, so what it holds still is read from the render script and the figure's code. L-ui-modernisation-151: two captures of one desk frame agree.

With the lower body, wisps, nebula and hair pinned (L-ui-modernisation-57), two captures of masculine stand still differed by
1,223 px above and 3,080 below the waist (eight frames: 415 to 1,263 above, 2,340 to 3,823 below): the arms were caught
wherever the live probe had them (left arm 8 vs 87.5 deg), the tail's own loop redrew it after the capture's sample (the
sample went through a window binding atlas-life.js no longer reads, so the idle cycle was never sampled at all), the
breath's Web Animation froze at any moment (torso 1.0132 vs 1.0141) and the pointer's aim wrote the eyes' offsets.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RENDER = (ROOT / "scripts" / "render_desk_frames.js").read_text(encoding="utf-8")
LIFE = (ROOT / "frontend" / "js" / "atlas-life.js").read_text(encoding="utf-8")


def test_source_text_the_tail_is_held_by_the_figure_s_own_hook() -> None:
    """Source text: "pin ... tail sway": the sample is drawn by a hook on an exported function (the tail drawing is inside
    atlas-life.js's closure), which stops the loop, cancels the rest sway and the breath, and keeps the loop from redrawing."""
    assert "atlasTailFrame.hold = (tail, w) => {" in LIFE
    assert "if (!box.isConnected || tail.held) return;" in LIFE
    hook = LIFE.split("atlasTailFrame.hold = (tail, w) => {", 1)[1].split("\n  };", 1)[0]
    assert "atlasBreathFrame(tail.box, false);" in hook
    assert "a.cancel()" in hook
    assert "atlasTailDraw(tail," in hook
    assert "atlasTailFrame.hold(" in RENDER
    assert "typeof atlasTailDraw" not in RENDER


def test_source_text_an_idle_frame_cannot_go_unsampled() -> None:
    """Source text: "two captures of one frame agree": a missing hook stops the render instead of shipping 24 copies of the stand."""
    assert 'throw new Error("no tail hold to sample")' in RENDER


def test_source_text_the_arms_are_drawn_on_their_mark_after_the_freeze() -> None:
    """Source text: "pin the arms": settleArms waits for the arms to stop, not for their pose; after every animation is
    held, the rig takes one still frame (not live: each joint set on its target) from the held probe."""
    freeze = RENDER.index("for (const a of document.getAnimations()) {")
    mark = RENDER.index("rig.fresh = true;")
    assert mark > freeze
    tail = RENDER[mark:mark + 700]
    assert "rig.reads = rig.arms.map((arm) => ({ ...atlasRigRead(arm), anim: false }));" in tail
    assert "atlasRigFrame(rig, performance.now());" in tail


def test_source_text_the_eyes_aim_is_held() -> None:
    """Source text: "pin ... eyes": the pointer's aim and the saccades write the eyes' offsets at any moment; the capture
    stops both and clears what they wrote before the frame is frozen."""
    assert "nameMarkBuddyAim.set = () => {};" in RENDER
    assert "atlasBlink.saccade.step = () => false;" in RENDER
    assert '["--nmb-ex", "--nmb-ey", "--nmb-hx"]' in RENDER
