// Owner 2026-10-11, companion large view: "the zzz isnt animated" (a), a blue
// box ring round the sleeping figure after a click (b), glitchy under load (c).
// Sleeps the companion, opens its large view, and measures the Zs' running
// animations and opacity over time, the face's outline after a click and
// after Tab, and (CPU=6) the same under CDP CPU throttling.
// Env: KIND (atlas), W (1440), THEME, CPU (1), ORDER (sleep-first|open-first).
const { boot } = require("./lib.js");
(async () => {
  const W = Number(process.env.W || 1440);
  const { browser, page } = await boot({ viewport: { width: W, height: 900 }, ...(W < 600 ? { hasTouch: true, isMobile: true } : {}), ...(process.env.REDUCED ? { reducedMotion: "reduce" } : {}) });
  await page.evaluate((k) => {
    localStorage.removeItem("nm-buddy-spots");
    const b = document.getElementById("avatar-buddy");
    b.value = k;
    b.dispatchEvent(new Event("change", { bubbles: true }));
  }, process.env.KIND || "atlas");
  console.log("booted");
  if (Number(process.env.CPU || 1) > 1) {
    const cdp = await page.context().newCDPSession(page);
    await cdp.send("Emulation.setCPUThrottlingRate", { rate: Number(process.env.CPU) });
  }

  await page.waitForTimeout(4000);
  await page.evaluate(() => { const w = window.nameMarkBuddyWake; window.__wakes = []; window.nameMarkBuddyWake = function (...a) { window.__wakes.push(new Error().stack.split("\n").slice(1, 5).join(" < ")); return w.apply(this, a); };
    const r = document.getElementById("nm-buddy"); window.__cls = []; new MutationObserver(() => { const c = [...r.classList].filter((x) => /nmb-(sleep|act)/.test(x)).join(" "); if (window.__cls[window.__cls.length - 1] !== c) window.__cls.push(c); }).observe(r, { attributes: true, attributeFilter: ["class"] }); });
  const sleep = () => page.evaluate(() => { nmb.lastInput = Date.now() - NMB_SLEEP_MS - 1000; nmb.awakeUntil = 0; nmb.tick(); });
  await page.mouse.move(W - 5, 5);
  // OPEN=menu opens it from its menu's Enlarge (no wake), as the owner may have.
  const open = () => page.evaluate((how) => how === "menu" ? openNameMarkViewer(document.getElementById("nm-buddy").dataset.seed || "", { visit: true }) : document.querySelector("#nm-buddy .nm-buddy-face").dispatchEvent(new MouseEvent("dblclick", { bubbles: true })), process.env.OPEN || "dbl");
  if (process.env.FULL) await page.evaluate(() => { document.documentElement.dataset.buddyMotion = "full"; });
  if (process.env.EXPR) await page.evaluate((e) => nameMarkBuddyExpress(e, 60000), process.env.EXPR);
  if (process.env.ACT) await page.evaluate((a) => nameMarkBuddyAct(a, 60000), process.env.ACT);
  if ((process.env.ORDER || "sleep-first") === "sleep-first") { await sleep(); await page.waitForTimeout(3600); await open(); }
  else { await open(); await page.waitForTimeout(1200); if (!process.env.SKIPSLEEP) await sleep(); }
  await page.waitForTimeout(1500);
  console.log("slept+opened");
  const zs = async () => page.evaluate(() => {
    const b = document.getElementById("nm-buddy");
    const zz = [...b.querySelectorAll(".nm-buddy-z i")];
    const az = [...b.querySelectorAll(".atl-zf, .atl-fx-zz")];
    const eff = (e) => { let o = 1; for (let n = e; n && n.nodeType === 1; n = n.parentNode) o *= +getComputedStyle(n).opacity; return o.toFixed(2); };
    const anc = (e) => { const out = []; for (let n = e; n && n.nodeType === 1 && n.id !== "nm-buddy"; n = n.parentNode) for (const a of n.getAnimations()) if (a.playState === "running") out.push(a.animationName || "waapi"); return out.join("+") || "-"; };
    const vis = [...b.querySelectorAll(".atl-zf")].map((e) => eff(e) + ":" + anc(e) + ":" + (e.closest("svg")?.getAttribute("class") || "").split(" ").filter((c) => /layer|mood/.test(c)).join("."));
    const run = (els) => els.map((e) => e.getAnimations().filter((a) => a.playState === "running").map((a) => a.animationName || "waapi").join("+") || "-");
    return {
      inView: !!b.closest(".nm-viewer-figure"), cls: [...b.classList].filter((c) => /nmb-(sleep|act)/.test(c)).join(" "), pose: b.dataset.pose,
      vis, mood: b.querySelector(".nm-atlas")?.dataset.atlasMood,
      zDisplay: getComputedStyle(b.querySelector(".nm-buddy-z")).display,
      zAnim: run(zz), zOp: zz.map((e) => (+getComputedStyle(e).opacity).toFixed(2)),
      atlZ: run(az), atlZop: az.map((e) => (+getComputedStyle(e).opacity).toFixed(2)),
      root: [document.documentElement.dataset.avatarMotion, document.documentElement.dataset.buddyMotion, document.documentElement.dataset.motion].join("/"),
      hidden: document.hidden, still: typeof nameMarkBuddyStill === "function" ? nameMarkBuddyStill() : null,
    };
  });
  const samples = [];
  for (let i = 0; i < 14; i += 1) { samples.push(await zs()); await page.waitForTimeout(500); }
  console.log("z times", JSON.stringify(await page.evaluate(() => [...document.querySelectorAll("#nm-buddy .nm-buddy-z i")].map((e) => e.getAnimations().map((a) => [a.animationName, a.playState, Math.round(a.currentTime), a.effect.getComputedTiming().iterations, a.effect.getComputedTiming().currentIteration])))));
  console.log(JSON.stringify(samples[0]));
  console.log("wakes", JSON.stringify(await page.evaluate(() => window.__wakes)), "\ncls", JSON.stringify(await page.evaluate(() => window.__cls)));
  console.log("over time", samples.map((s) => s.cls + "/" + s.pose + "/" + s.zDisplay + "/" + s.zAnim.join(",") + "/" + s.zOp.join(",") + " atl " + s.mood + " " + s.vis.join(" ")).join("\n"));
  // (b) the ring: a click inside the view, then Tab.
  const ring = () => page.evaluate(() => {
    const f = document.activeElement || document.body;
    const cs = getComputedStyle(f);
    return { el: f.tagName + "." + [...f.classList].join("."), id: f.id, fv: f.matches(":focus-visible"), outline: `${cs.outlineStyle} ${cs.outlineWidth} ${cs.outlineColor}`, shadow: cs.boxShadow.slice(0, 80), radius: cs.borderRadius, filter: cs.filter.slice(0, 80) };
  });
  const r = await page.evaluate(() => { const x = document.querySelector("#nm-buddy .nm-buddy-face").getBoundingClientRect(); return [x.left + x.width / 2, x.top + x.height / 2]; });
  await page.mouse.click(r[0], r[1]);
  await page.waitForTimeout(400);
  console.log("after click", JSON.stringify(await ring()));
  await page.evaluate(() => document.activeElement && document.activeElement.blur());
  await page.keyboard.press("Tab");
  for (let i = 0; i < 12; i += 1) { if (await page.evaluate(() => document.activeElement?.classList.contains("nm-buddy-face"))) break; await page.keyboard.press("Tab"); }
  console.log("after tab", JSON.stringify(await ring()));
  await browser.close();
})();
