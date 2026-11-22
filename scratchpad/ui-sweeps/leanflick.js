// The owner: "sometimes the companion leans or tilts to the left and right
// a bit back and forth too fast because of my mouse movement". Sweeps the
// pointer back and forth across the companion's head (100px each side) at
// 2Hz for 5s, as a person would, and counts how often its lean changed side
// (`--nmb-tilt`'s sign) and its head turn changed (`data-turn`). Then holds
// the pointer to one side for 2.5s: it should lean that way once.
// Env: KIND. Exits 1 on more than 2 changes of either while sweeping, or no
// lean when held.
const { boot } = require('./lib.js');

(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate((k) => { const b = $('avatar-buddy'); b.value = k; b.dispatchEvent(new Event('change', { bubbles: true })); }, process.env.KIND || 'me');
  await page.waitForTimeout(6000);
  const head = await page.evaluate(async () => {
    const buddy = document.getElementById('nm-buddy');
    const bar = nameMarkBuddyLedges().bottom;
    nameMarkBuddyAct('');
    nameMarkBuddyMoveTo(buddy, { x: 700, y: Math.round((bar ? bar.top : innerHeight) - NMB_FEET + 1), pose: 'stand', kind: 'bar' }, true);
    clearTimeout(nmb.timer);
    await new Promise((r) => setTimeout(r, 800));
    window.__lean = { tilt: [], turn: [] };
    const sign = (v) => Math.sign(Math.round(Number(v || 0) * 10));
    //: Atlas leans with its own drawing (`data-lean`, l or r); anything
    //: else by `--nmb-tilt`. Either is its lean.
    const leanOf = () => buddy.dataset.lean ? (buddy.dataset.lean === 'l' ? -1 : 1) : sign(buddy.style.getPropertyValue('--nmb-tilt'));
    let lastTilt = leanOf();
    let lastTurn = buddy.dataset.turn || '';
    new MutationObserver(() => {
      const t = leanOf();
      if (t !== lastTilt) { window.__lean.tilt.push(t); lastTilt = t; }
      const u = buddy.dataset.turn || '';
      if (u !== lastTurn) { window.__lean.turn.push(u); lastTurn = u; }
    }).observe(buddy, { attributes: true, attributeFilter: ['style', 'data-turn', 'data-lean'] });
    return [nmb.x + NMB_W / 2, nmb.y + NMB_HEAD / 2];
  });
  await page.mouse.move(head[0], head[1] - 10);
  const t0 = Date.now();
  while (Date.now() - t0 < 5000) {
    const phase = ((Date.now() - t0) / 500) * Math.PI * 2;
    await page.mouse.move(head[0] + Math.sin(phase) * 100, head[1] - 10);
    await page.waitForTimeout(16);
  }
  const sweep = await page.evaluate(() => ({ tilt: window.__lean.tilt.length, turn: window.__lean.turn.length }));
  await page.mouse.move(head[0] + 130, head[1] - 10, { steps: 6 });
  await page.waitForTimeout(2500);
  const held = await page.evaluate(() => { const b = document.getElementById('nm-buddy'); return { tilt: b.dataset.lean ? (b.dataset.lean === 'r' ? 1 : -1) : Number(b.style.getPropertyValue('--nmb-tilt') || 0), lean: b.dataset.lean || '', turn: b.dataset.turn || '' }; });
  console.log(JSON.stringify({ sweepChanges: sweep, held }));
  await browser.close();
  process.exit(sweep.tilt > 2 || sweep.turn > 2 || held.tilt <= 0 ? 1 : 0);
})();
