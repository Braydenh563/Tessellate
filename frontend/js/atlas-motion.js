//: **One blink of a layered figure** (INBOX 540): the lid a third down,
//: two thirds down, then shut, held, and back up through the same frames:
//: 120ms down, 40 held, 160 up, or a drowsy 380, 520 and 520 (`slow`).
//: Each frame is a root of its own (`lidf-1`, `lidf-2`, the lids), drawn
//: whole, so only their opacity changes, by a CSS animation the class
//: `atl-blinking` starts (`atl-blink-f1` and the rest, the CSS): the
//: compositor runs it, and nothing is laid out or painted for a blink. A
//: later frame lies over an earlier one and its skin covers the earlier
//: lid's edge, so the frames stack as the lid comes down. Strokes never
//: change width.
function atlasBlink(box, slow = false) {
  const roots = box.querySelectorAll(".atl-layer-lids");
  if (!roots.length) return;
  const cls = slow ? "atl-blinking-slow" : "atl-blinking";
  for (const el of roots) el.classList.add(cls);
  setTimeout(() => {
    for (const el of roots) el.classList.remove(cls);
  }, slow ? 1460 : 360);
}

//: **When the figures blink.** One clock for every layered figure on the
//: page: every 3.4 to 7.6 seconds each one that is on screen, has its eyes
//: open and may move blinks once, now and then twice; a drowsy or groggy companion
//: blinks slowly and stays shut a moment. Avatar animation Off, the app's
//: Reduced motion or the system's (unless the companion is set to Always)
//: and a hidden tab hold the eyes still: no idle loop runs there.
//: `atlasState` (the blink's timer, the rig's trace, the act's ease) is
//: atlas.js's: the boot's `setAtlasMood` writes it before this file loads.
const atlasBlinkOpen = new Map();
function atlasBlinkMay(box) {
  const root = document.documentElement;
  if (!box.isConnected || box.classList.contains("atl-off") || root.hasAttribute("data-atlas-hidden")) return false;
  //: The same motion settings every Atlas loop answers to (`atlasMotionOK`).
  if (!atlasMotionOK(box)) return false;
  const lids = box.querySelector(".atl-layer-lids:not(.atl-layer-lidf)");
  const buddy = box.closest("#nm-buddy");
  if (!lids || box.querySelector(".atl-blinking, .atl-blinking-slow") || box.hasAttribute("data-atl-moving") || buddy?.classList.contains("nmb-act-hide")) return false;
  //: Not behind a modal (INBOX 1587): unseen, and the read below settled the
  //: open overlay (237ms at 4x CPU with Settings open).
  if (buddy && nameMarkBuddyBehindCover()) return false;
  //: A closed-eye mood, or an act that moves the head, sets the layer's
  //: scale to 0 (the CSS): nothing to blink. Read once per mood and set
  //: of classes, not every blink (each read makes the page restyle).
  const key = `${box.dataset.atlasLook}|${box.dataset.atlasMood}|${buddy?.className || ""}`;
  if (!atlasBlinkOpen.has(key)) atlasBlinkOpen.set(key, getComputedStyle(lids).scale !== "0");
  return atlasBlinkOpen.get(key);
}
function atlasBlinkTick() {
  atlasState.blinkTimer = 0;
  const boxes = [...document.querySelectorAll(".atl-figure-box")];
  for (const box of boxes) {
    if (!atlasBlinkMay(box)) continue;
    if (box.closest(".nmb-drowsy, .nmb-groggy")) atlasBlink(box, true);
    else {
      atlasBlink(box);
      if (Math.random() < 0.15) setTimeout(() => atlasBlinkMay(box) && atlasBlink(box), 420);
    }
  }
  //: The gap's spread is the mood's and the tiredness's (`atlasBlink.vitals`): sleepy, more often; curious or startled, a held gaze.
  const box = boxes[0];
  const gap = box ? atlasBlink.vitals(box.closest(".nmb-drowsy, .nmb-groggy") ? "sleepy" : box.dataset.atlasMood).gap : 1;
  if (boxes.length) atlasState.blinkTimer = setTimeout(atlasBlinkTick, 3400 + Math.random() * 4200 * gap);
}
//: **The body's rhythms, one table for both companions** (INBOX 1719 b): `vitals` in companion-catalogue.json, which
//: the desk reads too (`src/tessellate/core/overlay/vitals.py`). For a mood (the figure's, mapped to the catalogue's),
//: a tiredness 0 to 1 and the ms since it last exerted itself: the blink's gap and length scales and the breath's period
//: scale (under 1 quicker). The table comes with the catalogue (`nmb.cat`); until then every scale is 1.
atlasBlink.vitals = (mood, tired = 0, since = Infinity) => {
  const v = typeof nmb !== "undefined" ? nmb.cat?.state.doc?.vitals : null;
  const m = atlasBlink.moods[mood] || mood || "content";
  const b = v?.blink;
  let [gap, len] = b?.mood?.[m] || [1, 1];
  const k = b?.tired ? Math.max(0, Math.min(1, (tired - b.tired_from) / (1 - b.tired_from))) : 0;
  if (k) [gap, len] = [gap * (1 + (b.tired[0] - 1) * k), len * (1 + (b.tired[1] - 1) * k)];
  const br = v?.breath;
  const out = br ? br.exert * 0.5 ** (Math.max(0, since) / 1000 / br.half_s) : 0;
  return { gap, len, breath: br ? (br.mood?.[m] ?? 1) / (1 + out) : 1 };
};
atlasBlink.moods = {
  calm: "content", delighted: "happy", laughing: "happy", love: "happy", smirk: "happy", thinking: "focus", determined: "focus",
  confused: "curious", surprised: "startled", worried: "startled", miffed: "startled", sad: "bored", shy: "content",
};
//: **Eyes are never quite still in a held gaze** (INBOX 1719 b): while the companion attends to a point, every 0.6 to 1.8 s
//: the irises take one small step off the held look (`ATLAS_SACCADE` of a look unit across, less up and down; the CSS
//: eases it) and the next aim writes the look back. Armed by `nameMarkBuddyAim`, it re-arms itself only while the look
//: is held (`nmb-attend`), so at rest no timer runs. A function property: the shared scope has a cap on names.
atlasBlink.saccade = () => {
  const s = atlasBlink.saccade;
  if (s.timer) return;
  s.timer = setTimeout(() => {
    s.timer = 0;
    if (s.step()) s();
  }, 600 + Math.random() * 1200);
};
//: One step; true while the look is still held. `r` is the two random draws (a fixed pair in a test).
atlasBlink.saccade.step = (r = [Math.random(), Math.random()]) => {
  const buddy = document.getElementById("nm-buddy");
  if (!buddy?.classList.contains("nmb-attend")) return false;
  //: And not at rest: the held look is kept, the irises stop stepping until the next input (`atlasTailCalm.rest`).
  if (globalThis.atlasTailCalm?.rest.on) return false;
  const box = buddy.querySelector(".atl-figure-box");
  if (document.hidden || !box || !atlasMotionOK(box) || buddy.classList.contains("nm-buddy-dragging")) return true;
  const ex = (nmb.ex || 0) + (r[0] - 0.5) * 0.5;
  const ey = (nmb.ey || 0) + (r[1] - 0.5) * 0.36;
  for (const iris of buddy.querySelectorAll(".nm-atlas .atl-iris")) {
    iris.style.setProperty("--nmb-ex", ex.toFixed(2));
    iris.style.setProperty("--nmb-ey", ey.toFixed(2));
  }
  return true;
};
function atlasBlinkStart() {
  if (!atlasState.blinkTimer) atlasState.blinkTimer = setTimeout(atlasBlinkTick, 1800);
  //: The small behaviours are a file of their own (atlas-micro.js), fetched once.
  if (typeof atlasMicroStart === "function") atlasMicroStart();
  else if (!atlasState.microLoad) atlasState.microLoad = lazyScript("/js/atlas-micro.js").then((ok) => ok && atlasMicroStart());
}//: **The rig: limbs that move like limbs** (INBOX 554, 564; the owner: "fix
//: how the arms connect to the atlas bodies and how they are used in
//: transitions between places and positions ... animate everything to be
//: smooth and boilogically lifelike", "dynamic and organic movement ...
//: like an azur lane character"). Each arm of a layered figure is a chain:
//: shoulder (its group's turn), elbow and wrist (`atlasArmPath`). Where an
//: arm should be is still the CSS's, every pose, act and mood rule and
//: every gesture as written, read off the arm's probe (`atl-arm-probe`);
//: the rig gets it there:
//: - each joint follows its target on a damped spring whose time is the
//:   move's size, 250ms for a nudge to 500ms for a half turn, so a move
//:   eases in and out and a target that moves mid-way is joined smoothly,
//:   never a jump; a move of over 40 degrees first draws back a little
//:   (anticipation) and settles past its mark (follow-through);
//: - the body leads and the limbs follow: the shoulder answers 30ms after
//:   the pose changes, the elbow 80ms, the wrist 130ms, and the hand
//:   trails a fast swing (overlapping action);
//: - gestures are joint targets: a wave lifts the forearm, pointing and
//:   reaching straighten the arm, an arm brought across the body folds at
//:   the elbow, a lifted arm bends a little; the elbow keeps to 0 to 135
//:   degrees, the wrist to 35 either way;
//: - while it travels the arms swing in counter-phase, the elbows easing
//:   on the back swing;
//: - the head steadies itself through a change of pose: it lags the body
//:   by a spring and catches up (`atl-head-lag`).
//: It runs only while something is moving (a pose or mood change, a
//: gesture, a walk) and stops when every joint has settled, so a figure at
//: rest costs nothing. With motion off or reduced it sets each pose at
//: once, in one frame.
const ATLAS_RIG_DELAY = { sh: 30, el: 80, wr: 130 };
const ATLAS_RIG_ZETA = { sh: 0.8, el: 0.74, wr: 0.62, sy: 0.9 };
function atlasLowerState(buddy, box) {
  const has = (c) => !!buddy && buddy.classList.contains(c);
  const pose = buddy?.dataset.pose || "";
  const mood = box.dataset.atlasMood || "calm";
  if (has("nmb-act-startle") || mood === "surprised") return "startle";
  if (/^(lie|curl)/.test(pose) || has("nmb-sleep") || has("nmb-act-nap") || has("nmb-act-lie") || has("nmb-act-blanket")) return "lie";
  if (has("nmb-falling")) return "fall";
  if (has("nmb-walking") || has("nm-buddy-dragging") || buddy?.dataset.travel) return "walk";
  const posed = atlasLowerState.acts.find((act) => has(`nmb-act-${act}`)) || (pose === "hang" ? "hang" : "");
  if (posed) return posed;
  if (pose === "lean") return "lean";
  if (pose === "sit" || has("nmb-act-chair") || has("nmb-act-beanbag") || has("nmb-act-meditate")) return "sit";
  if (["wave", "map", "shrug", "bell", "lantern", "carry", "juggle", "scratch", "facepalm", "cheer"].some((a) => has(`nmb-act-${a}`))) return "gesture";
  if (has("nmb-think") || mood === "thinking" || mood === "determined") return "think";
  if (["happy", "delighted", "laughing", "love", "proud"].includes(mood)) return "happy";
  if (["sad", "sleepy", "worried"].includes(mood) || has("nmb-drowsy")) return "sad";
  return "idle";
}
//: The acts that pose the lower body of their own (INBOX 1681, avatars.js, after `NMB_ATLAS_ACTS`); a hang does too, climbing or not (a property, not a global: `tests/test_global_scope_ratchet.py`).
atlasLowerState.acts = ["crouch", "lounge", "glide", "drift", "dangle", "kick", "swing", "sloth"];
//: **Away is off** (audit AI1, 2026-10-31: the companion faded out on every
//: tab but the one it lives on kept about 65 animations running, 540 ms of
//: main thread per 5 s at 4x CPU): a companion that is away (`nmb-away`,
//: opacity 0 and hidden) is not drawn, so nothing of it may move. Every loop
//: that asks this question rests; the class change wakes the rig and the
//: tail (`atlasRigWake`), so they resume the frame it comes back.
function atlasMotionOK(box) {
  const root = document.documentElement;
  if (root.dataset.avatarMotion === "off") return false;
  if (box.closest("#nm-buddy")?.classList.contains("nmb-away")) return false;
  //: One dataset read per frame of the tail loop; a query made anew each frame was 43ms of 1.3s of Atlas idle script.
  const reduced = root.dataset.motion === "reduced";
  return !reduced || (root.dataset.buddyMotion === "full" && !!box.closest("#nm-buddy"));
}
function atlasRigAttach(box) {
  const spec = ATLAS_LOOKS[box.dataset.atlasLook];
  const body = box.querySelector(".atl-layer-body");
  if (!spec?.armRig || !body || box.atlasRig) return;
  const joint = () => ({ x: 0, v: 0, w: 14, t: null });
  const rig = { box, body, look: box.dataset.atlasLook, arms: [], raf: 0, at: 0, still: 0, host: null, observer: null, pose: body.querySelector(".atl-pose"), heads: [...box.querySelectorAll(".atl-head-lag")], lag: { x: 0, v: 0, w: 9, t: null }, fresh: true };
  for (const side of ["l", "r"]) {
    const groups = [...body.querySelectorAll(`.nmb-arm-${side}:not(.atl-arm-probe)`)];
    for (const g of groups) {
      g.classList.add("atl-rigged");
      g.style.setProperty("rotate", "none", "important");
    }
    rig.arms.push({
      side,
      //: Inward (toward the body) is clockwise on screen for the right arm.
      sgn: side === "r" ? 1 : -1,
      probe: body.querySelector(`.atl-arm-probe.nmb-arm-${side}`),
      hold: body.querySelector(`.nmb-hold-${side}`),
      groups,
      paths: [...body.querySelectorAll(`.nmb-arm-${side}.atl-rigged > path`)],
      hand: body.querySelector(`.nmb-arm-${side}.atl-rigged > .atl-hand`),
      geo: spec.armRig[side],
      j: { sh: joint(), el: joint(), wr: joint(), sy: { x: 1, v: 0, w: 14, t: null } },
      hist: [],
      drawn: [0, 0],
      shown: "",
      antic: null,
      //: What animates on the probe, kept by its events (`atlasProbeWatch`).
      running: new Set(),
    });
    atlasProbeWatch(rig.arms[rig.arms.length - 1]);
  }
  box.atlasRig = rig;
  atlasRigWake(box);
}
//: **Whether the probe animates, from its events, not a scan** (audit HR1,
//: 2026-10-31: `getAnimations()` per arm per frame was 25 to 190 ms in a
//: 5 s agent turn, each call settling style for a page running 65
//: animations). The probe's gestures are CSS animations, so their names come
//: and go with `animationstart`, `animationend` and `animationcancel`; the
//: list is read once at the rig's first look, to seed the set.
function atlasProbeWatch(arm) {
  if (!arm.probe) return;
  const mark = (add) => (e) => {
    if (e.target === arm.probe) arm.running[add ? "add" : "delete"](e.animationName);
  };
  arm.probe.addEventListener("animationstart", mark(true));
  for (const type of ["animationend", "animationcancel"]) arm.probe.addEventListener(type, mark(false));
}
//: The list is read once, at the rig's first look (`atlasRigFrame`), not when it attaches (INBOX 1741, `atlas-motion.js
//: after 13ms`): `getAnimations()` settles the page's style first, and the attach ran in the task that had just appended
//: the figure (17ms of it at 4x CPU, for each figure). The first look comes after a frame has drawn, from a clean style.
atlasProbeWatch.seed = (arm) => {
  if (arm.probe) for (const a of arm.probe.getAnimations()) if (a.animationName) arm.running.add(a.animationName);
};
//: Where the CSS has the arm: the probe's turn (its transform's and any
//: gesture's `rotate`) and its vertical scale (a meditating arm's).
function atlasRigRead(arm) {
  const cs = getComputedStyle(arm.probe);
  let ang = 0;
  let sy = 1;
  const m = /matrix\(([^)]+)\)/.exec(cs.transform);
  if (m) {
    const [a, b, c, d] = m[1].split(",").map(Number);
    ang = (Math.atan2(b, a) * 180) / Math.PI;
    sy = (a * d - b * c) / (Math.hypot(a, b) || 1);
  }
  const r = parseFloat(cs.rotate);
  if (Number.isFinite(r)) ang += r;
  //: The raised arms of a hang, a carry or a cheer are their own drawing
  //: (`nmb-hold`), crossfaded with these; as this arm fades out it rises
  //: toward the held one's line, so the swap reads as one arm lifting.
  if (+cs.opacity < 0.5 && arm.hold && +getComputedStyle(arm.hold).opacity > 0.5) ang = -158 * arm.sgn;
  return { ang, sy };
}
//: **A raised forearm lifts, it never droops** (the owner, 2026-10-11:
//: clicked, "its arms ... just start rising ... and it stays bent
//: downwards, then falls again"). The bend is a turn about the elbow, and
//: with the upper arm out level the old inward turn (the same way as a
//: hanging arm's) pointed the forearm at the floor: clickarm.js measured
//: a wave's hand 7 to 15 units below the shoulder at its height. Raised
//: out, the forearm now turns up towards the head (a negative bend, down
//: to `ATLAS_EL_UP`), most for a wave, a little for any lifted arm.
const ATLAS_EL_UP = -70;
//: **The bend reads the arm as it is drawn** (INBOX 1402, the owner: "arm
//: positioning" like "a grumpy gangster"). The shoulder's target is
//: unwound (`atlasRigFrame`, so a turn past 180 never spins the long way),
//: and after a few big moves hers sat a whole turn round, -360 to -435
//: degrees for an arm hanging at 0 to -75; read raw here, that raise
//: folded the elbow its full 80 degrees, so her left forearm lay across
//: her body in 14 of 15 moods (atlasrest1402.js, moods). The raise is
//: taken in -180 to 180 first (180 itself kept: an arm straight up).
function atlasRigGesture(arm, raise, buddy) {
  raise = 180 - ((((180 - raise) % 360) + 360) % 360);
  const has = (c) => !!buddy && buddy.classList.contains(c);
  //: The turn of the bend goes over from in to up between 20 and 70
  //: degrees of raise, smoothly, so no target jumps on the way up.
  const up = 1 - 2 * Math.max(0, Math.min(1, (raise - 20) / 50));
  let el = raise < -8 ? Math.min(80, 0.9 * (-raise - 8)) : 14 * up * Math.sin((Math.min(raise, 180) * Math.PI) / 180);
  let wr = 0;
  //: A wave holds the forearm about upright whatever the upper arm does
  //: (his swings to 102 degrees, hers to 146), never over the head.
  if (arm.side === "r" && has("nmb-act-wave")) [el, wr] = [-Math.max(10, Math.min(60, 175 - raise)), -12];
  else if (arm.side === "r" && (has("nmb-act-bell") || has("nmb-act-lantern") || has("nmb-act-carry"))) [el, wr] = [-8, 0];
  return [Math.max(ATLAS_EL_UP, Math.min(135, el)), wr];
}
//: A damped spring toward `target`; a jump in the target sets its time.
//: **No joint turns faster than `ATLAS_RIG_MAX_SPEED`** (INBOX 669, the
//: owner: "atlas's arm movements are jerky and not smooth"). The spring's
//: time is a quarter to half a second whatever the move's size, so a
//: hundred-degree raise peaked at 9 degrees a frame and a wave's turn
//: back at 20 (atlas669-clicks.js), which at the large view's 2.2 times
//: reads as a jump, not a swing. Capped at 200 degrees a second, under 4
//: a frame at 60 a second: a small move keeps its spring, a big one
//: cruises and settles, and a wave's swings (about 150 at their fastest)
//: are untouched.
const ATLAS_RIG_MAX_SPEED = 200;
function atlasRigSpring(j, target, dt, zeta) {
  if (j.t === null) j.t = target;
  const jump = Math.abs(target - j.t);
  if (jump > 3) j.w = 5 / Math.min(0.5, 0.25 + (0.25 * jump) / 120);
  j.t = target;
  const n = Math.max(1, Math.ceil(dt / 0.004));
  const h = dt / n;
  for (let i = 0; i < n; i += 1) {
    j.v += (j.w * j.w * (target - j.x) - 2 * zeta * j.w * j.v) * h;
    j.v = Math.max(-ATLAS_RIG_MAX_SPEED, Math.min(ATLAS_RIG_MAX_SPEED, j.v));
    j.x += j.v * h;
  }
}
//: **A wake reads the page one frame later** (the lag log, a tab click:
//: `atlasRigWake 33ms (forced layout 32ms)`, 108ms at 4x CPU). A wake lands
//: in the click or the observer's microtask, with the arriving page's class
//: flips still unsettled; the frame it asked for runs before that frame's
//: style pass, so its first read of the arm, the lids or a prop's opacity
//: settled the whole page, forced. The next frame's callback follows the
//: frame that settled it: the same read, a clean style. One frame (16ms) late.
function atlasRigWake(host) {
  const box = host?.classList?.contains("atl-figure-box") ? host : host?.querySelector?.(".atl-figure-box");
  const rig = box?.atlasRig;
  //: The tail (`atlasTailFrame`) wakes with it: back on screen, a new
  //: state, a figure just put on the page.
  atlasTailWake(box);
  //: A figure waiting for its companion to show (`atlasWhenShown`) looks again.
  if (box?.atlasShow) atlasRigWake.after(box.atlasShow, 3);
  //: A wake is a change of what the CSS has the figure do (a class, a pose,
  //: a mood, a gesture): the rig and the props read the page's style again
  //: (`atlasRigFrame`, `atlasPropsFrame`) and hold what they read otherwise.
  if (box) box.atlasDirtyAt = performance.now();
  if (!rig) return;
  rig.dirty = true;
  if (!rig.observer && typeof MutationObserver === "function" && box.isConnected) {
    rig.host = box.closest("#nm-buddy") || box;
    //: A class record whose value is what it was (a `classList.add` of a class already
    //: there) changed nothing the CSS can show, so it does not wake the rig (DX1).
    rig.observer = new MutationObserver((records) => {
      //: A blink's class (`atl-blinking`, on the lids' layers) moves no arm: it does not wake the rig either (a read each time, 6ms at 4x).
      const plain = (v) => String(v || "").replace(/\batl-blinking\b/g, "").replace(/\s+/g, " ").trim();
      if (records.some((r) => r.attributeName !== "class" || plain(r.oldValue) !== plain(r.target.getAttribute("class")))) atlasRigWake(box);
    });
    const attributes = { attributes: true, attributeOldValue: true, attributeFilter: ["class", "data-pose", "data-atlas-variant", "data-atlas-mood", "data-travel", "data-side"] };
    for (const el of new Set([rig.host, box, rig.body])) rig.observer.observe(el, attributes);
  }
  rig.still = 0;
  //: **The first look is taken after a frame has drawn** (INBOX 1741, the owner's log: `atlas-motion.js after
  //: 13ms`, a 227ms frame; 96ms with 92 forced at 4x): with nothing read yet (`rig.reads`) the frame
  //: callback reads every arm's box before the frame's own style pass, and the figure's first
  //: paint had left that to this read. A timer after the frame finds the page clean.
  if (!rig.raf) rig.raf = (rig.reads ? atlasRigWake.after : atlasRigWake.afterPaint)((now) => atlasRigFrame(rig, now), 2);
  //: The look follows the frame that settled the page (`atlasRigLook`), never in the wake's own task.
  if (!rig.looking && rig.reads) {
    rig.looking = true;
    atlasRigWake.afterPaint(() => atlasRigWake.look(rig), 2);
  }
}
//: The only place a skipped or settled frame is asked for: `callback` after `frames` frames (2: after the one that draws the page).
atlasRigWake.after = (callback, frames) => requestAnimationFrame((t) => (frames > 1 ? atlasRigWake.after(callback, frames - 1) : callback(t)));
//: `callback` in the task after the `frames`th frame has drawn: its reads find the style settled.
//: Returns 1, a truthy token like a frame id (`rig.raf` is only ever tested and zeroed).
atlasRigWake.afterPaint = (callback, frames) => {
  atlasRigWake.after(() => setTimeout(function atlasRigWakeFirstLook() { callback(performance.now()); }, 0), frames);
  return 1;
};
//: **Throwing stars** (B88b, the owner, 2026-10-17: "the throwing stars
//: action for atlas isnt animated"). The juggle turned each star on a CSS
//: circle about one point over the head while both arms held still. The rig
//: throws them now, in its own frame: a shower, each star thrown from the
//: right hand high over the head to the left, held a moment, thrown back
//: low, three a third of a cycle apart, each hand dipping as it catches and
//: flicking up as it throws. Thrown across the screen, Atlas loses them: they
//: fly out of its hands, fall and fade, once a flight. Reduced motion is not
//: `live`, so the drawn stars stay where they are drawn.
const ATLAS_TOSS_SPOTS = [[10, 17], [31, 4], [52, 17]];
const ATLAS_TOSS_FLING = [[-28, -70], [18, -85], [40, -60]];
function atlasTossAt(p) {
  if (p < 0.42) {
    const u = p / 0.42;
    return [52 - 42 * u, 17 - 56 * u * (1 - u)];
  }
  if (p < 0.5) return [10, 17 + 1.5 * Math.sin((Math.PI * (p - 0.42)) / 0.08)];
  if (p < 0.92) {
    const u = (p - 0.5) / 0.42;
    return [10 + 42 * u, 17 - 40 * u * (1 - u)];
  }
  return [52, 17 + 1.5 * Math.sin((Math.PI * (p - 0.92)) / 0.08)];
}
//: A hand's lift in degrees, `d` cycles from its throw: down as it carries
//: the caught star, up as it lets go.
function atlasTossBob(d) {
  const w = d - Math.round(d);
  if (w >= -0.08 && w < 0) return -6 * Math.sin((Math.PI * (w + 0.08)) / 0.08);
  if (w >= 0 && w < 0.1) return 12 * Math.sin((Math.PI * w) / 0.1);
  return 0;
}
//: What the stars do this frame: `juggle`, `spill` (thrown), `back` (the act
//: over, eased home) or nothing; null when there is nothing to draw or clear.
function atlasTossState(rig, now, live, buddy) {
  const t = rig.toss || (rig.toss = { mode: "", at: 0, from: null, off: ATLAS_TOSS_SPOTS.map(() => [0, 0]), spillOf: null });
  const game = typeof nmb === "object" ? nmb : null;
  const has = (c) => !!buddy && buddy.classList.contains(c);
  const start = (mode) => Object.assign(t, { mode, at: now, from: t.off.map((o) => [...o]) });
  if (live && game?.flight && t.spillOf !== game.flight && has("nm-buddy-dragging") && !nameMarkBuddyActOff("juggle")) {
    t.spillOf = game.flight;
    start("spill");
  } else if (live && t.mode !== "spill" && (has("nmb-act-juggle") || has("nmb-act-toss"))) {
    const mode = has("nmb-act-juggle") ? "juggle" : "toss";
    if (t.mode !== mode) start(mode);
    t.kind = mode;
  } else if (live && (t.mode === "juggle" || t.mode === "toss")) start("back");
  const e = now - t.at;
  const ease = (x) => 1 - (1 - Math.min(1, x)) ** 3;
  if (!live || (t.mode === "spill" && e >= 1000) || (t.mode === "back" && e >= 250)) t.mode = "";
  if (!t.mode) {
    if (!t.from) return null;
    t.from = null;
    t.off = t.off.map(() => [0, 0]);
    return { mode: "", off: null, op: "", lift: null };
  }
  let op = "";
  const lift = { l: 0, r: 0 };
  //: One star tossed from the right hand and caught (`nmb-act-toss`, an act
  //: of companion-menu.js's mind): the arm up as for a juggle, the others
  //: away. Over (`back`), it fades in the hand rather than flying home.
  if (t.kind === "toss" && (t.mode === "toss" || t.mode === "back")) {
    const b = ease(e / 300);
    const p = (e / 1100) % 1;
    const u = Math.min(1, p / 0.8);
    const [x, y] = p < 0.8 ? [52 - 3 * Math.sin(Math.PI * u), 17 - 60 * u * (1 - u)] : [52, 17 + 1.2 * Math.sin((Math.PI * (p - 0.8)) / 0.2)];
    if (t.mode === "toss") t.off = t.off.map((o, k) => (k === 1 ? [t.from[1][0] + (x - 31 - t.from[1][0]) * b, t.from[1][1] + (y - 4 - t.from[1][1]) * b] : [0, 0]));
    lift.r = t.mode === "toss" ? b * atlasTossBob(p) : 0;
    return { mode: t.mode, off: t.off, op: ["0", "", "0"], lift, hold: t.mode === "toss" ? { r: 64 } : null, shown: t.mode === "toss" };
  }
  if (t.mode === "spill") {
    const s = e / 1000;
    t.off = t.from.map(([x, y], k) => [x + ATLAS_TOSS_FLING[k][0] * s, y + ATLAS_TOSS_FLING[k][1] * s + 100 * s * s]);
    op = (s < 0.45 ? 1 : Math.max(0, 1 - (s - 0.45) / 0.55)).toFixed(2);
  } else if (t.mode === "back") {
    const b = ease(e / 250);
    t.off = t.from.map(([x, y]) => [x * (1 - b), y * (1 - b)]);
  } else {
    const b = ease(e / 300);
    t.off = ATLAS_TOSS_SPOTS.map((spot, k) => {
      const p = (e / 1800 + (2 - k) / 3) % 1;
      lift.r += b * atlasTossBob(p);
      lift.l += b * atlasTossBob(p - 0.5);
      const [x, y] = atlasTossAt(p);
      return [t.from[k][0] + (x - spot[0] - t.from[k][0]) * b, t.from[k][1] + (y - spot[1] - t.from[k][1]) * b];
    });
  }
  return { mode: t.mode, off: t.off, op, lift };
}
function atlasTossDraw(rig, toss) {
  const { box } = rig;
  const els = rig.tossEls || (rig.tossEls = {
    root: box.querySelector(".atl-layer .nmp-stars"),
    arc: box.querySelector(".atl-layer .nmp-stars .atl-juggle-arc"),
    stars: [...box.querySelectorAll(".atl-layer .nmp-stars > .atl-juggle")],
  });
  const set = (el, k, v) => {
    if (el && el.style[k] !== v) el.style[k] = v;
  };
  //: Spilled in a flight, the stars are drawn every other frame (30 a
  //: second, as a walk's swing is): each move restyles its star's drawing
  //: on top of the flight's own (`atlasinval.js`, one throw: 2,277 style
  //: invalidations with no spill, 3,348 with it drawn every frame, 2,986 to
  //: 3,074 every other).
  const skip = toss.mode === "spill" && rig.tick % 2 === 1;
  for (const [k, star] of skip ? [] : els.stars.entries()) {
    const o = toss.off?.[k];
    set(star, "transform", o ? `translate(${atlasFix(o[0])}px, ${atlasFix(o[1])}px)` : "");
    set(star, "opacity", Array.isArray(toss.op) ? toss.op[k] : toss.op);
  }
  //: Spilled, the prop shows whatever the act (the CSS shows it only for the
  //: juggle) and the thread it runs on does not.
  set(els.root, "opacity", toss.mode === "spill" || toss.shown ? "1" : "");
  set(els.arc, "opacity", toss.mode === "spill" || Array.isArray(toss.op) ? "0" : "");
}
//: **Reduced motion keeps the juggle visible** (INBOX 1322b, "the juggling
//: stars dont animate at all": the one case that reproduced, 0 px of travel
//: in 2 s, was the system asking for less motion with the act asked for from
//: the large view). Nothing travels there, but a fade is allowed: each star
//: pulses its opacity, a third of a cycle apart, for as long as the act lasts.
function atlasStarsFade(rig, on) {
  if (!on) {
    if (rig.fades) for (const a of rig.fades) a.cancel();
    rig.fades = null;
    return;
  }
  if (rig.fades) return;
  const stars = rig.tossEls?.stars || [...rig.box.querySelectorAll(".atl-layer .nmp-stars > .atl-juggle")];
  rig.fades = stars.map((star, k) => star.animate?.([{ opacity: 1 }, { opacity: 0.35 }, { opacity: 1 }], { duration: 1500, delay: -k * 500, iterations: Infinity, easing: "ease-in-out" })).filter(Boolean);
}
//: **Where the CSS has the figure, read in a task after a drawn frame** (INBOX 1766; it was the top of
//: `atlasRigFrame`). Every read of the probes and the pose is taken here, all before any write, and
//: only when it may have changed: what they show changes with a class, a pose or a mood, which wakes
//: the rig (`rig.dirty`), or while an animation runs on an arm; once both arms and the turn have held
//: a quarter second with none running, the rig works from what it read until the next wake (B87a: a
//: carried Atlas at 4x CPU was 254 forced restyles and layouts in 1.3 s). The task runs on a clean
//: page, so a read is a lookup, and it asks for the next look itself (33ms) while the rig is dirty.
//: **Not the first to read a page that has just flipped** (INBOX 1560, a30v): inside `uiSettlingUntil`
//: (a tab, a dialog arriving) a read paid the whole arriving page's restyle, 71 to 262ms at 4x. It
//: works from what it read until the page has settled. Nor behind a dialog (INBOX 1667): the corner
//: figure is drawn at opacity 0 under it, and its read paid for the open dialog's restyles. Nor hidden
//: or off screen: the wake that brings it back reads again.
atlasRigWake.look = function atlasRigLook(rig, inFrame = false) {
  rig.looking = false;
  const { box } = rig;
  if (!box.isConnected || document.hidden || box.classList.contains("atl-off")) return;
  const now = performance.now();
  const buddy = rig.host && rig.host.id === "nm-buddy" ? rig.host : null;
  if (rig.reads && (now < (globalThis.uiSettlingUntil || 0) || (!!buddy && nameMarkBuddyBehindCover()))) {
    if (rig.dirty) atlasRigWake.look.soon(rig, 100);
    return;
  }
  const live = atlasMotionOK(box);
  if (!rig.reads) for (const arm of rig.arms) atlasProbeWatch.seed(arm);
  const reads = rig.arms.map((arm) => ({ ...atlasRigRead(arm), anim: live && arm.running.size > 0 }));
  const turnMatrix = rig.pose && rig.heads.length ? /matrix\(([^)]+)\)/.exec(getComputedStyle(rig.pose).transform) : null;
  const was = rig.reads;
  const held = !!was && (turnMatrix?.[1] || "") === (rig.turnMatrix?.[1] || "") && reads.every((r, i) => !r.anim && Math.abs(r.ang - was[i].ang) < 0.01 && Math.abs(r.sy - was[i].sy) < 0.001);
  rig.heldAt = held ? rig.heldAt || now : 0;
  if (held && now - rig.heldAt >= 250) rig.dirty = false;
  rig.reads = reads;
  rig.turnMatrix = turnMatrix;
  //: Something to draw: the frame loop is asleep or waiting, and starts again.
  if (!held && !inFrame) {
    rig.still = 0;
    if (!rig.raf && live) rig.raf = atlasRigWake.after((t) => atlasRigFrame(rig, t), 1);
  }
  if (rig.dirty) atlasRigWake.look.soon(rig, 33);
};
//: The next look in `ms`, one at a time.
atlasRigWake.look.soon = (rig, ms) => {
  if (rig.looking) return;
  rig.looking = true;
  setTimeout(atlasRigWake.look, ms, rig);
};
//: The walk's arm swing as offsets to the shoulder and elbow (degrees): 1.3 strides a second, 9 degrees
//: on the masculine look and 6 on the feminine, the two arms half a stride apart (L82: measured over a
//: held walk the raise stays within 4.6 to 21.4 of hanging, never across the body). The elbow only ever
//: bends further (0 to 0.6 of the swing), so the hand's arc stays below the shoulder.
atlasRigFrame.walkSwing = function (side, look, now) {
  const ph = (now / 1000) * 2 * Math.PI * 1.3 + (side === "r" ? 0 : Math.PI);
  const amp = look === "masculine" ? 9 : 6;
  return [amp * Math.sin(ph), amp * 0.6 * (1 + Math.sin(ph - 0.8)) * 0.5];
};

function atlasRigFrame(rig, now) {
  rig.raf = 0;
  const { box } = rig;
  if (!box.isConnected) {
    rig.observer?.disconnect();
    rig.observer = null;
    return;
  }
  //: **Nothing runs in a hidden window** (INBOX 1766): the loop stops where it stands, `dirty` for the look
  //: the return takes (`atlasHiddenSync` wakes the figure).
  if (document.hidden) {
    rig.at = 0;
    rig.dirty = true;
    return;
  }
  const live = atlasMotionOK(box) && !box.classList.contains("atl-off") && !rig.fresh;
  rig.fresh = false;
  const buddy = rig.host && rig.host.id === "nm-buddy" ? rig.host : null;
  //: **The corner companion's rig runs at 30 a second, not at the screen's rate** (the lag log:
  //: `atlasRigFrame 60 calls/s, 3.7ms each (219ms of every second)` on the library, 36 a second
  //: on the dashboard). A gesture, a walk or an act keeps it busy and each call restyles and
  //: repaints the body layer, at 64 by 92 pixels where a half-rate step is not seen (the walk
  //: was drawn every other frame already). A frame under `atlasRigFrame.gapMs` from the last
  //: one waits for the next; the springs take the longer step (`dt`, capped). Carried, it
  //: follows the hand every frame; the large view (no companion host) too.
  if (live && buddy && rig.at && now - rig.at < atlasRigFrame.gapMs && !buddy.classList.contains("nm-buddy-dragging")) {
    atlasRigFrame.again(rig);
    return;
  }
  const dt = rig.at ? Math.min(0.05, (now - rig.at) / 1000) : 1 / 60;
  rig.at = now;
  const walking = live && !!buddy && buddy.classList.contains("nmb-walking");
  let busy = walking;
  //: **The frame reads nothing** (INBOX 1766, the owner's lag log on a documents page with a diagram open:
  //: `atlasRigFrame 138-205ms (forced layout 136-203ms)`, 6 to 27 calls a second, 23ms growing to 130ms). A style
  //: read here landed in a frame callback, after every writer that had run since the last draw, and paid for
  //: all of it: the read of a `transform` resolves against layout. The reads live in `atlasRigLook`, a task
  //: that follows a drawn frame (clean style, so a read is a lookup); the frame works from what it took.
  //: Only the very first look, at attach, is taken here, and the wake has already put that after a paint.
  if (!rig.reads) atlasRigWake.look(rig, true);
  //: **A look that took nothing leaves nothing to draw** (INBOX 1111, `Cannot read properties of undefined (reading '0')`):
  //: the look returns unread for a figure below the fold (`atl-off`, set by the viewport observer before the first
  //: frame), and `reads[0]` threw. The class change that brings it back wakes the rig (`atlasRigWake`'s observer).
  if (!rig.reads) {
    rig.at = 0;
    rig.dirty = true;
    return;
  }
  const { reads, turnMatrix } = rig;
  const toss = atlasTossState(rig, now, live, buddy);
  for (const [i, arm] of rig.arms.entries()) {
    const got = { ...reads[i] };
    //: Unwrap the angle against the last target so a turn past 180
    //: degrees does not spin the long way round.
    const prev = arm.hist.length ? arm.hist[arm.hist.length - 1][1] : got.ang;
    while (got.ang - prev > 180) got.ang -= 360;
    while (got.ang - prev < -180) got.ang += 360;
    //: Anticipation: a big new target first draws the arm back a little.
    if (live && Math.abs(got.ang - prev) > 40) arm.antic = { until: now + 90, to: arm.j.sh.x - 0.08 * (got.ang - prev) };
    arm.hist.push([now, got.ang, got.sy]);
    while (arm.hist.length > 2 && arm.hist[1][0] <= now - 200) arm.hist.shift();
    const at = (ms) => {
      for (let i = arm.hist.length - 1; i >= 0; i -= 1) if (arm.hist[i][0] <= now - ms) return arm.hist[i];
      return arm.hist[0];
    };
    const [, shT, syT] = live ? at(ATLAS_RIG_DELAY.sh) : arm.hist[arm.hist.length - 1];
    const raise = -shT * arm.sgn;
    let [elT] = atlasRigGesture(arm, live ? -at(ATLAS_RIG_DELAY.el)[1] * arm.sgn : raise, buddy);
    let [, wrT] = atlasRigGesture(arm, raise, buddy);
    let sh = shT;
    if (walking && Math.abs(((((raise + 180) % 360) + 360) % 360) - 180) < 35) {
      //: Counter-phase: the right arm forward while the left is back.
      const swing = atlasRigFrame.walkSwing(arm.side, rig.look, now);
      sh += swing[0];
      elT += swing[1];
    }
    if (toss?.hold?.[arm.side]) {
      sh = -toss.hold[arm.side] * arm.sgn;
      [elT] = atlasRigGesture(arm, toss.hold[arm.side], buddy);
    }
    if (toss?.lift) {
      sh -= toss.lift[arm.side] * arm.sgn;
      elT -= 0.5 * toss.lift[arm.side];
    }
    if (arm.antic && now < arm.antic.until) sh = arm.antic.to;
    //: The hand trails a fast swing of the arm.
    wrT = Math.max(-35, Math.min(35, wrT - 0.03 * arm.j.sh.v));
    const j = arm.j;
    if (!live) {
      for (const [k, v] of [["sh", sh], ["el", elT], ["wr", wrT], ["sy", syT]]) Object.assign(j[k], { x: v, v: 0, t: v });
    } else {
      atlasRigSpring(j.sh, sh, dt, ATLAS_RIG_ZETA.sh);
      atlasRigSpring(j.el, elT, dt, ATLAS_RIG_ZETA.el);
      atlasRigSpring(j.wr, wrT, dt, ATLAS_RIG_ZETA.wr);
      atlasRigSpring(j.sy, syT, dt, ATLAS_RIG_ZETA.sy);
      j.el.x = Math.max(ATLAS_EL_UP, Math.min(135, j.el.x));
      j.wr.x = Math.max(-35, Math.min(35, j.wr.x));
    }
    //: Within 0.15 degrees and slower than 3 a second, a joint has
    //: arrived: it is set on its mark (a step no eye sees at this size)
    //: rather than drawn for another half second of spring tail.
    let moving = false;
    for (const k of ["sh", "el", "wr"]) if (Math.abs(j[k].x - j[k].t) > 0.15 || Math.abs(j[k].v) > 3) moving = true;
    if (!moving && live) for (const k of ["sh", "el", "wr", "sy"]) Object.assign(j[k], { x: j[k].t, v: 0 });
    if (moving) busy = true;
    if (live && (got.anim || (arm.antic && now < arm.antic.until))) busy = true;
    const t = `rotate(${atlasFix(j.sh.x)}deg)${Math.abs(j.sy.x - 1) > 0.002 ? ` scale(1, ${j.sy.x.toFixed(3)})` : ""}`;
    if (t !== arm.shown) {
      for (const g of arm.groups) g.style.setProperty("transform", t, "important");
      arm.shown = t;
    }
    const bend = j.el.x * arm.sgn;
    const wrist = j.wr.x * arm.sgn;
    if (Math.abs(bend - arm.drawn[0]) > 0.1 || Math.abs(wrist - arm.drawn[1]) > 0.1 || (!moving && (bend !== arm.drawn[0] || wrist !== arm.drawn[1]))) {
      const d = atlasArmPath(arm.geo, bend, wrist);
      for (const p of arm.paths) p.setAttribute("d", d);
      arm.hand?.setAttribute("transform", atlasArmHand(arm.geo, bend, wrist));
      arm.drawn = [bend, wrist];
    }
    if (atlasState.rigTrace) atlasState.rigTrace.push([now, rig.look, arm.side, +j.sh.x.toFixed(2), +j.el.x.toFixed(2), +j.wr.x.toFixed(2)]);
  }
  //: The head steadies itself: the body's turn (its pose group's), lagged
  //: by a spring, less the turn itself, is how far the head is left behind.
  if (rig.pose && rig.heads.length) {
    const m = turnMatrix;
    const turn = m ? (Math.atan2(+m[1].split(",")[1], +m[1].split(",")[0]) * 180) / Math.PI : 0;
    if (live) atlasRigSpring(rig.lag, turn, dt, 0.9);
    else Object.assign(rig.lag, { x: turn, v: 0, t: turn });
    const off = Math.max(-10, Math.min(10, rig.lag.x - turn));
    //: The hair's layer swings a third further, its follow-through.
    for (const el of rig.heads) {
      const k = el.closest(".atl-layer-hair") ? 1.3 : 1;
      const rot = Math.abs(off) > 0.05 ? `${atlasFix(off * k)}deg` : "";
      if (el.style.rotate !== rot) el.style.rotate = rot;
    }
    if (Math.abs(off) > 0.05 || Math.abs(rig.lag.v) > 1) busy = true;
    if (atlasState.rigTrace) atlasState.rigTrace.push([now, rig.look, "head", +off.toFixed(2), +turn.toFixed(2), 0]);
  }
  //: The lower body's pose for the state, once atlas-life.js has given the
  //: rig its lower body (`atlasRigLowerAttach`).
  if (rig.lower) atlasRigLower(rig, now, live, buddy);
  atlasStarsFade(rig, !live && !!buddy && !box.classList.contains("atl-off") && document.documentElement.dataset.avatarMotion !== "off" && (buddy.classList.contains("nmb-act-juggle") || buddy.classList.contains("nmb-act-toss")));
  if (toss) {
    atlasTossDraw(rig, toss);
    if (toss.mode) busy = true;
  }
  box.toggleAttribute("data-atl-moving", busy);
  //: Six quiet frames in a row and it sleeps until the next change.
  rig.still = busy ? 0 : rig.still + 1;
  if (live && rig.still < 6) rig.raf = requestAnimationFrame((t) => atlasRigFrame(rig, t));
  else rig.at = 0;
}
//: The shortest gap between two drawn frames of the corner companion's rig (a property, not a global: `tests/test_global_scope_ratchet.py`).
atlasRigFrame.gapMs = 24;
//: The same loop's next frame, for a frame skipped under the gap (the frame's end asks for the next one itself).
atlasRigFrame.again = (rig) => {
  rig.raf = atlasRigWake.after((t) => atlasRigFrame(rig, t), 1);
};
