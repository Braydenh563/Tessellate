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


def test_source_text_the_act_is_held_at_its_moment_from_the_start() -> None:
    """Source text: "two captures of one frame agree": the wait for the arms took 0.4 to 4.8 s, so a 2.4 s look had
    ended before the freeze in one capture of three (the head 1 px over, 1,379 px apart); the act is held as it starts."""
    setup = RENDER.index('b.dataset.feel = "calm";')
    hold = RENDER.index("a.currentTime = window.__actAt(a, frame); }", setup)
    assert hold < RENDER.index("await settleArms(page);", setup)
    assert RENDER.count("window.__actAt(a, frame)") == 3  # the setup, the freeze, and once more just before the shot
    assert RENDER.rindex("window.__actAt(a, frame)") < RENDER.index("const body = await steadyShot(page, clip);")


def test_source_text_the_pin_s_own_transitions_are_finished_before_the_shot() -> None:
    """Source text: "two captures of one frame agree": the pinned joints start transitions after the freeze, and a moving
    arm passed the shot's 1.5% (hang_one 144 to 261 px apart); they are finished in the same step."""
    pin = RENDER.index("atlasRigFrame(rig, performance.now());")
    shot = RENDER.index("const body = await steadyShot(page, clip);")
    assert "if (a.transitionProperty) a.finish();" in RENDER[pin:shot]


def test_source_text_a_frame_ships_only_when_two_takes_agree() -> None:
    """Source text: "two captures of one frame agree": with every part pinned, two captures of 126 frames still differed in
    two to three frames, a different one each run (a lean with the stand's arms, 11,468 px; an idle step 7 px over). Each
    frame is taken from its neutral start until two takes agree, and the capture stops when none do."""
    loop = RENDER.index("const takes = [];")
    body = RENDER[loop : RENDER.index("no two takes agree", loop)]
    assert "await shoot(f)" in body and "o[0].equals(t[0])" in body
    assert "fs.writeFileSync(path.join(out, look, `${f.name}.png`), pick[0]);" in RENDER


def test_source_text_the_rig_stays_shut_from_the_pin_to_the_shot() -> None:
    """Source text: "two captures of one frame agree": a live rig frame after the pin, woken by the rig's next look, eased
    hang_one's waving arm on in real time (five takes, five places, 348 to 706 px apart with every read the same)."""
    pin = RENDER.index("atlasRigFrame(rig, performance.now());")
    assert RENDER.index("window.__rigOpen = false;", pin) < RENDER.index("const body = await steadyShot(page, clip);")
    assert "if (window.__rigOpen) return frameReal(rig, now);" in RENDER
    assert "arm.hist = [];" in RENDER[RENDER.index("const rigBox"):pin]


def test_source_text_each_take_starts_the_act_afresh() -> None:
    """Source text: "two captures of one frame agree": the same class set again kept the last take's animations (a look's
    head turned left, right and ahead in five takes, 2,195 to 3,699 px apart)."""
    set_ = RENDER.index('b.className = frame.classes.join(" ");')
    assert RENDER.rindex('b.className = "";', 0, set_) > set_ - 600


def test_source_text_the_streams_redraw_is_held_every_frame() -> None:
    """Source text: "two captures of one frame agree": the streams' redraw timer came back during a run, and two runs that
    agreed take to take still had seven idle and walk frames 4,687 to 6,256 px apart below the waist."""
    pin = RENDER.index("const rigBox = b.querySelector(\".atl-figure-box\");")
    block = RENDER[RENDER.rindex("for (const r of new Set(", 0, pin):pin]
    assert "clearTimeout(r.lower.morph.timer);" in block and "atlasRigLower.morph.rest(r.lower);" in block


def test_source_text_every_take_draws_from_one_seeded_stream() -> None:
    """Source text: "two captures of one frame agree": runs that agreed take to take still drew seven to eleven idle and
    walk frames one of two ways (4,687 to 6,301 px apart): the page's random draws are seeded afresh in every take."""
    assert "Math.random = () => {" in RENDER
    setup = RENDER.index('b.dataset.feel = "calm";')
    assert RENDER.rindex("window.__seed(151);", 0, setup) > RENDER.rindex("for (const name of b.getAttributeNames())", 0, setup)


def test_source_text_the_full_figure_draws_in_every_frame() -> None:
    """Source text: "two captures of one frame agree": the page's frame budget can set the lite set part-way through a
    run when the shots slow it, and the frames after it drew the streams another way; the render keeps it off."""
    boot = RENDER.index("window.__actAt = (a, frame) => {")
    assert RENDER.rindex('root.removeAttribute("data-atlas-lite");', 0, boot) > 0
    assert 'attributeFilter: ["data-atlas-lite"]' in RENDER[:boot]
