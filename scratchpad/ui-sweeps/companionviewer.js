// INBOX 443 (b), (c), the owner: "the regular companion expanded popup
// window needs more life and not just a statue"; "if the companion is doing
// a specific action and i double click it to view it in the enlarged
// window, I want it to keep doing that action unless poked or something
// else happens".
//
// Sets the companion going on a long act (ACT, default "read", 20s), opens
// its large view with a double-click on it, and measures:
//   - that the element in the view is the companion itself, still on that
//     act (its class and `nmb.act`) 3s later;
//   - that the drawing changes over 5s (20 samples of every part's box and
//     the running animations: distinct states, and which acts played);
//   - that its eyes follow the pointer (`--nmb-ex` with the pointer to its
//     left and then its right);
//   - that a poke ends the act and it answers (the act after, a line said);
//   - that closing sends it home (back in its band, on its perch).
// Env: KIND (atlas), ACT (read), REDUCED=1 (prefers-reduced-motion: then
// only blinks may play), W (1440). Screenshots: out/buddy-viewer-*.png.
const { boot } = require("./lib.js");
const path = require("path");

const OUTDIR = path.join(__dirname, "out");
require("fs").mkdirSync(OUTDIR, { recursive: true });
const tag = `${process.env.KIND || "atlas"}${process.env.REDUCED ? "-reduced" : ""}`;

(async () => {
  const { browser, page } = await boot({ viewport: { width: Number(process.env.W || 1440), height: 900 }, ...(process.env.REDUCED ? { reducedMotion: "reduce" } : {}) });
  await page.evaluate((k) => {
    localStorage.removeItem("nm-buddy-spots");
    const b = $("avatar-buddy");
    b.value = k;
    b.dispatchEvent(new Event("change", { bubbles: true }));
  }, process.env.KIND || "atlas");
  await page.waitForTimeout(4000);
  const act = process.env.ACT || "read";
  const before = await page.evaluate((act) => {
    nameMarkBuddyAct(act, 20000);
    return { act: nmb.act, pose: nmb.pose, at: [nmb.x, nmb.y].map(Math.round) };
  }, act);
  await page.waitForTimeout(600);
  await page.evaluate(() => document.querySelector("#nm-buddy .nm-buddy-face").dispatchEvent(new MouseEvent("dblclick", { bubbles: true })));
  await page.waitForTimeout(1200);
  const opened = await page.evaluate(() => {
    const buddy = document.getElementById("nm-buddy");
    const fig = buddy?.querySelector(".nm-buddy-face")?.getBoundingClientRect();
    return {
      inView: !!buddy?.closest(".nm-viewer-figure"), act: nmb.act, cls: [...(buddy?.classList || [])].filter((c) => c.startsWith("nmb-act-")),
      visit: !!nmb.visit, face: fig && [fig.left, fig.top, fig.width, fig.height].map(Math.round),
      head: document.querySelector(".nm-viewer .dialog-head") ? document.querySelector(".nm-viewer .dialog-head").textContent.trim() : null,
      close: document.querySelector(".nm-viewer .dialog-head-btn")?.getAttribute("aria-label") || null,
      lines: [...document.querySelectorAll(".nm-viewer-card p")].map((p) => p.textContent),
    };
  });
  await page.screenshot({ path: `${OUTDIR}/buddy-viewer-${tag}-open.png` });
  await page.waitForTimeout(1800);
  const kept = await page.evaluate(() => ({ act: nmb.act, cls: [...document.getElementById("nm-buddy").classList].filter((c) => c.startsWith("nmb-act-")) }));
  // 5 seconds of the drawing: every part's box and every running animation.
  const states = new Set();
  const anims = new Set();
  const acts = new Set();
  for (let i = 0; i < 20; i += 1) {
    const s = await page.evaluate(() => {
      const root = document.querySelector(".nm-viewer-figure");
      const parts = [...root.querySelectorAll(".nm-eyes, .nmb-arm-r, .nmb-arm-l, .nm-buddy-head, .nm-buddy-char, .nm-figure, .nm-blinks")];
      const sig = parts.map((p) => {
        const r = p.getBoundingClientRect();
        return `${Math.round(r.left)},${Math.round(r.top)},${Math.round(r.width)},${Math.round(r.height)}`;
      }).join("|");
      const running = root.getAnimations({ subtree: true }).filter((a) => a.playState === "running").map((a) => a.animationName || "waapi");
      return { sig, running, act: nmb.act };
    });
    states.add(s.sig);
    s.running.forEach((n) => anims.add(n));
    if (s.act) acts.add(s.act);
    await page.waitForTimeout(250);
  }
  // Its eyes on the pointer, left and then right of it.
  const face = opened.face || [700, 300, 140, 200];
  const cx = face[0] + face[2] / 2;
  const cy = face[1] + face[3] * 0.3;
  await page.mouse.move(cx - 220, cy);
  await page.waitForTimeout(700);
  const exLeft = await page.evaluate(() => getComputedStyle(document.getElementById("nm-buddy")).getPropertyValue("--nmb-ex"));
  await page.mouse.move(cx + 220, cy + 10);
  await page.waitForTimeout(700);
  const exRight = await page.evaluate(() => getComputedStyle(document.getElementById("nm-buddy")).getPropertyValue("--nmb-ex"));
  await page.screenshot({ path: `${OUTDIR}/buddy-viewer-${tag}-alive.png` });
  // A poke.
  await page.evaluate(() => document.querySelector("#nm-buddy .nm-buddy-face").click());
  await page.waitForTimeout(500);
  const poked = await page.evaluate(() => ({ act: nmb.act, said: document.querySelector("#nm-buddy > .nm-say")?.textContent || "" }));
  await page.screenshot({ path: `${OUTDIR}/buddy-viewer-${tag}-poked.png` });
  // Close: home again.
  await page.keyboard.press("Escape");
  await page.waitForTimeout(800);
  const home = await page.evaluate(() => {
    const buddy = document.getElementById("nm-buddy");
    return { inBand: !!buddy?.closest("#nm-buddy-band"), visit: !!nmb.visit, at: [nmb.x, nmb.y].map(Math.round), viewer: !!document.querySelector(".nm-viewer") };
  });
  console.log(JSON.stringify({ before, opened, kept, distinctStates: states.size, anims: [...anims], actsSeen: [...acts], exLeft, exRight, poked, home }, null, 1));
  const reduced = !!process.env.REDUCED;
  const bad = !opened.inView || (!reduced && (kept.act !== act || states.size < 4)) || home.inBand !== true || home.viewer
    || (!reduced && !(parseFloat(exLeft) < 0 && parseFloat(exRight) > 0));
  console.log(bad ? "FAIL" : "PASS");
  process.exitCode = bad ? 1 : 0;
  await browser.close();
})();
