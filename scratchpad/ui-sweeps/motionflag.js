// INBOX 1565: which elements appear or vanish in one frame?
//
// The owner loved the graph hover card's fade (opacity only, `--ui-fast`) and
// asked for that quality everywhere. This sweep is the "before" and "after":
// on each surface it clicks, hovers and focuses a diverse set of triggers (one
// per element signature, not fifty identical note menus) and, for each, lists
// what went from not drawn to drawn (or was inserted) and the reverse. An
// element is FLAGGED when it appears with no running animation or transition
// on opacity, transform, translate, scale or rotate on it, an ancestor or a
// descendant, or vanishes (display none, removed) having never been animated.
// The measurement starts inside the page, in a capture listener, so the
// "before" is taken before the page reacts and frame 1 is really frame 1.
// A control (no action) is sampled first; what appears on its own is noise.
//
//   BASE=http://127.0.0.1:8807 THEME=dark W=390 OUT=/path/flags.json \
//     node scratchpad/ui-sweeps/motionflag.js [surface,...]
//
// Prints one line per flagged signature and a count per surface and kind.
const { boot } = require('./lib.js');
const fs = require('fs');

const W = Number(process.env.W || 1440);
const SURFACES = {
  dashboard: { root: '#tab-dashboard', go: "switchTab('dashboard')" },
  notes: { root: '#tab-notes', go: "switchTab('notes')", subtabs: '#notes-subtabs button' },
  chat: { root: '#tab-chat', go: "switchTab('chat')" },
  library: { root: '#tab-library', go: "switchTab('library')", subtabs: '#library-subtabs button' },
  graph: { root: '#tab-graph', go: "switchTab('graph')", scan: '#graph-pane-canvas' },
  timeline: { root: '#tab-timeline', go: "switchTab('timeline')" },
  reminders: { root: '#tab-reminders', go: "switchTab('reminders')" },
  board: { root: '#library-view-whiteboard', go: 'openWhiteboardBoard(41)' },
  documents: { root: '#tab-documents', go: "(async () => { switchTab('documents'); const d = await apiJson('/documents'); const l = Array.isArray(d) ? d : (d.documents || []); if (l[0]) await openDocument(l[0].id); })()" },
  settings: { root: '#settings-modal', go: null, sections: true },
};
const CAPS = { click: 40, hover: 22, focus: 8 };
const DANGER = /minimi|maximi|detach|delete|remove|trash|sign ?out|log ?out|lock|reset|erase|wipe|clear|quit|restart|shut|uninstall|factory|forget|discard|export|download|import|upload|install|pull |update|check for|print|share|connect|revoke|rotate|password|recover|stop|cancel|close|back/i;

const INSTRUMENT = (dangerSrc) => {
  if (window.__mf) return;
  // Long animation frames over the whole run (CPU=4 throttles the CPU four times).
  window.__loaf = { n: 0, ms: 0 };
  try {
    new PerformanceObserver((l) => { for (const e of l.getEntries()) { window.__loaf.n += 1; window.__loaf.ms += Math.round(e.duration); } }).observe({ type: 'long-animation-frame' });
  } catch (_) { window.__loaf.unsupported = true; }
  const DANGER = new RegExp(dangerSrc, 'i');
  const SKIP = new Set(['SCRIPT', 'STYLE', 'TEMPLATE', 'LINK', 'META', 'HEAD', 'BR', 'TITLE', 'NOSCRIPT', 'CANVAS']);
  const COMP = new Set(['opacity', 'transform', 'translate', 'scale', 'rotate']);
  const sig = (e) => {
    const cls = [...e.classList].filter((c) => !/^(hidden|active|open|is-|on$|off$|selected|focus|hover|current)/.test(c) && !/\d{3,}/.test(c)).slice(0, 3).join('.');
    return e.tagName.toLowerCase() + (e.id && !/\d{3,}/.test(e.id) ? '#' + e.id : '') + (cls ? '.' + cls : '') + (!cls && !e.id ? '[' + (e.getAttribute('role') || e.getAttribute('aria-label') || '').slice(0, 24) + ']' : '');
  };
  const info = (e) => {
    if (SKIP.has(e.tagName)) return null;
    const sv = e.closest('svg'); if (sv && sv !== e) return null;
    if (e.closest('.cm-editor, .wb-object-grip, .wb-handle') || e.classList.contains('wb-object-grip')) return null;
    if ((e.tagName === 'I' && e.classList.contains('ph')) || /resize/.test(e.className && e.className.baseVal === undefined ? e.className : '')) return null;
    if (e.parentElement && e.parentElement.closest('canvas')) return null;
    let ok = false;
    try { ok = e.checkVisibility({ visibilityProperty: true }) && e.getClientRects().length > 0; } catch (_) { return null; }
    if (!ok) return null;
    const r = e.getBoundingClientRect();
    if (r.width < 6 || r.height < 6 || r.width * r.height < 300) return null;
    return { w: Math.round(r.width), h: Math.round(r.height), p: e.parentElement };
  };
  const snap = () => { const m = new Map(); for (const e of document.querySelectorAll('body *')) { const i = info(e); if (i) m.set(e, i); } return m; };
  const animTargets = () => document.getAnimations().filter((a) => {
    const eff = a.effect; if (!eff || !eff.target) return false;
    if (a.transitionProperty) return COMP.has(a.transitionProperty);
    try { return eff.getKeyframes().some((k) => Object.keys(k).some((p) => COMP.has(p))); } catch (_) { return false; }
  }).map((a) => a.effect.target);
  const near = (targets, el) => targets.some((t) => t === el || t.contains(el) || el.contains(t));
  let armed = null;
  const begin = (kind) => {
    if (!armed || armed.started || armed.kind !== kind) return;
    armed.started = true; armed.t0 = performance.now();
    armed.before = snap(); armed.removed = []; armed.seen = new Set(); armed.vanished = new Set();
    armed.everAnimated = new Set(); armed.out = { appeared: [], vanished: [] }; armed.dirty = true; armed.n = 0;
    armed.mo = new MutationObserver(() => { armed && (armed.dirty = true); });
    armed.mo.observe(document.body, { childList: true, subtree: true, attributes: true });
    const tick = () => {
      const a = armed; if (!a) return;
      a.n += 1;
      if (a.dirty || a.n <= 3 || a.n % 4 === 0) { a.dirty = false; sample(a); }
      if (performance.now() - a.t0 < 520) requestAnimationFrame(tick); else finish(a);
    };
    requestAnimationFrame(tick);
  };
  const sample = (a) => {
    const cur = snap(); const at = animTargets(); const t = Math.round(performance.now() - a.t0);
    const gone = new Set(); for (const e of a.before.keys()) if (!e.isConnected) gone.add(sig(e));
    for (const [e, i] of cur) {
      if (a.before.has(e) || a.seen.has(e)) continue;
      a.seen.add(e);
      if (gone.has(sig(e))) continue; // a re-render's twin, not an arrival
      let under = false;
      for (let p = e.parentElement; p && !under; p = p.parentElement) under = a.seen.has(p) || (cur.has(p) && !a.before.has(p));
      if (under) continue;
      if (e.classList.contains('tab-page')) continue;
      a.out.appeared.push({ sig: sig(e), w: i.w, h: i.h, t, animated: near(at, e), parent: e.parentElement });
    }
    for (const [e, i] of a.before) {
      if (cur.has(e)) { if (near(at, e)) a.everAnimated.add(e); continue; }
      if (a.vanished.has(e)) continue;
      a.vanished.add(e);
      const p0 = i.p;
      let under = false;
      for (let p = e.parentElement; p && !under; p = p.parentElement) under = a.vanished.has(p) || (a.before.has(p) && !cur.has(p));
      if (under) continue;
      if (e.classList.contains('tab-page')) continue;
      if (!e.isConnected) {
        // a re-render replaces a node with its twin: not a vanish
        const twin = [...cur.keys()].some((c) => !a.before.has(c) && sig(c) === sig(e));
        if (twin) continue;
      }
      a.out.vanished.push({ sig: sig(e), w: i.w, h: i.h, t, animated: a.everAnimated.has(e), removed: !e.isConnected, parent: p0, inflow: e.isConnected && /^(static|relative|sticky)$/.test(getComputedStyle(e).position) });
    }
  };
  const finish = (a) => {
    a.mo.disconnect(); a.done = true;
    // A swap: something appeared and something vanished under the same parent (a sub-view, a tab panel).
    for (const x of a.out.appeared) for (const y of a.out.vanished) if (x.parent && x.parent === y.parent) { x.swap = true; y.swap = true; }
    for (const x of [...a.out.appeared, ...a.out.vanished]) delete x.parent;
    if (a.resolve) a.resolve(a.out);
  };
  for (const [ev, kind] of [['pointerdown', 'click'], ['pointerover', 'hover'], ['focusin', 'focus']]) {
    window.addEventListener(ev, () => begin(kind), true);
  }
  window.__mf = {
    arm(kind) { armed = { kind, started: false }; },
    async result() {
      const a = armed; if (!a) return null;
      if (!a.started) await new Promise((r) => setTimeout(r, 600));
      if (!a.started) { armed = null; return { nostart: true }; }
      if (!a.done) await new Promise((r) => { a.resolve = r; });
      armed = null; return a.out;
    },
    // Control: sample 520ms of nothing.
    control() { armed = { kind: 'control', started: false }; begin('control'); return this.result(); },
    candidates(rootSel, seenSigs, caps) {
      const root = document.querySelector(rootSel); if (!root) return [];
      document.querySelectorAll('[data-mf]').forEach((e) => e.removeAttribute('data-mf'));
      const out = []; let idx = 0;
      const sel = 'button, summary, [role="button"], [role="tab"], [role="switch"], [aria-haspopup], [aria-expanded], .chip, select, input, textarea, [contenteditable="true"], [data-help-for], li, .card, article, [tabindex="0"]';
      for (const e of root.querySelectorAll(sel)) {
        if (e.closest('#tab-bar, #status-bar') || (e.id === 'settings-btn' && rootSel !== '#tab-dashboard')) continue;
        const i = info(e); if (!i) continue;
        const r = e.getBoundingClientRect();
        if (r.bottom < 0 || r.top > innerHeight || r.right < 0 || r.left > innerWidth) continue;
        if (e.disabled || e.getAttribute('aria-disabled') === 'true') continue;
        if (e.type === 'file' || e.type === 'password' || (e.tagName === 'A' && e.target === '_blank')) continue;
        const label = [e.textContent.trim().slice(0, 40), e.getAttribute('aria-label'), e.title].join(' ');
        const isInput = /^(INPUT|TEXTAREA|SELECT)$/.test(e.tagName) || e.isContentEditable;
        const kinds = [];
        if (isInput) kinds.push('focus');
        else {
          if (!e.classList.contains('danger') && !DANGER.test(label) && !e.closest('.danger')) kinds.push('click');
          kinds.push('hover');
        }
        const s = sig(e);
        for (const k of kinds) {
          const key = k + '|' + s;
          if (seenSigs.includes(key) || out.filter((o) => o.k === k).length >= caps[k]) continue;
          seenSigs.push(key);
          e.setAttribute('data-mf', String(idx)); out.push({ i: idx, k, sig: s, label: label.trim().slice(0, 30) }); idx += 1;
          break;
        }
      }
      return out;
    },
  };
};

(async () => {
  const { browser, page } = await boot({ viewport: { width: W, height: W > 600 ? 900 : 844 } });
  if (Number(process.env.CPU)) { const cdp = await page.context().newCDPSession(page); await cdp.send('Emulation.setCPUThrottlingRate', { rate: Number(process.env.CPU) }); }
  await page.evaluate(INSTRUMENT, DANGER.source);
  const only = (process.argv[2] || '').split(',').filter(Boolean);
  const report = {};
  const settle = (ms = 350) => page.waitForTimeout(ms);
  const reset = async (s) => {
    await page.mouse.move(W - 3, 3);
    await page.keyboard.press('Escape'); if (!s.sections) await page.keyboard.press('Escape');
    await settle(320);
    return page.evaluate((root) => {
      const modal = document.querySelector('.modal-overlay:not(.hidden), .lock-overlay:not(#lock-overlay):not(.hidden)');
      const here = document.querySelector(root);
      return { modal: !!modal && root !== '#settings-modal', gone: !here || here.classList.contains('hidden') || here.getClientRects().length === 0 };
    }, s.root);
  };
  const enter = async (s, section) => {
    if (section && s.sections) await page.evaluate((x) => openSettingsModal(x), section);
    else {
      await page.evaluate(s.go);
      await settle(900);
      if (section) await page.evaluate(([q, i]) => document.querySelectorAll(q)[i]?.click(), [s.subtabs, Number(section.slice(3))]);
    }
    await settle(1100);
  };
  for (const [name, s] of Object.entries(SURFACES)) {
    if (only.length && !only.includes(name)) continue;
    const rows = { appeared: [], vanished: [], triggers: 0, nostart: 0, lost: 0 };
    const seenSigs = []; const noise = new Set();
    let sections = [null];
    if (s.sections) sections = await page.evaluate(() => SETTINGS_SECTIONS.slice());
    else if (s.subtabs) { await enter(s, null); const n = await page.evaluate((q) => document.querySelectorAll(q).length, s.subtabs); sections = Array.from({ length: n }, (_, i) => 'tab' + i); }
    for (const section of sections) {
      await enter(s, section);
      for (let i = 0; i < 2; i++) { const c = await page.evaluate(() => window.__mf.control()); for (const a of [...c.appeared, ...c.vanished]) noise.add(a.sig); }
      const caps = (s.sections || s.subtabs) ? { click: 12, hover: 6, focus: 3 } : CAPS;
      const cands = await page.evaluate(([r, seen, c]) => window.__mf.candidates(r, seen, c), [s.root, seenSigs, caps]);
      const jobs = cands.map((c) => ({ ...c }));
      if (s.scan && section === null) for (let gx = 1; gx <= 7; gx++) for (let gy = 1; gy <= 4; gy++) jobs.push({ k: 'scan', gx, gy, label: `canvas ${gx},${gy}` });
      let scanned = false;
      for (const job of jobs) {
        if (job.k === 'scan' && scanned) continue;
        let res = null;
        try {
          if (job.k === 'scan') {
            const el = await page.$(s.scan); const box = el && (await el.boundingBox());
            if (!box || box.width < 50) continue;
            await page.mouse.move(box.x + 3, box.y + 3); await settle(120);
            await page.evaluate(() => window.__mf.arm('hover'));
            await page.mouse.move(box.x + box.width * job.gx / 8, box.y + box.height * job.gy / 5, { steps: 4 });
            res = await page.evaluate(() => window.__mf.result());
            if (res && res.appeared && res.appeared.some((a) => /hovercard/.test(a.sig))) scanned = true;
          } else {
            let loc = page.locator(`[data-mf="${job.i}"]`).first();
            if (!(await loc.count())) {
              // the surface re-drew and dropped the marks: find this trigger again by its signature
              const again = await page.evaluate(([r, c]) => window.__mf.candidates(r, [], c), [s.root, { click: 999, hover: 999, focus: 999 }]);
              const hit = again.find((c) => c.k === job.k && c.sig === job.sig);
              if (hit) { job.i = hit.i; loc = page.locator(`[data-mf="${job.i}"]`).first(); }
            }
            if (!(await loc.count())) { rows.lost += 1; if (process.env.DEBUG) console.log('   LOST(mark)', job.k, job.label); continue; }
            await loc.scrollIntoViewIfNeeded({ timeout: 2000 }).catch(() => {});
            const box = await loc.boundingBox(); if (!box) { rows.lost += 1; if (process.env.DEBUG) console.log('   LOST(box)', job.k, job.label); continue; }
            const cx = box.x + box.width / 2, cy = box.y + box.height / 2;
            if (job.k === 'focus') {
              await page.evaluate(() => window.__mf.arm('focus'));
              await loc.focus({ timeout: 2000 });
            } else if (job.k === 'click') {
              await page.mouse.move(cx, cy); await settle(260);
              await page.evaluate(() => window.__mf.arm('click'));
              await page.mouse.down(); await page.mouse.up();
            } else {
              await page.mouse.move(W - 3, 3); await settle(120);
              await page.evaluate(() => window.__mf.arm('hover'));
              await page.mouse.move(cx, cy, { steps: 2 });
            }
            res = await page.evaluate(() => window.__mf.result());
          }
        } catch (e) { rows.lost += 1; if (process.env.DEBUG) console.log('   LOST', job.k, job.label, String(e.message).split('\n')[0].slice(0, 90)); await reset(s).catch(() => {}); continue; }
        rows.triggers += 1;
        if (!res || res.nostart) rows.nostart += 1;
        else {
          for (const a of res.appeared) rows.appeared.push({ ...a, trigger: `${job.k}:${job.label}` });
          for (const v of res.vanished) rows.vanished.push({ ...v, trigger: `${job.k}:${job.label}` });
        }
        const st = await reset(s);
        if (st.gone || st.modal) {
          if (process.env.DEBUG) console.log('   RESET', JSON.stringify(st), job.k, job.label);
          await enter(s, section);
          const again = await page.evaluate(([r, c]) => window.__mf.candidates(r, [], c), [s.root, { click: 999, hover: 999, focus: 999 }]);
          if (process.env.DEBUG) console.log('   REMARK', again.length, 'of', jobs.length, await page.evaluate(() => document.querySelector('#settings-modal')?.className));
          const byKey = new Map(again.map((c) => [c.k + '|' + c.sig, c.i]));
          for (const j of jobs) if (j.k !== 'scan' && byKey.has(j.k + '|' + j.sig)) j.i = byKey.get(j.k + '|' + j.sig);
        }
      }
    }
    // A signature that animates on one occasion and snaps on another is flagged once if any occasion snapped.
    const uniq = (list) => {
      const m = new Map();
      for (const x of list) { if (noise.has(x.sig)) continue; const o = m.get(x.sig); if (!o || (o.animated && !x.animated)) m.set(x.sig, x); }
      return [...m.values()];
    };
    const ua = uniq(rows.appeared), uv = uniq(rows.vanished);
    // Kept on purpose, and said: a sub-view swap would fade inside its own page's arrival (DESIGN.md, "A page arriving"),
    // and an in-flow exit would hold its space for the fade and then jump the neighbours.
    const kept = (x, vanish) => x.swap || (vanish && x.inflow);
    const flagA = ua.filter((x) => !x.animated && !kept(x, false)), flagV = uv.filter((x) => !x.animated && !kept(x, true));
    const keptN = ua.filter((x) => !x.animated && kept(x, false)).length + uv.filter((x) => !x.animated && kept(x, true)).length;
    report[name] = { kept: keptN, triggers: rows.triggers, nostart: rows.nostart, lost: rows.lost, appeared: ua.length, appearedFlagged: flagA.length, vanished: uv.length, vanishedFlagged: flagV.length, flaggedAppear: flagA, flaggedVanish: flagV };
    console.log(`${name.padEnd(10)} triggers ${rows.triggers} (no start ${rows.nostart}, lost ${rows.lost}) appear ${ua.length} flagged ${flagA.length}; vanish ${uv.length} flagged ${flagV.length}; kept ${keptN}`);
    for (const x of flagA) console.log(`   APPEAR ${x.sig} ${x.w}x${x.h} @${x.t}ms via ${x.trigger}`);
    for (const x of flagV) console.log(`   VANISH ${x.sig} ${x.w}x${x.h} ${x.removed ? 'removed' : 'hidden'} via ${x.trigger}`);
  }
  const total = Object.values(report).reduce((n, r) => n + r.appearedFlagged + r.vanishedFlagged, 0);
  console.log('LOAF', JSON.stringify(await page.evaluate(() => window.__loaf)), 'cpu x' + (process.env.CPU || 1));
  console.log(`TOTAL flagged ${total} at ${W} ${process.env.THEME || 'light'}`);
  if (process.env.OUT) fs.writeFileSync(process.env.OUT, JSON.stringify({ W, theme: process.env.THEME || 'light', total, report }, null, 1));
  await browser.close();
})();
