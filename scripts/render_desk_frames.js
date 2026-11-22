// Captures the desktop companion's overlay frames (BACKLOG 16, O2) from the live
// Atlas figure: one transparent PNG per frame and look, at device scale 2.
// `scripts/render_desk_frames.py` runs this, then crops and writes the shipped files.
//
//   BASE=http://127.0.0.1:8828 node scripts/render_desk_frames.js <out dir>
//
// The figure is cloned out of the page's own `#nm-buddy` into a bare body (the
// original lives on its own timers), every other element is hidden and the
// page background cleared, so `omitBackground` yields real alpha. Poses and
// acts are the app's own classes (frontend/js/avatars.js "What the companion
// sets on its #nm-buddy"); a running animation is frozen at a chosen moment.
const fs = require("fs");
const path = require("path");
const { boot } = require("../scratchpad/ui-sweeps/lib.js");

//: name -> { pose, classes, at } where `at` is the animation moment: seconds
//: into each running animation, or `phase` of its cycle (a walk).
const FRAMES = [
  { name: "stand", pose: "stand", classes: [] },
  { name: "blink", pose: "stand", classes: ["nmb-act-blink"], at: 0.12 },
  { name: "look", pose: "stand", classes: ["nmb-act-look"], at: 1.1 },
  //: Atlas has a wisp for a lower body: its "walk" is a float cycle, not steps.
  //: The app's own glide (`atl-glide`, 2px) and wisp sway are too small at this
  //: size, so each frame sets exaggerated transforms inline (see `floatFrame`):
  //: the body bobs 6px and leans into its travel, the tail swings about its
  //: root and the lower wisp skews, in a wave that travels down it (each part
  //: a little behind the one above). No `nmb-walking` class: its animations
  //: would otherwise be paused mid-way and fight the inline values.
  ...Array.from({ length: 12 }, (_, i) => ({ name: `walk${i}`, pose: "stand", classes: [], float: i / 12 })),
  { name: "sit", pose: "sit", classes: [] },
  { name: "sleep", pose: "sit", classes: ["nmb-sleep"], at: 1.0 },
  { name: "wave", pose: "stand", classes: ["nmb-desk-wave"], at: 0.45 },
  //: The wave's arm swing (INBOX 1696, the owner: one raised arm held still "looks liek a nazi salute"): six
  //: frames out and back about the raised arm, drawn in turn by the engine (`engine.WAVE_FPS`).
  ...[100, 112, 128, 140, 128, 112].map((deg, i) => ({ name: `wave${i}`, pose: "stand", classes: ["nmb-desk-wave"], at: 0.45, wave: deg })),
  { name: "held", pose: "stand", classes: ["nm-buddy-dragging"] },
  { name: "fall", pose: "stand", classes: ["nmb-act-startle"], at: 0.25 },
  { name: "land", pose: "stand", classes: ["nmb-act-land"], at: 0.1 },
  { name: "hop", pose: "stand", classes: ["nmb-act-hop"], at: 0.3 },
  //: The rig's own hanging pose: both arms raised to an edge above it.
  { name: "hang", pose: "hang", classes: [] },
  //: INBOX 1710 (W31 E2), the app's three acts the desk had no picture of: the lower wisp let down over an
  //: edge and swung (`act.dangle`, `kick0` and `kick1` for `act.kick_legs`: the hem thrown forward and back,
  //: the app's `atl-lower-flick`), and the hang with one hand let go (`act.hang_one_hand`, `nmb-act-onehand`:
  //: the far arm released and waving). `lower` is [skewX deg, scaleY, scaleX] about the hips.
  { name: "dangle", pose: "sit", classes: ["nmb-act-dangle"], at: 0.75, lower: [-8, 1.3, 0.9] },
  { name: "kick0", pose: "sit", classes: ["nmb-act-dangle"], at: 0.75, lower: [-18, 1.15, 0.88] },
  { name: "kick1", pose: "sit", classes: ["nmb-act-dangle"], at: 0.75, lower: [16, 1.15, 0.88] },
  { name: "hang_one", pose: "hang", classes: ["nmb-act-onehand"], at: 0.35, upright: true },
  //: W31 E1: the long sit with the eyes shut and the hands on the knees (`nmb-act-meditate`). Lounge and rest head
  //: stay the keyed `sit` (the rig draws them as a 2 to 7 degree lean of it: no picture of their own is worth its bytes).
  { name: "meditate", pose: "sit", classes: ["nmb-act-meditate"], at: 1.0 },
  //: A throw's mid-spin: the startled pose turned about its middle (the rig has no tumble of its own). The
  //: squash into #216 dropped this entry and kept its handler, so the renderer could not finish.
  { name: "tumble", pose: "stand", classes: ["nmb-act-startle"], at: 0.25, spin: 115 },
];
//: The idle cycle (`idle0` to `idle23`, engine.IDLE_FRAMES): the rig's own standing
//: motion sampled at fixed times, one full beat of the tail (`atlasTailBend` with
//: the sway act's own numbers, `atlas-life.js`) and one breath (`atlasBreathFrame`'s
//: raised cosine on the torso, plus a small rise of the whole figure so the
//: breath shows at this size), so the loop closes on itself.
const IDLE_N = 24;
FRAMES.push(...Array.from({ length: IDLE_N }, (_, i) => ({ name: `idle${i}`, pose: "stand", classes: [], idle: i / IDLE_N })));
const LOOKS = (process.env.LOOKS || "masculine,feminine").split(",");
//: The capture box around the figure, in CSS pixels: roomy, cropped later. INBOX 1663: at
//: 220 wide the feminine look's hang, hop, land, tumble and idle frames (the figure sits
//: further right in them) were cut by the clip itself and shipped with a straight edge;
//: `render_desk_frames.py` now refuses a capture that touches the clip's edge.
const BOX = { width: 400, height: 300, left: 120, top: 60 };

//: A fingerprint of the arms' drawing; the same three times running, 120 ms apart, is settled.
async function settleArms(page) {
  const sig = () => page.evaluate(() => [...document.querySelectorAll("#nm-buddy .nmb-arm-left, #nm-buddy .nmb-arm-right")].map((e) => e.outerHTML).join("|"));
  let last = await sig(), same = 0;
  for (let i = 0; i < 40 && same < 3; i++) {
    await page.waitForTimeout(120);
    const now = await sig();
    same = now === last ? same + 1 : 0;
    last = now;
  }
}

//: A screenshot that two takes agree on. The page is frozen, so a take that differs from the next
//: was caught half painted (seen: a third of a look's idle frames with half the figure missing).
async function steadyShot(page, file, clip) {
  let last = await page.screenshot({ omitBackground: true, clip });
  for (let i = 0; i < 8; i++) {
    await page.waitForTimeout(100);
    const now = await page.screenshot({ omitBackground: true, clip });
    //: Equal, or within 1.5% in size (a ring still turning on the page): a half-painted take is far off that.
    if (now.equals(last) || Math.abs(now.length - last.length) <= 0.015 * Math.max(now.length, last.length)) { fs.writeFileSync(file, now); return; }
    last = now;
  }
  throw new Error(`${file}: never held still`);
}

(async () => {
  const out = process.argv[2];
  if (!out) throw new Error("usage: node render_desk_frames.js <out dir>");
  const { browser, page } = await boot({ viewport: { width: Number(process.env.VW) || 700, height: Number(process.env.VH) || 500 }, scale: 2 });
  const report = {};
  for (const look of LOOKS) {
    await page.evaluate((l) => {
      prefs.set("avatar-buddy", "atlas");
      prefs.set("atlas-look", l);
      // "fades": the companion's own behaviours stand still (no roaming, naps or acts) while the CSS poses still run.
      prefs.set("avatar-buddy-motion", "fades");
    }, look);
    //: A reload, not a re-sync: the figure keeps the look it was drawn with.
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2500);
    await page.evaluate(() => syncNameMarkBuddy());
    await page.waitForTimeout(1500);
    const got = await page.evaluate(async (box) => {
      const real = document.getElementById("nm-buddy");
      if (!real) return { error: "no #nm-buddy" };
      const clone = real; // the live element, not a copy: its eyes and rig are driven by the page
      //: CSSOM, not a <style> element: the page's CSP refuses inline style text.
      const put = (el, props) => { for (const [k, v] of Object.entries(props)) el.style.setProperty(k, v, "important"); };
      //: Glass off (Performance mode's root attribute, docs/DESIGN.md "Turning it
      //: off"): over a desktop there is nothing to blur, so the body takes its
      //: solid fallbacks instead of translucent fills that read as a ghost.
      document.documentElement.setAttribute("data-glass", "off");
      document.documentElement.classList.add("nm-no-neb");
      //: Over a wallpaper the figure's atmosphere has nothing to sit on and reads
      //: as a pale ghost: the big aura ellipse, the orbit rings and the ground
      //: shadow are left out, and the layers that are the character itself (body,
      //: tail, face, front) are drawn at full opacity. The nebula stream (INBOX
      //: 1660, "the desktop companion is also missing the nebular stream") is
      //: captured as a second pass of each frame (`<name>.neb.png`, the class
      //: `nm-no-neb` off); `render_desk_frames.py` lifts it into the shipped frame,
      //: soft but visible, apart from the solid body.
      //: insertRule, not a <style> element: the page's CSP refuses inline style text.
      const sheet = document.styleSheets[0];
      for (const rule of [
        "html.nm-no-neb #nm-buddy :is(.atl-lw-neb, .atl-lw-neb-front, .atl-layer-neb, .atl-layer-neb-fr) { display: none !important; }",
        "#nm-buddy :is(.atl-aura, .atl-orbits, .atl-rings, .atl-ring-frame, .nmp-bubble) { display: none !important; }",
        "#nm-buddy::before, #nm-buddy::after, #nm-buddy .nm-buddy-face::before, #nm-buddy .nm-buddy-face::after { display: none !important; }",
        "#nm-buddy :is(.atl-layer-back, .atl-layer-front, .atl-layer-body, .atl-layer-tail) { opacity: 1 !important; }",
        //: The app fits its figure to the room round it (`nmb-fitting`, avatars.js) and eased it to 0.75 in about half the
        //: takes of a run (the figure box 48 by 69 for 64 by 92, the head 37 by 48 for 51 by 65): a frame shot then was a
        //: smaller figure than the rest and an idle cycle seamed on it (L150). The desk set is always the full size.
        "#nm-buddy .nm-buddy-face { scale: 1 !important; transition: none !important; }",
      ]) sheet.insertRule(rule, sheet.cssRules.length);
      put(document.documentElement, { background: "transparent" });
      put(document.body, { background: "transparent" });
      for (const el of document.body.children) put(el, { visibility: "hidden" });
      //: A mask's or clip path's content inherits `visibility` from where it is
      //: defined, not from the figure that uses it. Hiding the page left every
      //: mask and clip painting nothing (no torso below the head, the irises
      //: clipped away to blank white eyes), so they are made visible themselves.
      for (const el of document.querySelectorAll("mask, clipPath")) put(el, { visibility: "visible" });
      window.__pin = "translate(" + (box.left + 78) + "px, " + (box.top + 80) + "px)";
      put(clone, { transform: window.__pin, visibility: "visible" });
      //: Then nothing else may move it: the page's own timers write the figure's transform
      //: (home corner walks, drift) at any moment, even between the pin and the screenshot.
      const realSet = CSSStyleDeclaration.prototype.setProperty;
      window.__setProp = (el, k, v, pr) => realSet.call(el.style, k, v, pr);
      Object.defineProperty(clone.style, "transform", { get: () => window.__pin, set: () => {}, configurable: true });
      clone.style.setProperty = function (k, v, pr) { if (k !== "transform") realSet.call(this, k, v, pr); };
      clone.style.removeProperty = function (k) { return k === "transform" ? "" : CSSStyleDeclaration.prototype.removeProperty.call(this, k); };
      //: The companion in the app may be tucked behind a bar (`data-legs="peek"`
      //: clips it): keep only the gait, and set the pose per frame.
      for (const name of clone.getAttributeNames()) if (name.startsWith("data-") && !["data-gait", "data-atlas-variant"].includes(name)) clone.removeAttribute(name);
      //: The page's own placement (it re-perches the figure on a bar, sitting, legs peeking) rewrote
      //: the pose between a frame being set and shot: a third of a look's idle frames came out as a
      //: half-hidden sit (INBOX 1670: the "blinking" at 8 a second). Anything but the frame's pose is put back at once.
      window.__want = "stand";
      //: And its face: a page expression (hearts, a blush) came and went over four idle frames in a row.
      if (typeof setAtlasMood === "function") { setAtlasMood("calm", 0); window.setAtlasMood = () => {}; }
      new MutationObserver(() => {
        for (const n of ["data-perch", "data-legs", "data-side"]) if (clone.hasAttribute(n)) clone.removeAttribute(n);
        if (clone.dataset.pose !== window.__want) clone.dataset.pose = window.__want;
      }).observe(clone, { attributes: true, attributeFilter: ["data-pose", "data-perch", "data-legs", "data-side"] });
      return { look: atlasLook(), rect: JSON.stringify(clone.getBoundingClientRect()) };
    }, BOX);
    report[look] = got;
    if (got.error) throw new Error(got.error);
    fs.mkdirSync(path.join(out, look), { recursive: true });
    for (const f of FRAMES.filter((fr) => !process.env.ONLY || process.env.ONLY.split(",").includes(fr.name))) {
      await page.evaluate((frame) => {
        const b = document.getElementById("nm-buddy");
        //: Every frame from the same neutral start: the page's idle timer would
        //: otherwise make it drowsy (`data-feel`, a nightcap) part-way through.
        for (const name of b.getAttributeNames()) if (name.startsWith("data-") && !["data-gait", "data-seed", "data-atlas-variant"].includes(name)) b.removeAttribute(name);
        //: The page's blink clock closes the eyes at any moment, and the freeze below then holds that blink:
        //: a masculine `stand` shipped with shut eyes (INBOX 1696). No blink in any frame but the engine's own lids.
        if (typeof atlasState !== "undefined") { clearTimeout(atlasState.blinkTimer); atlasState.blinkTimer = 0; }
        for (const el of b.querySelectorAll(".atl-blinking, .atl-blinking-slow")) el.classList.remove("atl-blinking", "atl-blinking-slow");
        for (const el of b.querySelectorAll(".nm-buddy-char, .atl-lw-tail, .atl-lw-lower, .nm-atlas.atl-layer-lower")) { el.style.removeProperty("transform"); el.style.removeProperty("transform-origin"); }
        //: The page's own timers write `style.transform` (a plain write replaces the important
        //: one) and walk the figure to its home corner part-way through the run: every frame
        //: pins it again, or the later poses land elsewhere and the clip cuts or misses them
        //: (INBOX 1663: the feminine hang, hop, land, tumble and idle frames shipped half drawn).
        window.__setProp(b, "transform", window.__pin, "important");
        b.className = frame.classes.join(" ");
        window.__want = frame.pose;
        b.dataset.pose = frame.pose;
        b.dataset.feel = "calm";
      }, f);
      await page.waitForTimeout(60);
      //: The arms are eased toward their pose by the page's own loop, so the frame after a
      //: hang or a wave was caught with the arms still coming down (INBOX 1670: a third of the
      //: idle frames of a look had them up, a flicker at 8 a second). Wait until they stop moving.
      await settleArms(page);
      await page.evaluate((frame) => {
        //: Only the CSS animations the frame's class started are moved to the
        //: frame's moment; the page's own (WAAPI eyes, drift) are frozen where
        //: they are, not rewound, so the eyes stay as they were.
        for (const a of document.getAnimations()) {
          //: A CSS transition (the iris's opacity, a part's pose change) is
          //: paused at its START by the freeze below, which left the irises and
          //: the torso at the old value: white blank eyes and a missing body.
          //: A transition is finished instead, so the frame shows where it went.
          if (a.transitionProperty) { a.finish(); continue; }
          a.pause();
          if (a.animationName && /neb|wisp|glint/.test(a.animationName)) { a.currentTime = 0; continue; } // the same moment in every frame and in the stream pass
          //: The rig's own sways (`atl-lw-sway-*`, `atl-sway-body`) sit at one moment in every frame: `at` is the
          //: act's moment (a blink, a look), and it also moved these, so stand, blink, look, wave and land came
          //: out with a lower body 5 to 7 px apart (INBOX 1696 w, "framey"); stand's ran on at its live time.
          //: A sway is held at the middle of its swing (no lean), so the walk frames' own swing (inline) is the only one.
          if (a.animationName && /^atl-(lw-)?sway/.test(a.animationName)) {
            a.effect.updateTiming({ delay: 0 });
            a.currentTime = (a.effect.getComputedTiming().duration || 0) * 0.5;
            continue;
          }
          if (a.animationName && !/^nmb-/.test(a.animationName)) { a.currentTime = 0; continue; }
          //: The rings' own turns (WAAPI, no animation name) sit at their start in every frame: left where the page's clock had
          //: them, the ring and what rode it were at another angle in each idle frame (L150, the seam at the wrap).
          if (!a.animationName && a.effect?.target?.closest?.(".atl-orbits")) { a.currentTime = 0; continue; }
          if (!a.animationName || (frame.phase === undefined && frame.at === undefined)) continue;
          const t = a.effect.getComputedTiming();
          const cycle = (t.duration || 0) * (String(t.direction).startsWith("alternate") ? 2 : 1);
          const start = Math.max(0, t.delay || 0);
          a.currentTime = frame.phase !== undefined ? cycle * frame.phase + start : frame.at * 1000 + start;
        }
      }, f);
      await page.evaluate((frame) => {
        const b = document.getElementById("nm-buddy");
        const put = (el, t, origin) => { el.style.setProperty("transform", t, "important"); if (origin) el.style.setProperty("transform-origin", origin, "important"); };
        const char = b.querySelector(".nm-buddy-char");
        if (frame.spin) put(char, `rotate(${frame.spin}deg)`, "50% 45%");
        //: The desk's own hang pendulum swings the picture (`engine._hang_drag`): the rig's swing of the char is left out.
        if (frame.upright) char.style.setProperty("rotate", "0deg", "important");
        else char.style.removeProperty("rotate");
        if (frame.wave !== undefined) b.style.setProperty("--desk-wave", `${frame.wave}deg`);
        else b.style.removeProperty("--desk-wave");
        //: Every frame's tail sits at one moment (the loop's start for a non-idle frame): the live
        //: loop otherwise captured it anywhere, so stand's lowest row moved 17 px from idle's.
        {
          const w = (frame.idle || 0) * 2 * Math.PI;
          const box = [...b.querySelectorAll("*")].find((el) => el.atlasTail);
          if (!box && frame.idle !== undefined) throw new Error("no live tail to sample");
          if (box) {
          const tail = box.atlasTail;
          //: Stop the live loop and the compositor sway so nothing redraws over the sample.
          clearTimeout(tail.raf); cancelAnimationFrame(tail.raf); tail.raf = 0;
          if (tail.sway) { tail.sway.cancel(); tail.sway = null; }
          tail.svg.style.removeProperty("transform");
          //: The page's own loop redraws the tail between the sample and the shot (INBOX 1683 e: four of the
          //: 24 idle frames carried a tail from another moment, a seam of 5x an ordinary step at the wrap): its
          //: draws are dropped while a frame is held, only this one's pass through.
          const kit = atlasTailFrame.kit;
          const p = Object.fromEntries(Object.entries(kit.acts.sway).map(([k, v]) => [k, v]));
          kit.hold = null;
          kit.draw(tail, (s) => kit.bend(s, p, w, w, 0, 2 * w), () => 1 + 0.03 * Math.cos(2 * w));
          kit.hold = tail;
          { // the breath and the lower wisp too: stand sat 5 px below idle with only the tail pinned
          const k = (1 - Math.cos(w)) / 2;
          for (const el of box.querySelectorAll(".atl-layer-body .nmb-torso")) el.style.setProperty("scale", `${(1 + atlasTailFrame.kit.swell[0] * k).toFixed(4)} ${(1 + atlasTailFrame.kit.swell[1] * k).toFixed(4)}`);
          const lower = b.querySelectorAll(".nm-atlas.atl-layer-lower").length ? ".nm-atlas.atl-layer-lower" : ".atl-lw-lower";
          for (const low of b.querySelectorAll(lower)) put(low, `skewX(${(3 * Math.sin(w - 1.5)).toFixed(2)}deg)`, "50% 55%");
          }
          }
        }
        if (frame.lower) {
          const lower = b.querySelectorAll(".nm-atlas.atl-layer-lower").length ? ".nm-atlas.atl-layer-lower" : ".atl-lw-lower";
          for (const low of b.querySelectorAll(lower)) put(low, `skewX(${frame.lower[0]}deg) scale(${frame.lower[2]}, ${frame.lower[1]})`, "50% 20%");
        }
        if (frame.float !== undefined) {
          const w = frame.float * 2 * Math.PI;
          //: No translateY: the engine's slow bob (BOB_HZ) is the only vertical motion. This one
          //: baked 9.7 px at 1.33 Hz into the drift frames (INBOX 1670: "bobbing really fast").
          put(char, "rotate(4deg)", "50% 90%");
          for (const tail of b.querySelectorAll(".atl-lw-tail")) put(tail, `rotate(${(-7 + 2.5 * Math.sin(w - 1.0)).toFixed(2)}deg)`, "40% 35%");
          const lower = b.querySelectorAll(".nm-atlas.atl-layer-lower").length ? ".nm-atlas.atl-layer-lower" : ".atl-lw-lower";
          for (const low of b.querySelectorAll(lower)) put(low, `skewX(${(6 * Math.sin(w - 2.0)).toFixed(2)}deg)`, "50% 55%");
        }
      }, f);
      await page.waitForTimeout(40);
      const at = await page.evaluate(() => { const q = document.getElementById("nm-buddy").getBoundingClientRect(); return [Math.round(q.x), Math.round(q.y)]; });
      if (at[0] !== BOX.left + 78 || at[1] !== BOX.top + 80) throw new Error(`${look}/${f.name}: the figure moved to ${at} while it was captured`);
      const clip = { x: BOX.left, y: BOX.top, width: BOX.width, height: BOX.height };
      await steadyShot(page, path.join(out, look, `${f.name}.png`), clip);
      //: The same frame with the nebula stream drawn, its animations held where they start.
      await page.evaluate(() => {
        document.documentElement.classList.remove("nm-no-neb");
      });
      await page.waitForTimeout(60);
      //: The stream's own animations start when it is un-hidden, 60 ms or more ago: pinned to
      //: the start of their cycle so every frame has the same stream (INBOX 1670: "blinking").
      await page.evaluate(() => {
        for (const a of document.getAnimations()) {
          if (a.transitionProperty) { a.finish(); continue; }
          a.pause();
          if (a.animationName && /neb|wisp|glint/.test(a.animationName)) a.currentTime = 0;
        }
      });
      await steadyShot(page, path.join(out, look, `${f.name}.neb.png`), clip);
      await page.evaluate(() => document.documentElement.classList.add("nm-no-neb"));
    }
  }
  console.log(JSON.stringify(report));
  await browser.close();
})();
