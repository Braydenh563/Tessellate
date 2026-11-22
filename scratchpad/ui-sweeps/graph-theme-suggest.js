// Two owner bugs. (7) Toggling light and dark on the graph must repaint node outlines and label
// chips in the new theme: pixels sampled off the canvas after a fresh dark load, after switching
// to light and after switching back, against a fresh light load. (8) The Suggest links rows put
// the note icon on the words: icon and words centres per row, box centre and cap-height centre.
//   BASE=http://127.0.0.1:8880 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node scratchpad/ui-sweeps/graph-theme-suggest.js   (WIDTHS=1440,1920)
const { boot } = require('./lib.js');
const TOL = 16;
let failed = 0;
const say = (ok, name, detail) => { if (!ok) failed += 1; console.log(`${ok ? 'PASS' : 'FAIL'} ${name}: ${detail}`); };

async function seed(page) {
  await page.evaluate(async () => {
    if ((await apiJson('/entries/link-suggestions')).length >= 3) return;
    const post = (c) => apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: c }) });
    const n = ['Alpha trip', 'Beta budget', 'Gamma garden', 'Delta diary', 'Epsilon essay'];
    for (const x of n) await post(`${x} note about something`);
    for (const h of ['Hub one', 'Hub two']) await post(`${h} ${n.map((x) => `[[${x}]]`).join(' ')}`);
  });
  await page.waitForTimeout(1500);
}

// Patch roundRect once so the last label plates drawn are known; the chip and outline pixels are
// then read off the canvas as it stands, with no redraw asked for by the sweep.
const INSTALL = () => {
  window.__plates = [];
  const original = CanvasRenderingContext2D.prototype.roundRect;
  CanvasRenderingContext2D.prototype.roundRect = function (x, y, w, h, r) {
    if (this.canvas === gcTab.canvas && h >= 4 && h <= 30 && w > 20 && w < 260) {
      const m = this.getTransform();
      window.__plates.push({ a: m.a, d: m.d, e: m.e, f: m.f, x, y, w, h });
      if (window.__plates.length > 400) window.__plates.splice(0, 200);
    }
    return original.call(this, x, y, w, h, r);
  };
};

const SAMPLE = () => {
  const s = gcTab, c = s.canvas, ctx = c.getContext('2d');
  const px = (x, y) => { const d = ctx.getImageData(Math.round(x), Math.round(y), 1, 1).data; return [d[0], d[1], d[2]]; };
  const tok = (name) => {
    const t = document.createElement('canvas').getContext('2d');
    t.fillStyle = getComputedStyle(c).getPropertyValue(name).trim() || '#000'; t.fillRect(0, 0, 1, 1);
    const d = t.getImageData(0, 0, 1, 1).data; return [d[0], d[1], d[2]];
  };
  const k = s.transform.k, dpr = s.dpr;
  // Node outline: the ring of the largest note with no neighbour within 40 css px.
  const dots = s.nodes.filter((n) => !n.isGroup && Number.isFinite(n.x));
  const scr = (n) => ({ x: n.x * k + s.transform.x, y: n.y * k + s.transform.y });
  let best = null;
  for (const n of dots) {
    const a = scr(n);
    if (dots.some((o) => o !== n && Math.hypot(scr(o).x - a.x, scr(o).y - a.y) < 40)) continue;
    if (!best || n.r > best.r) best = n;
  }
  if (!best) best = dots.slice().sort((p, q) => q.r - p.r)[0];
  const a = scr(best);
  // The ring is the sprite's outermost opaque pixel on its centre row; the same offset is read off the screen.
  const sp = best._sprite, sc = sp.canvas.getContext('2d');
  const row = sc.getImageData(0, sp.half, sp.canvas.width, 1).data;
  let edge = 0;
  for (let x = sp.canvas.width - 1; x >= sp.half; x--) if (row[x * 4 + 3] === 255) { edge = x - sp.half; break; }
  const reach = Math.max(1, edge - 1) * (dpr === 1 ? 1 : 1);
  // Median of eight points round the ring, so a neighbour's line over one of them does not count.
  const pts = [0, 1, 2, 3, 4, 5, 6, 7].map((i) => px(a.x * dpr + Math.cos(i * Math.PI / 4) * reach, a.y * dpr + Math.sin(i * Math.PI / 4) * reach));
  const med = (i) => pts.map((p) => p[i]).sort((x, y) => x - y)[4];
  const outline = [med(0), med(1), med(2)];
  const plate = window.__plates[window.__plates.length - 1];
  let chip = null;
  if (plate) chip = px(plate.a * (plate.x + 1 / (plate.a / dpr || 1)) + plate.e, plate.d * (plate.y + plate.h / 2) + plate.f);
  return { theme: document.documentElement.dataset.theme, outline, chip, card: tok('--card'), ground: px(2 * dpr, 2 * dpr) };
};
const close = (p, q) => Math.max(...p.map((v, i) => Math.abs(v - q[i])));

async function openGraph(page) {
  await seed(page);
  await page.evaluate(() => switchTab('graph')); await page.waitForTimeout(3500);
  await page.evaluate(INSTALL);
  await page.evaluate(() => gcRequestDraw(gcTab)); await page.waitForTimeout(600);
}
async function themeTo(page, t) {
  await page.evaluate((x) => applyThemeChoice(x, true), t); await page.waitForTimeout(900);
}

async function part7(width, errs) {
  const run = async (theme, toggles) => {
    process.env.THEME = theme;
    const { browser, page } = await boot({ viewport: { width, height: 900 } });
    page.on('console', (m) => { if (m.type() === 'error' && !/404/.test(m.text())) errs.push(m.text()); });
    page.on('pageerror', (e) => errs.push(e.message));
    await openGraph(page);
    const out = { fresh: await page.evaluate(SAMPLE) };
    for (const t of toggles) { await themeTo(page, t); out[t] = await page.evaluate(SAMPLE); }
    await browser.close();
    return out;
  };
  const dark = await run('dark', ['light', 'dark']);
  const light = await run('light', []);
  const rows = [['dark fresh', dark.fresh, dark.fresh], ['to light', dark.light, light.fresh], ['back to dark', dark.dark, dark.fresh]];
  for (const [name, got, want] of rows) {
    const dChip = got.chip && want.chip ? close(got.chip, want.chip) : 999;
    const dOut = close(got.outline, want.outline);
    say(dChip <= TOL, `7 chip @${width} ${name}`, `pixel ${got.chip} vs fresh ${want.chip}, delta ${dChip} (tol ${TOL})`);
    say(dOut <= TOL, `7 outline @${width} ${name}`, `pixel ${got.outline} vs fresh ${want.outline}, delta ${dOut} (tol ${TOL}); card token ${got.card}`);
  }
}

const ROWS = () => {
  const probe = (cs) => {
    const host = document.createElement('div');
    for (const p of ['fontStyle', 'fontWeight', 'fontSize', 'fontFamily']) host.style[p] = cs[p];
    Object.assign(host.style, { position: 'fixed', left: '0', top: '0', lineHeight: 'normal', whiteSpace: 'nowrap', visibility: 'hidden' });
    const t = document.createTextNode('Hxg');
    const mk = (h) => { const s = document.createElement('span'); Object.assign(s.style, { display: 'inline-block', width: '0', height: h, verticalAlign: 'baseline' }); return s; };
    const base = mk('0'), cap = mk('1cap'); host.append(t, base, cap); document.body.append(host);
    const r = document.createRange(); r.selectNodeContents(t);
    const m = { asc: base.getBoundingClientRect().bottom - r.getBoundingClientRect().top, cap: cap.getBoundingClientRect().height };
    host.remove(); return m;
  };
  const out = [];
  for (const row of [...document.querySelectorAll('.link-suggestion')].slice(0, 6)) {
    for (const note of row.querySelectorAll('.link-suggestion-note')) {
      const icon = note.querySelector('.ph'), words = note.querySelector('.link-suggestion-name');
      const ir = icon.getBoundingClientRect(), wr = words.getBoundingClientRect();
      const range = document.createRange(); range.selectNodeContents(words);
      const q = range.getClientRects()[0], m = probe(getComputedStyle(words));
      const cap = q.top + m.asc - m.cap / 2;
      out.push({ box: (ir.top + ir.height / 2) - (wr.top + wr.height / 2), cap: (ir.top + ir.height / 2) - cap });
    }
  }
  return out;
};

// The owner's Windows font: Segoe UI's ascent and descent drawn on DejaVu glyphs (as iconalign.js).
async function segoe(page) {
  await page.evaluate(async () => {
    const faces = [['local("DejaVu Sans")', '400'], ['local("DejaVu Sans Bold")', '700']].map(([src, weight]) =>
      new FontFace('SweepSim', src, { ascentOverride: '107.9%', descentOverride: '25.1%', lineGapOverride: '0%', weight }));
    for (const f of faces) { await f.load(); document.fonts.add(f); }
    document.documentElement.style.setProperty('--ui-font', 'SweepSim', 'important');
    document.body.style.setProperty('font-family', 'SweepSim', 'important');
    window.dispatchEvent(new Event('resize'));
    if (typeof measureLabelOptics === 'function') measureLabelOptics();
  });
  await page.waitForTimeout(600);
}

async function part8(width, errs, font) {
  process.env.THEME = 'light';
  const { browser, page } = await boot({ viewport: { width, height: 900 } });
  page.on('console', (m) => { if (m.type() === 'error' && !/404/.test(m.text())) errs.push(m.text()); });
  page.on('pageerror', (e) => errs.push(e.message));
  await seed(page);
  await page.evaluate(() => switchTab('graph')); await page.waitForTimeout(2500);
  if (font === 'segoe') await segoe(page);
  await page.evaluate(() => openSuggestionsInbox('links')); await page.waitForTimeout(2500);
  const rows = await page.evaluate(ROWS);
  await browser.close();
  const worstBox = Math.max(...rows.map((r) => Math.abs(r.box))), worstCap = Math.max(...rows.map((r) => Math.abs(r.cap)));
  say(rows.length > 0, `8 rows @${width} ${font}`, `${rows.length} icons measured`);
  say(worstBox < 1, `8 box centre @${width} ${font}`, `worst |icon - words| ${worstBox.toFixed(2)}px`);
  say(worstCap < 1, `8 cap centre @${width} ${font}`, `worst |icon - words' cap-height centre| ${worstCap.toFixed(2)}px`);
}

(async () => {
  const errs = [];
  for (const w of (process.env.WIDTHS || '1440,1920').split(',').map(Number)) {
    await part7(w, errs);
    await part8(w, errs, 'dejavu');
    await part8(w, errs, 'segoe');
  }
  say(errs.length === 0, 'console errors', `${errs.length} ${errs.slice(0, 3).join(' | ')}`);
  console.log(failed ? `FAIL ${failed}` : 'PASS all');
  process.exit(failed ? 1 : 0);
})();
