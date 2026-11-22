// The owner, 2026-10-11: "if it is hanging, the expanded companion kinda
// looks awkward with both it's arms up". Atlas hangs from the top bar, its
// large view opens (`openNameMarkViewer`, visit), and each arm's turn (the
// rig's shoulder) is read against where its float pose puts it (the
// probe's), 300 ms in and later. PASS: every arm within 12 degrees of its
// resting place at 300 ms. Before: 150 and -151 degrees (still raised) at
// 300 ms, coming down over seconds on a loaded machine.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(() => { const b = $('avatar-buddy'); b.value = 'atlas'; b.dispatchEvent(new Event('change', { bubbles: true })); });
  await page.waitForTimeout(3000);
  await page.evaluate(() => { const top = document.getElementById('top-bar').getBoundingClientRect(); const b = document.getElementById('nm-buddy'); nameMarkBuddyMoveTo(b, { kind: 'hang', pose: 'hang', legs: '', x: 700, y: Math.round(top.bottom - NMB_GRIP) }, true); nmb.placedAt = Date.now(); nameMarkBuddyAct(''); });
  await page.waitForTimeout(1500);
  const arms = () => page.evaluate(() => { const b = document.getElementById('nm-buddy'); const rig = b.querySelector('.atl-figure-box')?.atlasRig; return { pose: b.dataset.pose, act: nmb.act, cls: [...b.classList].filter((c) => /act|hold|hang|swing/.test(c)).join(' '), arms: rig ? rig.arms.map((a) => [a.side, Math.round(a.j.sh.x), Math.round(a.j.el.x), Math.round(atlasRigRead(a).ang)]) : null, frames: (window.__fr || 0), hold: [...b.querySelectorAll('.nmb-hold')].map((h) => getComputedStyle(h).opacity) }; });
  await page.evaluate(() => { window.__fr = 0; const f = () => { window.__fr++; requestAnimationFrame(f); }; requestAnimationFrame(f); });
  console.log('perched', JSON.stringify(await arms()));
  await page.evaluate(() => openNameMarkViewer(document.getElementById('nm-buddy').dataset.seed || '', { visit: true }));
  let first = null;
  for (const ms of [300, 1200, 3000]) { await page.waitForTimeout(ms === 300 ? 300 : ms - 300); const a = await arms(); if (!first) first = a; console.log('viewer', ms, JSON.stringify(a)); }
  const off = first.arms ? Math.max(...first.arms.map((a) => Math.abs(a[1] - a[3]))) : 999;
  console.log(off <= 12 ? 'PASS' : `FAIL: an arm ${off} degrees from rest at 300 ms`);
  process.exitCode = off <= 12 ? 0 : 1;
  await browser.close();
})();
