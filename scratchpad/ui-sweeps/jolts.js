// The owner (2026-10-11): "make sure no jolts to start or stop various
// movemements". Measures the jump a class change makes in one frame: every
// move, act, and add or remove on #nm-buddy's class list from anything else
// (a walk's own end) is wrapped at its outermost call, and the rects of the body, head, legs and
// arms are read just before it and again after the caller's synchronous code
// (a microtask, after any blend it starts), against the companion's own
// box; a change made while it is faded out (a poof) is not counted. A jump over 1.5px on one is a
// snap. Walks the companion between perches, acts, and stops a walk short.
// KIND (atlas, me, persona), N rounds. PASS when no jump over 1.5px.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate((k) => { const b = $('avatar-buddy'); b.value = k; b.dispatchEvent(new Event('change', { bubbles: true })); }, process.env.KIND || 'atlas');
  await page.waitForTimeout(4000);
  await page.evaluate((d) => { window.__DEBUG = d; }, !!process.env.DEBUG);
  await page.evaluate(() => {
    const buddy = document.getElementById('nm-buddy');
    // Not Atlas's arm probe: an unseen box its rig reads its targets from.
    const SEL = '.nm-buddy-char, .nm-buddy-head, .nmb-leg-l, .nmb-leg-r, :is(.nmb-arm-l, .nmb-arm-r):not(.atl-arm-probe), .nm-figure';
    window.__jolts = [];
    // Against the companion's own box: a walk or a poof moves the whole
    // thing (eased by its own animation or faded), which is not a jolt.
    const look = (el) => { const c = getComputedStyle(el); return `${c.transform}|${c.translate}|${c.rotate}|${c.scale}|${c.transformOrigin}|${el.getAnimations().map((a) => a.animationName || a.transitionProperty || a.id || 'js').join(',')}`; };
    const rects = () => { const o = buddy.getBoundingClientRect(); return [...buddy.querySelectorAll(SEL)].map((el) => { const r = el.getBoundingClientRect(); return [el.className.baseVal ?? el.className, r.left - o.left, r.top - o.top, r.right - o.left, r.bottom - o.top, window.__debugJolts ? look(el) : '']; }); };
    // Where a change came from, for a jump (DEBUG=1).
    const process_stack = () => (window.__debugJolts ? new Error().stack.split('\n').slice(2, 7).map((l) => l.trim().split(' ')[1]).join(' < ') : '');
    window.__debugJolts = !!window.__DEBUG;
    // The jump is read across the outermost call: a move or an act read
    // from inside reads half of its own work (a cut-short float is put
    // back where it was drawn a few lines after its lean is cancelled).
    let depth = 0;
    const watch = (label, run) => {
      if (depth) return run();
      const before = rects();
      const stack = process_stack();
      const had = cl.value;
      depth += 1;
      let out;
      try { out = run(); } finally { depth -= 1; }
      const now = cl.value;
      if (cl.contains('nmb-poofing') || Number(getComputedStyle(buddy).opacity) < 0.5) return out;
      const names = [label, ...had.split(' ').filter((c) => c && !now.includes(c)).map((c) => `-${c}`), ...now.split(' ').filter((c) => c && !had.split(' ').includes(c)).map((c) => `+${c}`)].filter((c) => c.startsWith('+nmb-') || c.startsWith('-nmb-') || !c.startsWith('+') && !c.startsWith('-'));
      const verb = '';
      {
        queueMicrotask(() => {
          const after = rects();
          let worst = 0; let who = '';
          for (let i = 0; i < Math.min(before.length, after.length); i += 1) {
            const d = Math.max(...[1, 2, 3, 4].map((j) => Math.abs(after[i][j] - before[i][j])));
            if (d > worst) { worst = d; who = String(before[i][0]).split(' ')[0] + (window.__debugJolts ? ` ${before[i][5]} => ${after[i][5]}` : ''); }
          }
          const char = window.__debugJolts ? `char ${before[0][5]} => ${after[0][5]}` : '';
          window.__jolts.push({ change: `${verb}${names.join(' ')}`, px: +worst.toFixed(1), who, stack, state: had, char });
        });
      }
      return out;
    };
    const cl = buddy.classList;
    for (const name of ['nameMarkBuddyMoveTo', 'nameMarkBuddyAct']) {
      const orig = window[name];
      window[name] = function (...args) { return watch(name.replace('nameMarkBuddy', '') + (name.endsWith('Act') ? `(${args[0] || ''})` : ''), () => orig.apply(this, args)); };
    }
    // And a class changed from anything else (a walk's own end).
    for (const verb of ['add', 'remove']) {
      const orig = cl[verb].bind(cl);
      cl[verb] = (...names) => (depth ? orig(...names) : watch(`${verb} ${names.join(' ')}`, () => orig(...names)));
    }
  });
  const bar = await page.evaluate(() => document.getElementById('status-bar').getBoundingClientRect().top);
  for (let n = 0; n < Number(process.env.N || 3); n += 1) {
    for (const x of [300, 900, 500]) {
      await page.evaluate(([x, top]) => { const b = document.getElementById('nm-buddy'); DOMTokenList.prototype.remove.call(b.classList, 'nmb-sleep', 'nmb-drowsy'); nameMarkBuddyMoveTo(b, { kind: 'yours', pose: 'stand', legs: '', x, y: Math.round(top - NMB_FEET + 1) }); nmb.placedAt = Date.now(); }, [x, bar]);
      await page.waitForTimeout(2600);
    }
    // A walk cut short by the next.
    await page.evaluate(([top]) => { const b = document.getElementById('nm-buddy'); nameMarkBuddyMoveTo(b, { kind: 'yours', pose: 'stand', legs: '', x: 100, y: Math.round(top - NMB_FEET + 1) }); setTimeout(() => nameMarkBuddyMoveTo(b, { kind: 'yours', pose: 'stand', legs: '', x: 1100, y: Math.round(top - NMB_FEET + 1) }), 350); }, [bar]);
    await page.waitForTimeout(3000);
    for (const act of ['wave', 'cheer', 'land', 'startle']) {
      await page.evaluate((a) => nameMarkBuddyAct(a), act);
      await page.waitForTimeout(2200);
    }
  }
  const j = await page.evaluate(() => window.__jolts);
  if (process.env.DEBUG) for (const r of j) if (r.px > 1.5) console.log(JSON.stringify(r));
  const by = {};
  for (const r of j) { const k = r.change.split(' ').slice(0, /^(add|remove) /.test(r.change) ? 2 : 1).join(' '); by[k] = by[k] || { n: 0, max: 0, who: '' }; by[k].n += 1; if (r.px > by[k].max) { by[k].max = r.px; by[k].who = r.who; } }
  for (const [k, v] of Object.entries(by)) console.log(`${v.max > 1.5 ? 'JOLT' : 'ok  '} ${k} n=${v.n} max=${v.max}px ${v.who}`);
  console.log(j.some((r) => r.px > 1.5) ? 'FAIL' : 'PASS');
  await browser.close();
})();
