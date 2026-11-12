// INBOX 577: the boot, recorded. Lock screen, unlock, first tab, with a
// PerformanceObserver (layout shifts, long tasks, paints) and a per-frame
// probe of the companion: its figure's box and drawn scale every frame, so
// "the head goes large, then small, then large" is a number, not a feeling.
//   BASE=http://127.0.0.1:8860 BUDDY=atlas node scratchpad/ui-sweeps/smooth1005-boot.js
// Prints: CLS before and after unlock (with the shifting nodes), long tasks,
// the companion's box every time it changes after mount, and the frames
// where the splash, lock and shell overlap. SHOTS=1 saves a screencast.
// GATE=1 exits 1 when the boot's visible layout shift is 0.02 or more, or
// the companion's head changes size by more than 2% between two frames
// after it first shows (or it never shows).
const { chromium } = require('playwright');
const BASE = process.env.BASE || 'http://127.0.0.1:8860';
const fs = require('fs');
(async () => {
  const browser = await chromium.launch();
  const vp = { width: +(process.env.W || 1440), height: +(process.env.H || 900) };
  const ctx = await browser.newContext({ viewport: vp, reducedMotion: process.env.REDUCED ? 'reduce' : 'no-preference' });
  await ctx.addInitScript(([buddy, theme, dash]) => {
    try {
      localStorage.setItem('theme', theme);
      localStorage.setItem('onboardingDone', '1');
      localStorage.setItem('tourDone', '1');
      localStorage.setItem('nm-buddy-hint', 'done');
      if (buddy) localStorage.setItem('avatar-buddy', buddy);
      if (dash) localStorage.setItem('dash-mark', dash);
    } catch (e) {}
    const log = (window.__smooth = { shifts: [], long: [], paints: [], frames: [], anims: [] });
    window.__smoothVars = '';
    // Every animation started on the companion or the dashboard mark, with
    // its scale keyframes: the drawn size changes a frame probe can miss on a
    // loaded machine.
    const orig = Element.prototype.animate;
    Element.prototype.animate = function (kf, opts) {
      try {
        if (this.closest && this.closest('#nm-buddy-band, #dash-hero-emblem')) {
          const frames = Array.isArray(kf) ? kf : [];
          const sc = frames.map((f) => f.scale ?? f.transform ?? '').filter(Boolean);
          const cls = typeof this.className === 'string' ? this.className : this.className?.baseVal || this.nodeName;
          log.anims.push({ t: Math.round(performance.now()), on: (this.id ? '#' + this.id : cls.split(' ')[0]), scale: sc.join('>'), op: frames.map((f) => f.opacity ?? '').join(','), d: typeof opts === 'number' ? opts : opts?.duration });
        }
      } catch (e) {}
      return orig.call(this, kf, opts);
    };
    const name = (n) => !n ? '?' : n.id ? '#' + n.id : (typeof n.className === 'string' && n.className ? '.' + n.className.split(' ')[0] : n.nodeName);
    try {
      new PerformanceObserver((l) => { for (const e of l.getEntries()) log.shifts.push({ t: Math.round(e.startTime), v: +e.value.toFixed(4), input: e.hadRecentInput, nodes: (e.sources || []).map((s) => `${name(s.node)} y${Math.round(s.previousRect.y)}->${Math.round(s.currentRect.y)} h${Math.round(s.previousRect.height)}->${Math.round(s.currentRect.height)}`) }); }).observe({ type: 'layout-shift', buffered: true });
      new PerformanceObserver((l) => { for (const e of l.getEntries()) log.long.push({ t: Math.round(e.startTime), d: Math.round(e.duration) }); }).observe({ type: 'longtask', buffered: true });
      new PerformanceObserver((l) => { for (const e of l.getEntries()) log.paints.push({ n: e.name, t: Math.round(e.startTime) }); }).observe({ type: 'paint', buffered: true });
    } catch (e) {}
    const vis = (el) => { if (typeof el === 'string') el = document.getElementById(el); if (!el) return 0; const cs = getComputedStyle(el); if (cs.display === 'none' || cs.visibility === 'hidden' || el.classList.contains('hidden')) return 0; return +(+cs.opacity).toFixed(2); };
    const frame = (t) => {
      const host = document.getElementById('nm-buddy');
      const fig = host && (host.querySelector('.nm-figure') || host);
      let box = null;
      if (fig) {
        const r = fig.getBoundingClientRect();
        // Opacity as drawn: the host and every ancestor up to the band.
        let op = 1; for (let n = host; n && n !== document.body; n = n.parentElement) op *= +getComputedStyle(n).opacity;
        // The head's drawn scale: Atlas's own head group's screen matrix
        // (every transform above it, CSS and SVG, the host's entrance and
        // the character's squash included), across and down. Its bounding
        // box is no measure: ears and wisps inside it move on their own.
        const head = host.querySelector('.atl-head') || host.querySelector('svg');
        const m = head && head.getScreenCTM ? head.getScreenCTM() : null;
        const hw = m ? +Math.hypot(m.a, m.b).toFixed(3) : r.width, hh = m ? +Math.hypot(m.c, m.d).toFixed(3) : r.height;
        if (head && window.__smoothVars !== undefined) { const cs = getComputedStyle(head); const v = ['--atl-head-k', '--atl-tune-head', 'transform'].map((k) => cs.getPropertyValue(k).trim()).join(' | ') + ' svg:' + (head.ownerSVGElement?.getAttribute('class') || ''); if (v !== window.__smoothVars) { (log.vars ||= []).push(Math.round(t) + ' ' + v); window.__smoothVars = v; } }
        box = { x: Math.round(r.x), y: Math.round(r.y), w: +r.width.toFixed(1), h: +r.height.toFixed(1), hw, hh, op: +op.toFixed(2), away: host.classList.contains('nmb-away') ? 1 : 0 };
      }
      const shell = document.querySelector('.tab-page.active') || document.querySelector('main');
      const em = document.querySelector('#dash-hero-emblem > *');
      let emb = null; if (em) { const r = em.getBoundingClientRect(); emb = `${r.width.toFixed(1)}x${r.height.toFixed(1)}@${Math.round(r.x)},${Math.round(r.y)}`; }
      log.frames.push({ t: Math.round(t), splash: vis('boot-splash'), lock: vis('lock-overlay'), shell: shell ? vis(shell) : -1, box, emb });
      if (log.frames.length < 4000) requestAnimationFrame(frame);
    };
    requestAnimationFrame(frame);
  }, [process.env.BUDDY ?? 'atlas', process.env.THEME || 'light', process.env.DASH ?? 'atlas']);
  const page = await ctx.newPage();
  page.on('pageerror', (e) => console.log('PAGEERROR', e.message));
  let cdp = null; const shots = [];
  if (process.env.SHOTS) {
    cdp = await ctx.newCDPSession(page);
    cdp.on('Page.screencastFrame', async (f) => { shots.push({ t: f.metadata.timestamp, d: f.data }); try { await cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }); } catch (e) {} });
    await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 50, everyNthFrame: 1, maxWidth: 720 });
  }
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  const way = await (await page.waitForFunction(() => {
    const f = document.getElementById('lock-password'); const o = document.getElementById('lock-overlay');
    if (f && o && !o.classList.contains('hidden') && f.offsetParent !== null) return 'lock';
    if (o && o.classList.contains('hidden') && localStorage.getItem('token')) return 'app';
    return false;
  }, null, { timeout: 20000, polling: 50 })).jsonValue();
  await page.waitForTimeout(600);
  const unlockAt = await page.evaluate(() => performance.now());
  if (way === 'lock') { await page.fill('#lock-password', 'testpassword123'); await page.click('#lock-submit'); }
  await page.waitForTimeout(+(process.env.WAIT || 6000));
  await page.evaluate(() => { const c = [...document.querySelectorAll('.confirm-overlay')].find((o) => /Check for updates/.test(o.textContent)); const b = c && [...c.querySelectorAll('button')].find((x) => /Don.t check/.test(x.textContent)); if (b) b.click(); });
  const log = await page.evaluate(() => window.__smooth);
  if (process.env.DUMP) console.log((log.vars || []).join('\n'));
  if (process.env.DUMP) console.log(JSON.stringify(await page.evaluate(() => [...document.querySelectorAll('#nm-buddy .atl-head')].map((h) => { const m = h.getScreenCTM(); const svg = h.ownerSVGElement; return { cls: h.getAttribute('class'), svg: svg && svg.getAttribute('class'), k: svg && getComputedStyle(h).getPropertyValue('--atl-head-k'), sx: +Math.hypot(m.a, m.b).toFixed(3), sy: +Math.hypot(m.c, m.d).toFixed(3) }; }))));
  if (cdp) {
    await cdp.send('Page.stopScreencast');
    const dir = (process.env.OUT || '/tmp') + '/smooth-boot'; fs.mkdirSync(dir, { recursive: true });
    const first = shots[0]?.t || 0;
    shots.forEach((s, i) => fs.writeFileSync(`${dir}/${String(i).padStart(4, '0')}-${Math.round((s.t - first) * 1000)}ms.jpg`, Buffer.from(s.d, 'base64')));
    console.log('frames saved', shots.length, dir);
  }
  const cls = (a) => +a.filter((s) => !s.input).reduce((x, s) => x + s.v, 0).toFixed(4);
  const pre = log.shifts.filter((s) => s.t < unlockAt), post = log.shifts.filter((s) => s.t >= unlockAt);
  // A shift under an opaque curtain (the splash or the lock screen, drawn
  // at more than half) is one nobody sees: counted in the total, and kept
  // out of the visible figure the gate reads.
  const covered = (t) => { let f = null; for (const x of log.frames) { if (x.t > t) break; f = x; } return !!f && (f.splash > 0.5 || f.lock > 0.5); };
  const seen = log.shifts.filter((s) => !covered(s.t));
  console.log(JSON.stringify({ way, unlockAt: Math.round(unlockAt), clsBeforeUnlock: cls(pre), clsAfterUnlock: cls(post), clsTotal: cls(log.shifts), clsVisible: cls(seen), paints: log.paints }));
  for (const s of log.shifts.filter((s) => s.v > 0.0005)) console.log('  shift', s.t, s.v, s.input ? '(input)' : '', covered(s.t) ? '(under the curtain)' : '(VISIBLE)', s.nodes.slice(0, 4).join(' | '));
  console.log('long tasks', log.long.length, 'sum', log.long.reduce((x, l) => x + l.d, 0), 'ms; >100ms:', JSON.stringify(log.long.filter((l) => l.d > 100)));
  let lastKey = null, mounted = null; const sizeChanges = []; let maxDev = 0;
  for (const f of log.frames) {
    if (!f.box) continue;
    if (f.box.op > 0.05 && !f.box.away && f.box.w > 0 && mounted == null) mounted = f.t;
    const key = `${f.box.w}x${f.box.h} head scale ${f.box.hw}x${f.box.hh}`;
    if (key !== lastKey) { sizeChanges.push(`${f.t}:${key} op${f.box.op}${f.box.away ? ' away' : ''}`); lastKey = key; }
  }
  // The head's drawn size after it first shows, against where it ends:
  // width and height both, so a squash (wide and short) counts.
  const last = log.frames.filter((f) => f.box).slice(-1)[0]?.box;
  const finalW = last?.hw, finalH = last?.hh;
  // Two figures: the largest change from one frame to the next after it
  // first shows (the gate: a jump in size is a glitch), and how far it
  // strays from where it ends (its breathing is about 3% of that).
  let maxStep = 0, prevBox = null;
  for (const f of log.frames) {
    if (!(f.box && mounted != null && f.t >= mounted && f.t <= mounted + 2500 && f.box.op > 0.05 && finalW && finalH)) continue;
    maxDev = Math.max(maxDev, Math.abs(f.box.hw - finalW) / finalW, Math.abs(f.box.hh - finalH) / finalH);
    if (prevBox) {
      const step = Math.max(Math.abs(f.box.hw - prevBox.hw) / prevBox.hw, Math.abs(f.box.hh - prevBox.hh) / prevBox.hh);
      if (step > 0.015) console.log(`  head step ${(step * 100).toFixed(1)}% at ${f.t} (${f.t - prevBox.t}ms): ${prevBox.hw}x${prevBox.hh} -> ${f.box.hw}x${f.box.hh}`);
      maxStep = Math.max(maxStep, step);
    }
    f.box.t = f.t;
    prevBox = f.box;
  }
  console.log('companion head: largest frame-to-frame change', (maxStep * 100).toFixed(1) + '%');
  console.log('companion mounted at', mounted, 'final head scale', finalW + 'x' + finalH, 'max head scale deviation after mount', (maxDev * 100).toFixed(1) + '%');
  console.log('  size changes:', sizeChanges.slice(0, 40).join('  '));
  console.log('animations on the companion:', log.anims.filter((a) => a.scale || a.op.replace(/,/g, '')).slice(0, 25).map((a) => `${a.t} ${a.on} scale[${a.scale}] op[${a.op}] ${a.d}ms`).join('\n  '));
  const emSeq = []; let emPrev = '';
  for (const f of log.frames) if (f.emb !== emPrev) { emSeq.push(`${f.t}:${f.emb}`); emPrev = f.emb; }
  console.log('dashboard mark:', emSeq.slice(0, 30).join('  '));
  const seq = []; let prev = '';
  for (const f of log.frames) { const k = `splash${f.splash} lock${f.lock} page${f.shell}`; if (k !== prev) { seq.push(`${f.t}:${k}`); prev = k; } }
  console.log('layers:', seq.slice(0, 40).join('  '));
  const gaps = log.frames.filter((f, i) => i && f.t - log.frames[i - 1].t > 50).map((f, i) => f.t - log.frames[log.frames.indexOf(f) - 1].t);
  console.log('frames recorded', log.frames.length, 'frame gaps >50ms', gaps.length, 'max', Math.max(0, ...gaps));
  await browser.close();
  if (process.env.GATE && (cls(seen) >= 0.02 || maxStep > 0.02 || (process.env.BUDDY !== '' && mounted == null))) process.exit(1);
})();
