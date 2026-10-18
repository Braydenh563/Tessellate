// companion-1018: which single write of the release costs the restyle. Carries the companion, then
// applies the release's writes one at a time with a forced flush after each (4x CPU), timing the flush.
const { boot } = require('./lib.js');
const KIND = process.env.KIND || 'atlas', RATE = Number(process.env.RATE || 4);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  const { browser, page, ctx } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  const cdp = await ctx.newCDPSession(page);
  await page.evaluate((k) => { localStorage.removeItem('nm-buddy-spots'); const b = document.getElementById('avatar-buddy'); b.value = k; b.dispatchEvent(new Event('change', { bubbles: true })); }, KIND);
  await page.evaluate(() => revealTab('notes'));
  await page.waitForTimeout(3500);
  await page.evaluate(() => { nameMarkBuddyMoveTo(document.getElementById('nm-buddy'), { kind: 'yours', pose: 'float', legs: '', x: 180, y: 380 }, true); nmb.placedAt = Date.now(); });
  await sleep(900);
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: RATE });
  const f = await page.evaluate(() => { const r = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; });
  await page.mouse.move(f[0], f[1]); await page.mouse.down();
  for (let i = 1; i <= 30; i += 1) { await page.mouse.move(f[0] + i * 12, f[1] - Math.sin(i / 6) * 40); await sleep(16); }
  await sleep(300);
  const r = await page.evaluate(async () => {
    const b = document.getElementById('nm-buddy');
    const out = [];
    const step = (name, w) => { b.getBoundingClientRect(); const t0 = performance.now(); w(); const t = performance.now(); b.getBoundingClientRect(); out.push(`${name} call ${(t - t0).toFixed(0)}ms then flush ${(performance.now() - t).toFixed(0)}ms`); };
    step('translate=""', () => { b.style.translate = ''; });
    step('class -dragging', () => b.classList.remove('nm-buddy-dragging'));
    step('sway 0', () => nameMarkBuddySway(b, 0));
    step('del turn', () => { delete b.dataset.turn; });
    step('Put', () => nameMarkBuddyPut(b, Math.round(nmb.x), Math.round(nmb.y)));
    const spot = nameMarkBuddyDrop(nmb.x, nmb.y);
    out.push(`spot ${spot.kind}/${spot.pose}/${spot.legs || '-'} y${Math.round(spot.y)} cur ${nmb.pose}`);
    step('MoveTo', () => nameMarkBuddyMoveTo(b, spot));
    step('Act land', () => nameMarkBuddyAct('land'));
    return out;
  });
  console.log(r.join('\n'));
  await browser.close();
})();
