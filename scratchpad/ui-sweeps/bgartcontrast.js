// Does the background art cost the text any contrast? `contrast.js` reads
// computed colours and stops at the first non-transparent background, so it
// cannot see the art through glass at all. This measures pixels instead:
// every visible text element's colour, against the real rendered pixels
// behind it with the art on, taken from a screenshot with all text made
// transparent (so the glyphs are not their own background). For each
// element the worst sample under its box is kept, and the sweep reports, per
// style and theme, how many elements fall under WCAG AA (4.5:1, or 3:1 for
// large text) and the lowest ratio, beside the same numbers with the art off.
//
//   BASE=http://127.0.0.1:8797 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node scratchpad/ui-sweeps/bgartcontrast.js
//
// STYLES, THEMES and INTENSITY (default 45, the app's default; 100 is the
// slider's top) narrow it; TAB picks the tab (default dashboard).
const { chromium } = require('playwright');

const PW = 'testpassword123';
const BASE = process.env.BASE || 'http://127.0.0.1:8797';
const STYLES = (process.env.STYLES || 'off,aurora,constellation,waves,bubbles,mesh,microbes,mycelium').split(',');
const THEMES = (process.env.THEMES || 'light,dark').split(',');
const INTENSITY = process.env.INTENSITY || '45';
const TAB = process.env.TAB || 'dashboard';
// The art moves, so one moment can flatter or wrong it: SNAPS captures a
// second apart, and the report is the total of failures over all of them
// and the lowest ratio seen in any.
const SNAPS = Number(process.env.SNAPS || 3);

async function boot(browser, prefs) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  await ctx.addInitScript((p) => {
    try {
      localStorage.setItem('onboardingDone', '1');
      localStorage.setItem('tourDone', '1');
      for (const [k, v] of Object.entries(p)) localStorage.setItem(k, v);
    } catch (e) { /* private window */ }
  }, prefs);
  const page = await ctx.newPage();
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#lock-password', { state: 'visible', timeout: 20000 });
  await page.fill('#lock-password', PW);
  await page.click('#lock-submit');
  await page.waitForTimeout(3000);
  await page.evaluate((tab) => {
    const o = document.getElementById('onboarding-overlay');
    if (o) o.classList.add('hidden');
    if (typeof switchTab === 'function') switchTab(tab);
  }, TAB);
  await page.waitForTimeout(2000);
  return { ctx, page };
}

async function measure(page) {
  // Text elements: anything visible with its own text node.
  const texts = await page.evaluate(() => {
    const out = [];
    for (const el of document.querySelectorAll('body *')) {
      if (el.closest('.bg-art-canvas')) continue;
      const own = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
      if (!own) continue;
      const cs = getComputedStyle(el);
      if (cs.visibility === 'hidden' || cs.display === 'none' || Number(cs.opacity) === 0) continue;
      const r = el.getBoundingClientRect();
      if (r.width < 4 || r.height < 4 || r.bottom < 0 || r.top > innerHeight || r.right < 0 || r.left > innerWidth) continue;
      const m = /rgba?\(([^)]*)\)/.exec(cs.color);
      if (!m) continue;
      const [cr, cg, cb, ca = '1'] = m[1].split(/[\s,/]+/).filter(Boolean);
      if (Number(ca) < 0.5) continue;
      const size = parseFloat(cs.fontSize), weight = Number(cs.fontWeight) || 400;
      out.push({
        r: [r.left, r.top, r.width, r.height], c: [Number(cr), Number(cg), Number(cb)],
        large: size >= 24 || (size >= 18.66 && weight >= 700),
        name: `${el.tagName.toLowerCase()}${el.id ? '#' + el.id : ''}${el.classList[0] ? '.' + el.classList[0] : ''} "${el.textContent.trim().slice(0, 30)}"`,
      });
      el.dataset.bgcText = el.style.color || '-';
      el.style.color = 'transparent';
    }
    return out;
  });
  await page.waitForTimeout(150);
  const shot = await page.screenshot();
  await page.evaluate(() => {
    for (const el of document.querySelectorAll('[data-bgc-text]')) {
      el.style.color = el.dataset.bgcText === '-' ? '' : el.dataset.bgcText;
      delete el.dataset.bgcText;
    }
  });
  return page.evaluate(async ({ png, texts }) => {
    const img = new Image();
    img.src = 'data:image/png;base64,' + png;
    await img.decode();
    const c = document.createElement('canvas');
    c.width = img.width; c.height = img.height;
    const g = c.getContext('2d', { willReadFrequently: true });
    g.drawImage(img, 0, 0);
    const lum = (r, gg, b) => {
      const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
      return 0.2126 * f(r) + 0.7152 * f(gg) + 0.0722 * f(b);
    };
    let fails = 0, min = 99;
    const failed = [];
    const ratios = [];
    for (const t of texts) {
      const [x, y, w, h] = t.r;
      const L = lum(...t.c);
      let worst = 99;
      for (let i = 0; i < 5; i++) {
        for (let j = 0; j < 3; j++) {
          const px = Math.min(c.width - 1, Math.max(0, Math.round(x + (w * (i + 0.5)) / 5)));
          const py = Math.min(c.height - 1, Math.max(0, Math.round(y + (h * (j + 0.5)) / 3)));
          const d = g.getImageData(px, py, 1, 1).data;
          const B = lum(d[0], d[1], d[2]);
          const ratio = (Math.max(L, B) + 0.05) / (Math.min(L, B) + 0.05);
          if (ratio < worst) worst = ratio;
        }
      }
      ratios.push(worst);
      if (worst < (t.large ? 3 : 4.5)) { fails++; failed.push(`${t.name} ${worst.toFixed(2)}`); }
      if (worst < min) min = worst;
    }
    ratios.sort((a, b) => a - b);
    return { n: texts.length, fails, failed, min: +min.toFixed(2), median: +ratios[Math.floor(ratios.length / 2)].toFixed(2) };
  }, { png: shot.toString('base64'), texts });
}

(async () => {
  const browser = await chromium.launch();
  for (const theme of THEMES) {
    for (const style of STYLES) {
      const prefs = style === 'off'
        ? { theme, bgArt: 'off' }
        : { theme, bgArt: 'on', 'bg-style': style, 'bg-motion': 'moving', 'bg-intensity': INTENSITY };
      const { ctx, page } = await boot(browser, prefs);
      let fails = 0, min = 99, n = 0;
      const failed = new Map();
      for (let k = 0; k < SNAPS; k++) {
        if (k) await page.waitForTimeout(1000);
        const r = await measure(page);
        fails += r.fails; n = r.n;
        if (r.min < min) min = r.min;
        for (const f of r.failed) failed.set(f.replace(/ [\d.]+$/, ''), f);
      }
      console.log(`${theme.padEnd(5)} ${style.padEnd(13)} ${n} text elements x ${SNAPS}: ${fails} under AA, lowest ${min}:1`);
      if (process.env.DETAIL) for (const f of failed.values()) console.log(`      ${f}`);
      await ctx.close();
    }
  }
  await browser.close();
})();
