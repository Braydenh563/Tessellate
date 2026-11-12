// INBOX 462, the owner: "the companion perches dont handle collapsed
// sidebars at least in the chat tab". Puts the companion on a perch inside
// a tab's sidebar (the best one the chooser offers there), folds the sidebar
// with its own button, and reads, 1.5s later: where it is, what it stands
// on, and whether that perch can be seen (inside the folded sidebar is
// not). Then unfolds and reads again. Env: BASE, KIND (atlas|me), TABS
// (chat,documents,skills). Exits 1 when, folded, it is still held to
// something inside the folded sidebar, or floats over nothing.
const { boot } = require('./lib.js');
const KIND = process.env.KIND || 'atlas';
const TABS = (process.env.TABS || 'chat,documents,skills').split(',');
const ASIDE = { chat: 'chat-sidebar', documents: 'doc-sidebar', skills: 'skills-sidebar' };

(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(async (kind) => { localStorage.removeItem('nm-buddy-spots'); prefs.set('avatar-buddy', kind); await ensureModule('characters'); syncNameMarkBuddy(); }, KIND);
  let bad = 0;
  for (const tab of TABS) {
    await page.evaluate((t) => switchTab(t), tab);
    await page.waitForTimeout(3500);
    const put = await page.evaluate((id) => {
      const aside = document.getElementById(id);
      if (!aside || !aside.getClientRects().length) return { skipped: 'no sidebar' };
      if (aside.classList.contains('sidebar-collapsed')) aside.querySelector('.sidebar-collapse-toggle').click();
      nameMarkBuddyIndexReset();
      const tab = nameMarkBuddyTab();
      const inside = nmb.inner.nameMarkBuddyPerches(tab).filter((p) => p.edge?.el && aside.contains(p.edge.el) && p.x >= 0);
      const spot = inside.find((p) => !nmb.inner.nameMarkBuddyHits(p.x, p.y, p.pose, nmb.inner.nameMarkBuddyObstacles(tab), p.legs)) || inside[0];
      if (!spot) return { skipped: 'no perch inside' };
      nameMarkBuddyMoveTo(document.getElementById('nm-buddy'), spot, true);
      const el = spot.edge.el;
      return { x: nmb.x, y: nmb.y, on: `${el.tagName.toLowerCase()}.${[...el.classList].slice(0, 2).join('.')}` };
    }, ASIDE[tab]);
    if (put.skipped) { console.log(`${tab}: skipped (${put.skipped})`); continue; }
    await page.waitForTimeout(400);
    const read = () => page.evaluate((id) => {
      const aside = document.getElementById(id);
      const el = nmb.glue?.el;
      const ab = aside.getBoundingClientRect();
      const seen = el ? (el.checkVisibility({ opacityProperty: true, visibilityProperty: true }) && !el.closest('.sidebar-collapsed')) : null;
      return { x: Math.round(nmb.x), y: Math.round(nmb.y), pose: nmb.pose, perch: nmb.perch, inAside: el ? aside.contains(el) : false, seen, asideW: Math.round(ab.width), on: el ? `${el.tagName.toLowerCase()}.${[...el.classList].slice(0, 2).join('.')}` : '(none)' };
    }, ASIDE[tab]);
    const before = await read();
    await page.evaluate((id) => document.querySelector(`#${id} .sidebar-collapse-toggle`).click(), ASIDE[tab]);
    await page.mouse.move(900, 450);
    await page.waitForTimeout(1500);
    const folded = await read();
    await page.evaluate((id) => document.querySelector(`#${id} .sidebar-collapse-toggle`).click(), ASIDE[tab]);
    await page.mouse.move(900, 450);
    await page.waitForTimeout(1500);
    const open = await read();
    const wrong = (folded.inAside && folded.seen === false) || folded.pose === 'float';
    if (wrong) bad += 1;
    console.log(`${tab}: put on ${put.on} at ${put.x},${put.y}; before ${JSON.stringify(before)}`);
    console.log(`  folded ${JSON.stringify(folded)}${wrong ? '  WRONG' : ''}`);
    console.log(`  unfolded ${JSON.stringify(open)}`);
  }
  console.log(bad ? 'FAIL' : 'PASS');
  process.exitCode = bad ? 1 : 0;
  await browser.close();
})();
