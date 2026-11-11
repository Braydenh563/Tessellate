// WCAG 2.2 2.4.11 and 2.4.13 (Phase 12 decision 4): Tab through each tab and,
// for every focused control, read its focus indicator (outline or box-shadow
// ring) and the contrast of the ring's colour against the nearest opaque
// ground behind the control. Bar: every stop has a ring at least 2px wide at
// 3:1 or more.   BASE=... [THEME=dark] [TABS=notes,chat] [STOPS=40] node focusring.js
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const STOPS = +(process.env.STOPS || 40);
  // The ring's colour transitions in (0.12s): read at the start of it, every
  // stop looked ringless. A constructed sheet, since the CSP refuses <style>.
  await page.evaluate(() => {
    const sheet = new CSSStyleSheet();
    sheet.replaceSync('*, *::before, *::after { transition: none !important; }');
    document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet];
  });
  let total = 0, weak = [], none = [], min = 99;
  for (const tab of (process.env.TABS || 'dashboard,notes,chat,library,timeline,reminders,graph,documents').split(',')) {
    await page.evaluate((t) => switchTab(t), tab); await page.waitForTimeout(1200);
    await page.evaluate(() => document.activeElement && document.activeElement.blur());
    await page.mouse.click(720, 2);
    for (let i = 0; i < STOPS; i++) {
      await page.keyboard.press('Tab');
      const r = await page.evaluate(() => {
        const e = document.activeElement; if (!e || e === document.body) return null;
        const cv = document.createElement('canvas').getContext('2d');
        const rgba = (c) => { cv.clearRect(0, 0, 1, 1); cv.fillStyle = '#000'; cv.fillStyle = c; cv.fillRect(0, 0, 1, 1); return [...cv.getImageData(0, 0, 1, 1).data]; };
        const lum = (a) => { const v = a.slice(0, 3).map((x) => { x /= 255; return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); }); return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]; };
        let ground = null;
        for (let x = e.parentElement; x; x = x.parentElement) { const c = getComputedStyle(x).backgroundColor; const a = rgba(c); if (a[3] > 250) { ground = a; break; } }
        ground = ground || rgba(getComputedStyle(document.documentElement).backgroundColor);
        //: A search field's input is ringed by its field (`.search-field:
        //: focus-within`, an outline over an accent border).
        //: A card's title takes the focus but the card wears the ring (`:has()`, 08-consistency.css).
        const host = e.closest('.search-field:focus-within') || (e.classList.contains('card-open') && e.closest('.library-card, .doc-list-item')) || e;
        const s = getComputedStyle(host);
        let ring = null, w = 0;
        if (s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0 && rgba(s.outlineColor)[3] > 0) { ring = s.outlineColor; w = parseFloat(s.outlineWidth) + (host !== e && s.borderTopColor === s.outlineColor ? parseFloat(s.borderTopWidth) : 0); }
        else { const m = s.boxShadow.match(/(rgba?\([^)]*\)|color\([^)]*\)|#[0-9a-f]+)[^,]*?(\d+(?:\.\d+)?)px(?:\s|$)/); if (s.boxShadow !== 'none' && !/inset/.test(s.boxShadow) && m) { ring = m[1]; w = 2; } }
        const id = (e.id ? '#' + e.id : e.tagName.toLowerCase()) + '.' + [...e.classList].slice(0, 2).join('.') + (e.matches(':focus-visible') ? '' : ' (not :focus-visible)') + ' ' + s.outlineStyle + ' ' + s.outlineColor;
        if (!ring) return { id, cr: 0, w: 0 };
        const a = lum(rgba(ring)), b = lum(ground);
        return { id, w, g: ground.join(','), ring, cr: Math.round(((Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)) * 100) / 100 };
      });
      if (!r) continue;
      total++;
      if (!r.w) none.push(tab + ' ' + r.id); else { min = Math.min(min, r.cr); if (r.cr < 3 || r.w < 2) weak.push(`${tab} ${r.id} ${r.w}px ${r.cr}:1 ring ${r.ring} on ${r.g}`); }
    }
  }
  console.log(`${total} focus stops; ${none.length} without a ring; ${weak.length} under 2px or 3:1; min ${min}:1`);
  for (const x of [...new Set(none)].slice(0, 12)) console.log('  none ' + x);
  for (const x of [...new Set(weak)].slice(0, 12)) console.log('  weak ' + x);
  await browser.close();
})();
