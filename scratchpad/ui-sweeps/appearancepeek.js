// Appearance panel at rest and on Peek (L-ui-modernisation-46): the share of
// the window's area the panel covers at five sizes, and each visible label's ink
// against the pixels behind it, read from two screenshots (text on, text
// transparent) so a translucent ground over app content is measured as drawn.
// Ratio: the label's computed ink against the ground pixels under its glyphs,
// the 10th percentile (the worst tenth of the ground it is drawn on).
// THEME=dark. Prints "size" lines and one "rest"/"peek" line each.
const {boot} = require('./lib.js');
const {execFileSync} = require('child_process');
const path = require('path');
const SHOT = path.join(require('os').tmpdir(), 'appearancepeek.png');
const PX = `import sys,json\nsys.path.insert(0, ${JSON.stringify(path.join(__dirname, '..'))})\nfrom pngpixel import read_png\nw,h,rows=read_png(sys.argv[1])\nprint(json.dumps([list(p[:3]) for r in rows for p in r]))`;
const pixels = () => JSON.parse(execFileSync('python3', ['-c', PX, SHOT], {maxBuffer: 1 << 27}).toString());
const lum = ([r, g, b]) => { const f = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };

async function open(page, peek) {
  await page.evaluate(async (peek) => {
    switchTab('notes'); await openAppearancePanel();
    document.querySelector('.appearance-panel').classList.toggle('peeking', peek);
  }, peek);
  await page.waitForTimeout(800);
}

async function labels(page, mode) {
  const boxes = await page.evaluate(() => {
    // Any colour syntax (oklch, color(srgb), rgb) resolved by drawing it.
    const x = new OffscreenCanvas(1, 1).getContext('2d', {willReadFrequently: true});
    const paint = (c) => { x.clearRect(0, 0, 1, 1); x.fillStyle = c; x.fillRect(0, 0, 1, 1); return [...x.getImageData(0, 0, 1, 1).data.slice(0, 3)]; };
    const out = [], w = document.createTreeWalker(document.querySelector('.appearance-panel'), NodeFilter.SHOW_TEXT);
    while (w.nextNode()) {
      const n = w.currentNode; if (!n.textContent.trim()) continue;
      const r = document.createRange(); r.selectNodeContents(n); const b = r.getBoundingClientRect();
      if (b.height && b.top >= 0 && b.bottom <= innerHeight) { n.parentElement.dataset.peekProbe = out.length; out.push({ink: paint(getComputedStyle(n.parentElement).color), t: n.textContent.trim().slice(0, 24), x: b.left, y: b.top, w: b.width, h: b.height}); }
    }
    return out;
  });
  const res = [];
  for (const [i, b] of boxes.entries()) {
    const clip = {x: Math.floor(b.x), y: Math.floor(b.y), width: Math.max(1, Math.ceil(b.w)), height: Math.max(1, Math.ceil(b.h))};
    const set = (c) => page.evaluate(([i, c]) => { document.querySelector(`[data-peek-probe="${i}"]`).style.color = c; }, [i, c]);
    await page.screenshot({clip, path: SHOT}); const ink = pixels();
    await set('transparent'); await page.screenshot({clip, path: SHOT}); const bare = pixels(); await set('');
    const ratios = [];
    ink.forEach((p, k) => {
      const q = bare[k];
      if (Math.abs(p[0] - q[0]) + Math.abs(p[1] - q[1]) + Math.abs(p[2] - q[2]) > 60) { const [a, c] = [lum(b.ink), lum(q)].sort((m, n) => n - m); ratios.push((a + 0.05) / (c + 0.05)); }
    });
    if (ratios.length) res.push([b.t, +ratios.sort((m, n) => n - m)[Math.floor(ratios.length * 0.1)].toFixed(2)]);
  }
  res.sort((a, b) => a[1] - b[1]);
  console.log(mode, process.env.THEME || 'light', 'n', res.length, 'lowest', JSON.stringify(res.slice(0, 5)));
}

(async () => {
  const {browser, page} = await boot({viewport: {width: 1440, height: 900}});
  for (let i = 0; i < 12; i++) await page.evaluate((i) => api('/entries', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({content: `Garden note ${i}: tomatoes, beans and a long line of words to fill the card`})}), i);
  for (const [w, h] of [[1280, 800], [1440, 900], [1920, 1200], [2560, 1440], [390, 844]]) {
    await page.setViewportSize({width: w, height: h}); await open(page, false);
    const r = await page.evaluate(() => { const b = document.querySelector('.appearance-panel').getBoundingClientRect(); return {w: b.width, h: b.height}; });
    console.log('size', `${w}x${h}`, 'height', Math.round(r.h), 'area share', +(r.w * r.h / (w * h)).toFixed(2));
  }
  await page.setViewportSize({width: 1440, height: 900});
  await open(page, false); await labels(page, 'rest');
  await open(page, true); await labels(page, 'peek');
  await browser.close();
})();
