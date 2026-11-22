// The owner: "when it sleeps can it lay down?? ... masculine and feminine
// ways to stand and move the body". As Atlas: a nap where there is room
// (found along the bottom bar) lies down (the act becomes `lie`), a nap
// squeezed beside a control dozes where it is, and a wake from lying goes
// through its way up (`nmb-unwind`); its float by look (how long a 160px
// float takes). As you, with Face look set: the walk's bob by look and how
// long a 160px walk takes. Exits 1 on any of those not as described.
const { boot } = require('./lib.js');

(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const setKind = (k) => page.evaluate((k) => { const b = $('avatar-buddy'); b.value = k; b.dispatchEvent(new Event('change', { bubbles: true })); }, k);
  const travel = () => page.evaluate(async () => {
    const buddy = document.getElementById('nm-buddy');
    const bar = nameMarkBuddyLedges().bottom;
    const y = Math.round((bar ? bar.top : innerHeight) - NMB_FEET + 1);
    nameMarkBuddyAct('');
    nameMarkBuddyMoveTo(buddy, { x: 600, y, pose: 'stand', kind: 'bar' }, true);
    await new Promise((r) => setTimeout(r, 600));
    nameMarkBuddyMoveTo(buddy, { x: 760, y, pose: 'stand', kind: 'bar' });
    await new Promise((r) => setTimeout(r, 200));
    const bob = buddy.getAnimations({ subtree: true }).map((a) => a.animationName).filter((n) => n && n.startsWith('nmb-bob'))[0] || '';
    const took = nmb.anim ? Math.round(nmb.anim.effect.getComputedTiming().duration) : 0;
    await new Promise((r) => setTimeout(r, 1800));
    return { gait: buddy.dataset.gait || '', bob, ms: took };
  });
  const out = { atlas: {}, you: {} };
  await setKind('atlas');
  await page.waitForTimeout(6000);
  for (const look of ['masculine', 'feminine']) {
    await page.evaluate((l) => { const s = document.getElementById('atlas-look'); s.value = l; s.dispatchEvent(new Event('change', { bubbles: true })); }, look);
    await page.waitForTimeout(1200);
    out.atlas[look] = await travel();
  }
  out.nap = await page.evaluate(async () => {
    const buddy = document.getElementById('nm-buddy');
    const bar = nameMarkBuddyLedges().bottom;
    const y = Math.round((bar ? bar.top : innerHeight) - NMB_FEET + 1);
    let roomy = null;
    for (let x = 80; x < innerWidth - 150 && roomy === null; x += 40) {
      nameMarkBuddyMoveTo(buddy, { x, y, pose: 'stand', kind: 'bar' }, true);
      nameMarkBuddyIndexReset();
      if (nameMarkBuddyLieRoom()) roomy = x;
    }
    if (roomy === null) return { roomy };
    nameMarkBuddyAct('');
    nmb.cool = {};
    nameMarkBuddyAct('nap', 4000);
    const open = nmb.act;
    await new Promise((r) => setTimeout(r, 1500));
    const lying = getComputedStyle(buddy.querySelector('.nm-buddy-char')).transform;
    nameMarkBuddyWake(true);
    await new Promise((r) => setTimeout(r, 100));
    const unwinding = buddy.classList.contains('nmb-unwind');
    nameMarkBuddyAct('');
    await new Promise((r) => setTimeout(r, 1600));
    // Squeezed: a small control right behind it.
    const block = document.createElement('button');
    block.textContent = 'x';
    block.style.position = 'fixed';
    block.style.left = `${nmb.x - 26}px`;
    block.style.top = `${nmb.y + NMB_FEET - 24}px`;
    block.style.width = '24px';
    block.style.height = '20px';
    document.getElementById(`tab-${nameMarkBuddyTab()}`).appendChild(block);
    nameMarkBuddyIndexReset();
    nmb.cool = {};
    nameMarkBuddyAct('nap', 3000);
    const squeezed = nmb.act;
    block.remove();
    nameMarkBuddyAct('');
    return { roomy, inTheOpen: open, lyingTransform: lying !== 'none', unwinding, squeezed };
  });
  await setKind('me');
  await page.waitForTimeout(3000);
  for (const look of ['masculine', 'feminine']) {
    await page.evaluate((l) => { localStorage.setItem('face-look', l); const s = document.getElementById('face-look'); if (s) { s.value = l; s.dispatchEvent(new Event('change', { bubbles: true })); } }, look);
    await page.waitForTimeout(1500);
    out.you[look] = await travel();
  }
  console.log(JSON.stringify(out));
  await browser.close();
  const ok = out.atlas.masculine.ms > out.atlas.feminine.ms && out.you.masculine.bob === 'nmb-bob-heavy' && out.you.feminine.bob === 'nmb-bob-light'
    && out.you.masculine.ms > out.you.feminine.ms && out.nap.inTheOpen === 'lie' && out.nap.lyingTransform && out.nap.unwinding && out.nap.squeezed === 'nap';
  // One line the lane runners count (they read FAIL, not the exit code alone).
  console.log(!ok ? 'FAIL napgait: a measure above is out of bounds' : 'PASS napgait');
  process.exit(ok ? 0 : 1);
})();
