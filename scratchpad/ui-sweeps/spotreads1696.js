// Every geometry or style read inside a throw's landing (spotNow, plan.land), the slow ones with a stack (INBOX 1696 l).
const { boot } = require('./lib.js');
(async () => {
  const { browser, page, ctx } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  const cdp = await ctx.newCDPSession(page);
  await page.evaluate(() => { prefs.set('avatar-buddy', 'atlas'); syncNameMarkBuddy(); revealTab(location.hash ? 'dashboard' : 'dashboard'); });
  await page.waitForTimeout(4000);
  const face = () => page.evaluate(() => { const b = (document.querySelector('#nm-buddy .nm-buddy-face') || document.getElementById('nm-buddy')).getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]; });
  const fling = async () => { const r = await face(); await page.mouse.move(r[0], r[1]); await page.mouse.down(); for (let i = 1; i <= 6; i++) { await page.mouse.move(r[0] - i * 40, r[1] - i * 30); await page.waitForTimeout(8); } await page.mouse.up(); await page.waitForTimeout(3500); };
  await fling(); // loads companion-throw.js
  await page.evaluate(() => {
    window.__reads = []; window.__inLand = false;
    const wrap = (obj, name, label) => { const f = obj[name]; obj[name] = function (...a) { if (!__inLand) return f.apply(this, a); const t = performance.now(); const r = f.apply(this, a); const d = performance.now() - t; __reads.push({ label, el: (this?.id || this?.className?.baseVal || this?.className || this?.tagName || String(a[0]?.id || a[0]?.tagName)).toString().slice(0, 40), d: +d.toFixed(2), stack: true ? new Error().stack.split('\n').slice(2, 10).map((s) => s.trim().replace(/https?:\/\/[^/]+\//, '')).join(' < ') : '' }); return r; }; };
    wrap(Element.prototype, 'getBoundingClientRect', 'rect');
    wrap(Element.prototype, 'getClientRects', 'rects');
    wrap(window, 'getComputedStyle', 'cs');
    for (const p of ['offsetHeight', 'offsetWidth', 'offsetTop', 'offsetLeft', 'scrollTop', 'scrollHeight', 'clientHeight', 'clientWidth']) {
      const proto = p.startsWith('offset') ? HTMLElement.prototype : Element.prototype; const d = Object.getOwnPropertyDescriptor(proto, p); if (!d) continue;
      Object.defineProperty(proto, p, { ...d, get() { if (!__inLand) return d.get.call(this); const t = performance.now(); const r = d.get.call(this); const dd = performance.now() - t; __reads.push({ label: p, el: (this.id || this.className || this.tagName).toString().slice(0, 40), d: +dd.toFixed(2), stack: dd > 1 ? new Error().stack.split('\n').slice(2, 10).map((s) => s.trim().replace(/https?:\/\/[^/]+\//, '')).join(' < ') : '' }); return r; } });
    }
    const f = window.nameMarkBuddyMeasureOnce;
    window.nameMarkBuddyMeasureOnce = (fn, tk) => { __inLand = true; const t = performance.now(); try { return f(fn, tk); } finally { __inLand = false; __reads.push({ label: 'TOTAL', d: +(performance.now() - t).toFixed(1) }); } };
  });
  const dirs = [[40, -30], [-40, -30], [40, 10], [-40, 10], [0, -45], [30, 30], [-30, 30], [45, -5]];
  for (const [k, [dx, dy]] of dirs.entries()) {
    await page.evaluate(([x, y]) => { const spot = { kind: 'yours', pose: 'float', legs: '', x, y }; nameMarkBuddyMoveTo(document.getElementById('nm-buddy'), spot, true); nmb.placedAt = Date.now(); }, [300 + (k % 4) * 250, 380]);
    await page.waitForTimeout(1500);
    await page.evaluate(() => { __reads = []; });
    const r = await face(); await page.mouse.move(r[0], r[1]); await page.mouse.down();
    for (let i = 1; i <= 6; i++) { await page.mouse.move(r[0] + i * dx, r[1] + i * dy); await page.waitForTimeout(8); }
    await page.mouse.up(); await page.waitForTimeout(3000);
    const reads = await page.evaluate(() => __reads);
    const first = reads.find((x) => x.label !== 'TOTAL');
    const fstack = first ? await page.evaluate(() => { const f = __reads.find((x) => x.label !== 'TOTAL'); return f.stack; }) : '';
    console.log(k, JSON.stringify(await page.evaluate(() => nmb.thrown && { fate: nmb.thrown.fate, to: nmb.thrown.to })), 'reads', reads.length - 1, 'ms', reads.filter((x) => x.label === 'TOTAL').map((x) => x.d).join(','), first ? first.label + ' ' + first.el + ' :: ' + (first.label === 'cs' ? first.stack : '') : '');
  }
  await page.evaluate(() => { const f = Element.prototype.getBoundingClientRect; });
  await browser.close();
})();
