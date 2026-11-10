// The feminine Atlas's lustre (INBOX 550, 554, 555, 556, 559, 563), as
// numbers.
//
//   BASE=http://127.0.0.1:8823 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     SCRATCH=/tmp/x REF_DIR=/tmp/x/base node scratchpad/ui-sweeps/atlasluster.js
//   PART=blink,rig,wave,fringe,wisps,dress,tail,hair,arms,body,gap,masc,motion,cost  (default: all)
//   POSES=, MOODS=  narrow the blink part (INBOX 540)
// - blink, rig, wave (INBOX 540, 554, 564): see each part's own note below.
//   RUNS=3        frame-cost runs (median)
//   REF_DIR=dir   atlas.js and 08-consistency.css from before, served in
//                 place of the app's (lib.js's OVERRIDE_*) for every "before"
//
// `turn` everywhere is the largest change of direction along an outline per
// 0.1 unit of length, in degrees: a hard point turns 120 or more in one
// step, a round end of radius 0.25 about 25.
// - fringe: every `.atl-fringe-lock` in a full drawing, its turn and its
//   tip's width over its root's (from the outline: twice the distance from
//   the centreline to the nearest outline point); the cap's own turn.
// - wisps: per wisp, its front and back runs, the largest turn over its
//   cores, its widths at 3%, 30% and 97% along, the alpha its cores paint on
//   a clear page along its centreline (the ends near 0); the glints, their
//   sizes; in the companion, whether the back runs' layer is under the body.
// - dress: its outline's turn, the overlap (IoU) of its shape with
//   REF_DIR's, its parts, and any stroke on it (none: no outline).
// - tail (INBOX 565): her comet tail's length now over before, its tip's
//   width, its filaments and their paint beside the wings'.
// - hair (INBOX 567): her locks, their largest turn, and the pixels midway
//   between neighbouring locks in the companion (the page in none).
// - arms (INBOX 564, 567, 568): the rest pose's upper-arm angle off
//   vertical, the elbow's angle, the wrist's width over the shoulder's, and
//   the largest luminance step on a line across the shoulder join.
// - body: the head's height over the figure's (head top to the lowest point
//   of the body), the face's height over its width, her hips over her
//   shoulders; now and before.
// - gap (INBOX 555): pixels along the hair's outer arc, 0.8 inside it, in
//   the companion at 6x on a magenta page, three moods, four phases of every
//   running loop: how many are the page's colour (none should be).
// - masc: the masculine figure's layers, markup now and before: which
//   differ (only the head may, INBOX 563), and 6x pixels.
// - motion: each look's loops (name and period) with motion on, reduced and
//   Off, how many of the INBOX 550 and 554 loops run, and the loops on each
//   flowing part (hair, tail and its tip, lower body, stream, wisps).
// - cost: main-thread time (CDP TaskDuration) over 8s with her companion
//   figure, and separately a 208px full mark, minus the page without; now
//   and before, interleaved.
const { boot } = require('./lib.js');
const fs = require('fs');
const crypto = require('crypto');
const { execFileSync } = require('child_process');
const PARTS = (process.env.PART || 'mount,blink,rig,wave,lower,fringe,wisps,dress,tail,hair,arms,body,gap,masc,motion,cost').split(',');
const RUNS = Number(process.env.RUNS || 3);
const REF_DIR = process.env.REF_DIR || '';
const SCRATCH = process.env.SCRATCH || '/tmp';
const PY = process.env.PY || require('path').resolve(__dirname, '..', '..', '.venv', 'bin', 'python');
//: Pixels that differ between two PNGs (the count); the alpha at given
//: device pixels, the largest in a 3x3 patch; the RGB at given pixels.
const DIFF = 'import sys\nfrom PIL import Image, ImageChops\na=Image.open(sys.argv[1]).convert("RGBA");b=Image.open(sys.argv[2]).convert("RGBA")\nprint(-1 if a.size!=b.size else sum(1 for p in ImageChops.difference(a,b).getdata() if max(p)>2))';
const ALPHA = 'import sys,json\nfrom PIL import Image\nim=Image.open(sys.argv[1]).convert("RGBA");w,h=im.size\nout=[]\nfor t,x,y in json.loads(sys.argv[2]):\n  out.append([t,max(im.getpixel((min(w-1,max(0,x+dx)),min(h-1,max(0,y+dy))))[3] for dx in (-1,0,1) for dy in (-1,0,1))])\nprint(json.dumps(out))';
const RGB = 'import sys,json\nfrom PIL import Image\nim=Image.open(sys.argv[1]).convert("RGB");w,h=im.size\nprint(json.dumps([im.getpixel((min(w-1,max(0,x)),min(h-1,max(0,y)))) for x,y in json.loads(sys.argv[2])]))';
const BG = [255, 0, 255];

const side = (ref) => {
  if (ref) { process.env.OVERRIDE_JS = `atlas.js=${REF_DIR}/atlas.js`; process.env.OVERRIDE_CSS = `08-consistency.css=${REF_DIR}/08-consistency.css`; }
  else { delete process.env.OVERRIDE_JS; delete process.env.OVERRIDE_CSS; }
};

const GEOMETRY = () => {
  window.__lusterOutline = (path) => {
    const n = path.getTotalLength();
    const pts = [];
    for (let s = 0; s <= n; s += 0.1) { const p = path.getPointAtLength(s); pts.push([p.x, p.y]); }
    let turn = 0;
    for (let i = 2; i < pts.length; i += 1) {
      const a = Math.atan2(pts[i - 1][1] - pts[i - 2][1], pts[i - 1][0] - pts[i - 2][0]);
      const b = Math.atan2(pts[i][1] - pts[i - 1][1], pts[i][0] - pts[i - 1][0]);
      let d = Math.abs(b - a) * 180 / Math.PI;
      if (d > 180) d = 360 - d;
      if (Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]) > 0.02) turn = Math.max(turn, d);
    }
    return { pts, turn: +turn.toFixed(1) };
  };
  window.__lusterWidth = (pts, c) => 2 * Math.min(...pts.map(([x, y]) => Math.hypot(x - c[0], y - c[1])));
};

async function mountFigure(page, look, extra = {}) {
  await page.evaluate(({ look, extra }) => {
    localStorage.setItem('atlas-look', look);
    document.getElementById('luster-box')?.remove();
    document.getElementById('nm-buddy')?.remove();
    const box = document.createElement('div'); box.id = 'luster-box';
    Object.assign(box.style, { position: 'fixed', left: '0', top: '0', width: '160px', height: '170px', zIndex: '9999', overflow: 'hidden', background: '#f3f4fa' });
    const holder = document.createElement('div'); holder.id = 'nm-buddy';
    Object.assign(holder.style, { position: 'absolute', left: '40px', top: '40px', width: '64px', height: '92px' });
    if (extra.pose && extra.pose !== 'stand') holder.dataset.pose = extra.pose;
    const mood = extra.mood || 'calm';
    try { atlasMoodNow = mood; } catch (e) {}
    const fig = atlasFigure(); Object.assign(fig.style, { position: 'relative', display: 'block', width: '64px', height: '92px' });
    for (const svg of fig.querySelectorAll('svg')) atlasApply(svg, mood);
    holder.append(fig); box.append(holder); document.body.append(box);
    if (extra.still) for (const el of box.querySelectorAll('*')) el.style.animation = 'none';
  }, { look, extra });
}

async function drawingPart(fn, arg) {
  const { browser, page } = await boot({ viewport: { width: 520, height: 700 }, scale: 6 });
  await page.evaluate(GEOMETRY);
  await page.evaluate(() => { document.documentElement.dataset.avatarMotion = 'off'; });
  const out = await fn(page, arg);
  await page.evaluate(() => localStorage.removeItem('atlas-look'));
  await browser.close();
  return out;
}

const fringePart = (page) => page.evaluate(() => {
  localStorage.setItem('atlas-look', 'feminine');
  const svg = atlasDraw(400, 'calm', 'full');
  document.body.append(svg);
  const spec = ATLAS_LOOKS.feminine;
  const locks = [...svg.querySelectorAll('.atl-fringe-lock')].map((p, i) => {
    const { pts, turn } = window.__lusterOutline(p);
    const seg = spec.fringe[i].seg;
    const w = (t) => +window.__lusterWidth(pts, atlasSegsAt(seg, t)).toFixed(2);
    return { turn, root: w(0.04), tip: w(0.96), taper: +(w(0.96) / w(0.04)).toFixed(2) };
  });
  const capTurn = window.__lusterOutline(svg.querySelector('.atl-cap-fill')).turn;
  const inCap = !!svg.querySelector('.atl-hair-cap .atl-fringe-lock');
  const parts = ['atl-fringe-shadow', 'atl-fringe-sheen', 'atl-flyaway'].map((c) => svg.querySelectorAll(`.${c}`).length);
  svg.remove();
  return { locks: locks.length, maxTurn: Math.max(...locks.map((l) => l.turn)), maxTaper: Math.max(...locks.map((l) => l.taper)), capTurn, inCapGroup: inCap, shadowSheenFlyaway: parts, each: locks };
});

async function wispsPart(page) {
  const out = await page.evaluate(() => {
    localStorage.setItem('atlas-look', 'feminine');
    const svg = atlasDraw(400, 'calm', 'full');
    svg.id = 'luster-svg';
    Object.assign(svg.style, { position: 'fixed', left: '0', top: '0', zIndex: '9999' });
    document.body.append(svg);
    const spec = ATLAS_LOOKS.feminine;
    const each = spec.wisps.map((wisp, i) => {
      const cores = [...svg.querySelectorAll(`.atl-astral-core[data-wisp="${i}"]`)];
      const outl = cores.map((p) => window.__lusterOutline(p));
      const pts = outl.flatMap((o) => o.pts);
      const w = (t) => +window.__lusterWidth(pts, atlasSegsAt(wisp.seg, t)).toFixed(2);
      return { runs: { front: cores.filter((c) => c.dataset.run === 'front').length, back: cores.filter((c) => c.dataset.run === 'back').length }, turn: Math.max(...outl.map((o) => o.turn)), w03: w(0.03), w30: w(0.3), w97: w(0.97) };
    });
    window.__lusterCore = (i) => {
      //: Everything hidden but this wisp's cores (CSSOM: the page's CSP
      //: refuses a <style> written here).
      for (const el of [document.documentElement, document.body]) { el.style.background = 'transparent'; el.style.visibility = 'hidden'; }
      svg.style.visibility = 'hidden';
      for (const el of svg.querySelectorAll('*')) el.style.visibility = 'hidden';
      //: The masks' contents live in the shared defs, which must show.
      for (const d of document.querySelectorAll('svg.atl-defs')) d.style.visibility = 'visible';
      const cores = [...svg.querySelectorAll(`.atl-astral-core[data-wisp="${i}"]`)];
      for (const c of cores) c.style.visibility = 'visible';
      const box = svg.getBoundingClientRect();
      return [0.01, 0.04, 0.5, 0.96, 0.99].map((t) => {
        const [x, y] = atlasSegsAt(spec.wisps[i].seg, t);
        const q = new DOMPoint(x, y).matrixTransform(cores[0].getScreenCTM());
        return [t, Math.round((q.x - box.left) * 6), Math.round((q.y - box.top) * 6)];
      });
    };
    const glints = [...svg.querySelectorAll('.atl-wisp-glint')];
    return { glints: glints.length, glintSizes: new Set(glints.map((g) => g.dataset.k)).size, oldDots: svg.querySelectorAll('.atl-astral-sparkle').length, each };
  });
  for (let i = 0; i < out.each.length; i += 1) {
    const pts = await page.evaluate((i) => window.__lusterCore(i), i);
    await page.waitForTimeout(300);
    const file = `${SCRATCH}/atlasluster-core${i}.png`;
    const r = await page.evaluate(() => { const b = document.getElementById('luster-svg').getBoundingClientRect(); return { x: b.left, y: b.top, width: b.width, height: b.height }; });
    await page.screenshot({ path: file, omitBackground: true, clip: r });
    out.each[i].alpha = JSON.parse(execFileSync(PY, ['-c', ALPHA, file, JSON.stringify(pts)]).toString());
  }
  await page.evaluate(() => { document.getElementById('luster-svg')?.remove(); for (const el of [document.documentElement, document.body]) { el.style.background = ''; el.style.visibility = ''; } });
  await mountFigure(page, 'feminine', { still: true });
  out.backLayerUnderBody = await page.evaluate(() => {
    const kids = [...document.querySelector('#luster-box .atl-figure-box').children];
    const at = (cls) => kids.findIndex((k) => k.classList.contains(cls) || k.querySelector(`.${cls}`));
    return at('atl-layer-wisps-back') >= 0 && at('atl-layer-wisps-back') < at('atl-layer-body');
  });
  return out;
}

async function dressPart() {
  let refFill = null;
  if (REF_DIR) {
    side(true);
    refFill = await drawingPart((page) => page.evaluate(() => { localStorage.setItem('atlas-look', 'feminine'); atlasBuild(); return ATLAS_LOOKS.feminine.sower.fill; }));
    side(false);
  }
  return drawingPart((page, refFill) => page.evaluate((refFill) => {
    localStorage.setItem('atlas-look', 'feminine');
    const svg = atlasDraw(400, 'calm', 'full');
    document.body.append(svg);
    const fill = svg.querySelector('.atl-sower-fill');
    const { turn } = window.__lusterOutline(fill);
    let iou = null;
    if (refFill) {
      //: Both shapes rasterised at 10 px a unit; the overlap over the union.
      const k = 10;
      const c = document.createElement('canvas'); c.width = 90 * k; c.height = 70 * k;
      const ctx = c.getContext('2d');
      const mask = (d) => { ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.clearRect(0, 0, c.width, c.height); ctx.setTransform(k, 0, 0, k, 20 * k, -40 * k); ctx.fill(new Path2D(d)); return ctx.getImageData(0, 0, c.width, c.height).data; };
      const a = mask(fill.getAttribute('d'));
      const b = mask(refFill);
      //: Whole, and below y 64 (the dress past the hips, which INBOX 563
      //: narrowed on purpose).
      const count = (fromY) => {
        let and = 0; let or = 0;
        for (let i = 3; i < a.length; i += 4) {
          if (Math.floor((i - 3) / 4 / c.width) / k + 40 < fromY) continue;
          const x = a[i] > 127; const y = b[i] > 127;
          if (x && y) and += 1;
          if (x || y) or += 1;
        }
        return +(and / or).toFixed(3);
      };
      iou = { whole: count(-99), belowHips: count(64) };
    }
    const parts = Object.fromEntries(['atl-dress-neb', 'atl-dress-sheen', 'atl-dress-rim', 'atl-dress-star', 'atl-dress-glint', 'atl-dress-mote', 'atl-sower-glow'].map((c) => [c, svg.querySelectorAll(`.${c}`).length]));
    const strokes = [...svg.querySelectorAll('.atl-sower *')].filter((el) => getComputedStyle(el).stroke !== 'none').length;
    const dust = [...svg.querySelectorAll('.atl-dress-star')].map((p) => (p.getAttribute('d').match(/a([0-9.]+)/g) || []).map((m) => +m.slice(1)))[0] || [];
    return { turn, iouWithBefore: iou, parts, strokes, dustSizes: new Set(dust).size, mask: fill.parentElement.getAttribute('mask') };
  }, refFill), refFill);
}

async function bodyPart(ref) {
  side(ref);
  const out = await drawingPart(async (page) => {
    const res = {};
    for (const look of ['feminine', 'masculine']) {
      await mountFigure(page, look, { still: true });
      await page.waitForTimeout(800);
      res[look] = await page.evaluate((look) => {
        const box = document.querySelector('#luster-box .atl-figure-box');
        const headSkin = [...box.querySelectorAll('.atl-layer-body .atl-head .atl-skin')].find((p) => p.getAttribute('d') === ATLAS_HEAD_PATH);
        const h = headSkin.getBoundingClientRect();
        let bottom = 0;
        for (const p of box.querySelectorAll('.atl-layer-body .atl-fills > *, .atl-layer-lower .atl-fills .atl-sower-fill, .atl-layer-lower .atl-fills .atl-ribbon-veil, [class*="atl-layer-leg"] .atl-fills .atl-skin')) bottom = Math.max(bottom, p.getBoundingClientRect().bottom);
        const tmp = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', ATLAS_HEAD_PATH); tmp.append(path); document.body.append(tmp);
        const bb = path.getBBox();
        const spec = ATLAS_LOOKS[look];
        path.setAttribute('d', spec.torsoNow);
        const n = path.getTotalLength();
        const rows = {};
        for (let s = 0; s <= n; s += 0.05) { const q = path.getPointAtLength(s); const y = Math.round(q.y * 2) / 2; (rows[y] ||= []).push(q.x); }
        const wAt = (y0, y1) => Math.max(...Object.entries(rows).filter(([y]) => +y >= y0 && +y <= y1).map(([, xs]) => Math.max(...xs) - Math.min(...xs)));
        tmp.remove();
        return { headOverHeight: +(h.height / (bottom - h.top)).toFixed(3), faceAspect: +(bb.height / bb.width).toFixed(3), hipsOverShoulders: +(wAt(55, 62) / wAt(37, 38.5)).toFixed(2), hips: +wAt(55, 62).toFixed(1) };
      }, look);
    }
    return res;
  });
  side(false);
  return out;
}

async function gapPart() {
  const { browser, page } = await boot({ viewport: { width: 520, height: 700 }, scale: 6 });
  await page.evaluate(() => { document.documentElement.dataset.avatarMotion = 'always'; });
  const out = { samples: 0, background: 0, worst: [] };
  for (const mood of ['calm', 'surprised', 'happy']) {
    await mountFigure(page, 'feminine', { mood });
    //: Magenta behind her, which no part of her is, so a sample that is the
    //: page cannot be mistaken for her palest hair.
    await page.evaluate(() => { document.getElementById('luster-box').style.background = '#ff00ff'; });
    await page.waitForTimeout(1500);
    for (const phase of [0, 0.25, 0.5, 0.75]) {
      const pts = await page.evaluate((phase) => {
        const box = document.getElementById('luster-box');
        for (const a of box.getAnimations({ subtree: true })) {
          a.pause();
          const d = a.effect.getComputedTiming().duration;
          if (Number.isFinite(d)) a.currentTime = d * phase;
        }
        const cap = box.querySelector('.atl-layer-body .atl-cap-fill');
        const m = cap.getScreenCTM();
        const r = box.getBoundingClientRect();
        //: The cap's outer arc (its first two curves, from the left temple
        //: over the crown to the right), 0.8 in toward the head's middle.
        const tmp = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        tmp.setAttribute('d', cap.getAttribute('d').split('C').slice(0, 3).join('C'));
        cap.parentNode.append(tmp);
        const n = tmp.getTotalLength();
        const res = [];
        for (let i = 1; i < 40; i += 1) {
          const q = tmp.getPointAtLength((n * i) / 40);
          const dx = 31 - q.x; const dy = 24 - q.y; const len = Math.hypot(dx, dy);
          const p = new DOMPoint(q.x + (dx / len) * 0.8, q.y + (dy / len) * 0.8).matrixTransform(m);
          res.push([Math.round((p.x - r.left) * 6), Math.round((p.y - r.top) * 6)]);
        }
        tmp.remove();
        return res;
      }, phase);
      const file = `${SCRATCH}/atlasluster-gap.png`;
      await (await page.$('#luster-box')).screenshot({ path: file });
      const rgb = JSON.parse(execFileSync(PY, ['-c', RGB, file, JSON.stringify(pts)]).toString());
      for (const c of rgb) {
        out.samples += 1;
        const d = Math.max(...c.map((v, k) => Math.abs(v - BG[k])));
        if (d < 40) { out.background += 1; if (out.worst.length < 5) out.worst.push({ mood, phase, c }); }
      }
    }
  }
  await page.evaluate(() => localStorage.removeItem('atlas-look'));
  await browser.close();
  return out;
}

async function mascPart() {
  const snap = async (ref) => {
    side(ref);
    const res = await drawingPart(async (page) => {
      const layers = await page.evaluate(() => {
        localStorage.setItem('atlas-look', 'masculine');
        const span = document.createElement('span'); span.append(atlasDraw(92, 'calm', 'figure'));
        //: The head's own geometry (its outline and the cheeks), named, so
        //: a layer can be compared with the head's changes taken out.
        const head = (html) => ATLAS_GEO.cheeks.reduce((h, [x, y], i) => h.replace(`cx="${x}" cy="${y}"`, `cheek${i}`), html.split(ATLAS_HEAD_PATH).join('HEAD').split(ATLAS_HEAD_EDGE).join('EDGE'));
        return Object.fromEntries([...span.querySelectorAll('svg.atl-layer')].map((s) => [s.dataset.atlasLayer, [s.outerHTML, head(s.outerHTML)]]));
      });
      await mountFigure(page, 'masculine', { still: true });
      await page.waitForTimeout(1200);
      const file = `${SCRATCH}/atlasluster-masc-${ref ? 'ref' : 'now'}.png`;
      await (await page.$('#luster-box')).screenshot({ path: file });
      return { layers, file };
    });
    side(false);
    return res;
  };
  const now = await snap(false);
  if (!REF_DIR) return { note: 'set REF_DIR to compare' };
  const ref = await snap(true);
  const differ = Object.keys(now.layers).filter((k) => now.layers[k][0] !== ref.layers[k][0]);
  const beyondHead = differ.filter((k) => now.layers[k][1] !== ref.layers[k][1]);
  return { layersDiffer: differ, differBeyondTheHead: beyondHead, pixelsDiffering: +execFileSync(PY, ['-c', DIFF, now.file, ref.file]).toString() };
}

async function motionPart() {
  const out = {};
  for (const look of ['feminine', 'masculine']) for (const [state, opts, attr] of [['on', {}, 'always'], ['reduced', { reducedMotion: 'reduce' }, 'always'], ['off', {}, 'off']]) {
    const name = `${look}-${state}`;
    const { browser, page } = await boot({ viewport: { width: 520, height: 700 }, ...opts });
    await page.evaluate((attr) => { document.documentElement.dataset.avatarMotion = attr; }, attr);
    await mountFigure(page, look);
    await page.waitForTimeout(1200);
    out[name] = await page.evaluate(() => {
      const box = document.querySelector('#luster-box .atl-figure-box');
      const anims = [box, ...box.querySelectorAll('*')].flatMap((el) => el.getAnimations());
      const loops = [...new Set(anims.map((a) => `${a.animationName} ${+(a.effect.getComputedTiming().duration / 1000).toFixed(1)}s`))].sort();
      const ours = anims.filter((a) => ['atl-float', 'atl-hem-wind', 'atl-glint-twinkle', 'atl-wisp-drift', 'atl-hair-trail', 'atl-tail-wave'].includes(a.animationName)).length;
      //: Per flowing part (the owner: "the tail ... the hair, and the nebular
      //: stream ... all need to be dynamically animated"): the loops on it or
      //: on any box or root it sits in.
      const partOf = { hair: '.atl-layer-hair', tail: '.atl-layer-tail:not(.atl-layer-tail-tip)', tailTip: '.atl-layer-tail-tip', lower: '.atl-layer-lower', stream: '.atl-layer-neb-front', wisps: '.atl-layer-wisps' };
      const parts = {};
      for (const [part, sel] of Object.entries(partOf)) {
        const el = box.querySelector(sel);
        const chain = [];
        for (let n = el; n && n !== box.parentNode; n = n.parentElement) chain.push(n);
        parts[part] = el ? [...new Set(chain.flatMap((n) => n.getAnimations()).map((a) => a.animationName))].sort().join(' ') : 'none';
      }
      return { loops, ours, parts };
    });
    await page.evaluate(() => localStorage.removeItem('atlas-look'));
    await browser.close();
  }
  return out;
}

async function costPart() {
  const measure = async (what, ref) => {
    side(ref);
    const { browser, ctx, page } = await boot({ viewport: { width: 1280, height: 800 } });
    await page.evaluate((what) => {
      document.documentElement.dataset.avatarMotion = 'always';
      localStorage.setItem('atlas-look', 'feminine');
      document.getElementById('nm-buddy')?.remove();
      const stage = document.createElement('div'); stage.id = 'cost-stage';
      Object.assign(stage.style, { position: 'fixed', right: '16px', top: '80px', zIndex: '9999', display: 'flex', gap: '8px', alignItems: 'end' });
      document.body.append(stage);
      if (what === 'figure') {
        const holder = document.createElement('div'); holder.id = 'nm-buddy';
        Object.assign(holder.style, { position: 'relative', width: '64px', height: '92px' });
        const fig = atlasFigure(); Object.assign(fig.style, { position: 'relative', display: 'block', width: '64px', height: '92px' });
        holder.append(fig); stage.append(holder);
      }
      if (what === 'mark') stage.append(nameMarkLive('Atlas', 208));
    }, what);
    await page.waitForTimeout(2000);
    const cdp = await ctx.newCDPSession(page);
    await cdp.send('Performance.enable');
    const read = async () => Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((m) => [m.name, m.value]));
    const a = await read();
    await page.waitForTimeout(8000);
    const b = await read();
    await page.evaluate(() => localStorage.removeItem('atlas-look'));
    await browser.close();
    side(false);
    return (b.TaskDuration - a.TaskDuration) * 1000;
  };
  const median = (xs) => xs.slice().sort((x, y) => x - y)[Math.floor(xs.length / 2)];
  const sides = REF_DIR ? ['now', 'ref'] : ['now'];
  const runs = {};
  for (let i = 0; i < RUNS; i += 1) for (const s of sides) for (const what of ['none', 'figure', 'mark']) (runs[`${s}-${what}`] ||= []).push(await measure(what, s === 'ref'));
  const out = {};
  for (const s of sides) {
    const none = median(runs[`${s}-none`]);
    out[s] = Object.fromEntries(['figure', 'mark'].map((w) => [w, +(median(runs[`${s}-${w}`]) - none).toFixed(1)]));
  }
  if (REF_DIR) out.change = Object.fromEntries(['figure', 'mark'].map((w) => [w, `${(100 * (out.now[w] / out.ref[w] - 1)).toFixed(1)}%`]));
  out.runs = Object.fromEntries(Object.entries(runs).map(([k, v]) => [k, v.map((x) => +x.toFixed(0))]));
  return out;
}

//: INBOX 565: her tail's centreline length, now and before, its width at
//: the tip, its filaments, and the paint of the filaments and of the tip's
//: glow beside the wings' own (the same colours, the tail's fainter).
async function tailPart(ref) {
  side(ref);
  const out = await drawingPart((page) => page.evaluate(() => {
    localStorage.setItem('atlas-look', 'feminine');
    const spec = ATLAS_LOOKS.feminine;
    let len = 0;
    const n = spec.tail.length * 40;
    let prev = atlasSegsAt(spec.tail, 0);
    for (let i = 1; i <= n; i += 1) { const q = atlasSegsAt(spec.tail, i / n); len += Math.hypot(q[0] - prev[0], q[1] - prev[1]); prev = q; }
    const svg = atlasDraw(400, 'calm', 'full');
    document.body.append(svg);
    const cs = (sel, prop) => { const el = svg.querySelector(sel); return el ? `${getComputedStyle(el)[prop]} @${getComputedStyle(el).opacity}` : null; };
    const res = { length: +len.toFixed(1), tipWidth: +spec.tailWidth(1).toFixed(2), filaments: (svg.querySelector('.atl-tail-filament')?.getAttribute('d').match(/M/g) || []).length, filament: cs('.atl-tail-filament', 'stroke'), earFeather: cs('.atl-ear-feather', 'stroke'), tipGlow: cs('.atl-tail-tip-glow', 'fill'), earGlow: cs('.atl-ear-glow:not(.atl-tail-tip-glow)', 'fill') };
    svg.remove();
    return res;
  }));
  side(false);
  return out;
}

//: INBOX 567: her long hair's locks (count, the largest turn on their
//: outlines, so no point), and, in the companion at 6x on a magenta page,
//: the pixels midway between neighbouring locks down their fall, which
//: must be hair (the mass behind), never the page.
async function hairPart() {
  const shape = await drawingPart((page) => page.evaluate(() => {
    localStorage.setItem('atlas-look', 'feminine');
    const svg = atlasDraw(400, 'calm', 'full');
    document.body.append(svg);
    const locks = [...svg.querySelectorAll('.atl-mane .atl-lock:not(.atl-hair-mass)')];
    const turns = locks.map((p) => window.__lusterOutline(p).turn);
    svg.remove();
    return { locks: locks.length, maxTurn: Math.max(...turns) };
  }));
  const { browser, page } = await boot({ viewport: { width: 520, height: 700 }, scale: 6 });
  await page.evaluate(() => { document.documentElement.dataset.avatarMotion = 'off'; });
  await mountFigure(page, 'feminine', { still: true });
  await page.evaluate(() => { document.getElementById('luster-box').style.background = '#ff00ff'; });
  await page.waitForTimeout(1200);
  const pts = await page.evaluate(() => {
    const box = document.getElementById('luster-box');
    const mane = box.querySelector('.atl-layer-hair .atl-mane, .atl-layer-body .atl-mane');
    const m = mane.querySelector('path').getScreenCTM();
    const r = box.getBoundingClientRect();
    const locks = ATLAS_LOOKS.feminine.locks.filter((l) => !l.mass).slice(0, 4);
    const res = [];
    for (let i = 0; i < locks.length - 1; i += 1) {
      for (let t = 0.3; t <= 0.81; t += 0.1) {
        const a = atlasSegsAt(locks[i].seg, t);
        const b = atlasSegsAt(locks[i + 1].seg, t);
        const q = new DOMPoint((a[0] + b[0]) / 2, (a[1] + b[1]) / 2).matrixTransform(m);
        res.push([Math.round((q.x - r.left) * 6), Math.round((q.y - r.top) * 6)]);
      }
    }
    return res;
  });
  const file = `${SCRATCH}/atlasluster-hair.png`;
  await (await page.$('#luster-box')).screenshot({ path: file });
  const rgb = JSON.parse(execFileSync(PY, ['-c', RGB, file, JSON.stringify(pts)]).toString());
  await page.evaluate(() => localStorage.removeItem('atlas-look'));
  await browser.close();
  return { ...shape, between: rgb.length, pageBetween: rgb.filter((c) => Math.max(...c.map((v, k) => Math.abs(v - BG[k]))) < 40).length };
}

//: INBOX 564, 567, 568: the arms at rest, both looks. From the drawn
//: centreline: the upper arm's angle off vertical (15 or less), the angle
//: at the elbow (160 to 170), and the width at the wrist over the width at
//: the shoulder (0.7 or less), read off the arm's own outline. In the
//: companion at 6x, calm, still: the luminance along a line across the
//: shoulder, from the torso into the arm, its largest step between
//: neighbouring samples (a seam would be a step).
async function armsPart(ref) {
  side(ref);
  const out = await drawingPart(async (page) => {
    const res = {};
    for (const look of ['feminine', 'masculine']) {
      await mountFigure(page, look, { still: true });
      await page.waitForTimeout(900);
      const got = await page.evaluate((look) => {
        const spec = ATLAS_LOOKS[look];
        const seg = spec.arm;
        const ang = (a, b) => Math.atan2(b[0] - a[0], b[1] - a[1]) * 180 / Math.PI;
        const p0 = seg[0].slice(0, 2);
        const p1 = seg[0].slice(6, 8);
        const p2 = seg.at(-1).slice(6, 8);
        const upper = Math.abs(ang(p0, p1));
        const elbow = 180 - Math.abs(ang(p0, p1) - ang(p1, p2));
        const arm = document.querySelector('#luster-box .atl-layer-body .nmb-arm-r path.atl-skin');
        const { pts } = window.__lusterOutline(arm);
        const w = (t) => window.__lusterWidth(pts, atlasSegsAt(seg, t));
        const box = document.getElementById('luster-box').getBoundingClientRect();
        const m = arm.getScreenCTM();
        const line = [];
        for (let k = -3; k <= 3; k += 0.5) {
          const q = new DOMPoint(p0[0] + k, p0[1] + 3).matrixTransform(m);
          line.push([Math.round((q.x - box.left) * 6), Math.round((q.y - box.top) * 6)]);
        }
        return { upperFromVertical: +upper.toFixed(1), elbow: +elbow.toFixed(1), taper: +(w(0.8) / w(0.1)).toFixed(2), line };
      }, look);
      const file = `${SCRATCH}/atlasluster-arm-${look}.png`;
      await (await page.$('#luster-box')).screenshot({ path: file });
      const rgb = JSON.parse(execFileSync(PY, ['-c', RGB, file, JSON.stringify(got.line)]).toString());
      const lum = rgb.map(([r, g, b]) => 0.2126 * r + 0.7152 * g + 0.0722 * b);
      got.seamStep = +Math.max(...lum.slice(1).map((v, i) => Math.abs(v - lum[i]))).toFixed(1);
      delete got.line;
      res[look] = got;
    }
    return res;
  });
  side(false);
  return out;
}

//: INBOX 540: the blink (`atlasBlink`), both looks, six poses, every mood
//: whose eyes are open, and drowsy. Each blink is stepped 16ms at a time
//: and read off the drawing in screen px, against the open eye's white
//: (`.atl-sclera`, the body layer) and the brow:
//: - outside: the largest distance the lid's edge line or her lashes reach
//:   past the eye's box plus a margin of a third of its width, where the
//:   clip lets them show (none should);
//: - cover: the shut lid's clip covers the eye's box, to 0.3px (every case);
//: - foot: the shut edge's lowest point less the eye's, over its height;
//: - brow: the largest move of a brow's box over the blink (0);
//: - strokes: the spread of each stroke's width (its stroke-width times
//:   the drawing's scale) over the blink (0);
//: - liner: at 6x on the shut frame, points on the upper liner and 1.4
//:   inside it whose luminance differs by over 20 from the same frame with
//:   the open eyes hidden (the face's skin): the eye showing round a lid.
async function blinkPart() {
  const { browser, page } = await boot({ viewport: { width: 520, height: 700 }, scale: 6 });
  await page.evaluate(() => { document.documentElement.dataset.avatarMotion = 'always'; clearTimeout(atlasState.blinkTimer); atlasBlinkTick = () => {}; });
  const res = { cases: 0, frames: 0, outside: 0, uncovered: [], footMax: 0, browMove: 0, strokeSpread: 0, linerShowing: 0, linerSamples: 0, worst: [] };
  for (const look of ['feminine', 'masculine']) {
    for (const pose of (process.env.POSES || 'stand,sit,hang,float,lie,curl').split(',')) {
      for (const mood of process.env.MOODS ? process.env.MOODS.split(',') : [...Object.keys(await page.evaluate(() => ATLAS_MOODS)), 'drowsy']) {
        const got = await page.evaluate(async ([look, pose, mood]) => {
          localStorage.setItem('atlas-look', look);
          document.getElementById('luster-box')?.remove();
          document.getElementById('nm-buddy')?.remove();
          const box = document.createElement('div'); box.id = 'luster-box';
          Object.assign(box.style, { position: 'fixed', left: '0', top: '0', width: '160px', height: '170px', zIndex: '9999', overflow: 'hidden', background: '#f3f4fa' });
          const holder = document.createElement('div'); holder.id = 'nm-buddy';
          Object.assign(holder.style, { position: 'absolute', left: '40px', top: '40px', width: '64px', height: '92px' });
          if (pose !== 'stand') holder.dataset.pose = pose;
          if (mood === 'drowsy') holder.classList.add('nmb-drowsy');
          const fig = atlasFigure(); Object.assign(fig.style, { position: 'relative', display: 'block', width: '64px', height: '92px' });
          for (const svg of fig.querySelectorAll('svg')) atlasApply(svg, mood === 'drowsy' ? 'calm' : mood);
          holder.append(fig); box.append(holder); document.body.append(box);
          for (const a of box.getAnimations({ subtree: true })) { a.pause(); a.currentTime = 0; }
          await new Promise((r) => setTimeout(r, 700));
          for (const a of box.getAnimations({ subtree: true })) { a.pause(); a.currentTime = 0; }
          const lids = fig.querySelector('.atl-layer-lids:not(.atl-layer-lidf)');
          if (getComputedStyle(lids).scale === '0') return null;
          const ms = mood === 'drowsy' ? 1420 : 320;
          //: What `atlasBlink` does, without taking the class off after the blink.
          for (const el of fig.querySelectorAll('.atl-layer-lids')) el.classList.add(mood === 'drowsy' ? 'atl-blinking-slow' : 'atl-blinking');
          const anims = box.getAnimations({ subtree: true }).filter((a) => /^atl-blink-/.test(a.animationName));
          for (const a of anims) a.pause();
          const rect = (el) => { const b = el.getBoundingClientRect(); return [b.left, b.top, b.right, b.bottom]; };
          const width = (el) => parseFloat(getComputedStyle(el).strokeWidth) * Math.hypot(el.getScreenCTM().a, el.getScreenCTM().b);
          const out = { frames: 0, outside: 0, browMove: 0, strokeSpread: 0, foot: 0, covered: true };
          const sides = ['l', 'r'];
          const brow0 = sides.map((s) => rect(fig.querySelector(`.atl-layer-body .atl-brow-${s}`)));
          const widths = {};
          for (let t = 0; t <= ms; t += 16) {
            for (const a of anims) a.currentTime = t;
            out.frames += 1;
            for (const [k, s] of sides.entries()) {
              const eye = rect(fig.querySelector(`.atl-layer-body .atl-eye-${s} .atl-sclera`));
              const m = (eye[2] - eye[0]) / 3;
              const lidEye = lids.querySelector(`.atl-eye-${s}`);
              const clipEl = document.querySelector(`#atl-${look}-lid${s}`);
              //: The clip's box in screen px: its shapes through the lid eye
              //: group's own matrix.
              const cm = lidEye.getScreenCTM();
              const cb = [...clipEl.children].map((c) => c.getBBox()).reduce((a, b) => [Math.min(a[0], b.x), Math.min(a[1], b.y), Math.max(a[2], b.x + b.width), Math.max(a[3], b.y + b.height)], [1e9, 1e9, -1e9, -1e9]);
              const corners = [[cb[0], cb[1]], [cb[2], cb[1]], [cb[0], cb[3]], [cb[2], cb[3]]].map(([x, y]) => new DOMPoint(x, y).matrixTransform(cm));
              const clip = [Math.min(...corners.map((p) => p.x)), Math.min(...corners.map((p) => p.y)), Math.max(...corners.map((p) => p.x)), Math.max(...corners.map((p) => p.y))];
              const parts = [lidEye.querySelector('.atl-lid-edge'), lidEye.querySelector('.atl-lid-lashes path')].filter(Boolean);
              for (const el of parts) {
                const r = rect(el);
                const vis = [Math.max(r[0], clip[0]), Math.max(r[1], clip[1]), Math.min(r[2], clip[2]), Math.min(r[3], clip[3])];
                const shown = el.closest('.atl-lid-lashes') ? +getComputedStyle(el.closest('.atl-lid-lashes')).opacity > 0.05 : true;
                if (shown && vis[2] > vis[0] && vis[3] > vis[1]) {
                  const past = Math.max(eye[0] - m - vis[0], vis[2] - (eye[2] + m), eye[1] - m - vis[1], vis[3] - (eye[3] + m), 0);
                  out.outside = Math.max(out.outside, past);
                }
                const key = `${s}-${el.getAttribute('class')}`;
                (widths[key] ||= []).push(width(el));
              }
              (widths[`${s}-brow`] ||= []).push(width(fig.querySelector(`.atl-layer-body .atl-brow-${s} path`)));
              const b = rect(fig.querySelector(`.atl-layer-body .atl-brow-${s}`));
              out.browMove = Math.max(out.browMove, ...b.map((v, i) => Math.abs(v - brow0[k][i])));
              const shutAt = mood === 'drowsy' ? 380 : 120;
              if (Math.abs(t - shutAt) < 8) {
                if (!(clip[0] <= eye[0] + 0.3 && clip[1] <= eye[1] + 0.3 && clip[2] >= eye[2] - 0.3 && clip[3] >= eye[3] - 0.3)) { out.covered = false; out.cov = [s, ...eye, ...clip].map((v) => (typeof v === "number" ? +v.toFixed(1) : v)).join(" "); }
                const edge = rect(lidEye.querySelector('.atl-lid-edge'));
                out.foot = Math.max(out.foot, Math.abs(edge[3] - eye[3]) / (eye[3] - eye[1]));
              }
            }
          }
          out.strokeSpread = Math.max(...Object.values(widths).map((v) => Math.max(...v) - Math.min(...v)));
          //: The shut frame, for the pixels: the upper liner's points, and
          //: points 1.2 units further from the eye's middle (the lid's skin).
          for (const a of anims) a.currentTime = mood === 'drowsy' ? 600 : 140;
          out.dbg = [getComputedStyle(lids).opacity, getComputedStyle(lids.querySelector('.atl-lid-sweep')).translate, anims.map((a) => a.playState + a.currentTime).join(',')].join(' | ');
          const bx = box.getBoundingClientRect();
          const pts = [];
          for (const s of sides) {
            const liner = fig.querySelector(`.atl-layer-body .atl-eye-${s} .atl-liner:not(.atl-liner-low)`);
            const m = liner.getScreenCTM();
            const n = liner.getTotalLength();
            const sclera = fig.querySelector(`.atl-layer-body .atl-eye-${s} .atl-sclera`).getBBox();
            const c = [sclera.x + sclera.width / 2, sclera.y + sclera.height / 2];
            for (let i = 2; i <= 10; i += 1) {
              const q = liner.getPointAtLength((n * i) / 12);
              const d = Math.hypot(q.x - c[0], q.y - c[1]) || 1;
              const p = new DOMPoint(q.x, q.y).matrixTransform(m);
              const o = new DOMPoint(q.x + ((c[0] - q.x) / d) * 1.4, q.y + ((c[1] - q.y) / d) * 1.4).matrixTransform(m);
              pts.push([Math.round((p.x - bx.left) * 6), Math.round((p.y - bx.top) * 6)], [Math.round((o.x - bx.left) * 6), Math.round((o.y - bx.top) * 6)]);
            }
          }
          out.pts = pts;
          return out;
        }, [look, pose, mood]);
        if (!got) continue;
        if (process.env.DBG) console.log(look, pose, mood, got.dbg);
        const file = `${SCRATCH}/atlasluster-blink.png`;
        await (await page.$('#luster-box')).screenshot({ path: file });
        //: The same frame with the open eyes taken out of the body layer:
        //: what a shut eye should look like there (the face's own skin),
        //: and the points that differ by more than 20 in luminance.
        await page.evaluate(() => { for (const el of document.querySelectorAll('#luster-box .atl-layer-body .atl-eye')) el.style.visibility = 'hidden'; });
        const bare = `${SCRATCH}/atlasluster-blink-bare.png`;
        await (await page.$('#luster-box')).screenshot({ path: bare });
        const lumOf = (f) => JSON.parse(execFileSync(PY, ['-c', RGB, f, JSON.stringify(got.pts)]).toString()).map(([r, g, b]) => 0.2126 * r + 0.7152 * g + 0.0722 * b);
        const lum = lumOf(file);
        const ref = lumOf(bare);
        let showing = 0;
        for (let i = 0; i < lum.length; i += 1) if (Math.abs(lum[i] - ref[i]) > 20) showing += 1;
        res.cases += 1;
        res.frames += got.frames;
        if (got.outside > res.outside) res.outsideAt = `${look} ${pose} ${mood}`;
        res.outside = Math.max(res.outside, +got.outside.toFixed(2));
        if (!got.covered) res.uncovered.push(`${look} ${pose} ${mood} ${got.cov}`);
        res.footMax = Math.max(res.footMax, +got.foot.toFixed(2));
        res.browMove = Math.max(res.browMove, +got.browMove.toFixed(3));
        res.strokeSpread = Math.max(res.strokeSpread, +got.strokeSpread.toFixed(3));
        res.linerShowing += showing;
        res.linerSamples += lum.length;
        if ((showing || got.outside > 0.05) && res.worst.length < 8) res.worst.push({ look, pose, mood, showing, outside: +got.outside.toFixed(2) });
      }
    }
  }
  await page.evaluate(() => localStorage.removeItem('atlas-look'));
  await browser.close();
  return res;
}

//: INBOX 554, 564: the rig through a run of transitions, both looks, in
//: the companion (motion on), each step held 1.1s while every frame is
//: recorded (`atlasState.rigTrace`, and the arms' and held arms' opacity):
//: - perFrame: the largest change of any joint in one frame (deg, scaled
//:   to 16.7ms), and `jerk`, the largest ratio of a frame's change to the
//:   frame before's where that one moved over 0.5 (a pop is a spike);
//: - settle: the longest time from a change to the rig going quiet;
//: - flicker: limbs whose shown state (opacity over 0.5) changed more than
//:   once in a step (0);
//: - head: the largest lag of the head behind a change of pose (deg);
//: - swing: while travelling, the correlation of the two shoulders' swing
//:   (near -1 is counter-phase).
const RIG_STEPS = [
  ['sit', 'sit', []], ['stand', 'stand', []], ['float', 'float', []], ['hang', 'hang', []], ['stand2', 'stand', []],
  ['wave', 'stand', ['nmb-act-wave']], ['rest', 'stand', []], ['fold', 'stand', ['nmb-act-fold']], ['clasp', 'stand', ['nmb-act-clasp']],
  ['map', 'stand', ['nmb-act-map']], ['shrug', 'stand', ['nmb-act-shrug']], ['bell', 'stand', ['nmb-act-bell']], ['lie', 'lie', []],
  ['stand3', 'stand', []], ['walk', 'stand', ['nmb-walking']], ['stop', 'stand', []],
];
async function rigPart() {
  const { browser, page } = await boot({ viewport: { width: 520, height: 700 } });
  await page.evaluate(() => { document.documentElement.dataset.avatarMotion = 'always'; });
  const res = {};
  for (const look of ['feminine', 'masculine']) {
    await mountFigure(page, look);
    await page.waitForTimeout(800);
    const steps = [];
    for (const [label, pose, classes] of RIG_STEPS) {
      const got = await page.evaluate(async ([pose, classes]) => {
        const buddy = document.getElementById('nm-buddy');
        atlasState.rigTrace = [];
        const shown = [];
        let on = true;
        const sample = () => {
          if (!on) return;
          const row = {};
          for (const s of ['l', 'r']) {
            row[`arm-${s}`] = +getComputedStyle(buddy.querySelector(`.atl-layer-body .nmb-arm-${s}.atl-rigged`)).opacity;
            row[`hold-${s}`] = +getComputedStyle(buddy.querySelector(`.atl-layer-body .nmb-hold-${s}`)).opacity;
          }
          shown.push(row);
          requestAnimationFrame(sample);
        };
        requestAnimationFrame(sample);
        const t0 = performance.now();
        buddy.className = classes.join(' ');
        if (pose === 'stand') delete buddy.dataset.pose; else buddy.dataset.pose = pose;
        let quietAt = 0;
        const box = buddy.querySelector('.atl-figure-box');
        for (let i = 0; i < 66; i += 1) {
          await new Promise((r) => requestAnimationFrame(r));
          if (!box.hasAttribute('data-atl-moving') && !quietAt && performance.now() - t0 > 60) quietAt = performance.now() - t0;
          if (box.hasAttribute('data-atl-moving')) quietAt = 0;
        }
        on = false;
        const trace = atlasState.rigTrace;
        atlasState.rigTrace = null;
        return { trace, shown, settle: quietAt || 1100 };
      }, [pose, classes]);
      //: Per joint, per frame.
      let perFrame = 0;
      let jerk = 0;
      let head = 0;
      const series = {};
      for (const [t, , side, sh, el, wr] of got.trace) {
        if (side === 'head') { head = Math.max(head, Math.abs(sh)); continue; }
        (series[side] ||= []).push([t, sh, el, wr]);
      }
      for (const rows of Object.values(series)) {
        for (let k = 1; k <= 3; k += 1) {
          let prev = null;
          for (let i = 1; i < rows.length; i += 1) {
            const dt = Math.max(1, rows[i][0] - rows[i - 1][0]);
            const d = (Math.abs(rows[i][k] - rows[i - 1][k]) * 16.7) / dt;
            perFrame = Math.max(perFrame, d);
            if (prev !== null && prev > 0.5) jerk = Math.max(jerk, d / prev);
            prev = d;
          }
        }
      }
      let flicker = 0;
      for (const key of ['arm-l', 'arm-r', 'hold-l', 'hold-r']) {
        let flips = 0;
        for (let i = 1; i < got.shown.length; i += 1) if ((got.shown[i][key] > 0.5) !== (got.shown[i - 1][key] > 0.5)) flips += 1;
        if (flips > 1) flicker += 1;
      }
      const step = { label, frames: got.trace.length, perFrame: +perFrame.toFixed(1), jerk: +jerk.toFixed(1), settle: Math.round(got.settle), flicker, head: +head.toFixed(1) };
      if (label === 'walk') {
        const l = (series.l || []).map((r) => r[1]);
        const r = (series.r || []).map((r) => r[1]);
        const n = Math.min(l.length, r.length);
        const mean = (a) => a.reduce((x, y) => x + y, 0) / a.length;
        const ml = mean(l.slice(0, n));
        const mr = mean(r.slice(0, n));
        let sxy = 0; let sxx = 0; let syy = 0;
        for (let i = Math.floor(n / 3); i < n; i += 1) { sxy += (l[i] - ml) * (r[i] - mr); sxx += (l[i] - ml) ** 2; syy += (r[i] - mr) ** 2; }
        //: The shoulders' screen angles: one arm swinging forward (one
        //: way round) as the other swings back (the other way) is -1.
        step.swing = +(sxy / Math.sqrt(sxx * syy || 1)).toFixed(2);
      }
      steps.push(step);
    }
    res[look] = {
      perFrameMax: Math.max(...steps.map((s) => s.perFrame)),
      jerkMax: Math.max(...steps.map((s) => s.jerk)),
      settleMax: Math.max(...steps.map((s) => s.settle)),
      flicker: steps.reduce((a, s) => a + s.flicker, 0),
      headMax: Math.max(...steps.map((s) => s.head)),
      steps,
    };
  }
  await page.evaluate(() => localStorage.removeItem('atlas-look'));
  await browser.close();
  return res;
}

//: INBOX 554: the wave down her tail, in the companion standing, motion on.
//: Every animation is stepped together over one whole cycle of the tail's
//: sway (16.6s, the 8.3s alternate), 0.2s at a time; at each step a point
//: on the root half (t 0.3) and one on the tip half (t 0.85) are read off
//: their own layers in screen px: each half's heading (root to joint,
//: joint to tip point). Each
//: angle's phase at the cycle's fundamental (a one-bin DFT): `lagDeg` is
//: how far the tip's phase is behind the root's (positive: the sway runs
//: tipward), `amp` each one's swing in degrees. `seam` is the largest gap
//: between the two halves' centrelines at the joint over the cycle, px.
async function wavePart() {
  const { browser, page } = await boot({ viewport: { width: 520, height: 700 } });
  await page.evaluate(() => { document.documentElement.dataset.avatarMotion = 'always'; });
  await mountFigure(page, 'feminine');
  await page.waitForTimeout(600);
  const got = await page.evaluate(() => {
    const box = document.querySelector('#luster-box .atl-figure-box');
    const anims = [box, ...box.querySelectorAll('*')].flatMap((el) => el.getAnimations());
    for (const a of anims) a.pause();
    const base = box.querySelector('svg.atl-layer-tail:not(.atl-layer-tail-tip) .atl-fills .atl-tail-swish > .atl-skin');
    const tip = box.querySelector('svg.atl-layer-tail-tip .atl-fills .atl-tail-swish > .atl-skin');
    if (!tip) return null;
    const segs = ATLAS_LOOKS.feminine.tailSegsNow;
    const at = (el, t) => { const [x, y] = atlasSegsAt(segs, t); const p = new DOMPoint(x, y).matrixTransform(el.getScreenCTM()); return [p.x, p.y]; };
    const rows = [];
    for (let ms = 2200; ms <= 18800; ms += 200) {
      for (const a of anims) a.currentTime = ms;
      const root = at(base, 0);
      const b = at(base, 0.3);
      const t = at(tip, 0.85);
      const jb = at(base, ATLAS_LOOKS.feminine.tailWave.t);
      const jt = at(tip, ATLAS_LOOKS.feminine.tailWave.t);
      const ang = (p) => (Math.atan2(p[1] - root[1], p[0] - root[0]) * 180) / Math.PI;
      //: Each half's heading: the root half from the root to the joint, the
      //: tip half from the joint to its point (both read off their own layer).
      const dir = (p, q) => (Math.atan2(q[1] - p[1], q[0] - p[0]) * 180) / Math.PI;
      rows.push([ms, dir(root, jb), dir(jt, t), Math.hypot(jb[0] - jt[0], jb[1] - jt[1])]);
    }
    return rows;
  });
  await browser.close();
  if (!got) return { note: 'no tip layer' };
  const fit = (k) => {
    const n = got.length - 1;
    let c = 0; let s = 0;
    const mean = got.slice(0, n).reduce((a, r) => a + r[k], 0) / n;
    for (let i = 0; i < n; i += 1) { const w = (2 * Math.PI * got[i][0]) / 16600; c += (got[i][k] - mean) * Math.cos(w); s += (got[i][k] - mean) * Math.sin(w); }
    return { phase: (Math.atan2(s, c) * 180) / Math.PI, amp: (2 * Math.hypot(c, s)) / n };
  };
  const b = fit(1);
  const t = fit(2);
  let lag = b.phase - t.phase;
  while (lag < -180) lag += 360;
  while (lag > 180) lag -= 360;
  return { lagDeg: +(-lag).toFixed(1), amp: { root: +b.amp.toFixed(2), tip: +t.amp.toFixed(2) }, seam: +Math.max(...got.map((r) => r[3])).toFixed(2) };
}

//: INBOX 575: the lower body by state, both looks, motion on. Each state is
//: set on the companion (its pose, an act class or the mood) and each of
//: its variants forced in turn; once settled (1.3s), the silhouette of the
//: dress or cloak, the tail, the hair and the nebula stream (each part's
//: fill shapes through their own screen matrices, painted into a canvas)
//: is kept. Per part, `between`: the largest IoU between two states' first
//: variants, and how many state pairs differ (IoU under 0.97); `within`:
//: the largest IoU between two variants of one state (repeats differ);
//: `perFrame`, `jerk`: the lower joints through each change of state.
const LOWER_STATES = [
  ['idle', {}], ['walk', { cls: ['nmb-walking'] }], ['sit', { pose: 'sit' }], ['lie', { pose: 'lie' }],
  ['gesture', { cls: ['nmb-act-wave'] }], ['think', { cls: ['nmb-think'] }], ['happy', { mood: 'happy' }],
  ['sad', { mood: 'sad' }], ['startle', { cls: ['nmb-act-startle'] }],
];
async function lowerPart() {
  const { browser, page } = await boot({ viewport: { width: 520, height: 700 } });
  await page.evaluate(() => { document.documentElement.dataset.avatarMotion = 'always'; });
  const res = {};
  for (const look of ['feminine', 'masculine']) {
    await mountFigure(page, look);
    await page.waitForTimeout(700);
    const masks = {};
    let perFrame = 0;
    let jerk = 0;
    for (const [state, set] of LOWER_STATES) {
      const n = await page.evaluate(([state, set]) => {
        const buddy = document.getElementById('nm-buddy');
        buddy.className = (set.cls || []).join(' ');
        if (set.pose) buddy.dataset.pose = set.pose; else delete buddy.dataset.pose;
        for (const svg of buddy.querySelectorAll('svg.atl-layer')) atlasApply(svg, set.mood || 'calm');
        return ATLAS_LOWER_STATES[state].v.length;
      }, [state, set]);
      for (let k = 0; k < n; k += 1) {
        const got = await page.evaluate(async ([state, k]) => {
          const box = document.querySelector('#luster-box .atl-figure-box');
          const rig = box.atlasRig;
          rig.lower.state = state;
          rig.lower.variant = k;
          rig.lower.at = performance.now() + 60000;
          atlasRigWake(box);
          //: Every frame of the change: the dress's and the tail's turn, as
          //: the compositor has them (their computed transform).
          const ang = (el) => { const m = /matrix\(([^)]+)\)/.exec(getComputedStyle(el).transform); if (!m) return 0; const [a, b] = m[1].split(',').map(Number); return (Math.atan2(b, a) * 180) / Math.PI; };
          const lowEl = box.querySelector('.atl-lw-pose-lower');
          const tailEl = box.querySelector('.atl-lw-pose-tail');
          const trace = [];
          const t0 = performance.now();
          while (performance.now() - t0 < 1300) {
            await new Promise((r) => requestAnimationFrame(r));
            trace.push([performance.now(), 0, 0, lowEl ? ang(lowEl) : 0, 0, tailEl ? ang(tailEl) : 0]);
          }
          const at = document.getElementById('luster-box').getBoundingClientRect();
          //: Each flowing part's silhouette on its own canvas.
          const parts = {
            lower: '.atl-layer-lower .atl-fills :is(.atl-sower-fill, .atl-ribbon-veil)',
            tail: '.atl-layer-tail .atl-fills .atl-tail-swish > .atl-skin',
            hair: '.atl-layer-hair .atl-fills .atl-mane > .atl-lock, .atl-layer-hair .atl-mane > .atl-lock',
            stream: ':is(.atl-layer-neb, .atl-layer-neb-front) .atl-band-fill',
          };
          const bits = {};
          for (const [part, sel] of Object.entries(parts)) {
            const c = document.createElement('canvas'); c.width = 160; c.height = 170;
            const ctx = c.getContext('2d');
            for (const el of box.querySelectorAll(sel)) {
              const m = el.getScreenCTM();
              ctx.setTransform(m.a, m.b, m.c, m.d, m.e - at.left, m.f - at.top);
              ctx.fill(new Path2D(el.getAttribute('d')));
            }
            const data = ctx.getImageData(0, 0, 160, 170).data;
            const row = [];
            for (let i = 3; i < data.length; i += 4) row.push(data[i] > 128 ? 1 : 0);
            bits[part] = row.join('');
          }
          return { trace, bits };
        }, [state, k]);
        masks[`${state}-${k}`] = got.bits;
        let prev = null;
        for (let i = 1; i < got.trace.length; i += 1) {
          const dt = Math.max(1, got.trace[i][0] - got.trace[i - 1][0]);
          const d = Math.max(Math.abs(got.trace[i][3] - got.trace[i - 1][3]), Math.abs(got.trace[i][5] - got.trace[i - 1][5])) * 16.7 / dt;
          perFrame = Math.max(perFrame, d);
          if (prev !== null && prev > 0.5) jerk = Math.max(jerk, d / prev);
          prev = d;
        }
      }
    }
    const iou = (a, b) => { let i = 0; let u = 0; for (let k = 0; k < a.length; k += 1) { const x = a[k] === '1'; const y = b[k] === '1'; if (x && y) i += 1; if (x || y) u += 1; } return u ? i / u : 1; };
    const keys = Object.keys(masks);
    const out = { perFrame: +perFrame.toFixed(2), jerk: +jerk.toFixed(1) };
    //: Per part: the largest IoU between two states (first variants) and
    //: the share of state pairs it differs in (IoU under 0.97), and the
    //: largest IoU between two variants of one state.
    for (const part of ['lower', 'tail', 'hair', 'stream']) {
      let between = 0; let within = 0; let pairs = 0; let differ = 0;
      for (let a = 0; a < keys.length; a += 1) {
        for (let b = a + 1; b < keys.length; b += 1) {
          const [sa, va] = keys[a].split('-');
          const [sb, vb] = keys[b].split('-');
          const v = iou(masks[keys[a]][part], masks[keys[b]][part]);
          if (sa === sb) within = Math.max(within, v);
          else if (va === '0' && vb === '0') { between = Math.max(between, v); pairs += 1; if (v < 0.97) differ += 1; }
        }
      }
      out[part] = { between: +between.toFixed(3), statePairsDiffer: `${differ}/${pairs}`, within: +within.toFixed(3) };
    }
    res[look] = out;
  }
  await page.evaluate(() => localStorage.removeItem('atlas-look'));
  await browser.close();
  return res;
}

//: INBOX 577 (the owner: "when loading into the app, the companion or
//: atlas's head goes large then small then large again then settles"): the
//: head's size through the first 2s after the figure is put on the page,
//: both looks, motion on, every frame: its scale over the figure box's
//: (so the companion's own entrance, which moves or scales the whole
//: figure, does not count), as the largest change over the smallest, in
//: percent (under 1), and the whole figure's scale (smallest, largest,
//: last). Once in the harness and once as the app's own companion.
async function mountPart() {
  const out = {};
  for (const look of ['feminine', 'masculine']) {
    for (const where of ['harness', 'companion']) {
      const { browser, page } = await boot({ viewport: { width: 1280, height: 800 } });
      await page.evaluate((look) => { document.documentElement.dataset.avatarMotion = 'always'; localStorage.setItem('atlas-look', look); }, look);
      const got = await page.evaluate(async (where) => {
        let fig;
        if (where === 'harness') {
          document.getElementById('nm-buddy')?.remove();
          const holder = document.createElement('div'); holder.id = 'nm-buddy';
          Object.assign(holder.style, { position: 'fixed', left: '200px', top: '200px', width: '64px', height: '92px', zIndex: '9999' });
          fig = atlasFigure(); Object.assign(fig.style, { position: 'relative', display: 'block', width: '64px', height: '92px' });
          holder.append(fig); document.body.append(holder);
        } else {
          document.getElementById('nm-buddy')?.remove();
          localStorage.setItem('avatar-buddy', 'persona');
          syncNameMarkBuddy();
        }
        const rows = [];
        const t0 = performance.now();
        while (performance.now() - t0 < 2000) {
          await new Promise((r) => requestAnimationFrame(r));
          const box = document.querySelector('#nm-buddy .atl-figure-box');
          const head = box && [...box.querySelectorAll('.atl-layer-body .atl-head .atl-skin')].find((p) => p.getAttribute('d') === ATLAS_HEAD_PATH);
          if (!head) continue;
          //: The head's own scale (the square root of its screen matrix's
          //: determinant: a turn does not change it, as it would a box's
          //: height) over its layer root's, so whatever scales the whole
          //: figure (the companion's entrance) is taken out.
          const det = (el) => { const m = el.getScreenCTM(); return Math.sqrt(Math.abs(m.a * m.d - m.b * m.c)); };
          const root = box.querySelector('.atl-layer-body');
          rows.push(det(head) / det(root));
          //: And the whole figure's scale, for the report.
          (window.__figScale ||= []).push(det(root));
        }
        const scales = window.__figScale || [];
        window.__figScale = [];
        return { rows, fig: scales.length ? [Math.min(...scales), Math.max(...scales), scales[scales.length - 1]].map((v) => +v.toFixed(3)) : [] };
      }, where);
      await browser.close();
      const figure = got.fig;
      const rows = got.rows;
      const max = Math.max(...rows);
      const min = Math.min(...rows);
      out[`${look}-${where}`] = { frames: rows.length, changePct: rows.length ? +((100 * (max - min)) / min).toFixed(2) : null, figureScaleMinMaxLast: figure, ...(process.env.SERIES ? { series: rows.filter((_, i) => i % 3 === 0).map((v) => +v.toFixed(4)) } : {}) };
    }
  }
  return out;
}

(async () => {
  const out = {};
  if (PARTS.includes('mount')) out.mount = await mountPart();
  if (PARTS.includes('lower')) out.lower = await lowerPart();
  if (PARTS.includes('wave')) out.wave = await wavePart();
  if (PARTS.includes('rig')) out.rig = await rigPart();
  if (PARTS.includes('blink')) out.blink = await blinkPart();
  if (PARTS.includes('arms')) out.arms = { now: await armsPart(false), ...(REF_DIR ? { before: await armsPart(true) } : {}) };
  if (PARTS.includes('hair')) out.hair = await hairPart();
  if (PARTS.includes('tail')) {
    out.tail = { now: await tailPart(false), ...(REF_DIR ? { before: await tailPart(true) } : {}) };
    if (out.tail.before) out.tail.lengthRatio = +(out.tail.now.length / out.tail.before.length).toFixed(2);
  }
  if (PARTS.includes('fringe')) out.fringe = await drawingPart(fringePart);
  if (PARTS.includes('wisps')) out.wisps = await drawingPart(wispsPart);
  if (PARTS.includes('dress')) out.dress = await dressPart();
  if (PARTS.includes('body')) out.body = { now: await bodyPart(false), ...(REF_DIR ? { before: await bodyPart(true) } : {}) };
  if (PARTS.includes('gap')) out.gap = await gapPart();
  if (PARTS.includes('masc')) out.masc = await mascPart();
  if (PARTS.includes('motion')) out.motion = await motionPart();
  if (PARTS.includes('cost')) out.cost = await costPart();
  console.log(JSON.stringify(out, null, 1));
})();
