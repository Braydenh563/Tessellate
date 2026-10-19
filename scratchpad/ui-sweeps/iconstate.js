// INBOX 904 B58 (second half): every standalone icon-only toggle (aria-pressed,
// no pressed siblings) is pressed once; the icon (class, or the button's fill
// class) must change. Lists those whose icon class stays the same.
//   BASE=http://127.0.0.1:8793 node scratchpad/ui-sweeps/iconstate.js
const { boot } = require('./lib.js');
const TABS = ['notes', 'dashboard', 'chat', 'graph', 'library', 'documents', 'timeline', 'reminders', 'settings:appearance', 'settings:models', 'settings:privacy', 'settings:system'];
(async () => {
  const { browser, page } = await boot({});
  const seen = new Set(); const same = []; let tested = 0, changed = 0;
  for (const tab of TABS) {
    if (tab.startsWith('settings')) { await page.evaluate((p) => openSettingsModal(p), tab.split(':')[1]); }
    else { await page.evaluate((t) => { closeSettingsModal?.(); switchTab(t); }, tab); }
    await page.waitForTimeout(1500);
    const n = await page.evaluate(() => {
      let i = 0; window.__t = [];
      for (const b of document.querySelectorAll('button[aria-pressed]')) {
        if (b.disabled) continue;
        const sibs = [...b.parentElement.children].filter((c) => c !== b && c.hasAttribute('aria-pressed'));
        if (sibs.length) continue; // a segmented choice keeps its icons
        if (b.textContent.trim().length > 1 || !b.querySelector('i.ph')) continue;
        window.__t.push(b); b.setAttribute('data-ts', i++);
      }
      return i;
    });
    for (let k = 0; k < n; k++) {
      const info = await page.evaluate((k) => {
        const b = window.__t[k]; if (!b || !b.isConnected) return null;
        return { id: b.id || b.getAttribute('aria-label') || b.title || b.className, icon: b.querySelector('i.ph').className, cls: b.className, bg: getComputedStyle(b).backgroundColor, ttl: b.title };
      }, k);
      if (!info) continue;
      const key = info.id; if (seen.has(key)) continue; seen.add(key);
      try { await page.evaluate((k) => window.__t[k].click(), k); } catch (e) { continue; }
      await page.waitForTimeout(250);
      const after = await page.evaluate((k) => {
        const b = window.__t[k]; if (!b || !b.isConnected) return null; const i = b.querySelector('i.ph');
        return i ? { icon: i.className, cls: b.className, bg: getComputedStyle(b).backgroundColor, ttl: b.title } : null; }, k);
      if (after === null) continue;
      tested++;
      if (after.icon === info.icon && after.cls === info.cls && after.bg === info.bg && after.ttl === info.ttl) same.push(key + ' [' + info.icon + ']'); else changed++;
      await page.evaluate((k) => { const b = window.__t[k]; if (b && b.isConnected) b.click(); }, k); // restore
      await page.waitForTimeout(150);
    }
  }
  console.log(JSON.stringify({ tested, changed, same_count: same.length, same }, null, 1));
  await browser.close();
})();
