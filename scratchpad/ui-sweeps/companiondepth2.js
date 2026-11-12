// companion (Atlas) main-thread and mood sweeps, consolidated: one async function per case.
// Run one case by name, or every case in order with no argument:
//   node scratchpad/ui-sweeps/companiondepth2.js companionmoods

// INBOX 742, the owner: "atlas doesnt seem to change emotions alot if at
// all", and the owner's 2026-10-10 list: "I barely get to see atlas change
// expression". How often the face changes in one scripted session: the
// companion on the dashboard, then a saved note, an error toast, the chat's
// box focused and typed in, the notes tab, a rub, and idle to the end. Polls
// every 100ms: Atlas's mood (`atlasMoodNow`, every Atlas on the page) or the
// generated companion's face (`data-expr`). Prints the changes, the distinct
// faces and the longest stretch with no change.
// Env: KIND (atlas|me), MS (180000), BASE, SCRATCH.
async function companionmoods() {
  const { boot } = require('./lib.js');
  const KIND = process.env.KIND || 'atlas';
  const MS = Number(process.env.MS || 180000);
    const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
    await page.evaluate(async (k) => {
      localStorage.removeItem('nm-buddy-spots');
      prefs.set('avatar-buddy', k); await ensureModule('characters'); syncNameMarkBuddy();
      revealTab('dashboard');
    }, KIND);
    await page.waitForTimeout(5000);
    await page.evaluate(() => {
      window.__faces = [];
      const read = () => (typeof atlasMoodNow !== 'undefined' && document.querySelector('#nm-buddy .nm-atlas') ? atlasMoodNow : document.getElementById('nm-buddy')?.dataset.expr || '');
      let last = null;
      const t0 = performance.now();
      window.__facePoll = setInterval(() => {
        const now = read();
        if (now !== last) { window.__faces.push([Math.round(performance.now() - t0), now]); last = now; }
      }, 100);
    });
    const at = (ms, fn) => setTimeout(() => fn().catch(() => {}), ms);
    const steps = [
      [15000, () => page.evaluate(() => apiJson('/entries', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content: 'A note from the moods sweep' }) }))],
      [35000, () => page.evaluate(() => toast('Could not reach the server', true))],
      [55000, async () => { await page.evaluate(() => revealTab('chat')); await page.waitForTimeout(800); await page.focus('#chat-input'); await page.keyboard.type('what did I plan', { delay: 60 }); }],
      [80000, () => page.evaluate(() => revealTab('notes'))],
      [100000, async () => {
        const box = await page.evaluate(() => { const r = document.querySelector('#nm-buddy .nm-buddy-face')?.getBoundingClientRect(); return r ? [r.left + r.width / 2, r.top + 20] : null; });
        if (!box) return;
        for (let i = 0; i < 8; i++) { await page.mouse.move(box[0] + (i % 2 ? 12 : -12), box[1], { steps: 3 }); await page.waitForTimeout(60); }
        await page.mouse.move(10, 450);
      }],
    ];
    for (const [ms, fn] of steps) if (ms < MS) at(ms, fn);
    await page.waitForTimeout(MS);
    const faces = await page.evaluate(() => { clearInterval(window.__facePoll); return window.__faces; });
    const changes = Math.max(0, faces.length - 1);
    let still = 0;
    for (let i = 1; i <= faces.length; i++) still = Math.max(still, (i < faces.length ? faces[i][0] : MS) - faces[i - 1][0]);
    console.log(JSON.stringify({ kind: KIND, ms: MS, changes, perMinute: +(changes * 60000 / MS).toFixed(1), distinct: [...new Set(faces.map((f) => f[1]))], longestStillMs: still, trace: faces }));
    await browser.close();
}

// Companion main-thread cost: idle 2.6s, and a float (Atlas) or walk (as you)
// between two places, from CDP Performance.getMetrics deltas (style recalc
// ms and count, layouts, task ms). Env: BASE, KIND (atlas|me), REPS (3), ROUTE
// (float, glide, leap, ... forced for every move; the default is the real pick),
// LOOK (masculine, the default, or feminine).
async function companioncost() {
  const { boot } = require('./lib.js');
  const KIND = process.env.KIND || 'atlas';
  const REPS = Number(process.env.REPS || 3);
    const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
    const cdp = await page.context().newCDPSession(page);
    await cdp.send('Performance.enable');
    const metric = async () => Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((m) => [m.name, m.value]));
    await page.evaluate(async ([k, look]) => {
      localStorage.setItem('atlas-look', look); localStorage.removeItem('nm-buddy-spots');
      prefs.set('avatar-buddy', k); await ensureModule('characters'); syncNameMarkBuddy();
    }, [KIND, process.env.LOOK || 'masculine']);
    await page.waitForTimeout(3000);
    await page.evaluate((r) => {
      clearTimeout(nmb.timer);
      window.nameMarkBuddySchedule = () => {}; window.nameMarkBuddyTick = () => {};
      window.nameMarkBuddyQueuePlace = () => {}; window.nameMarkBuddyCheck = () => {};
      if (r) window.nameMarkBuddyRoute = () => r;
    }, process.env.ROUTE || "");
    const win = async (act) => {
      const a = await metric(); await act(); const b = await metric();
      const d = (k) => b[k] - a[k];
      return { recalcMs: +(d('RecalcStyleDuration') * 1000).toFixed(1), recalcs: d('RecalcStyleCount'), layouts: d('LayoutCount'), layoutMs: +(d('LayoutDuration') * 1000).toFixed(1), taskMs: +(d('TaskDuration') * 1000).toFixed(0) };
    };
    const out = { idle: [], move: [] };
    for (let i = 0; i < REPS; i += 1) {
      out.idle.push(await win(() => page.waitForTimeout(2600)));
      const from = i % 2 ? [560, 380] : [400, 420]; const to = i % 2 ? [400, 420] : [560, 380];
      await page.evaluate(([f]) => { const b = document.getElementById('nm-buddy'); nameMarkBuddyRide(null, f[0], f[1]); nameMarkBuddyMoveTo(b, { kind: 'card', pose: 'stand', legs: '', x: f[0], y: f[1] }, true); }, [from]);
      await page.waitForTimeout(700);
      out.move.push(await win(() => page.evaluate(async ([t]) => {
        const b = document.getElementById('nm-buddy');
        nameMarkBuddyMoveTo(b, { kind: 'card', pose: 'stand', legs: '', x: t[0], y: t[1] });
        await new Promise((r) => setTimeout(r, 2600));
      }, [to])));
    }
    const avg = (xs, k) => +(xs.reduce((s, x) => s + x[k], 0) / xs.length).toFixed(1);
    const sum = (xs) => ({ recalcMs: avg(xs, 'recalcMs'), recalcs: avg(xs, 'recalcs'), layouts: avg(xs, 'layouts'), layoutMs: avg(xs, 'layoutMs'), taskMs: avg(xs, 'taskMs') });
    console.log(KIND, 'idle', JSON.stringify(sum(out.idle)), 'move', JSON.stringify(sum(out.move)));
    console.log(JSON.stringify(out));
    await browser.close();
}

// The big style recalcs of one Atlas float in order: each UpdateLayoutTree of
// 100+ elements with its duration, and the attribute mutations under
// #nm-buddy (marked with performance.mark) that came just before it, so the
// attribute behind each is named. Env: BASE, LOOK (masculine).
async function companionrecalcorder() {
  const { boot } = require('./lib.js');
    const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
    await page.evaluate(async (look) => {
      localStorage.setItem('atlas-look', look); localStorage.removeItem('nm-buddy-spots');
      prefs.set('avatar-buddy', 'atlas'); await ensureModule('characters'); syncNameMarkBuddy();
    }, process.env.LOOK || 'masculine');
    await page.waitForTimeout(3500);
    await page.evaluate(() => {
      clearTimeout(nmb.timer);
      window.nameMarkBuddySchedule = () => {}; window.nameMarkBuddyTick = () => {};
      window.nameMarkBuddyQueuePlace = () => {}; window.nameMarkBuddyCheck = () => {};
      const buddy = document.getElementById('nm-buddy');
      nameMarkBuddyRide(null, 400, 420);
      nameMarkBuddyMoveTo(buddy, { kind: 'card', pose: 'stand', legs: '', x: 400, y: 420 }, true);
      window.__mo = new MutationObserver((list) => { for (const m of list) performance.mark(`mut ${m.target.id || m.target.className.toString().split(' ')[0] || m.target.tagName} ${m.attributeName}=${m.target.getAttribute(m.attributeName)?.slice(0, 30)}`); });
      window.__mo.observe(buddy, { attributes: true, subtree: true, attributeFilter: ['class', 'data-pose', 'data-lean', 'data-atlas-variant', 'data-perch', 'data-legs', 'data-side', 'data-route', 'data-travel', 'data-gait', 'style'] });
    });
    await page.waitForTimeout(1500);
    const cdp = await page.context().newCDPSession(page);
    const events = [];
    cdp.on('Tracing.dataCollected', (d) => events.push(...d.value));
    await cdp.send('Tracing.start', { traceConfig: { includedCategories: ['devtools.timeline', 'blink.user_timing'] } });
    await page.evaluate(() => { nameMarkBuddyMoveTo(document.getElementById('nm-buddy'), { kind: 'card', pose: 'stand', legs: '', x: 560, y: 380 }); });
    await page.waitForTimeout(2800);
    const done = new Promise((r) => cdp.once('Tracing.tracingComplete', r));
    await cdp.send('Tracing.end'); await done;
    const rel = events.filter((e) => (e.name === 'UpdateLayoutTree' && e.ph === 'X') || (e.cat || '').includes('blink.user_timing')).sort((a, b) => a.ts - b.ts);
    const t0 = rel[0]?.ts || 0;
    for (const e of rel) {
      if (e.name === 'UpdateLayoutTree') {
        if ((e.args?.elementCount ?? 0) >= 100 || e.dur > 6000) console.log(`${((e.ts - t0) / 1000).toFixed(0).padStart(5)}ms  RECALC ${e.args?.elementCount} el  ${(e.dur / 1000).toFixed(1)}ms`);
      } else if (e.name.startsWith('mut ')) console.log(`${((e.ts - t0) / 1000).toFixed(0).padStart(5)}ms    ${e.name}`);
    }
    await browser.close();
}

const CASES = {
  companionmoods,
  companioncost,
  companionrecalcorder,
};
const names = process.argv.slice(2);
const unknown = names.filter((n) => !Object.prototype.hasOwnProperty.call(CASES, n));
if (unknown.length) {
  console.error(`unknown case: ${unknown.join(", ")}`);
  console.error(`cases: ${Object.keys(CASES).join(", ")}`);
  process.exit(2);
}
(async () => {
  for (const name of names.length ? names : Object.keys(CASES)) await CASES[name]();
})();
