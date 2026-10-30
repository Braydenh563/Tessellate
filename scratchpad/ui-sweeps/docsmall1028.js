// Audit 1028 U29, U33, U36, U37: the Documents empty state's New buttons, the
// new-document prompt, and label contrast in dark.
//   BASE=http://127.0.0.1:8791 THEME=dark node docsmall1028.js
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const ev = (fn, a) => page.evaluate(fn, a);
  await ev(() => switchTab('documents')); await page.waitForTimeout(1500);
  const out = await ev(() => {
    const lum = (c) => { const m = c.match(/[\d.]+/g).map(Number); const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(m[0]) + 0.7152 * f(m[1]) + 0.0722 * f(m[2]); };
    const bgOf = (el) => { for (let n = el; n; n = n.parentElement) { const b = getComputedStyle(n).backgroundColor; if (!/rgba\(0, 0, 0, 0\)|transparent/.test(b) && !/, 0\)$/.test(b)) return b; } return 'rgb(0,0,0)'; };
    const ratio = (el) => { if (!el) return null; const a = lum(getComputedStyle(el).color), b = lum(bgOf(el)); const op = getComputedStyle(el).opacity; return [((Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)).toFixed(2), op, getComputedStyle(el).color, bgOf(el)]; };
    const news = [...document.querySelectorAll('#tab-documents button')].filter((b) => /new document/i.test(b.textContent + (b.getAttribute('aria-label') || '')) && b.offsetParent).map((b) => [b.id, b.className, Math.round(b.getBoundingClientRect().height), b.textContent.trim()]);
    return { news, ai: ratio(document.querySelector('.doc-ai-label')) };
  });
  console.log(JSON.stringify(out));
  await browser.close();
})();
