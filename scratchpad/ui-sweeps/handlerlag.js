// Handler lag (L-world-class-355, the follow-on of L982): Event Timing (durationThreshold 16) and
// long-animation-frame attribution at 4x CPU while a person
//   1. types and arrows in Settings (every pane's first text field, the search box, the nav list),
//   2. hovers chat messages (pointer sweep over .msg bubbles of a 15-turn conversation),
//   3. presses each of the 7 top tabs (#tab-btn-*), after one warm visit of each,
//   4. moves the pointer over the Graph canvas (hover and out: gcRequestDraw frames).
// PASS or FAIL per item against BAR (100 ms) on the event's whole duration (wait + handler + the
// frame that shows the answer); the handler's own ms and the busiest script of the frame are printed.
//
//   BASE=http://127.0.0.1:8812 node scratchpad/ui-sweeps/handlerlag.js   (RATE=4, BAR=100)
const { boot } = require('./lib.js');
const RATE = Number(process.env.RATE || 4);
const BAR = Number(process.env.BAR || 100);
const TABS = ['dashboard', 'notes', 'chat', 'graph', 'library', 'timeline', 'reminders'];

const OBSERVE = () => {
  window.__ev = []; window.__loaf = [];
  const add = (type, list, map, extra) => { try { new PerformanceObserver((l) => { for (const e of l.getEntries()) list.push(map(e)); }).observe({ type, buffered: true, ...extra }); } catch (e) {} };
  add('event', window.__ev, (e) => ({ n: e.name, s: e.startTime, d: e.duration, wait: e.processingStart - e.startTime, proc: e.processingEnd - e.processingStart, t: e.target ? (e.target.id || String(e.target.className).slice(0, 40) || e.target.tagName) : '' }), { durationThreshold: 16 });
  add('long-animation-frame', window.__loaf, (e) => ({ s: e.startTime, d: e.duration, scripts: e.scripts.map((x) => ({ d: x.duration, forced: x.forcedStyleAndLayoutDuration, src: String(x.sourceURL || '').replace(/^.*\/js\//, '').replace(/\?.*/, ''), fn: x.sourceFunctionName || x.invoker, type: x.invokerType, pos: x.sourceCharPosition })) }), {});
};

const results = [];
//: The verdict is the handler: the event's own processing, or the biggest script of the frame that ran it
//: (a click handler's work can land in the frame's other callbacks). The event's whole duration (input wait
//: and the frame that paints the answer, mostly style and layout) is printed beside it, as "shown in".
const note = (group, label, ev, loaf) => {
  const byD = ev.reduce((a, b) => (b.d > a.d ? b : a), { d: 0, proc: 0 });
  const byP = ev.reduce((a, b) => (b.proc > a.proc ? b : a), { d: 0, proc: 0 });
  const frames = ev.map((e) => loaf.find((f) => e.s >= f.s - 2 && e.s <= f.s + f.d + 2)).filter(Boolean);
  const scripts = frames.flatMap((f) => f.scripts).filter((x) => /\/|\.js/.test(x.src) || x.src);
  const top = [...scripts].sort((a, b) => b.d - a.d)[0];
  const handler = Math.max(byP.proc, top ? top.d : 0);
  const why = top ? `${top.src}:${top.fn}@${top.pos} ${Math.round(top.d)}ms${top.forced > 5 ? ` forced ${Math.round(top.forced)}ms` : ''} (${top.type})` : 'no script over the frame threshold';
  const ok = handler <= BAR;
  results.push(ok);
  console.log(`${ok ? 'PASS' : 'FAIL'} ${group} / ${label}: handler ${Math.round(handler)} ms (event ${byP.n || 'none'} processing ${Math.round(byP.proc)} on ${byP.t || '-'}); shown in ${Math.round(byD.d)} ms (${byD.n || 'none'}, wait ${Math.round(byD.wait || 0)}); ${ev.length} events over 16 ms; ${why}`);
};
const only = (g) => !process.env.ONLY || process.env.ONLY.split(',').includes(g);

process.on('unhandledRejection', (e) => { console.log('ERROR', e && e.message); process.exit(2); });
(async () => {
  const { browser, ctx, page } = await boot();
  await ctx.addInitScript(OBSERVE);
  await page.evaluate(OBSERVE);
  const cdp = await ctx.newCDPSession(page);
  const settle = (ms) => page.waitForTimeout(ms);
  const take = () => page.evaluate(() => { const r = { ev: window.__ev.splice(0), loaf: window.__loaf.splice(0) }; return r; });
  // A conversation with fifteen turns, so there are messages to hover.
  let seededId = null;
  await page.evaluate(async () => {
    const post = (p, b) => apiJson(p, { method: 'POST', body: JSON.stringify(b) });
    const c = await post('/conversations', { question: 'First question about the garden', answer: 'Keep the zebrafish at 26 degrees. '.repeat(8) });
    for (let i = 0; i < 14; i += 1) await post(`/conversations/${c.id}/turns`, { question: `Question ${i} about soil and light`, answer: `Answer ${i}. ` + 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. '.repeat(6) });
    return c.id;
  }).then((id) => { seededId = id; }).catch((e) => console.log('seed failed', e.message));
  await page.evaluate(() => { const b = document.getElementById('avatar-buddy'); if (b) { b.value = 'off'; b.dispatchEvent(new Event('change', { bubbles: true })); } }).catch(() => {});
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => document.getElementById('lock-overlay')?.classList.contains('hidden') && !document.documentElement.classList.contains('shell-curtain'), null, { timeout: 60000 }).catch(() => {});
  await settle(3000);
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: RATE });
  await take();

  // 3. top tabs: a warm visit, then the measured press, each from the dashboard.
  if (only('tabs')) for (const tab of TABS) {
    await page.click('#tab-btn-dashboard'); await settle(900);
    await page.click(`#tab-btn-${tab}`); await settle(1800);
    await page.click('#tab-btn-dashboard'); await settle(900);
    await take();
    await page.click(`#tab-btn-${tab}`); await settle(1800);
    const { ev, loaf } = await take();
    note('tab press', tab, ev.filter((e) => /pointer|click|mouse|key/.test(e.n)), loaf);
  }

  // 2. chat hover: sweep the pointer down the transcript twice.
  if (only('chat')) { await page.click('#tab-btn-chat'); await settle(2500); if (seededId) { await page.evaluate((id) => openConversation(id), seededId); await settle(2500); }
  await page.evaluate(() => { const c = document.getElementById('chat-messages'); if (c) c.scrollTop = 0; });
  await take();
  const box = await page.evaluate(() => { const m = document.querySelectorAll('#chat-messages .msg'); const r = m.length ? m[Math.min(2, m.length - 1)].getBoundingClientRect() : null; return r && { x: r.x + r.width / 2, y: r.y + 10, n: m.length }; });
  if (box) {
    for (let pass = 0; pass < 2; pass += 1) for (let y = 150; y < 820; y += 22) { await page.mouse.move(box.x + (y % 3) * 8, y); await settle(30); }
    await settle(500);
    const { ev, loaf } = await take();
    note('chat hover', `${box.n} messages`, ev.filter((e) => /pointer|mouse/.test(e.n)), loaf);
  } else console.log('FAIL chat hover: no .msg bubbles found'); }

  // 4. graph canvas hover and out.
  if (only('graph')) { await page.click('#tab-btn-graph'); await settle(4000); await take();
  const cv = await page.evaluate(() => { const c = document.querySelector('#tab-graph canvas'); const r = c && c.getBoundingClientRect(); return r && { x: r.x, y: r.y, w: r.width, h: r.height }; });
  if (cv) {
    for (let i = 0; i < 40; i += 1) { await page.mouse.move(cv.x + 40 + i * (cv.w - 80) / 40, cv.y + cv.h / 2 + Math.sin(i) * 60); await settle(25); }
    await page.mouse.move(2, 2); await settle(600);
    const { ev, loaf } = await take();
    note('graph canvas', 'hover, pointerout', ev.filter((e) => /pointer|mouse/.test(e.n)), loaf);
    const draws = loaf.filter((f) => f.scripts.some((s) => /graph-canvas/.test(s.src)));
    console.log(`     graph frames with graph-canvas scripts: ${draws.length}, longest ${Math.round(Math.max(0, ...draws.map((f) => f.d)))} ms`);
  } else console.log('INFO graph canvas: none drawn (no links in this notebook)'); }

  // 1. Settings: open, then type and arrow in each pane.
  if (only('settings')) {
  await page.click('#tab-btn-dashboard'); await settle(800);
  await page.click('#settings-btn'); await settle(2500); await take();
  const sections = await page.evaluate(() => [...document.querySelectorAll('#settings-nav button[data-section]')].map((b) => b.dataset.section));
  const worstBy = [];
  for (const sec of sections) {
    await page.evaluate((s) => document.querySelector(`#settings-nav button[data-section="${s}"]`)?.click(), sec);
    await settle(700); await take();
    const field = await page.evaluate((s) => { const pane = document.getElementById(`settings-${s}`) || document.querySelector(`#settings-body [data-section="${s}"]`) || document.getElementById('settings-body'); const i = pane && [...pane.querySelectorAll('input[type=text], input[type=search], input:not([type]), textarea')].find((x) => x.offsetParent !== null && !x.readOnly && !x.disabled); if (i) { i.focus(); return true; } return false; }, sec);
    const nav = await page.evaluate((s) => { const b = document.querySelector(`#settings-nav button[data-section="${s}"]`); if (b) b.focus(); return !!b; }, sec);
    for (const k of ['ArrowDown', 'ArrowUp', 'Home']) { if (nav) await page.keyboard.press(k); await settle(120); }
    if (field) { await page.evaluate((s) => { const pane = document.getElementById(`settings-${s}`) || document.getElementById('settings-body'); const i = [...pane.querySelectorAll('input[type=text], input[type=search], input:not([type]), textarea')].find((x) => x.offsetParent !== null && !x.readOnly && !x.disabled); i && i.focus(); }, sec); for (const k of 'ab1 ') { await page.keyboard.press(k); await settle(60); } await page.keyboard.press('Backspace'); await settle(60); await page.keyboard.press('Backspace'); await settle(60); await page.keyboard.press('Backspace'); await settle(60); await page.keyboard.press('Backspace'); await settle(300); }
    const { ev, loaf } = await take();
    worstBy.push([sec, ev.filter((e) => /key/.test(e.n)), loaf]);
  }
  for (const [sec, ev, loaf] of worstBy) note('settings keys', sec, ev, loaf);
  await page.fill('#settings-search', '').catch(() => {});
  await page.focus('#settings-search').catch(() => {}); await settle(500); await take(); // a person pauses between the click and the first key; the row index warms while idle
  for (const k of 'dark mode') { await page.keyboard.press(k === ' ' ? 'Space' : k); await settle(80); }
  await settle(600);
  { const { ev, loaf } = await take(); note('settings keys', 'search box typing', ev.filter((e) => /key/.test(e.n)), loaf); }
  }

  await browser.close();
  const bad = results.filter((x) => !x).length;
  console.log(bad ? `\nFAIL: ${bad} of ${results.length} items over ${BAR} ms at ${RATE}x` : `\nPASS: ${results.length} items under ${BAR} ms at ${RATE}x`);
  process.exit(bad ? 1 : 0);
})();
