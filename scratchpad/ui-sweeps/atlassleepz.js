// The owner, 2026-10-19: lying asleep, the Zs rose from where a standing
// head would be. Per sleeping pose: the head's centre (the eyes) and the
// first z, relative to each other. PASS when every z sits within 40px of
// the head and above it.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(() => { const b = document.getElementById('avatar-buddy'); b.value = 'atlas'; b.dispatchEvent(new Event('change', { bubbles: true })); });
  await page.waitForTimeout(4000);
  let bad = 0;
  for (const pose of (process.env.POSES || 'stand,sit,lie,lie-2,curl,curl-2').split(',')) {
    for (const v1 of [0, 1, 2]) {
      const r = await page.evaluate(async ([pose, v1]) => {
        const b = document.getElementById('nm-buddy');
        nameMarkBuddyAct('');
        b.dataset.pose = pose;
        b.dataset.atlasVariant = String(v1);
        b.classList.add('nmb-sleep');
        await new Promise((r) => setTimeout(r, 900));
        const eyes = [...b.querySelectorAll('.atl-figure .atl-layer-body .atl-e-doze, .atl-figure .atl-e-doze')].map((e) => e.getBoundingClientRect()).filter((q) => q.width);
        const z = b.querySelector('.nm-buddy-z').getBoundingClientRect();
        if (!eyes.length) return { pose, v1, err: 'no eyes' };
        const hx = eyes.reduce((s, q) => s + q.left + q.width / 2, 0) / eyes.length;
        const hy = eyes.reduce((s, q) => s + q.top + q.height / 2, 0) / eyes.length;
        return { pose, v1, dx: Math.round(z.left + z.width / 2 - hx), dy: Math.round(z.top + z.height / 2 - hy) };
      }, [pose, v1]);
      const ok = !r.err && Math.abs(r.dx) <= 60 && r.dy < 0 && r.dy > -60;
      if (!ok) bad++;
      console.log(ok ? 'ok ' : 'BAD', JSON.stringify(r));
    }
  }
  console.log(bad ? `FAIL ${bad}` : 'PASS');
  await browser.close();
})();
