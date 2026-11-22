// quickadd.js sweep (Brief 66, CHAT_PLAN decision 50): the 60-phrase set
// (tests/fixtures/composer/quickadd_1010.json) typed into its surface with
// the page clock at the set's "now". For each phrase: the chips' latency from
// the last key, what the save sent (intercepted: nothing is stored), whether
// that equals the fixture (the score) and whether it equals what the chips
// said (saved = chip). LAYOUT=1 instead opens each surface with one phrase at
// the current viewport and theme and measures the chip row (no overflow,
// inside the viewport, chips at least 24px tall, ink not the ground).
//
//   BASE=http://127.0.0.1:8812 node scratchpad/ui-sweeps/quickadd.js
//   BASE=... LAYOUT=1 WIDTH=390 THEME=dark node scratchpad/ui-sweeps/quickadd.js
const fs = require('fs');
const path = require('path');
const { boot } = require('./lib');

const FIX = JSON.parse(fs.readFileSync(path.join(__dirname, '../../tests/fixtures/composer/quickadd_1010.json'), 'utf8'));
const WIDTH = Number(process.env.WIDTH || 1440);
const phone = WIDTH < 600;

const FIELD = { reminder: '#reminder-magic', note: '#quick-note-text', meeting: '#meeting-new-title', timeline: '#timeline-search', palette: '#palette-input' };

async function openSurface(page, surface) {
  await page.evaluate(async (s) => {
    document.querySelectorAll('[data-sheet] .sheet-close, [data-sheet] [aria-label="Close"]').forEach((b) => b.click());
    if (document.getElementById('quick-note')?.open) document.getElementById('quick-note').close();
    if (!document.getElementById('palette-overlay').classList.contains('hidden')) closePalette();
    if (s === 'reminder') { await switchTab('reminders'); openReminderCompose(); }
    if (s === 'note') await openQuickNote();
    if (s === 'meeting') await openNewMeeting();
    if (s === 'timeline') await switchTab('timeline');
    if (s === 'palette') await openPalette();
    await ensureModule('quickAdd');
  }, surface);
  await page.waitForSelector(FIELD[surface], { state: 'visible', timeout: 10000 });
  await page.waitForTimeout(300);
}

//: Types the phrase, then waits for its reading; answers the chips and the
//: time from the last key to the chip row's last change.
async function typePhrase(page, surface, text) {
  const sel = FIELD[surface];
  await page.evaluate((sel) => {
    const f = document.querySelector(sel);
    f.value = '';
    f.dispatchEvent(new Event('input', { bubbles: true }));
  }, sel);
  await page.waitForTimeout(150);
  await page.evaluate((sel) => {
    const f = document.querySelector(sel);
    window.__qaKey = 0;
    window.__qaLast = 0;
    f.addEventListener('input', () => { window.__qaKey = performance.now(); });
    const state = quickAddAttach.fields.get(f);
    if (window.__qaObs) window.__qaObs.disconnect();
    window.__qaObs = new MutationObserver(() => { window.__qaLast = performance.now(); });
    window.__qaObs.observe(state.row, { childList: true, subtree: true, attributes: true });
  }, sel);
  await page.focus(sel);
  await page.keyboard.type(text, { delay: 25 });
  await page.waitForFunction((sel) => {
    const f = document.querySelector(sel);
    const st = quickAddAttach.fields.get(f);
    return st && st.text === f.value && !st.timer && !st.pending;
  }, sel, { timeout: 8000 });
  return page.evaluate((sel) => {
    const st = quickAddAttach.fields.get(document.querySelector(sel));
    const chips = [...st.row.querySelectorAll('.qa-chip')].map((c) => ({ kind: c.dataset.kind, value: c.dataset.value, on: !c.classList.contains('is-off'), words: c.textContent.trim() }));
    return { chips, latency: window.__qaLast && window.__qaKey ? window.__qaLast - window.__qaKey : null, reading: !!st.reading };
  }, sel);
}

function local(iso) {
  const d = new Date(iso);
  const p = (n) => String(n).padStart(2, '0');
  return { date: `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`, time: `${p(d.getHours())}:${p(d.getMinutes())}` };
}

function chipWhen(chips) {
  const on = chips.filter((c) => c.on && ['date', 'time', 'datetime'].includes(c.kind));
  let date = null;
  let time = null;
  for (const c of on) for (const part of c.value.split(' ')) {
    if (/^\d{4}-/.test(part)) date = part; else if (/^\d{2}:\d{2}$/.test(part)) time = part;
  }
  return { date, time };
}

async function score(page) {
  const sent = [];
  await page.route(/\/(reminders|entries|meetings)$/, (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    sent.push({ url: route.request().url(), body: JSON.parse(route.request().postData() || '{}') });
    return route.fulfill({ status: 422, contentType: 'application/json', body: JSON.stringify({ detail: 'Sweep: not saved.' }) });
  });
  const rows = [];
  //: First letters compared without case: the reader writes "Pay rent".
  const same = (a, b) => String(a || '').toLowerCase() === String(b || '').toLowerCase();
  for (const row of FIX.phrases) {
    //: Back to the set's "now" for every phrase, so "in 20 minutes" is read
    //: from the same minute however long the run has taken.
    await page.clock.setSystemTime(new Date(FIX.now));
    await openSurface(page, row.surface);
    const typed = await typePhrase(page, row.surface, row.text);
    sent.length = 0;
    const e = row.expect;
    let got = {};
    let ok = false;
    let chipOk = true;
    if (row.surface === 'timeline') {
      await page.keyboard.press('Enter');
      await page.waitForTimeout(400);
      got = await page.evaluate(() => ({ start: $('timeline-start-date').value, end: $('timeline-end-date').value, rest: $('timeline-search').value, days: $('timeline-days').value }));
      ok = got.days === 'custom' && got.start === e.range.start && got.end === e.range.end && got.rest === e.rest;
      await page.evaluate(() => { $('timeline-days').value = '30'; $('timeline-days').dispatchEvent(new Event('change')); $('timeline-search').value = ''; $('timeline-start-date').value = ''; $('timeline-end-date').value = ''; });
    } else if (row.surface === 'palette') {
      const first = await page.evaluate(() => document.querySelector('#palette-list [role="option"], #palette-list li:not(.palette-group-header)')?.textContent.trim() || '');
      got.first = first;
      if (!e.act) ok = !/^Remind you/.test(first);
      else {
        await page.keyboard.press('Enter');
        await page.waitForTimeout(700);
        const r = sent.find((s) => /reminders$/.test(s.url));
        if (r) {
          const w = local(r.body.due_at);
          got = { first, text: r.body.text, ...w, recurring: r.body.recurring };
          ok = same(r.body.text, e.title) && w.date === e.date && w.time === e.time && r.body.recurring === e.recurring;
          const c = chipWhen(typed.chips);
          chipOk = (!c.date || c.date === w.date) && (!c.time || c.time === w.time);
        }
      }
    } else if (row.surface === 'reminder') {
      await page.keyboard.press('Enter');
      await page.waitForTimeout(700);
      const r = sent.find((s) => /reminders$/.test(s.url));
      const ask = await page.evaluate(() => { const a = quickAddAttach.fields.get($('reminder-magic')).ask; return a.classList.contains('hidden') ? '' : a.textContent; });
      if (e.ask) { ok = !r && !!ask; got = { ask }; }
      else if (r) {
        const w = local(r.body.due_at);
        got = { text: r.body.text, ...w, recurring: r.body.recurring };
        ok = same(r.body.text, e.title) && w.date === e.date && w.time === e.time && r.body.recurring === e.recurring;
        const c = chipWhen(typed.chips);
        chipOk = (!c.date || c.date === w.date) && (!c.time || c.time === w.time);
      } else got = { ask, none: true };
    } else if (row.surface === 'note') {
      await page.keyboard.press('Control+Enter');
      await page.waitForTimeout(700);
      const n = sent.find((s) => /entries$/.test(s.url));
      got = { tags: n?.body.tags };
      ok = !!n && JSON.stringify([...(n.body.tags || [])].sort()) === JSON.stringify([...e.tags].sort());
      const tagChips = typed.chips.filter((c) => c.kind === 'tag' && c.on).map((c) => c.value).sort();
      chipOk = JSON.stringify(tagChips) === JSON.stringify([...(n?.body.tags || [])].sort());
      //: The note's save is refused here, so its reminder is never asked
      //: for: what the chips would remind is checked instead.
      if (e.reminder) {
        const c = chipWhen(typed.chips);
        got.when = c;
        ok = ok && c.date === e.reminder.date && c.time === e.reminder.time;
      }
      await page.evaluate(() => { $('quick-note-text').value = ''; quickAddClear($('quick-note-text')); });
    } else if (row.surface === 'meeting') {
      await page.keyboard.press('Enter');
      await page.waitForTimeout(700);
      const m = sent.find((s) => /meetings$/.test(s.url));
      if (m) {
        got = { title: m.body.title, when: m.body.when, attendees: m.body.attendees };
        const [date, time] = (m.body.when || '').split('T');
        ok = same(m.body.title, e.title) && (e.date ? date === e.date && time === e.time : true)
          && e.people.every((p) => (m.body.attendees || []).includes(p)) && (m.body.attendees || []).length === e.people.length;
        const c = chipWhen(typed.chips);
        chipOk = (!c.date || c.date === date) && (!c.time || c.time === time);
      }
    }
    rows.push({ surface: row.surface, text: row.text, ok, chipOk, latency: typed.latency, chips: typed.chips.length, reading: typed.reading, got, expect: e });
    if (!ok || !chipOk) console.log('MISS', row.surface, JSON.stringify(row.text), JSON.stringify(got), 'chips', JSON.stringify(typed.chips.map((c) => `${c.kind}=${c.value}${c.on ? '' : '(off)'}`)));
  }
  const lat = rows.map((r) => r.latency).filter((x) => x != null).sort((a, b) => a - b);
  const pct = (q) => lat.length ? Math.round(lat[Math.min(lat.length - 1, Math.floor(q * lat.length))]) : null;
  const passed = rows.filter((r) => r.ok).length;
  const per = {};
  for (const r of rows) { per[r.surface] = per[r.surface] || [0, 0]; per[r.surface][1]++; if (r.ok) per[r.surface][0]++; }
  console.log(`SCORE ${passed}/${rows.length} = ${(passed / rows.length).toFixed(3)}`, JSON.stringify(per));
  console.log(`SAVED=CHIP ${rows.filter((r) => r.chipOk).length}/${rows.length}`);
  console.log(`LATENCY ms median ${pct(0.5)} p90 ${pct(0.9)} max ${lat.length ? Math.round(lat[lat.length - 1]) : null} over ${lat.length}; over 150: ${lat.filter((x) => x > 150).length}`);
  console.log(`NO READING ${rows.filter((r) => !r.reading).length}`);
  fs.writeFileSync(path.join(process.env.SCRATCH || '.', 'quickadd-score.json'), JSON.stringify(rows, null, 1));
}

async function layout(page) {
  const SAMPLE = { reminder: 'call mum tomorrow at 6pm every week', note: 'remind me to call the plumber tomorrow at 10am #house #work', meeting: 'Kickoff with Priya and Sam on 22 october at 9:30am', timeline: 'harbor last week', palette: 'remind me friday 9 dentist' };
  const out = [];
  for (const surface of Object.keys(SAMPLE)) {
    await openSurface(page, surface);
    await typePhrase(page, surface, SAMPLE[surface]);
    const m = await page.evaluate((sel) => {
      const st = quickAddAttach.fields.get(document.querySelector(sel));
      const row = st.row;
      const r = row.getBoundingClientRect();
      const chips = [...row.querySelectorAll('.qa-chip')];
      const cs = chips[0] ? getComputedStyle(chips[0]) : null;
      return {
        shown: !row.classList.contains('hidden') && r.height > 0, chips: chips.length,
        overflow: row.scrollWidth - row.clientWidth, left: Math.round(r.left), right: Math.round(r.right), vw: innerWidth,
        minH: chips.length ? Math.min(...chips.map((c) => c.getBoundingClientRect().height)) : 0,
        color: cs?.color, bg: cs?.backgroundColor,
        //: Hit boxes (the chip's own box grown to the target height) that
        //: overlap each other or the field: a tap that lands on two.
        clash: (() => {
          const raw = getComputedStyle(document.documentElement).getPropertyValue('--target-min').trim();
          const t = /rem$/.test(raw) ? parseFloat(raw) * parseFloat(getComputedStyle(document.documentElement).fontSize) : parseFloat(raw) || 28;
          const hit = (el) => { const b = el.getBoundingClientRect(); const pad = Math.max(0, (t - b.height) / 2); return { l: b.left, r: b.right, t: b.top - pad, b: b.bottom + pad }; };
          const boxes = chips.map(hit);
          const fb = st.field.getBoundingClientRect();
          let n = boxes.filter((b) => b.t < fb.bottom - 0.5 && b.l < fb.right && b.r > fb.left).length;
          for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
            const a = boxes[i], c = boxes[j];
            if (a.l < c.r - 0.5 && c.l < a.r - 0.5 && a.t < c.b - 0.5 && c.t < a.b - 0.5) n++;
          }
          return n;
        })(), offscreen: chips.filter((c) => { const b = c.getBoundingClientRect(); return b.right > innerWidth + 0.5 || b.left < -0.5; }).length,
      };
    }, FIELD[surface]);
    await page.screenshot({ path: path.join(process.env.SCRATCH || '.', `shots/quickadd-${surface}-${WIDTH}-${process.env.THEME || 'light'}.png`) });
    const bad = !m.shown || m.clash || m.overflow > 0 || m.offscreen || m.right > m.vw || m.left < 0 || m.minH < 20 || m.color === m.bg;
    out.push({ surface, ...m, bad });
    console.log(bad ? 'BAD ' : 'OK  ', surface, JSON.stringify(m));
  }
  console.log(`LAYOUT ${WIDTH} ${process.env.THEME || 'light'}: ${out.filter((o) => !o.bad).length}/${out.length} clean`);
}

(async () => {
  const opts = { viewport: { width: WIDTH, height: phone ? 844 : 900 }, clock: FIX.now };
  if (phone) Object.assign(opts, { hasTouch: true, isMobile: true });
  const { browser, page } = await boot(opts);
  try {
    if (process.env.LAYOUT) await layout(page); else await score(page);
  } finally {
    await browser.close();
  }
})();
