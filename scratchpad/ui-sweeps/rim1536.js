// INBOX 1536: every edge and corner of a movable panel resizes, the opposite edge held still.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.waitForTimeout(2500);
  await page.evaluate(() => localStorage.removeItem('tessellate.panels'));
  await page.evaluate(() => openSettingsModal('models'));
  await page.waitForTimeout(900);
  const box = () => page.evaluate(() => { const p = panelOf(document.getElementById('settings-modal').querySelector('.dialog-head')); const b = p.getBoundingClientRect(); return { l: Math.round(b.left), t: Math.round(b.top), r: Math.round(b.right), b: Math.round(b.bottom), rim: p.dataset.rim || '', cur: getComputedStyle(p).cursor }; });
  let b = await box();
  await page.mouse.move((b.l + b.r) / 2, (b.t + 30)); await page.waitForTimeout(150);
  b = await box();
  const out = [];
  const ALL = { w: [b.l + 2, (b.t + b.b) / 2, -60, 0], e: [b.r - 2, (b.t + b.b) / 2, -50, 0], n: [(b.l + b.r) / 2, b.t + 2, 0, 40], s: [(b.l + b.r) / 2, b.b - 2, 0, -40], nw: [b.l + 2, b.t + 2, 30, 30], se: [b.r - 2, b.b - 2, -20, -20] };
  const edges = process.env.ONLY ? Object.fromEntries(process.env.ONLY.split(',').map((k) => [k, ALL[k]])) : ALL;
  for (const [edge, [x, y, ddx, ddy]] of Object.entries(edges)) {
    const a = await box();
    const px = edge.includes('w') ? a.l + 2 : edge.includes('e') ? a.r - 2 : (a.l + a.r) / 2;
    const py = edge.includes('n') ? a.t + 2 : edge.includes('s') ? a.b - 2 : (a.t + a.b) / 2;
    await page.mouse.move(px - (edge.includes('w') ? -20 : edge.includes('e') ? 20 : 0), py - (edge.includes('n') ? -20 : edge.includes('s') ? 20 : 0));
    await page.mouse.move(px, py, { steps: 3 }); await page.waitForTimeout(80);
    const h = await box();
    await page.mouse.down(); await page.mouse.move(px + ddx, py + ddy, { steps: 6 }); await page.mouse.up(); await page.waitForTimeout(120);
    const z = await box();
    out.push(`${edge}: hover rim=${h.rim} cursor=${h.cur} | l ${a.l}->${z.l} t ${a.t}->${z.t} r ${a.r}->${z.r} b ${a.b}->${z.b}`);
  }
  console.log(out.join('\n'));
  await browser.close();
})();
