// W31 E4, INBOX 1607 (the masculine Atlas, second pass): both looks in the live companion, pinned on a plain
// ground as atlasm1108.js does, at device scale SCALE, for
//   - poses: the 12 most used poses and acts plus the juggle, each with the rig's head, eye and lid numbers;
//   - angles: both arms forced to each of 8 angles the poses use, screenshotted twice (black and white ground,
//     so the Python can tell paint from ground) for the shoulder join;
//   - faces: the bust avatar in every mood at 40, 72 and 120 px.
// scratchpad/ui-sweeps/atlasm1111.py turns OUT into the numbers and the sheets.
//   BASE=http://127.0.0.1:PORT SCALE=4 OUT=dir node scratchpad/ui-sweeps/atlasm1111.js
const fs = require('fs');
const path = require('path');
const { boot } = require('./lib.js');
const SCALE = Number(process.env.SCALE || 4);
const OUT = process.env.OUT || 'cells';
const LOOKS = (process.env.LOOKS || 'masculine,feminine').split(',');
const PARTS = (process.env.PARTS || 'poses,angles,faces').split(',');
const BOX = { width: 400, height: 300, left: 120, top: 60 };
const CLIP = { x: BOX.left + 40, y: BOX.top + 30, width: 240, height: 230 };
const POSES = [
  ['stand', 'stand', ''], ['walk', 'stand', 'nmb-walking'], ['sit', 'sit', ''], ['float', 'float', ''],
  ['wave', 'stand', 'nmb-act-wave'], ['bell', 'stand', 'nmb-act-bell'], ['shrug', 'stand', 'nmb-act-shrug'],
  ['hips', 'stand', 'nmb-act-hips'], ['read', 'stand', 'nmb-act-read'], ['clasp', 'stand', 'nmb-act-clasp'],
  ['chair', 'sit', 'nmb-act-chair'], ['meditate', 'float', 'nmb-act-meditate'], ['juggle', 'stand', 'nmb-act-juggle'],
];
const ANGLES = [0, 13, 28, 40, 70, 100, 120, 130];

const MEASURE = () => {
  const b = document.getElementById('nm-buddy');
  const r = (el) => { if (!el) return null; const q = el.getBoundingClientRect(); return [q.x, q.y, q.width, q.height].map((v) => +v.toFixed(2)); };
  const head = b.querySelector('.atl-head .atl-sway > path.atl-skin');
  const cap = b.querySelector('.atl-head .atl-hair-cap');
  const scl = [...b.querySelectorAll('.atl-eye .atl-sclera')];
  const iris = [...b.querySelectorAll('.atl-eye .atl-iris-fill')];
  const lids = [...b.querySelectorAll('.atl-eye .atl-lid > path.atl-skin')];
  const lows = [...b.querySelectorAll('.atl-eye .atl-lid-low > path.atl-skin')];
  const inks = [...b.querySelectorAll('.atl-eye .atl-ink')];
  // The iris's top against the white's upper edge straight above it, and the lid's edge there, in px.
  const eyes = scl.map((s, i) => {
    const ir = iris[i].getBoundingClientRect(); const sr = s.getBoundingClientRect();
    const cx = ir.x + ir.width / 2;
    let top = null;
    const m = s.getScreenCTM(); const inv = m.inverse();
    for (let y = sr.y - 2; y < sr.bottom; y += 0.1) {
      const p = new DOMPoint(cx, y).matrixTransform(inv);
      if (s.isPointInFill(p)) { top = y; break; }
    }
    const lr = lids[i] ? lids[i].getBoundingClientRect() : null;
    const lo = lows[i] ? lows[i].getBoundingClientRect() : null;
    return { sclera: r(s), iris: r(iris[i]), scleraTopAtIris: top && +top.toFixed(2), irisTop: +ir.y.toFixed(2), inkTop: inks[i] ? +inks[i].getBoundingClientRect().y.toFixed(2) : null, lidBottom: lr && +lr.bottom.toFixed(2), lowTop: lo && +lo.y.toFixed(2), lidOp: lids[i] && getComputedStyle(lids[i].closest('.atl-lid')).opacity };
  });
  const arms = [...b.querySelectorAll('.atl-fills .nmb-arm > path.atl-skin')];
  const torso = b.querySelector('.atl-fills .nmb-torso path.atl-skin') || b.querySelector('.nmb-torso path.atl-skin');
  const outline = (el, n = 240) => { if (!el) return []; const m = el.getScreenCTM(); const L = el.getTotalLength(); const o = []; for (let i = 0; i <= n; i++) { const p = el.getPointAtLength(L * i / n); o.push([+(m.a * p.x + m.c * p.y + m.e).toFixed(2), +(m.b * p.x + m.d * p.y + m.f).toFixed(2)]); } return o; };
  // Each arm's root in screen px (its path's first point).
  const roots = arms.map((a) => { const m = a.getScreenCTM(); const p = a.getPointAtLength(0); return [m.a * p.x + m.c * p.y + m.e, m.b * p.x + m.d * p.y + m.f]; });
  return { head: r(head), cap: r(cap), eyes, arms: arms.map(r), roots, armOutlines: arms.map((a) => outline(a)), torsoOutline: outline(torso), unit: head ? +head.getScreenCTM().a.toFixed(3) : 0 };
};

async function pinned(page, look) {
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
      'html.__ground-w, html.__ground-w body { background: #fff !important; }',
    ]) sheet.insertRule(rule, sheet.cssRules.length);
    sheet.insertRule('html, html body { background: #000 !important; }', sheet.cssRules.length);
    for (const el of document.body.children) put(el, { visibility: 'hidden' });
    for (const el of document.querySelectorAll('mask, clipPath')) put(el, { visibility: 'visible' });
    window.__pin = `translate(${box.left + 78}px, ${box.top + 80}px)`;
    put(b, { transform: window.__pin, visibility: 'visible' });
    const realSet = CSSStyleDeclaration.prototype.setProperty;
    Object.defineProperty(b.style, 'transform', { get: () => window.__pin, set: () => {}, configurable: true });
    b.style.setProperty = function (k, v, pr) { if (k !== 'transform') realSet.call(this, k, v, pr); };
    window.__mood = setAtlasMood; window.setAtlasMood = () => {};
    window.__want = 'stand'; window.__cls = '';
    new MutationObserver(() => {
      for (const n of ['data-perch', 'data-legs', 'data-side']) if (b.hasAttribute(n)) b.removeAttribute(n);
      if (b.dataset.pose !== window.__want) b.dataset.pose = window.__want;
      const want = window.__cls; if (b.className !== want) b.className = want;
    }).observe(b, { attributes: true, attributeFilter: ['data-pose', 'data-perch', 'data-legs', 'data-side', 'class'] });
  }, BOX);
}

async function hold(page) {
  await page.waitForTimeout(1300);
  await page.evaluate(() => { for (const a of document.getAnimations()) { if (a.transitionProperty) { a.finish(); continue; } a.pause(); if (a.animationName && /blink/.test(a.animationName)) a.currentTime = 0; } });
  await page.waitForTimeout(80);
}

async function shoot(page, file, both) {
  await page.screenshot({ path: file, clip: CLIP });
  if (!both) return;
  await page.evaluate(() => document.documentElement.classList.add('__ground-w'));
  await page.screenshot({ path: file.replace(/\.png$/, '-w.png'), clip: CLIP });
  await page.evaluate(() => document.documentElement.classList.remove('__ground-w'));
}

(async () => {
  const { browser, page } = await boot({ viewport: { width: 700, height: 500 }, scale: SCALE, clock: '2026-10-27T14:00:00' });
  const report = { scale: SCALE, clip: CLIP };
  for (const look of LOOKS) {
    report[look] = { poses: {}, angles: {}, faces: {} };
    fs.mkdirSync(path.join(OUT, look), { recursive: true });
    await pinned(page, look);
    const set = (pose, cls, mood, angle) => page.evaluate(([pose, cls, mood, angle]) => {
      const b = document.getElementById('nm-buddy');
      for (const n of b.getAttributeNames()) if (n.startsWith('data-') && !['data-gait', 'data-seed', 'data-atlas-variant'].includes(n)) b.removeAttribute(n);
      window.__cls = cls; b.className = cls;
      window.__want = pose; b.dataset.pose = pose; b.dataset.feel = 'calm';
      for (const el of b.querySelectorAll('.nmb-arm-l, .nmb-arm-r')) el.style.removeProperty('transform');
      if (angle !== null) {
        for (const el of b.querySelectorAll('.nmb-arm-l')) el.style.setProperty('transform', `rotate(${angle}deg)`, 'important');
        for (const el of b.querySelectorAll('.nmb-arm-r')) el.style.setProperty('transform', `rotate(${-angle}deg)`, 'important');
      }
      window.__mood(mood, 0, { quiet: true });
    }, [pose, cls, mood, angle]);
    if (PARTS.includes('poses')) for (const [name, pose, cls] of POSES) {
      await set(pose, cls, 'calm', null);
      await hold(page);
      await shoot(page, path.join(OUT, look, `pose-${name}.png`), false);
      report[look].poses[name] = await page.evaluate((fn) => new Function(`return (${fn})()`)(), MEASURE.toString());
      await page.evaluate(() => { for (const a of document.getAnimations()) a.play(); });
    }
    if (PARTS.includes('angles')) for (const a of ANGLES) {
      await set('stand', '', 'calm', a);
      await hold(page);
      await shoot(page, path.join(OUT, look, `angle-${a}.png`), true);
      report[look].angles[a] = await page.evaluate((fn) => new Function(`return (${fn})()`)(), MEASURE.toString());
      await page.evaluate(() => { for (const a of document.getAnimations()) a.play(); });
    }
    if (PARTS.includes('faces')) {
      const moods = await page.evaluate(() => Object.keys(ATLAS_MOODS));
      for (const px of [40, 72, 120]) {
        // A row of busts, one per mood, on a plain ground, each in its own cell.
        await page.evaluate(([moods, px]) => {
          let host = document.getElementById('__faces');
          if (host) host.remove();
          host = document.createElement('div'); host.id = '__faces';
          host.style.cssText = 'position:fixed;left:0;top:0;z-index:99999;display:flex;gap:8px;padding:8px;background:#1b1d2a;visibility:visible';
          for (const m of moods) { const s = atlasDraw(px, window.__moodNow = m, 'bust'); s.style.visibility = 'visible'; host.appendChild(s); }
          document.documentElement.appendChild(host);
        }, [moods, px]);
        await page.waitForTimeout(900);
        await page.evaluate(() => { for (const a of document.getAnimations()) { a.pause(); if (a.animationName && /blink/.test(a.animationName)) a.currentTime = 0; } });
        const boxes = await page.evaluate(() => [...document.querySelectorAll('#__faces > svg')].map((s) => { const q = s.getBoundingClientRect(); const h = s.querySelector('.atl-head .atl-sway > path.atl-skin').getBoundingClientRect(); return { cell: [q.x, q.y, q.width, q.height], head: [h.x, h.y, h.width, h.height] }; }));
        const w = Math.ceil(Math.max(...boxes.map((b) => b.cell[0] + b.cell[2])) + 8);
        await page.setViewportSize({ width: Math.max(700, w), height: 500 });
        await page.screenshot({ path: path.join(OUT, look, `faces-${px}.png`), clip: { x: 0, y: 0, width: w, height: px + 16 } });
        report[look].faces[px] = { moods, boxes };
        await page.setViewportSize({ width: 700, height: 500 });
        await page.evaluate(() => document.getElementById('__faces').remove());
      }
    }
  }
  fs.writeFileSync(path.join(OUT, 'measure.json'), JSON.stringify(report, null, 1));
  console.log('ok');
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
