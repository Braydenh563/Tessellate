// INBOX 669 (the owner: "when I click atlas, it often starts tilting to the
// left then just snaps back" / "in the enlarged view panel"; "atlas's arm
// movements are jerky and not smooth"). Opens the large view, clicks Atlas
// 20 times at varied intervals (single clicks, quick double clicks, a click
// mid-move) with real mouse clicks at the head, and samples every animation
// frame the screen-space angle and position of the head and each arm
// (getScreenCTM, so every wrapper's CSS transform counts), plus the local
// turn of each wrapper that moves the figure. Reports, per part, the
// largest step in a frame (degrees and px, scaled to a 60fps frame), and
// for the worst steps what changed on that frame (a class, the mood, an
// animation started or ended).
//   BASE=... CASES=buddy-m,buddy-f,atlas-m,atlas-f node atlas669-clicks.js
// Cases acts-float-m, acts-sit-f and the like play every act that moves an
// arm and every poke mood in the large view, in that pose and look.
// Exits 1 when a rotation steps over 4deg or a position over 3px a frame.
const { boot } = require('./lib.js');
const ALL = ['buddy-m', 'buddy-f', 'atlas-m', 'atlas-f'];
const CLICKS = [1500, 6500, 8500, 9000, 9110, 13000, 13090, 17000, 17700, 18400, 22500, 23800, 24000, 28500, 29200, 33000, 33140, 37500, 39000, 43000];
const END = 50000;
// The acts that move the arms, each played in turn (every other one cut
// short 700ms in by the next), then the poke moods, each of which sets the
// arms for its mood: in the large view, in the pose the case names.
const ARM_ACTS = ['wave', 'scratch', 'onehand', 'facepalm', 'shrug', 'cheer', 'startle', 'wake', 'bell', 'carry', 'lantern', 'hide', 'wiggle', 'hop'];
const MOODS = ['happy', 'delighted', 'laughing', 'love', 'curious', 'shy', 'surprised', 'worried', 'proud', 'confused', 'sad', 'calm'];
const ACT_PLAN = [];
{
  let t = 800;
  ARM_ACTS.forEach((a, i) => {
    ACT_PLAN.push([t, a]);
    if (i % 2) { ACT_PLAN.push([t + 700, ARM_ACTS[(i + 3) % ARM_ACTS.length]]); t += 3400; } else t += 2900;
  });
  for (const m of MOODS) { ACT_PLAN.push([t, 'mood:' + m]); t += 1500; }
  ACT_PLAN.push([t + 4000, 'mood:calm']);
}
const ACT_END = ACT_PLAN[ACT_PLAN.length - 1][0] + 3000;
const LIM_DEG = 4;
const LIM_PX = 3;

async function sampler(page) {
  await page.evaluate(() => {
    const S = (window.__s = { rows: [], ctx: [], stop: false });
    const root = () => document.querySelector('.nm-viewer .nm-viewer-figure') || document.getElementById('nm-buddy');
    const svgParts = {
      head: '.atl-layer-body .nm-buddy-head',
      armR: '.atl-layer-body .nmb-arm-r:not(.atl-arm-probe)',
      armL: '.atl-layer-body .nmb-arm-l:not(.atl-arm-probe)',
      // The body: its pose group, at a fixed point of its own (the
      // drawing's middle), so an arm can be measured against it.
      body: '.atl-layer-body .atl-pose',
    };
    const htmlParts = {
      face: '.nm-buddy-face',
      char: '.nm-buddy-char',
      box: '.atl-figure-box',
      lwBody: '.atl-lw-body',
      mood: '.atl-layer-body .atl-mood',
      pose: '.atl-layer-body .atl-pose',
    };
    const ang = (cs) => {
      let a = 0;
      const m = /matrix\(([^)]+)\)/.exec(cs.transform);
      if (m) { const [p, q] = m[1].split(',').map(Number); a = (Math.atan2(q, p) * 180) / Math.PI; }
      const r = parseFloat(cs.rotate);
      if (Number.isFinite(r)) a += r;
      return +a.toFixed(3);
    };
    const tr = (cs) => {
      let x = 0; let y = 0;
      const m = /matrix\(([^)]+)\)/.exec(cs.transform);
      if (m) { const v = m[1].split(',').map(Number); x += v[4]; y += v[5]; }
      if (cs.translate && cs.translate !== 'none') { const v = cs.translate.split(' ').map(parseFloat); x += v[0] || 0; y += v[1] || 0; }
      return [+x.toFixed(2), +y.toFixed(2)];
    };
    let lastCtx = '';
    const t0 = performance.now();
    S.t0 = t0;
    // Read after every frame callback has run (the rig draws the arms in
    // one), not inside this one: a callback registered before the rig's
    // read the rig's previous frame, so a 50ms frame's step was counted
    // against the next 16ms one. A message is the first task after the
    // frame; if another frame has begun by then, that sample is dropped.
    const port = new MessageChannel();
    let pending = 0;
    port.port1.onmessage = () => { const now = pending; pending = 0; if (document.timeline.currentTime === now) read(now); };
    const tick = (now) => {
      if (S.stop) return;
      pending = now;
      port.port2.postMessage(0);
      requestAnimationFrame(tick);
    };
    const read = (now) => {
      const r = root();
      if (r) {
        const row = { t: +(now - t0).toFixed(1) };
        for (const [k, sel] of Object.entries(svgParts)) {
          const el = r.querySelector(sel);
          if (!el || !el.getScreenCTM) continue;
          const m = el.getScreenCTM();
          let b; try { b = el.getBBox(); } catch (e) { b = { x: 0, y: 0, width: 0, height: 0 }; }
          const pt = (k === 'body' ? new DOMPoint(32, 46) : new DOMPoint(b.x + b.width / 2, b.y + b.height / 2)).matrixTransform(m);
          row[k] = [+((Math.atan2(m.b, m.a) * 180) / Math.PI).toFixed(3), +pt.x.toFixed(2), +pt.y.toFixed(2)];
        }
        for (const [k, sel] of Object.entries(htmlParts)) {
          const el = r.querySelector(sel);
          if (!el) continue;
          const cs = getComputedStyle(el);
          row[k] = [ang(cs), ...tr(cs)];
        }
        // Each arm's own turn at the shoulder, as drawn (the rig's output on
        // a layered figure; the stylesheet's elsewhere).
        for (const side of ['l', 'r']) {
          const a = r.querySelector(`.atl-layer-body .nmb-arm-${side}:not(.atl-arm-probe)`);
          if (a) row['arm' + side.toUpperCase() + 'Own'] = [ang(getComputedStyle(a)), 0, 0];
        }
        // Each probe: where the CSS has the arm (the rig's target).
        for (const side of ['l', 'r']) {
          const p = r.querySelector(`.atl-layer-body .atl-arm-probe.nmb-arm-${side}`);
          if (p) row['probe' + side.toUpperCase()] = [ang(getComputedStyle(p)), 0, 0];
        }
        const buddy = document.getElementById('nm-buddy');
        const box = r.querySelector('.atl-figure-box');
        const body = r.querySelector('.atl-layer-body');
        const anims = [];
        for (const el of [r.querySelector('.nm-buddy-face'), r.querySelector('.nm-buddy-char'), box, r.querySelector('.atl-lw-body'), r.querySelector('.atl-layer-body .atl-mood'), r.querySelector('.atl-layer-body .atl-pose'), r.querySelector('.atl-layer-body .nm-buddy-head'), r.querySelector('.atl-layer-body .atl-arm-probe.nmb-arm-r'), r.querySelector('.atl-layer-body .atl-arm-probe.nmb-arm-l')]) {
          if (!el) continue;
          for (const a of el.getAnimations()) anims.push((el.getAttribute('class') || '').split(' ')[0] + ':' + (a.animationName || a.id || 'anim') + '@' + a.playState);
        }
        const ctx = [
          buddy ? buddy.className : '',
          buddy ? buddy.dataset.pose || '' : '',
          box ? box.dataset.atlasMood + '/' + (box.dataset.atlasVariant || '') : '',
          body ? body.getAttribute('class') : '',
          anims.join(','),
        ].join(' | ');
        if (ctx !== lastCtx) { S.ctx.push([row.t, ctx]); lastCtx = ctx; }
        S.rows.push(row);
      }
    };
    requestAnimationFrame(tick);
  });
}

async function headPoint(page) {
  return page.evaluate(() => {
    const r = document.querySelector('.nm-viewer .nm-viewer-figure') || document.getElementById('nm-buddy');
    const h = r.querySelector('.atl-layer-body .nm-buddy-head') || r;
    const b = h.getBoundingClientRect();
    return [b.left + b.width / 2, b.top + b.height * 0.45];
  });
}

function analyse(rows, ctx) {
  // Each arm against the body (its turn at the shoulder and where its
  // middle is, the body's own move taken out): the arm's own motion.
  for (const r of rows) {
    for (const k of ['armR', 'armL']) if (r[k] && r.body) r[k + 'Rel'] = [r[k][0] - r.body[0], r[k][1] - r.body[1], r[k][2] - r.body[2]];
  }
  const parts = ['head', 'armR', 'armL', 'armROwn', 'armLOwn', 'armRRel', 'armLRel', 'body', 'face', 'char', 'box', 'lwBody', 'mood', 'pose', 'probeR', 'probeL'];
  const out = {};
  const steps = [];
  for (const k of parts) {
    let deg = 0; let px = 0; let degAt = 0; let pxAt = 0;
    for (let i = 1; i < rows.length; i += 1) {
      const a = rows[i - 1][k]; const b = rows[i][k];
      if (!a || !b) continue;
      // Scaled to a 60fps frame by the frames' own timestamps, so a long
      // frame on a loaded machine does not read as a jump, nor two quick
      // callbacks as smooth.
      const dt = Math.max(4, rows[i].t - rows[i - 1].t);
      const s = 16.67 / dt;
      let d = b[0] - a[0];
      while (d > 180) d -= 360;
      while (d < -180) d += 360;
      const dd = Math.abs(d) * s;
      const dp = Math.hypot(b[1] - a[1], b[2] - a[2]) * s;
      if (dd > deg) { deg = dd; degAt = rows[i].t; }
      if (dp > px) { px = dp; pxAt = rows[i].t; }
      if (['head', 'armR', 'armL', 'armROwn', 'armLOwn'].includes(k) && (dd > LIM_DEG || dp > LIM_PX)) steps.push({ k, t: rows[i].t, deg: +dd.toFixed(2), px: +dp.toFixed(2) });
    }
    out[k] = { deg: +deg.toFixed(2), degAt: Math.round(degAt), px: +px.toFixed(2), pxAt: Math.round(pxAt) };
  }
  const ctxAt = (t) => {
    let before = ''; let now = '';
    for (const [ct, c] of ctx) { if (ct < t) { before = now; now = c; } if (ct >= t - 0.01 && ct <= t + 0.01) { before = now; now = c; } }
    return now;
  };
  // The context change nearest before each big step (within 150ms).
  const why = (t) => {
    let i = ctx.findIndex(([ct]) => ct > t);
    if (i < 0) i = ctx.length;
    const prev = ctx[i - 1];
    const prev2 = ctx[i - 2];
    if (!prev || t - prev[0] > 150) return 'no change in 150ms';
    return `${Math.round(t - prev[0])}ms after: ${diff(prev2 ? prev2[1] : '', prev[1])}`;
  };
  steps.sort((a, b) => Math.max(b.deg / LIM_DEG, b.px / LIM_PX) - Math.max(a.deg / LIM_DEG, a.px / LIM_PX));
  return { parts: out, over: steps.length, worst: steps.slice(0, 8).map((s) => ({ ...s, why: why(s.t) })), ctxAt };
}

function diff(a, b) {
  const A = a.split(' | '); const B = b.split(' | ');
  const names = ['buddy', 'pose', 'mood', 'body', 'anims'];
  const res = [];
  for (let i = 0; i < B.length; i += 1) {
    if (A[i] === B[i]) continue;
    const x = new Set((A[i] || '').split(/[ ,]/)); const y = new Set((B[i] || '').split(/[ ,]/));
    const add = [...y].filter((v) => v && !x.has(v)); const rem = [...x].filter((v) => v && !y.has(v));
    res.push(`${names[i]} +[${add.join(' ')}] -[${rem.join(' ')}]`);
  }
  return res.join('; ') || 'same';
}

async function openCase(c) {
  const { browser, page } = await boot({ viewport: { width: 1280, height: 800 } });
  const look = c.endsWith('-f') ? 'feminine' : 'masculine';
  await page.evaluate((look) => { localStorage.setItem('atlas-look', look); document.documentElement.dataset.avatarMotion = 'always'; }, look);
  await page.evaluate(() => {
    localStorage.removeItem('nm-buddy-spots');
    const b = $('avatar-buddy');
    b.value = 'atlas';
    b.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await page.waitForTimeout(3500);
  return { browser, page };
}

// `node atlas669-clicks.js --analyse <dump.json>...`: the same report from
// a run's DUMP files, without a browser (a before and an after compared on
// one measure).
if (process.argv[2] === '--analyse') {
  for (const f of process.argv.slice(3)) {
    const { rows, ctx } = JSON.parse(require('fs').readFileSync(f));
    const res = analyse(rows, ctx);
    const keep = ['head', 'armR', 'armL', 'armROwn', 'armLOwn', 'char'];
    console.log(f.split('/').pop(), rows.length, 'frames', JSON.stringify(Object.fromEntries(keep.map((k) => [k, res.parts[k] && [res.parts[k].deg, res.parts[k].px]]))));
  }
  process.exit(0);
}

(async () => {
  const fails = [];
  const table = {};
  for (const c of (process.env.CASES || ALL.join(',')).split(',')) {
    const { browser, page } = await openCase(c);
    if (!c.startsWith('atlas')) {
      await page.evaluate(() => document.querySelector('#nm-buddy .nm-buddy-face').dispatchEvent(new MouseEvent('dblclick', { bubbles: true })));
    } else {
      await page.evaluate(() => openNameMarkViewer('Atlas'));
    }
    await page.waitForTimeout(1200);
    const acts = c.startsWith('acts-');
    if (acts) {
      // The pose named in the case, held: the companion's own state and
      // its attribute, as its pose code sets them.
      const pose = c.split('-')[1];
      await page.evaluate((pose) => { nmb.pose = pose; document.getElementById('nm-buddy').dataset.pose = pose; }, pose);
      await page.waitForTimeout(1200);
    }
    await sampler(page);
    const t0 = Date.now();
    const plan = acts ? ACT_PLAN : CLICKS.map((at) => [at, 'click']);
    for (const [at, what] of plan) {
      const wait = at - (Date.now() - t0);
      if (wait > 0) await page.waitForTimeout(wait);
      if (what === 'click') {
        const [x, y] = await headPoint(page);
        await page.mouse.click(x, y);
      } else if (what.startsWith('mood:')) {
        await page.evaluate((m) => setAtlasMood(m, 2200, { quiet: true, backEaseMs: 1200 }), what.slice(5));
      } else {
        await page.evaluate((a) => nameMarkBuddyAct(a), what);
      }
    }
    const rest = (acts ? ACT_END : END) - (Date.now() - t0);
    if (rest > 0) await page.waitForTimeout(rest);
    const { rows, ctx } = await page.evaluate(() => { window.__s.stop = true; return { rows: window.__s.rows, ctx: window.__s.ctx }; });
    const res = analyse(rows, ctx);
    delete res.ctxAt;
    table[c] = res.parts;
    console.log(`\n${c}: ${rows.length} frames, ${res.over} steps over the limit`);
    for (const [k, v] of Object.entries(res.parts)) console.log(`  ${k.padEnd(7)} ${String(v.deg).padStart(7)}deg @${v.degAt}  ${String(v.px).padStart(7)}px @${v.pxAt}`);
    for (const w of res.worst) console.log(`  worst ${w.k} ${w.deg}deg ${w.px}px @${Math.round(w.t)}: ${w.why}`);
    if (process.env.DUMP) require('fs').writeFileSync(`${process.env.DUMP}-${c}.json`, JSON.stringify({ rows, ctx }));
    // A click: the whole figure, as seen. The acts: each arm's own move
    // (a hop or a cheer moves the whole body as fast as it is drawn to;
    // that is the body's, reported above, not the arm's).
    for (const k of c.startsWith('acts-') ? ['armROwn', 'armLOwn'] : ['head', 'armR', 'armL', 'armROwn', 'armLOwn']) {
      const v = res.parts[k];
      if (v.deg > LIM_DEG) fails.push(`${c}: ${k} turned ${v.deg}deg in a frame at ${v.degAt}ms`);
      if (v.px > LIM_PX) fails.push(`${c}: ${k} moved ${v.px}px in a frame at ${v.pxAt}ms`);
    }
    await browser.close();
  }
  console.log(JSON.stringify(table));
  console.log(fails.length ? `FAIL\n  ${fails.join('\n  ')}` : 'ok');
  process.exit(fails.length ? 1 : 0);
})();
