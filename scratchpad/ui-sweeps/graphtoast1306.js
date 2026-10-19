// INBOX 1306: a toast shown over the Graph tab. Measures the toast's own
// background alpha, its text contrast, and its overlap with the legend row,
// the zoom strip, the minimap and the dock. THEME=dark for dark.
//   BASE=http://127.0.0.1:8797 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/graphtoast1306.js
const { boot } = require('./lib.js');
(async () => {
  const W = Number(process.env.W || 1440), H = Number(process.env.H || 900);
  const { browser, page } = await boot({ viewport: { width: W, height: H } });
  await page.evaluate(() => switchTab('graph'));
  await page.waitForTimeout(5000);
  await page.evaluate(() => { document.querySelectorAll('dialog[open] button, .modal-overlay:not(.hidden) .ghost').forEach((b) => /don.t check|not now|close/i.test(b.textContent) && b.click()); });
  // The options panel is remembered open; shut it so only the map is under the toast.
  await page.evaluate(() => { if (!document.getElementById('graph-options').classList.contains('hidden')) document.getElementById('graph-options-toggle').click(); });
  if (process.env.GLASSOP) await page.evaluate((v) => document.documentElement.style.setProperty('--glass-opacity', v), process.env.GLASSOP);
  await page.evaluate(() => toastAction('Map settings reset to defaults.', 'Undo', () => {}));
  await page.waitForTimeout(900);
  const r = await page.evaluate(() => {
    const box = (sel) => { const e = document.querySelector(sel); if (!e || !e.offsetParent && getComputedStyle(e).position !== 'fixed') return null; const b = e.getBoundingClientRect(); return b.width ? { l: b.left, t: b.top, r: b.right, b: b.bottom } : null; };
    const toast = document.querySelector('#toast-box > .toast:last-child');
    const cs = getComputedStyle(toast);
    const tb = toast.getBoundingClientRect();
    const T = { l: tb.left, t: tb.top, r: tb.right, b: tb.bottom };
    const hit = (o) => o && o.l < T.r && o.r > T.l && o.t < T.b && o.b > T.t;
    const names = { legend: '.graph-legend-row', legendInner: '#graph-legend', zoom: '.graph-zoom', minimap: '#graph-minimap', dock: '[data-dock-name="graph"]' };
    const ov = {};
    for (const [k, s] of Object.entries(names)) { const o = box(s); ov[k] = o ? (hit(o) ? 'OVERLAP' : 'clear') : 'absent'; if (o) ov[k + 'Box'] = [o.l, o.t, o.r, o.b].map(Math.round); }
    return { bg: cs.backgroundColor, color: cs.color, blur: cs.backdropFilter, opacity: cs.opacity, box: [T.l, T.t, T.r, T.b].map(Math.round), z: cs.zIndex, ov, glass: document.documentElement.getAttribute('data-glass') };
  });
  console.log(JSON.stringify(r));
  await page.screenshot({ path: (process.env.SCRATCH || '.') + `/shots/toast1306-${process.env.THEME || 'light'}.png`, clip: { x: W - 700, y: H - 260, width: 700, height: 260 } });
  await browser.close();
})();
