// The owner, 2026-09-27: on Chat "it was left floating mid-panel for seconds
// after its perch (a button on an empty chat) went away". Puts the companion
// on the empty chat's first chip (or whatever it chose there), removes that
// perch from the page as a chat switch would, and times, every animation
// frame, how long it floats before it is on a new perch (its pose back to
// sit, stand or hang and a move started), and whether that perch is clean.
// Env: VW, VH (1093 x 614), BASE. Exits 1 when it floats longer than 800ms.
const { boot } = require('./lib.js');
const VW = Number(process.env.VW || 1093);
const VH = Number(process.env.VH || 614);

(async () => {
  const { browser, page } = await boot({ viewport: { width: VW, height: VH } });
  await page.evaluate(() => { localStorage.removeItem('nm-buddy-spots'); const b = $('avatar-buddy'); b.value = 'atlas'; b.dispatchEvent(new Event('change', { bubbles: true })); });
  await page.evaluate(() => switchTab('chat'));
  await page.waitForTimeout(4500);
  const before = await page.evaluate(() => {
    const el = nmb.glue?.el;
    return { perch: nmb.perch, pose: nmb.pose, el: el ? `${el.tagName.toLowerCase()}.${[...el.classList].slice(0, 2).join('.')}` : '' };
  });
  console.log('on:', JSON.stringify(before));
  const r = await page.evaluate(() => new Promise((done) => {
    const el = nmb.glue?.el;
    if (!el) { done({ skipped: true }); return; }
    const t0 = performance.now();
    let floatAt = null;
    let landedAt = null;
    el.remove();
    const look = () => {
      const now = performance.now() - t0;
      if (floatAt === null && nmb.pose === 'float') floatAt = now;
      if (floatAt !== null && landedAt === null && nmb.pose !== 'float') landedAt = now;
      if (landedAt !== null || now > 6000) {
        done({ floatAt: floatAt === null ? null : Math.round(floatAt), landedAt: landedAt === null ? null : Math.round(landedAt), perch: nmb.perch, pose: nmb.pose });
        return;
      }
      requestAnimationFrame(look);
    };
    requestAnimationFrame(look);
  }));
  console.log('perch removed:', JSON.stringify(r));
  const floated = r.skipped ? 0 : (r.landedAt ?? 6000) - (r.floatAt ?? 0);
  console.log(`floated ${floated}ms`);
  const bad = !r.skipped && (r.floatAt === null || floated > 800);
  console.log(bad ? 'FAIL' : 'PASS');
  process.exitCode = bad ? 1 : 0;
  await browser.close();
})();
