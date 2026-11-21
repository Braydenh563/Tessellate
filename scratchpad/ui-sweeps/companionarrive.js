// How the companion comes on screen (INBOX 501, the owner: "when atlas or
// the companion appears on the screen it just kinda appears and there is no
// smooth or creative animation for it to happen, or even differences on how
// it gets there"). For each way it appears (turned on from the companion
// setting, which is also the boot path, and a return after a dwell away),
// samples every frame from the moment it is asked for: the host's opacity,
// its offset from its perch, and the character's scale; reports the
// entrance chosen (`data-route`), the frames from first visible to settled,
// and the largest one-frame opacity step (a pop is 0 to 1 in a frame).
// Env: BASE, RUNS (4), LOOK. Exits 1 on any pop (> 0.5 in a frame), an
// entrance shorter than 150ms, or one way only over three runs or more.
// Measured (2026-10-04, dashboard, 1440x900): before, "enter-down" five
// times in five, faded up in 136 to 200ms.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate((look) => { localStorage.setItem('atlas-look', look); }, process.env.LOOK || 'feminine');
  let bad = 0;
  const runs = Number(process.env.RUNS || 4);
  const routes = [];
  for (let i = 0; i < runs; i += 1) {
    await page.evaluate(() => ensureModule("characters"));
    const r = await page.evaluate(() => new Promise((done) => {
      prefs.set("avatar-buddy", "off"); syncNameMarkBuddy();
      setTimeout(() => {
        localStorage.removeItem('nm-buddy-spots');
        prefs.set("avatar-buddy", "atlas"); syncNameMarkBuddy();
        const t0 = performance.now();
        const frames = [];
        const tick = () => {
          const b = document.getElementById('nm-buddy');
          if (b) {
            let o = 1;
            for (let el = b.querySelector('.nm-buddy-char') || b; el && el !== document.body; el = el.parentElement) o *= Number(getComputedStyle(el).opacity);
            frames.push([performance.now() - t0, o, b.dataset.route || '']);
          }
          if (performance.now() - t0 < 4500) requestAnimationFrame(tick);
          else {
            const shown = frames.filter((f) => f[1] > 0.05);
            const first = shown[0];
            const full = frames.find((f) => f[1] > 0.95 && first && f[0] >= first[0]);
            let step = 0;
            for (let k = 1; k < frames.length; k += 1) step = Math.max(step, frames[k][1] - frames[k - 1][1]);
            done({ route: (shown.at(-1) || [0, 0, ''])[2], firstMs: first ? Math.round(first[0]) : -1, fadeMs: first && full ? Math.round(full[0] - first[0]) : -1, maxStep: +step.toFixed(2) });
          }
        };
        requestAnimationFrame(tick);
      }, 600);
    }));
    routes.push(r.route);
    const ok = r.maxStep <= 0.5 && r.fadeMs >= 150;
    if (!ok) bad += 1;
    console.log(ok ? 'ok ' : 'BAD', JSON.stringify(r));
  }
  //: The same way every time is the other half of the report.
  const kinds = new Set(routes);
  if (runs >= 3 && kinds.size < 2) bad += 1;
  console.log(bad ? `FAIL ${bad}` : 'PASS', 'routes', [...kinds].join(','));
  await browser.close();
  process.exitCode = bad ? 1 : 0;
})();
