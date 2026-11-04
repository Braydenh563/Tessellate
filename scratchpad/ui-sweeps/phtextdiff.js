// INBOX 1646: which .ph-text labels change (height, clipped) with the ellipsis rule on vs off, per tab.
const { boot } = require('./lib.js');
const TABS = ['dashboard', 'notes', 'library', 'graph', 'timeline', 'reminders', 'chat', 'whiteboard', 'documents'];
(async () => {
  for (const [w, h] of [[1440, 900], [390, 844]]) {
    const { browser, page } = await boot({ viewport: { width: w, height: h } });
    for (const tab of TABS) {
      try { await page.evaluate((t) => revealTab(t), tab); } catch { continue; }
      await page.waitForTimeout(1200);
      const snap = () => page.evaluate(() => [...document.querySelectorAll('.ph-text')].filter((t) => t.getClientRects().length).map((t) => ({ k: (t.parentElement.id || t.parentElement.className || '').toString().slice(0, 50) + ':' + t.textContent.slice(0, 24), h: Math.round(t.getBoundingClientRect().height), c: t.scrollWidth > t.clientWidth + 1 })));
      const on = await snap();
      await page.evaluate(() => { const sh = [...document.styleSheets].find((x) => { try { return x.cssRules; } catch { return false; } }); window.__ri = sh.insertRule('.ph-text{min-width:auto!important;overflow:visible!important}', sh.cssRules.length); window.__sh = sh; });
      await page.waitForTimeout(100);
      const off = await snap();
      await page.evaluate(() => window.__sh.deleteRule(window.__ri));
      const diffs = on.map((a, i) => [a, off[i]]).filter(([a, b]) => b && (a.h !== b.h || a.c));
      console.log(`${w} ${tab}: ${on.length} labels, ${diffs.length} differ`, diffs.slice(0, 6).map(([a, b]) => `${a.k} h ${b.h}->${a.h}${a.c ? ' clipped' : ''}`).join(' | '));
    }
    await browser.close();
  }
})();
