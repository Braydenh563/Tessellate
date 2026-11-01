// INBOX 1517: ten small drags, layout metrics after each release. Env: DIST (px of mouse travel), N (drags), BASE, SCRATCH, THEME.
const { boot } = require('./lib.js');
const N = +(process.env.N || 10), DIST = +(process.env.DIST || 30);
const METRICS = () => {
  const s = gcTab, nodes = s.nodes.filter((n) => Number.isFinite(n.x));
  let cx = 0, cy = 0; for (const n of nodes) { cx += n.x; cy += n.y; } cx /= nodes.length; cy /= nodes.length;
  let spread = 0, minx = 1e9, maxx = -1e9, miny = 1e9, maxy = -1e9;
  for (const n of nodes) { spread += Math.hypot(n.x - cx, n.y - cy); minx = Math.min(minx, n.x); maxx = Math.max(maxx, n.x); miny = Math.min(miny, n.y); maxy = Math.max(maxy, n.y); }
  let link = 0, k = 0; for (const e of s.edges) { const a = e.source, b = e.target; if (a && b && Number.isFinite(a.x) && Number.isFinite(b.x)) { link += Math.hypot(a.x - b.x, a.y - b.y); k++; } }
  // mean nearest-neighbour distance: "all really close together"
  let nn = 0; for (const a of nodes) { let m = 1e9; for (const b of nodes) if (a !== b) m = Math.min(m, Math.hypot(a.x - b.x, a.y - b.y)); nn += m; }
  const gs = new Map(); for (const n of nodes) { if (!gs.has(n.group)) gs.set(n.group, []); gs.get(n.group).push(n); } let gsum = 0, gk = 0; for (const l of gs.values()) { if (l.length < 3) continue; const mx = l.reduce((a, n) => a + n.x, 0) / l.length, my = l.reduce((a, n) => a + n.y, 0) / l.length; for (const n of l) { gsum += Math.hypot(n.x - mx, n.y - my); gk++; } }
  return { grp: +(gsum / (gk || 1)).toFixed(1), n: nodes.length, link: +(link / (k || 1)).toFixed(1), spread: +(spread / nodes.length).toFixed(1), bbox: Math.round(maxx - minx) + 'x' + Math.round(maxy - miny), nn: +(nn / nodes.length).toFixed(1), k: +s.transform.k.toFixed(3) };
};
(async () => {
  const { browser, page } = await boot({ serviceWorkers: 'block' });
  await page.evaluate(() => switchTab('graph'));
  await page.waitForFunction(() => gcTab.nodes.length > 0, null, { timeout: 60000 });
  await page.waitForFunction(() => !gcTab.layoutRunning && gcTab.settledSig && gcTab.settledSig === gcTab.layoutSig, null, { timeout: 90000, polling: 200 }).catch(() => console.log('settle-wait1'));
  await page.waitForTimeout(2500);
  const rows = [await page.evaluate(METRICS)];
  console.log('start', JSON.stringify(rows[0]));
  for (let d = 1; d <= N; d++) {
    // the node nearest the middle of the canvas that is not pinned, as a person would grab it
    const at = await page.evaluate((d) => { const s = gcTab, t = s.transform; const box = document.querySelector('#graph-canvas').getBoundingClientRect(); const nodes = s.nodes.filter((n) => Number.isFinite(n.x)); const pick = nodes[(d * 7) % nodes.length]; return { id: pick.id, x: box.left + pick.x * t.k + t.x, y: box.top + pick.y * t.k + t.y }; }, d);
    await page.mouse.move(at.x, at.y); await page.mouse.down();
    const dx = (d % 2 ? 1 : -1) * DIST, dy = (d % 3 ? 1 : -1) * DIST / 2;
    for (let i = 1; i <= 6; i++) { await page.mouse.move(at.x + dx * i / 6, at.y + dy * i / 6); await page.waitForTimeout(30); }
    await page.mouse.up();
    await page.waitForTimeout(500);
    await page.waitForFunction(() => !gcTab.layoutRunning, null, { timeout: 60000, polling: 100 }).catch(() => console.log('settle-wait', d));
    await page.waitForTimeout(500);
    const m = await page.evaluate(METRICS); rows.push(m);
    console.log('drag', d, JSON.stringify(m));
  }
  const a = rows[0], z = rows[rows.length - 1];
  console.log('SUMMARY link', a.link, '->', z.link, 'spread', a.spread, '->', z.spread, 'nn', a.nn, '->', z.nn);
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
