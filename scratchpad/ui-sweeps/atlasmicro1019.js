// Atlas micro behaviours: the effect of each kind on real elements, then 60 s of the real clock
// (kinds seen, long tasks over 50 ms, rAF calls from the micro file). Env: BASE, RM=reduce, SECS (60).
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block', reducedMotion: process.env.RM || 'no-preference' });
  await page.addInitScript(() => { window.__lt = []; try { new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__lt.push(Math.round(e.duration)); }).observe({ entryTypes: ['longtask'] }); } catch (e) {} });
  await page.evaluate(() => { const b = document.getElementById('avatar-buddy'); b.value = 'atlas'; b.dispatchEvent(new Event('change', { bubbles: true })); });
  await page.evaluate(() => revealTab('notes'));
  await page.waitForTimeout(4000);
  console.log('loaded', await page.evaluate(() => typeof atlasMicroStart === 'function' && !!atlasMicroState.timer));
  const eff = await page.evaluate(async () => {
    const box = document.querySelector('#nm-buddy .atl-figure-box');
    const out = {};
    const head = box.atlasRig.heads[0];
    const body = box.querySelector('.atl-lw-body');
    const ear = box.querySelector('.atl-ear');
    const rb = () => ear.getBoundingClientRect();
    const sample = async (el, prop, kind) => { const v = []; for (let i = 0; i < 12; i += 1) { v.push(getComputedStyle(el)[prop]); await new Promise((r) => setTimeout(r, 200)); } return v; };
    atlasMicroDo('tilt', box); out.tilt = (await sample(head, 'rotate')).filter((x, i, a) => a.indexOf(x) === i).length;
    atlasMicroDo('shift', box); out.shift = (await sample(body, 'translate')).filter((x, i, a) => a.indexOf(x) === i).length;
    const w0 = JSON.stringify(rb()); const seen = new Set();
    atlasMicroDo('ear', box); for (let i = 0; i < 40; i += 1) { seen.add(JSON.stringify(rb())); await new Promise((r) => setTimeout(r, 20)); }
    out.ear = seen.size; out.earTotal = document.querySelectorAll('#nm-buddy .atl-ear').length;
    return out;
  });
  console.log('effects (distinct computed values over 2.4 s)', JSON.stringify(eff));
  // real clock
  await page.evaluate(() => { window.__kinds = {}; window.__lt = []; try { new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__lt.push(Math.round(e.duration)); }).observe({ entryTypes: ['longtask'] }); } catch (e) {} const d = atlasMicroDo; window.atlasMicroDo = function (k, b) { window.__kinds[k] = (window.__kinds[k] || 0) + 1; return d(k, b); }; window.__raf = 0; const r = window.requestAnimationFrame; });
  if (process.env.NOMICRO) await page.evaluate(() => { clearTimeout(atlasMicroState.timer); atlasMicroState.timer = 0; window.atlasMicroStart = () => {}; });
  const secs = Number(process.env.SECS || 60);
  await page.mouse.move(400, 400);
  for (let i = 0; i < secs / 5; i += 1) { await page.waitForTimeout(5000); await page.mouse.move(300 + (i * 97) % 700, 300 + (i * 53) % 400); }
  console.log('kinds in', secs, 's', JSON.stringify(await page.evaluate(() => window.__kinds)), 'longtasks>50ms', JSON.stringify(await page.evaluate(() => window.__lt.filter((x) => x > 50))), 'all', await page.evaluate(() => window.__lt.length));
  await browser.close();
})();
