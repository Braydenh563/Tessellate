// INBOX 1696 bb: "the screen scrolls again when I throw the in-app companion (sometimes)".
// Throws Atlas in 8 directions at 2 speeds on several tabs; logs every scroll event's target and
// every script call that can scroll (scrollIntoView, scrollTo, scrollBy, focus, scrollTop set) with its stack.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  await page.evaluate(() => { prefs.set('avatar-buddy', 'atlas'); syncNameMarkBuddy(); });
  await page.evaluate(() => {
    window.__sc = [];
    const who = (t) => t === document || t === window ? 'document' : `${t.tagName}#${t.id}.${String(t.className).slice(0, 40)}`;
    document.addEventListener('scroll', (e) => __sc.push({ t: Math.round(performance.now()), sel: String(getSelection()).length, ev: who(e.target), top: e.target === document ? scrollY : e.target.scrollTop, left: e.target === document ? scrollX : e.target.scrollLeft }), true);
    const wrap = (proto, name) => { const f = proto[name]; proto[name] = function (...a) { __sc.push({ call: name, on: who(this), opts: JSON.stringify(a[0] ?? null).slice(0, 60), stack: new Error().stack.split('\n').slice(2, 6).join(' | ') }); return f.apply(this, a); }; };
    wrap(Element.prototype, 'scrollIntoView'); wrap(Element.prototype, 'scrollTo'); wrap(Element.prototype, 'scrollBy'); wrap(HTMLElement.prototype, 'focus'); wrap(window, 'scrollTo');
    const d = Object.getOwnPropertyDescriptor(Element.prototype, 'scrollTop');
    Object.defineProperty(Element.prototype, 'scrollTop', { get: d.get, set(v) { __sc.push({ call: 'scrollTop=', on: who(this), v, stack: new Error().stack.split('\n').slice(2, 6).join(' | ') }); d.set.call(this, v); }, configurable: true });
  });
  const dirs = [[1, 0], [-1, 0], [0, 1], [0, -1], [1, 1], [-1, 1], [1, -1], [-1, -1]];
  for (const tab of (process.env.TABS || 'dashboard,notes,chat,timeline').split(',')) {
    await page.evaluate((t) => revealTab(t), tab);
    await page.waitForTimeout(2500);
    for (let rep = 0; rep < Number(process.env.REPS || 1); rep++) for (const step of [12, 40]) for (const [dx, dy] of dirs) {
      await page.evaluate(() => { __sc.length = 0; });
      const r = await page.evaluate(() => { const e = document.querySelector('#nm-buddy .nm-buddy-face') || document.getElementById('nm-buddy'); const b = e.getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]; });
      if (!r[0]) continue;
      await page.mouse.move(r[0], r[1]); await page.mouse.down();
      for (let i = 1; i <= 6; i++) { await page.mouse.move(r[0] + dx * i * step, r[1] + dy * i * step); await page.waitForTimeout(16); }
      await page.evaluate(() => __sc.push({ call: 'UP', t: Math.round(performance.now()), sel: String(getSelection()).length }));
      await page.mouse.up();
      await page.waitForTimeout(2500);
      const sc = await page.evaluate(() => __sc.filter((x) => x.call || x.ev !== "DIV#.heatmap").slice(0, 40).map((x) => x.call ? x : `${x.t} ${x.ev}:${x.top} sel${x.sel}`));
      if (sc.length) console.log(JSON.stringify({ tab, step, dx, dy, sc }));
    }
    console.log('tab done', tab);
  }
  await browser.close();
})();
