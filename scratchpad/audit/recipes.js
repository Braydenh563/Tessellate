// Distinct control recipes per tab at 1440x900 (COARSE=1: kind, radius class, ground, edge; V=1 lists them).
// The radius class is the largest corner: a split button's caret keeps only its outer corners (DESIGN.md), and read by
// its top-left alone it counted as a square recipe of its own (L-world-class-250).
// Rebuilt 2026-11-14 (L-world-class-62): the original was not in the tree. BASE=http://127.0.0.1:PORT, THEME=dark.
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const BASE = process.env.BASE || 'http://127.0.0.1:8801';
const W = +(process.env.W || 1440);
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: W, height: 900 } });
  const page = await ctx.newPage();
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#lock-password', { state: 'visible', timeout: 20000 });
  await page.fill('#lock-password', 'testpassword123'); await page.click('#lock-submit');
  await page.waitForTimeout(3000);
  if (await page.isVisible('#lock-password').catch(() => false)) { await page.fill('#lock-password', 'testpassword123'); await page.click('#lock-submit'); await page.waitForTimeout(3000); }
  await page.evaluate((t) => { if (document.documentElement.dataset.theme !== t && typeof applyThemeChoice === 'function') applyThemeChoice(t); }, process.env.THEME || 'light');
  await page.evaluate(() => { const o = document.getElementById('onboarding-overlay'); if (o) o.classList.add('hidden'); });
  await page.waitForTimeout(800);
  for (const tab of ['dashboard', 'notes', 'chat', 'graph', 'library', 'timeline', 'reminders']) {
    await page.evaluate((t) => document.getElementById('tab-btn-' + t).click(), tab);
    await page.waitForTimeout(1800);
    const r = await page.evaluate(([tab, COARSE]) => {
      const root = document.getElementById('tab-' + tab);
      const sigs = new Map();
      const sel = 'button, input:not([type=hidden]), select, textarea, [role=button], [role=tab], a[href]';
      const els = [...root.querySelectorAll(sel), ...document.querySelectorAll('#top-bar ' + sel.split(', ').join(', #top-bar '))];
      for (const e of els) {
        const b = e.getBoundingClientRect();
        if (b.width < 12 || b.height < 12 || e.type === 'file') continue;
        const cs = getComputedStyle(e);
        if (cs.visibility === 'hidden' || cs.display === 'none') continue;
        const kind = e.tagName === 'BUTTON' || e.getAttribute('role') === 'button' || e.getAttribute('role') === 'tab' ? 'btn' : e.tagName.toLowerCase() + (e.type ? ':' + (['checkbox', 'radio', 'range'].includes(e.type) ? e.type : 'text') : '');
        const bg = cs.backgroundColor === 'rgba(0, 0, 0, 0)' ? 'none' : 'fill';
        const edge = parseFloat(cs.borderTopWidth) > 0 && cs.borderTopStyle !== 'none' ? 'edge' : 'noedge';
        const rad = Math.max(...['TopLeft', 'TopRight', 'BottomRight', 'BottomLeft'].map((c) => parseFloat(cs['border' + c + 'Radius']) || 0)); const sig = COARSE ? [kind, rad >= 100 ? 'pill' : rad > 0 ? 'rounded' : 'square', bg, edge].join('|') : [kind, Math.round(b.height / 4) * 4, Math.round(rad), bg, edge, cs.fontSize, cs.fontWeight].join('|');
        const s = sigs.get(sig) || { n: 0, ex: (e.id || e.className || e.tagName).toString().slice(0, 40) };
        s.n++; sigs.set(sig, s);
      }
      return { n: sigs.size, rows: [...sigs.entries()].map(([k, v]) => `${v.n}\t${k}\t${v.ex}`) };
    }, [tab, !!process.env.COARSE]);
    console.log(tab, 'recipes:', r.n);
    if (process.env.V) console.log(r.rows.join('\n'));
  }
  await browser.close();
})();
