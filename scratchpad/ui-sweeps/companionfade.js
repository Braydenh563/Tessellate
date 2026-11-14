// INBOX 443, the owner: "I also want companion transitions to be better
// even with reduced motion on". With reduced motion the companion does not
// travel: a move was a fade out where it was and a fade in where it went,
// with a moment of nothing between. Now a still copy fades out where it was
// while it fades in where it is. This boots with prefers-reduced-motion,
// sends it to a new perch (a tab change, then its own beat) and samples
// every frame for 700ms: the companion's opacity, the copy's, and their
// combined presence (1 - (1 - a)(1 - b)). Exits 1 when the presence ever
// drops under 0.75 (the old dip went to 0), or no copy was drawn.
// Env: KIND (atlas), W (1440).
const { boot } = require("./lib.js");

(async () => {
  const { browser, page } = await boot({ viewport: { width: Number(process.env.W || 1440), height: 900 }, reducedMotion: "reduce" });
  await page.evaluate(async (k) => {
    localStorage.removeItem("nm-buddy-spots");
    prefs.set("avatar-buddy", k); await ensureModule("characters"); syncNameMarkBuddy();
  }, process.env.KIND || "atlas");
  await page.waitForTimeout(3500);
  const r = await page.evaluate(async () => {
    const buddy = document.getElementById("nm-buddy");
    const from = [nmb.x, nmb.y];
    //: A move it would make on its own: the far end of the window's bar.
    const { bottom } = nameMarkBuddyLedges();
    const x = nmb.x > innerWidth / 2 ? 40 : innerWidth - 140;
    nameMarkBuddyMoveTo(buddy, { kind: "bar", pose: "stand", legs: "", x, y: bottom.top - NMB_FEET + 1, edge: { el: document.getElementById("status-bar"), type: "top", kind: "bar", y: bottom.top } });
    const samples = [];
    let ghosts = 0;
    const t0 = performance.now();
    await new Promise((done) => {
      const step = () => {
        const ghost = document.querySelector(".nmb-ghost");
        if (ghost) ghosts += 1;
        const a = Number(getComputedStyle(buddy).opacity);
        const b = ghost ? Number(getComputedStyle(ghost).opacity) : 0;
        samples.push({ t: Math.round(performance.now() - t0), a, b, presence: 1 - (1 - a) * (1 - b) });
        if (performance.now() - t0 < 700) requestAnimationFrame(step);
        else done();
      };
      requestAnimationFrame(step);
    });
    return { from: from.map(Math.round), to: [nmb.x, nmb.y].map(Math.round), ghosts, left: !!document.querySelector(".nmb-ghost"), min: Math.min(...samples.map((s) => s.presence)), samples: samples.filter((_, i) => i % 4 === 0) };
  });
  console.log(`moved ${r.from} -> ${r.to}; frames with a copy ${r.ghosts}; copy left after ${r.left}; lowest presence ${r.min.toFixed(2)}`);
  console.log(r.samples.map((s) => `${s.t}ms a=${s.a.toFixed(2)} b=${s.b.toFixed(2)}`).join("\n"));
  const bad = r.min < 0.75 || !r.ghosts || r.left;
  console.log(bad ? "FAIL" : "PASS");
  process.exitCode = bad ? 1 : 0;
  await browser.close();
})();
