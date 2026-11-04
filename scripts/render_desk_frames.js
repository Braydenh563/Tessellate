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
  ...[0, 1, 2, 3, 4, 5].map((i) => ({ name: `walk${i}`, pose: "stand", classes: ["nmb-walking"], phase: i / 6 })),
  { name: "sit", pose: "sit", classes: [] },
  { name: "sleep", pose: "sit", classes: ["nmb-sleep"], at: 1.0 },
  { name: "wave", pose: "stand", classes: ["nmb-act-wave"], at: 0.45 },
  { name: "held", pose: "stand", classes: ["nm-buddy-dragging"] },
  { name: "fall", pose: "stand", classes: ["nmb-act-startle"], at: 0.25 },
  { name: "land", pose: "stand", classes: ["nmb-act-land"], at: 0.1 },
  { name: "hop", pose: "stand", classes: ["nmb-act-hop"], at: 0.3 },
];
const LOOKS = ["masculine", "feminine"];
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
      put(document.documentElement, { background: "transparent" });
      put(document.body, { background: "transparent" });
      for (const el of document.body.children) put(el, { visibility: "hidden" });
      put(clone, { transform: "translate(" + (box.left + 78) + "px, " + (box.top + 80) + "px)", visibility: "visible" });
      //: The companion in the app may be tucked behind a bar (`data-legs="peek"`
      //: clips it): keep only the gait, and set the pose per frame.
      for (const name of clone.getAttributeNames()) if (name.startsWith("data-") && name !== "data-gait") clone.removeAttribute(name);
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
        for (const name of b.getAttributeNames()) if (name.startsWith("data-") && name !== "data-gait" && name !== "data-seed") b.removeAttribute(name);
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
          a.pause();
          if (!a.animationName || (frame.phase === undefined && frame.at === undefined)) continue;
          const t = a.effect.getComputedTiming();
          const cycle = (t.duration || 0) * (String(t.direction).startsWith("alternate") ? 2 : 1);
          const start = Math.max(0, t.delay || 0);
          a.currentTime = frame.phase !== undefined ? cycle * frame.phase + start : frame.at * 1000 + start;
        }
      }, f);
      await page.waitForTimeout(40);
      await page.screenshot({
        path: path.join(out, look, `${f.name}.png`),
        omitBackground: true,
        clip: { x: BOX.left, y: BOX.top, width: BOX.width, height: BOX.height },
      });
    }
  }
  console.log(JSON.stringify(report));
  await browser.close();
})();
