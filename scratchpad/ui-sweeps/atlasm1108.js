// INBOX 1607 b, c, d (the masculine Atlas design pass): a pose cell per mood (stand), sit and walk for both
// looks in the live companion, and the rig's numbers on stand and sit (head, torso rows, arms' outlines, eyes,
// face framing by hair, eye and brow paint). scratchpad/ui-sweeps/atlasm1108.py turns OUT into the sheet and
// the metrics (docs/roadmap/agent-remaining/atlasm-1108.md has the before numbers).
//   BASE=http://127.0.0.1:PORT SCALE=1|2 OUT=dir [LOOKS=masculine] [ONLY=stand-calm] node scratchpad/ui-sweeps/atlasm1108.js
const fs = require('fs');
const path = require('path');
const { boot } = require('./lib.js');
const SCALE = Number(process.env.SCALE || 2);
const OUT = process.env.OUT || 'cells';
const LOOKS = (process.env.LOOKS || 'masculine,feminine').split(',');
const BOX = { width: 400, height: 300, left: 120, top: 60 };
const MEASURE = () => {
  const b = document.getElementById('nm-buddy');
  const r = (el) => { if (!el) return null; const q = el.getBoundingClientRect(); return [q.x, q.y, q.width, q.height].map((v) => +v.toFixed(2)); };
  const body = b.querySelector('.atl-layer-body') || b;
  const head = b.querySelector('.atl-head .atl-sway > path.atl-skin');
  const torso = body.querySelector('.atl-fills .nmb-torso path.atl-skin') || body.querySelector('.nmb-torso path.atl-skin');
  const arms = [...body.querySelectorAll('.atl-fills .nmb-arm > path.atl-skin')].map(r);
  const scl = [...b.querySelectorAll('.atl-eye .atl-sclera')].map(r);
  const iris = [...b.querySelectorAll('.atl-eye .atl-iris-fill')].map(r);
  const hairLayer = b.querySelector('.atl-layer-hair');
  const headG = b.querySelector('.atl-head');
  // whole drawn figure: union of layer content bboxes on screen
  let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
  for (const s of b.querySelectorAll('svg.atl-layer')) {
    if (/neb|aura|ring/.test(s.getAttribute('class'))) continue;
    for (const el of s.querySelectorAll('path.atl-skin, path.atl-lock, .atl-tail-core, path')) {
      const q = el.getBoundingClientRect(); if (!q.width || getComputedStyle(el).display === 'none') continue;
      x0 = Math.min(x0, q.x); y0 = Math.min(y0, q.y); x1 = Math.max(x1, q.right); y1 = Math.max(y1, q.bottom);
    }
  }
  // the torso outline sampled in screen px: width at each 0.5 unit row
  let rows = [];
  if (torso) {
    const m = torso.getScreenCTM(); const L = torso.getTotalLength(); const pts = [];
    for (let i = 0; i <= 400; i++) { const p = torso.getPointAtLength(L * i / 400); pts.push([m.a * p.x + m.c * p.y + m.e, m.b * p.x + m.d * p.y + m.f, p.x, p.y]); }
    for (let uy = 35.5; uy <= 62; uy += 0.5) {
      const near = pts.filter((p) => Math.abs(p[3] - uy) < 0.35);
      if (near.length < 2) continue;
      rows.push([uy, +(Math.max(...near.map((p) => p[2])) - Math.min(...near.map((p) => p[2]))).toFixed(2)]);
    }
  }

  const outline = (el, n = 240) => { if (!el) return []; const m = el.getScreenCTM(); const L = el.getTotalLength(); const o = []; for (let i = 0; i <= n; i++) { const p = el.getPointAtLength(L * i / n); o.push([+(m.a * p.x + m.c * p.y + m.e).toFixed(2), +(m.b * p.x + m.d * p.y + m.f).toFixed(2)]); } return o; };
  const armEls = [...body.querySelectorAll('.atl-fills .nmb-arm > path.atl-skin')];
  // face coverage: unit points on the head, tested against every hair fill
  const hm = head.getScreenCTM();
  const hairs = [...b.querySelectorAll('.atl-head .atl-hair-cap path.atl-lock, .atl-head .atl-ear > path.atl-skin, .atl-head .atl-wisps > path.atl-skin')].filter((p) => getComputedStyle(p).display !== 'none');
  const covered = (ux, uy) => { const sx = hm.a * ux + hm.c * uy + hm.e, sy = hm.b * ux + hm.d * uy + hm.f; return hairs.some((p) => { const mi = p.getScreenCTM().inverse(); const pt = new DOMPoint(mi.a * sx + mi.c * sy + mi.e, mi.b * sx + mi.d * sy + mi.f); return p.isPointInFill(pt); }); };
  const inHead = (ux, uy) => head.isPointInFill(new DOMPoint(ux, uy));
  let hairline = null; for (let uy = 8; uy <= 30; uy += 0.2) { if (inHead(31, uy) && !covered(31, uy)) { hairline = +uy.toFixed(1); break; } }
  const span = (uy) => { const xs = []; for (let ux = 17; ux <= 45; ux += 0.2) if (inHead(ux, uy) && !covered(ux, uy)) xs.push(ux); return xs.length ? [+xs[0].toFixed(1), +xs[xs.length - 1].toFixed(1), +(xs[xs.length - 1] - xs[0]).toFixed(1)] : null; };
  const st = (sel) => { const el = b.querySelector(sel); if (!el) return null; const c = getComputedStyle(el); return { sw: c.strokeWidth, stroke: c.stroke, fill: c.fill, op: c.opacity, r: r(el) }; };
  const extraOut = { armOutlines: armEls.map((a) => outline(a)), torsoOutline: outline(torso), hairline, brow: span(20.6), eyeRow: span(27), cheek: span(32), styles: { liner: st('.atl-eye-l .atl-liner'), lash: st('.atl-eye-l .atl-lash'), lashes: st('.atl-eye-l .atl-lashes'), brow: st('.atl-brow-l .atl-brow-line'), ink: st('.atl-eye-l .atl-ink'), mouth: st('.atl-m-calm path, .atl-m-calm ellipse') } };

  const anyHair = [...b.querySelectorAll('path.atl-lock, path.atl-cap-fill, path.atl-fringe-lock, .atl-ear > path.atl-skin, .atl-wisps > path.atl-skin, .atl-mane path.atl-skin, path.atl-strand')].filter((p) => getComputedStyle(p).display !== 'none');
  const hairAt = (sx, sy) => anyHair.some((p) => { const mi = p.getScreenCTM().inverse(); return p.isPointInFill(new DOMPoint(mi.a * sx + mi.c * sy + mi.e, mi.b * sx + mi.d * sy + mi.f)); });
  const HL = head.getTotalLength(); let fr = { all: 0, bare: 0, low: 0, lowBare: 0 };
  for (let i = 0; i < 300; i++) { const p = head.getPointAtLength(HL * i / 300); const dx = p.x - 31, dy = p.y - 24; const k = 1.2 / Math.hypot(dx, dy); const ux = p.x + dx * k, uy = p.y + dy * k; const sx = hm.a * ux + hm.c * uy + hm.e, sy = hm.b * ux + hm.d * uy + hm.f; const bare = !hairAt(sx, sy); fr.all++; if (bare) fr.bare++; if (p.y > 18) { fr.low++; if (bare) fr.lowBare++; } }
  extraOut.framing = { bareAll: +(fr.bare / fr.all).toFixed(3), bareBelowBrow: +(fr.lowBare / fr.low).toFixed(3) };
  return { ...extraOut, head: r(head), headGroup: r(headG), hair: r(hairLayer), torso: r(torso), arms, scl, iris, fig: [x0, y0, x1 - x0, y1 - y0].map((v) => +v.toFixed(2)), torsoRows: rows, scale: head ? +(head.getScreenCTM().a).toFixed(3) : 0 };
};
(async () => {
  const { browser, page } = await boot({ viewport: { width: 700, height: 500 }, scale: SCALE, clock: '2026-10-27T14:00:00' });
  const report = {};
  for (const look of LOOKS) {
    await page.evaluate((l) => { prefs.set('avatar-buddy', 'atlas'); prefs.set('atlas-look', l); prefs.set('avatar-buddy-motion', 'fades'); }, look);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);
    await page.evaluate(() => syncNameMarkBuddy());
    await page.waitForTimeout(1500);
    await page.evaluate((box) => {
      const b = document.getElementById('nm-buddy');
      const put = (el, props) => { for (const [k, v] of Object.entries(props)) el.style.setProperty(k, v, 'important'); };
      document.documentElement.setAttribute('data-glass', 'off');
      const sheet = document.styleSheets[0];
      for (const rule of [
        '#nm-buddy :is(.atl-lw-neb, .atl-lw-neb-front, .atl-layer-neb, .atl-layer-neb-fr, .atl-aura, .atl-orbits, .atl-rings, .atl-ring-frame, .nmp-bubble) { display: none !important; }',
        '#nm-buddy::before, #nm-buddy::after, #nm-buddy .nm-buddy-face::before, #nm-buddy .nm-buddy-face::after { display: none !important; }',
      ]) sheet.insertRule(rule, sheet.cssRules.length);
      put(document.documentElement, { background: '#1b1d2a' }); put(document.body, { background: '#1b1d2a' });
      for (const el of document.body.children) put(el, { visibility: 'hidden' });
      for (const el of document.querySelectorAll('mask, clipPath')) put(el, { visibility: 'visible' });
      window.__pin = `translate(${box.left + 78}px, ${box.top + 80}px)`;
      put(b, { transform: window.__pin, visibility: 'visible' });
      const realSet = CSSStyleDeclaration.prototype.setProperty;
      window.__setProp = (el, k, v, pr) => realSet.call(el.style, k, v, pr);
      Object.defineProperty(b.style, 'transform', { get: () => window.__pin, set: () => {}, configurable: true });
      b.style.setProperty = function (k, v, pr) { if (k !== 'transform') realSet.call(this, k, v, pr); };
      window.__mood = setAtlasMood; window.setAtlasMood = () => {};
      window.__want = 'stand';
      new MutationObserver(() => {
        for (const n of ['data-perch', 'data-legs', 'data-side']) if (b.hasAttribute(n)) b.removeAttribute(n);
        if (b.dataset.pose !== window.__want) b.dataset.pose = window.__want;
      }).observe(b, { attributes: true, attributeFilter: ['data-pose', 'data-perch', 'data-legs', 'data-side'] });
    }, BOX);
    const moods = await page.evaluate(() => Object.keys(ATLAS_MOODS));
    let cells = [...moods.map((m) => ({ name: `stand-${m}`, pose: 'stand', mood: m })), { name: 'sit-calm', pose: 'sit', mood: 'calm' }, { name: 'walk-calm', pose: 'stand', mood: 'calm', walk: true }];
    if (process.env.ONLY) cells = cells.filter((c) => process.env.ONLY.split(',').includes(c.name));
    fs.mkdirSync(path.join(OUT, look), { recursive: true });
    report[look] = {};
    for (const c of cells) {
      await page.evaluate((c) => {
        const b = document.getElementById('nm-buddy');
        for (const n of b.getAttributeNames()) if (n.startsWith('data-') && !['data-gait', 'data-seed', 'data-atlas-variant'].includes(n)) b.removeAttribute(n);
        b.className = c.walk ? 'nmb-walking' : '';
        window.__want = c.pose; b.dataset.pose = c.pose; b.dataset.feel = 'calm';
        window.__mood(c.mood, 0, { quiet: true });
      }, c);
      await page.waitForTimeout(1400);
      await page.evaluate(() => { for (const a of document.getAnimations()) { if (a.transitionProperty) { a.finish(); continue; } a.pause(); if (a.animationName && /blink/.test(a.animationName)) a.currentTime = 0; } });
      await page.waitForTimeout(80);
      await page.screenshot({ path: path.join(OUT, look, `${c.name}.png`), clip: { x: BOX.left + 60, y: BOX.top + 40, width: 200, height: 220 } });
      report[look][c.name] = await page.evaluate(() => { const q = document.querySelector('#nm-buddy .atl-head .atl-sway > path.atl-skin').getBoundingClientRect(); return [q.x, q.y, q.width, q.height]; });
      if (c.name === 'stand-calm' || c.name === 'sit-calm') report[look][c.name] = await page.evaluate((fn) => new Function(`return (${fn})()`)(), MEASURE.toString());
      await page.evaluate(() => { for (const a of document.getAnimations()) a.play(); });
    }
  }
  fs.writeFileSync(path.join(OUT, `measure-${SCALE}x.json`), JSON.stringify(report, null, 1));
  console.log('ok');
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
