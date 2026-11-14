// The owner, 2026-09-27: emotes and acts on a click "must ease back to the
// prior state, never cut back after a few seconds". Plays a face-changing
// act on Atlas (cheer: happy eyes, a big grin), and samples every frame how
// long the happy eyes take to go from their cheer value back to rest once
// the act's class comes off. Exits 1 when that is under 600ms (a cut).
// Env: ACT (cheer), BASE.
const { boot } = require('./lib.js');

(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(async () => { prefs.set('avatar-buddy', 'atlas'); await ensureModule('characters'); syncNameMarkBuddy(); });
  await page.waitForTimeout(4500);
  const r = await page.evaluate((act) => new Promise((done) => {
    const buddy = document.getElementById('nm-buddy');
    const eye = buddy.querySelector('.atl-e-happy');
    nameMarkBuddyAct(act);
    const frames = [];
    let off = null;
    const t0 = performance.now();
    const look = () => {
      const now = performance.now() - t0;
      const on = buddy.classList.contains(`nmb-act-${act}`);
      if (!on && off === null) off = now;
      frames.push([Math.round(now), Number(getComputedStyle(eye).opacity)]);
      if (now < 6000) requestAnimationFrame(look);
      else {
        const after = frames.filter((f) => off !== null && f[0] >= off);
        const start = after[0]?.[1] ?? 0;
        const rest = after[after.length - 1]?.[1] ?? 0;
        const settled = after.find((f) => Math.abs(f[1] - rest) < 0.05 * Math.max(0.01, Math.abs(start - rest)) + 0.01);
        done({ off: Math.round(off), start, rest, easedMs: settled ? Math.round(settled[0] - off) : null });
      }
    };
    requestAnimationFrame(look);
  }), process.env.ACT || 'cheer');
  console.log(JSON.stringify(r));
  const bad = r.off === null || r.easedMs === null || (Math.abs(r.start - r.rest) > 0.3 && r.easedMs < 600);
  console.log(bad ? 'FAIL' : 'PASS');
  process.exitCode = bad ? 1 : 0;
  await browser.close();
})();
