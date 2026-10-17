// The companion's mind (B87c, B88c): loaded at the first tick, it leads into
// a big act on a beat, its new acts run (ponder, sigh, Atlas's toss), and a
// day of picks spreads over what it does. Prints page errors, the mind's
// state, the acts seen and Atlas's tossed star.
// Env: BASE.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 200)); });
  await page.evaluate(() => { localStorage.removeItem('nm-buddy-spots'); const b = document.getElementById('avatar-buddy'); b.value = 'atlas'; b.dispatchEvent(new Event('change', { bubbles: true })); });
  await page.evaluate(() => revealTab('notes'));
  await page.waitForTimeout(3000);
  const before = await page.evaluate(() => !!nmb.mind);
  await page.evaluate(() => nameMarkBuddyTick());
  await page.waitForTimeout(1500);
  const loaded = await page.evaluate(() => ({ mind: !!nmb.mind, acts: ['ponder', 'sigh', 'toss'].every((a) => a in NAME_MARK_BUDDY_ACTS), wait: nmb.mind?.nextIn() }));
  await page.evaluate(() => nameMarkBuddyAct(''));
  await page.waitForTimeout(600);
  const lead = await page.evaluate(() => new Promise((done) => {
    const buddy = document.getElementById('nm-buddy');
    const led = nmb.mind.lead(buddy, 'wave');
    const at0 = nmb.act;
    setTimeout(() => done({ led, at0, at400: nmb.act }), 400);
  }));
  await page.evaluate(() => nameMarkBuddyAct(''));
  await page.waitForTimeout(800);
  const acts = {};
  for (const act of ['ponder', 'sigh']) {
    acts[act] = await page.evaluate((a) => new Promise((done) => {
      nameMarkBuddyAct(a);
      setTimeout(() => done({ act: nmb.act, limbs: (nmb.limbAnims || []).length, tilt: nmb.tilt || 0 }), 500);
    }), act);
    await page.evaluate(() => nameMarkBuddyAct(''));
    await page.waitForTimeout(800);
  }
  const toss = await page.evaluate(() => new Promise((done) => {
    const box = document.querySelector('#nm-buddy .atl-figure-box');
    const stars = [...box.querySelectorAll('.atl-layer .nmp-stars > .atl-juggle')];
    const root = box.querySelector('.atl-layer .nmp-stars');
    const svg = root.ownerSVGElement;
    nameMarkBuddyAct('toss');
    const ys = [];
    const t0 = performance.now();
    const step = () => {
      const inv = svg.getScreenCTM().inverse();
      const r = stars[1].querySelector('.atl-juggle-star').getBoundingClientRect();
      ys.push(+new DOMPoint(r.left + r.width / 2, r.top + r.height / 2).matrixTransform(inv).y.toFixed(1));
      if (performance.now() - t0 < 3000) requestAnimationFrame(step);
      else done({ shown: getComputedStyle(root).opacity, others: [getComputedStyle(stars[0]).opacity, getComputedStyle(stars[2]).opacity], y: [Math.min(...ys.slice(30)), Math.max(...ys.slice(30))], frames: ys.length });
    };
    requestAnimationFrame(step);
  }));
  await page.evaluate(() => nameMarkBuddyAct(''));
  // A thousand picks: how spread the pool is when idle in notes vs typing.
  const spread = await page.evaluate(() => {
    const count = (setup) => {
      const seen = {};
      const keep = { keyAt: nmb.keyAt, lastInput: nmb.lastInput, cool: nmb.cool, lastAct: nmb.lastAct, recent: nmb.recentActs };
      setup();
      nmb.cool = {};
      nmb.recentActs = [];
      for (let i = 0; i < 1000; i += 1) { const a = nameMarkBuddyDecide(); seen[a] = (seen[a] || 0) + 1; }
      Object.assign(nmb, { keyAt: keep.keyAt, lastInput: keep.lastInput, cool: keep.cool, lastAct: keep.lastAct, recentActs: keep.recent });
      return Object.entries(seen).sort((a, b) => b[1] - a[1]).slice(0, 8);
    };
    return { idle: count(() => { nmb.lastInput = Date.now() - 60000; nmb.keyAt = 0; }), typing: count(() => { nmb.keyAt = Date.now() - 1000; nmb.lastInput = Date.now(); }) };
  });
  console.log(JSON.stringify({ errors, before, loaded, lead, acts, toss, spread }));
  await browser.close();
})();
