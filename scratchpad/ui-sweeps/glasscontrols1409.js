// INBOX 1409: Settings, Appearance, Glass controls. Counts the icon buttons
// that take the glass chip look in four states: switch off, on with glass on,
// on with glass off, and the lazy sheet's presence.
//   BASE=http://127.0.0.1:8789 node scratchpad/ui-sweeps/glasscontrols1409.js
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1280, height: 720 } });
  await page.waitForTimeout(1500);
  const count = () => page.evaluate(() => {
    const all = [...document.querySelectorAll('button.ghost.icon-only')].filter((b) => b.offsetParent);
    const glass = all.filter((b) => getComputedStyle(b).backdropFilter !== 'none');
    const sheet = [...document.styleSheets].some((s) => (s.href || '').includes('glass-controls-lazy'));
    return { visibleIconButtons: all.length, withBlur: glass.length, sheet, glass: document.documentElement.dataset.glass, controls: document.documentElement.dataset.glassControls };
  });
  await page.evaluate(() => { prefs.set('perf', 'off'); prefs.set('glass', 'on'); prefs.set('glass-controls', 'off'); applyAppearance(); });
  await page.waitForTimeout(500);
  const out = { off: await count() };
  await page.evaluate(() => { prefs.set('glass-controls', 'on'); applyAppearance(); });
  await page.waitForTimeout(1200);
  out.on = await count();
  await page.evaluate(() => { prefs.set('glass', 'off'); applyAppearance(); });
  await page.waitForTimeout(500);
  out.glassOff = await count();
  await page.evaluate(() => { prefs.set('glass', 'on'); applyAppearance(); });
  const row = await page.evaluate(() => { const r = document.getElementById('glass-controls-row'); return { exists: !!r, checked: document.getElementById('glass-controls-toggle').checked }; });
  out.row = row;
  console.log(JSON.stringify(out));
  await browser.close();
})();
