// Does a cheaper background style look the same? A frame of each style at a
// fixed seed, before and after, compared pixel by pixel (INBOX 1436, the
// cheaper-equivalent pass: each change must differ by under 2 percent).
//
// "Before" is a copy of bg-art.js (BEFORE_JS, e.g. `git show <rev>:frontend/js/bg-art.js`),
// "after" is the file the server serves. Both run the real runtime
// (`bgArtRun`) in a page: Math.random and the shared noise table are seeded,
// requestAnimationFrame is driven by hand at 60 ticks a second for SIM_SECONDS
// of art time (so a style that now draws at 15 fps is compared at the same
// moment as one that drew at 30), and the canvas is read back, scaled to
// 360x225 (styles at different pixel densities compare at one size).
//
// The figure is the share of pixels in which any channel differs by more than
// 16 of 255 (the gate is 2 percent), and the mean channel difference as a
// share of 255. The page's own look is not in the picture: only the art canvas.
//
//   BASE=http://127.0.0.1:8806 BEFORE_JS=/path/old-bg-art.js \
//     PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/bgartdiff.js
//
// STYLES and THEMES narrow it; SIM_SECONDS defaults to 6. With no BEFORE_JS it
// compares the served file with itself (a determinism check: must be 0).
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const fs = require('fs');

const BASE = process.env.BASE || 'http://127.0.0.1:8806';
const STYLES = (process.env.STYLES || 'aurora,constellation,waves,bubbles,mesh,microbes,mycelium,dusk,ripples,fireflies,rain,wander,drift').split(',');
const THEMES = (process.env.THEMES || 'light,dark').split(',');
const SIM = Number(process.env.SIM_SECONDS || 6);
const OUT_W = 360, OUT_H = 225;

async function open(browser, js, theme) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  await ctx.addInitScript((t) => {
    try {
      localStorage.setItem('onboardingDone', '1');
      localStorage.setItem('ui-synced', '{}');
      localStorage.setItem('theme', t);
      localStorage.setItem('bgArt', 'off');
      Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
      Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
    } catch (e) { /* the page copes */ }
    // Art callbacks are held back for the harness; the app's own go through.
    const raf = window.requestAnimationFrame.bind(window);
    window.__artQueue = [];
    window.requestAnimationFrame = (cb) => {
      if (/bg-art\.js/.test(new Error().stack || '')) { window.__artQueue.push(cb); return window.__artQueue.length; }
      return raf(cb);
    };
    window.cancelAnimationFrame = ((orig) => (id) => {
      if (id && window.__artQueue[id - 1]) window.__artQueue[id - 1] = null; else orig(id);
    })(window.cancelAnimationFrame.bind(window));
  }, theme);
  if (js) {
    const body = fs.readFileSync(js, 'utf8');
    await ctx.route('**/bg-art.js*', (route) => route.fulfill({ body, contentType: 'application/javascript' }));
  }
  const page = await ctx.newPage();
  page.on('pageerror', (e) => console.log('  pageerror', String(e)));
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#lock-password', { state: 'visible', timeout: 20000 });
  await page.fill('#lock-password', 'testpassword123');
  await page.click('#lock-submit');
  await page.waitForTimeout(3000);
  await page.evaluate(() => ensureModule('bgArt'));
  return { ctx, page };
}

function render(page, style, theme, sim) {
  return page.evaluate(({ style, dark, sim, W, H }) => {
    // mulberry32, so every run draws the same thing.
    let s = 12345;
    Math.random = () => { s = (s + 0x6d2b79f5) | 0; let t = Math.imul(s ^ (s >>> 15), 1 | s); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
    for (let i = 0; i < BG_FLOW.length; i++) BG_FLOW[i] = Math.random();
    bgArtRun({ style, dark, accent: '#4664f0', density: 0.9, seedText: 'Brayden', still: false, requested: true, restart: null });
    // Drive the art's loop by hand: 60 ticks a second of art time.
    const q = window.__artQueue;
    let now = 1000;
    const ticks = Math.round(sim * 60);
    for (let i = 0; i < ticks; i++) {
      now += 1000 / 60;
      const batch = q.splice(0, q.length);
      for (const cb of batch) if (cb) cb(now);
    }
    const src = document.getElementById('bg-art-canvas');
    const out = document.createElement('canvas');
    out.width = W; out.height = H;
    const g = out.getContext('2d', { willReadFrequently: true });
    for (const el of [src, document.getElementById('bg-art-twin')]) {
      if (!el) continue;
      const k = /\* ([\d.]+)\)$/.exec(el.style.opacity);
      g.globalAlpha = k ? Number(k[1]) : 1;
      g.drawImage(el, 0, 0, W, H);
    }
    const d = g.getImageData(0, 0, W, H).data;
    let bin = '';
    for (let i = 0; i < d.length; i += 4096) bin += String.fromCharCode.apply(null, d.subarray(i, i + 4096));
    const info = { w: src.width, h: src.height };
    bgArtHalt();
    return { b64: btoa(bin), info };
  }, { style, dark: theme === 'dark', sim, W: OUT_W, H: OUT_H });
}

(async () => {
  const browser = await chromium.launch();
  const rows = [];
  let failed = 0;
  for (const theme of THEMES) {
    const before = await open(browser, process.env.BEFORE_JS || '', theme);
    const after = await open(browser, '', theme);
    for (const style of STYLES) {
      let a, b;
      try {
        a = await render(before.page, style, theme, SIM);
        b = await render(after.page, style, theme, SIM);
      } catch (e) { console.log(`${theme} ${style}: ${String(e).slice(0, 120)}`); continue; }
      const A = Buffer.from(a.b64, 'base64'), B = Buffer.from(b.b64, 'base64');
      let changed = 0, sum = 0;
      for (let i = 0; i < A.length; i += 4) {
        let m = 0;
        for (let c = 0; c < 4; c++) { const d = Math.abs(A[i + c] - B[i + c]); sum += d; if (d > m) m = d; }
        if (m > 16) changed++;
      }
      const pct = (100 * changed) / (A.length / 4);
      const mean = (100 * sum) / (A.length * 255);
      const ok = pct < 2;
      if (!ok) failed++;
      console.log(`${theme.padEnd(5)} ${style.padEnd(13)} changed ${pct.toFixed(2)}% mean ${mean.toFixed(2)}% canvas ${a.info.w}x${a.info.h} -> ${b.info.w}x${b.info.h} ${ok ? 'ok' : 'FAIL'}`);
    }
    await before.ctx.close();
    await after.ctx.close();
  }
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
