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
  ...[0, 1, 2, 3, 4, 5].map((i) => ({ name: `walk${i}`, pose: "stand", classes: [], float: i / 6 })),
  { name: "sit", pose: "sit", classes: [] },
  { name: "sleep", pose: "sit", classes: ["nmb-sleep"], at: 1.0 },
  { name: "wave", pose: "stand", classes: ["nmb-act-wave"], at: 0.45 },
  { name: "held", pose: "stand", classes: ["nm-buddy-dragging"] },
  { name: "fall", pose: "stand", classes: ["nmb-act-startle"], at: 0.25 },
  { name: "land", pose: "stand", classes: ["nmb-act-land"], at: 0.1 },
  { name: "hop", pose: "stand", classes: ["nmb-act-hop"], at: 0.3 },
  //: The rig's own hanging pose: both arms raised to an edge above it.
  { name: "hang", pose: "hang", classes: [] },
  //: A throw's mid-spin: the startled pose turned about its middle (the rig has
  //: no tumble of its own, so this one is a transform of an existing pose).
  { name: "tumble", pose: "stand", classes: ["nmb-act-startle"], at: 0.25, spin: 115 },
];
//: The idle cycle (`idle0` to `idle11`, engine.IDLE_FRAMES): the rig's own standing
//: motion sampled at fixed times, one full beat of the tail (`atlasTailBend` with
//: the sway act's own numbers, `atlas-life.js`) and one breath (`atlasBreathFrame`'s
//: raised cosine on the torso, plus a small rise of the whole figure so the
//: breath shows at this size), so the loop closes on itself.
const IDLE_N = 12;
FRAMES.push(...Array.from({ length: IDLE_N }, (_, i) => ({ name: `idle${i}`, pose: "stand", classes: [], idle: i / IDLE_N })));
const LOOKS = (process.env.LOOKS || "masculine,feminine").split(",");
//: The capture box around the figure, in CSS pixels: roomy, cropped later.
const BOX = { width: 220, height: 260, left: 120, top: 60 };

(async () => {
  const out = process.argv[2];
  if (!out) throw new Error("usage: node render_desk_frames.js <out dir>");
  const { browser, page } = await boot({ viewport: { width: 700, height: 500 }, scale: 2 });
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
      ]) sheet.insertRule(rule, sheet.cssRules.length);
      put(document.documentElement, { background: "transparent" });
      put(document.body, { background: "transparent" });
      for (const el of document.body.children) put(el, { visibility: "hidden" });
      //: A mask's or clip path's content inherits `visibility` from where it is
      //: defined, not from the figure that uses it. Hiding the page left every
      //: mask and clip painting nothing (no torso below the head, the irises
      //: clipped away to blank white eyes), so they are made visible themselves.
      for (const el of document.querySelectorAll("mask, clipPath")) put(el, { visibility: "visible" });
      put(clone, { transform: "translate(" + (box.left + 78) + "px, " + (box.top + 80) + "px)", visibility: "visible" });
      //: The companion in the app may be tucked behind a bar (`data-legs="peek"`
      //: clips it): keep only the gait, and set the pose per frame.
      for (const name of clone.getAttributeNames()) if (name.startsWith("data-") && !["data-gait", "data-atlas-variant"].includes(name)) clone.removeAttribute(name);
      return { look: atlasLook(), rect: JSON.stringify(clone.getBoundingClientRect()) };
    }, BOX);
    report[look] = got;
    if (got.error) throw new Error(got.error);
    fs.mkdirSync(path.join(out, look), { recursive: true });
    for (const f of FRAMES) {
      await page.evaluate((frame) => {
        const b = document.getElementById("nm-buddy");
        //: Every frame from the same neutral start: the page's idle timer would
        //: otherwise make it drowsy (`data-feel`, a nightcap) part-way through.
        for (const name of b.getAttributeNames()) if (name.startsWith("data-") && !["data-gait", "data-seed", "data-atlas-variant"].includes(name)) b.removeAttribute(name);
        for (const el of b.querySelectorAll(".nm-buddy-char, .atl-lw-tail, .atl-lw-lower, .nm-atlas.atl-layer-lower")) { el.style.removeProperty("transform"); el.style.removeProperty("transform-origin"); }
        b.className = frame.classes.join(" ");
        b.dataset.pose = frame.pose;
        b.dataset.feel = "calm";
      }, f);
      await page.waitForTimeout(60);
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
        if (frame.idle !== undefined) {
          const w = frame.idle * 2 * Math.PI;
          const box = [...b.querySelectorAll("*")].find((el) => el.atlasTail);
          if (!box) throw new Error("no live tail to sample");
          const tail = box.atlasTail;
          //: Stop the live loop and the compositor sway so nothing redraws over the sample.
          clearTimeout(tail.raf); cancelAnimationFrame(tail.raf); tail.raf = 0;
          if (tail.sway) { tail.sway.cancel(); tail.sway = null; }
          tail.svg.style.removeProperty("transform");
          const p = Object.fromEntries(Object.entries(ATLAS_TAIL_ACTS.sway).map(([k, v]) => [k, v]));
          atlasTailDraw(tail, (s) => atlasTailBend(s, p, w, w, 0, 2 * w), () => 1 + 0.03 * Math.cos(2 * w));
          const k = (1 - Math.cos(w)) / 2;
          for (const el of box.querySelectorAll(".atl-layer-body .nmb-torso")) el.style.setProperty("scale", `${(1 + ATLAS_BREATH_SWELL[0] * k).toFixed(4)} ${(1 + ATLAS_BREATH_SWELL[1] * k).toFixed(4)}`);
          put(char, `translateY(${(-1.5 * k).toFixed(2)}px)`, "50% 90%");
          const lower = b.querySelectorAll(".nm-atlas.atl-layer-lower").length ? ".nm-atlas.atl-layer-lower" : ".atl-lw-lower";
          for (const low of b.querySelectorAll(lower)) put(low, `skewX(${(3 * Math.sin(w - 1.5)).toFixed(2)}deg)`, "50% 55%");
        }
        if (frame.float !== undefined) {
          const w = frame.float * 2 * Math.PI;
          put(char, `translateY(${(-6 * Math.sin(w)).toFixed(2)}px) rotate(4deg)`, "50% 90%");
          for (const tail of b.querySelectorAll(".atl-lw-tail")) put(tail, `rotate(${(11 * Math.sin(w - 1.0)).toFixed(2)}deg)`, "40% 35%");
          const lower = b.querySelectorAll(".nm-atlas.atl-layer-lower").length ? ".nm-atlas.atl-layer-lower" : ".atl-lw-lower";
          for (const low of b.querySelectorAll(lower)) put(low, `skewX(${(9 * Math.sin(w - 2.0)).toFixed(2)}deg)`, "50% 55%");
        }
      }, f);
      await page.waitForTimeout(40);
      const clip = { x: BOX.left, y: BOX.top, width: BOX.width, height: BOX.height };
      await page.screenshot({ path: path.join(out, look, `${f.name}.png`), omitBackground: true, clip });
      //: The same frame with the nebula stream drawn, its animations held where they start.
      await page.evaluate(() => {
        document.documentElement.classList.remove("nm-no-neb");
      });
      await page.waitForTimeout(60);
      await page.evaluate(() => { for (const a of document.getAnimations()) { if (a.transitionProperty) a.finish(); else a.pause(); } });
      await page.screenshot({ path: path.join(out, look, `${f.name}.neb.png`), omitBackground: true, clip });
      await page.evaluate(() => document.documentElement.classList.add("nm-no-neb"));
    }
  }
  console.log(JSON.stringify(report));
  await browser.close();
})();
