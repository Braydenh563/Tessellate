// Computed styles of every collapsed sidebar and its direct children in three
// states (rest, mouse over the aside, keyboard focus inside it), for a
// before/after diff when the peek rules move (tab-entry cost: the focus twin
// `:is(:focus-visible, :has(:focus-visible)) > :not(...)` was a :has() anchor
// with a universal descendant, which restyled a whole card on every insert).
//
//   OUT=/tmp/a.json BASE=... node sbpeekdump.js
//   OLD=1 OLD07=a.css OLD08=b.css OUT=/tmp/o.json BASE=... node sbpeekdump.js  (previous CSS text)
//   node sbpeekdump.js --diff a.json b.json
const fs = require('fs');
if (process.argv[2] === '--diff') {
  const a = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
  const b = JSON.parse(fs.readFileSync(process.argv[4], 'utf8'));
  let n = 0;
  for (const key of new Set([...Object.keys(a), ...Object.keys(b)])) {
    if (!(key in a) || !(key in b)) { console.log('MISSING', key); n++; continue; }
    for (const prop of new Set([...Object.keys(a[key]), ...Object.keys(b[key])])) {
      if (a[key][prop] !== b[key][prop]) { console.log(key, prop, a[key][prop], '->', b[key][prop]); n++; }
    }
  }
  console.log(`${Object.keys(a).length} records, ${n} differences`);
  process.exit(0);
}
const { boot } = require('./lib.js');
const TABS = (process.env.TABS || 'notes,chat,library,documents,timeline,graph,reminders,dashboard').split(',');
// FORCE=doc-sidebar,skills-sidebar: asides on pages the tab bar does not reach
// (the documents tab, Library's skills view) are shown by unhiding their ancestors.
const FORCE = (process.env.FORCE || '').split(',').filter(Boolean);
(async () => {
  const { browser, page, ctx } = await boot({ viewport: { width: +(process.env.W || 1440), height: 900 }, serviceWorkers: 'block' });
  if (process.env.OLD) {
    for (const [pat, file] of [['**/css/07-whiteboard-misc.css*', process.env.OLD07], ['**/css/08-consistency.css*', process.env.OLD08]]) {
      await ctx.route(pat, (route) => route.fulfill({ status: 200, contentType: 'text/css', body: fs.readFileSync(file, 'utf8') }));
    }
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1500);
    await page.fill('#lock-password', 'testpassword123').catch(() => {});
    await page.click('#lock-submit').catch(() => {});
    await page.waitForTimeout(2000);
  }
  await page.getByRole('button', { name: "Don't check" }).click({ timeout: 3000 }).catch(() => {});
  await page.evaluate(() => { const b = document.getElementById('avatar-buddy'); if (b) { b.value = 'off'; b.dispatchEvent(new Event('change', { bubbles: true })); } });
  const out = {};
  const snap = async (label, sel) => {
    const rec = await page.evaluate((sel) => {
      const aside = document.querySelector(sel);
      const res = {};
      const list = [aside, ...aside.children];
      list.forEach((el, i) => {
        const cs = getComputedStyle(el);
        const r = {};
        for (let j = 0; j < cs.length; j += 1) r[cs[j]] = cs.getPropertyValue(cs[j]);
        res[`${i}:${el.tagName}#${el.id}.${[...el.classList].join('.')}`] = r;
      });
      return res;
    }, sel);
    for (const [k, v] of Object.entries(rec)) out[`${label} ${k}`] = v;
  };
  for (const tab of FORCE.length ? [] : TABS) {
    await page.click(`#tab-bar button[data-tab="${tab}"]`, { timeout: 4000 }).catch(() => {});
    await page.waitForTimeout(1200);
    const asides = await page.evaluate((tab) => [...document.querySelectorAll(`#tab-${tab} aside[data-resizable]`)].map((a, i) => { if (!a.id) a.id = `sbd-${tab}-${i}`; return a.id; }), tab);
    for (const id of asides) {
      const sel = `#${id}`;
      const ok = await page.evaluate((sel) => {
        const a = document.querySelector(sel);
        const r = a.getBoundingClientRect();
        if (!r.width) return false;
        a.classList.add('sidebar-collapsed');
        a.parentElement.classList.add('layout-sidebar-collapsed');
        return true;
      }, sel);
      if (!ok) continue;
      await page.mouse.move(2, 2);
      await page.waitForTimeout(1500);
      await snap(`${tab}/${id} rest`, sel);
      const box = await (await page.$(sel)).boundingBox();
      await page.mouse.move(box.x + box.width / 2, box.y + Math.min(box.height / 2, 200));
      await page.waitForTimeout(1500);
      await snap(`${tab}/${id} hover`, sel);
      await page.mouse.move(2, 2);
      await page.waitForTimeout(1500);
      // Keyboard modality, then focus the first focusable inside (visible or not: opacity 0 still takes focus).
      await page.keyboard.press('Shift');
      const focused = await page.evaluate((sel) => {
        const a = document.querySelector(sel);
        const f = [...a.querySelectorAll('button:not(.sidebar-collapse-toggle):not(.sidebar-resize), a[href], input, select, [tabindex]:not([tabindex="-1"])')].find((e) => e.offsetParent !== null && e.getClientRects().length);
        if (!f) return false;
        f.focus({ focusVisible: true });
        return f.matches(':focus-visible');
      }, sel);
      await page.waitForTimeout(1500);
      await snap(`${tab}/${id} focus${focused ? '' : '-none'}`, sel);
      await page.evaluate(() => document.activeElement && document.activeElement.blur());
      await page.evaluate((sel) => { const a = document.querySelector(sel); a.classList.remove('sidebar-collapsed'); a.parentElement.classList.remove('layout-sidebar-collapsed'); }, sel);
    }
  }
  for (const id of FORCE) {
    await page.evaluate((id) => {
      document.querySelectorAll('.tab-page').forEach((t) => t.classList.add('hidden'));
      for (let e = document.getElementById(id); e && e !== document.body; e = e.parentElement) e.classList.remove('hidden');
    }, id);
    await page.waitForTimeout(800);
    const ok = await page.evaluate((id) => {
      const a = document.getElementById(id);
      if (!a.getBoundingClientRect().width) return false;
      a.classList.add('sidebar-collapsed');
      a.parentElement.classList.add('layout-sidebar-collapsed');
      return true;
    }, id);
    if (!ok) { console.log('not visible', id); continue; }
    const sel = `#${id}`;
    await page.mouse.move(2, 2);
    await page.waitForTimeout(1500);
    await snap(`${id} rest`, sel);
    const box = await (await page.$(sel)).boundingBox();
    await page.mouse.move(box.x + box.width / 2, box.y + Math.min(box.height / 2, 200));
    await page.waitForTimeout(1500);
    await snap(`${id} hover`, sel);
    await page.mouse.move(2, 2);
    await page.waitForTimeout(1500);
    await page.keyboard.press('Shift');
    const focused = await page.evaluate((sel) => {
      const a = document.querySelector(sel);
      const f = [...a.querySelectorAll('button:not(.sidebar-collapse-toggle):not(.sidebar-resize), a[href], input, select, [tabindex]:not([tabindex="-1"])')].find((e) => e.offsetParent !== null && e.getClientRects().length);
      if (!f) return false;
      f.focus({ focusVisible: true });
      return f.matches(':focus-visible');
    }, sel);
    await page.waitForTimeout(1500);
    await snap(`${id} focus${focused ? '' : '-none'}`, sel);
  }
  fs.writeFileSync(process.env.OUT, JSON.stringify(out));
  console.log(Object.keys(out).length, 'records;', [...new Set(Object.keys(out).map((k) => k.split(' ').slice(0, 2).join(' ')))].join(' | '));
  await browser.close();
})();
