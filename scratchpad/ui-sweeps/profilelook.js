// INBOX 426 w: Your look's Holding select with a style saved before the
// rude gesture came out (73.png, 90.png), and your profile picture opened
// large by a double-click, as the companion is. Env: SCRATCH (a shot of
// the pickers). Exits 1 when a retired part is still read, any picker
// shows empty, or a double-click on either profile picture opens nothing.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const fails = [];
  // A style as one was saved before: the retired hand, and a hair.
  // Set once Settings has loaded the preferences, which it does on opening.
  await page.evaluate(() => openSettingsModal('preferences'));
  await page.waitForTimeout(800);
  await page.evaluate(() => {
    // avatars.js keeps the own style in a closed-over `nameMarkOwn` that wins over
    // prefsCache once set, so the old `nameMarkOwn = null` here only made a window
    // global; the exported setter is the way in (same clean-on-read path).
    setOwnNameMarkStyle({ hand: 'middlefinger', hair: 'bob', mood: 'happy' });
  });
  await page.evaluate(() => { const d = document.getElementById('profile-look')?.closest('details'); if (d) d.open = true; mountProfileLook(); });
  await page.waitForTimeout(300);
  const look = await page.evaluate(() => {
    const out = {};
    for (const sel of document.querySelectorAll('#profile-look-parts select')) out[sel.dataset.part] = { value: sel.value, shown: sel.options[sel.selectedIndex]?.textContent || '' };
    return { parts: out, style: ownNameMarkStyle() };
  });
  if ('hand' in look.style) fails.push(`style still has hand: ${JSON.stringify(look.style)}`);
  for (const [k, v] of Object.entries(look.parts)) if (!v.shown) fails.push(`${k} picker shows empty (${v.value})`);
  if (look.parts.hand?.shown !== 'From your name') fails.push(`holding: ${JSON.stringify(look.parts.hand)}`);
  if (look.parts.hair?.value !== 'bob') fails.push(`hair lost: ${JSON.stringify(look.parts.hair)}`);
  const holdingOptions = await page.evaluate(() => document.getElementById('profile-look-hand').options.length);
  if (holdingOptions < 5) fails.push(`holding has ${holdingOptions} options`);
  console.log('look', JSON.stringify({ hand: look.parts.hand, hair: look.parts.hair, holdingOptions, style: look.style }));
  if (process.env.SCRATCH) {
    await page.evaluate(() => { document.querySelectorAll('#profile-look details').forEach((d) => { d.open = true; }); document.getElementById('profile-look-parts').scrollIntoView({ block: 'center' }); });
    await page.waitForTimeout(300);
    const box = await page.evaluate(() => { const r = document.getElementById('profile-look-parts').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; });
    await page.screenshot({ path: `${process.env.SCRATCH}/profile-look-holding.png`, clip: { x: box[0] - 8, y: box[1] - 8, width: Math.min(900, box[2] + 16), height: Math.min(400, box[3] + 16) } });
  }
  // Double-clicks: the profile head's picture, and the Settings head's.
  const viewerAfter = async (sel) => {
    await page.evaluate(() => document.querySelectorAll('.nm-viewer').forEach((v) => v.remove()));
    const r = await page.evaluate((s) => { const el = document.querySelector(s); if (!el) return null; el.scrollIntoView({ block: 'center' }); const b = el.getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]; }, sel);
    if (!r) return 'missing';
    await page.mouse.dblclick(r[0], r[1]);
    await page.waitForTimeout(400);
    return page.evaluate(() => (document.querySelector('.nm-viewer') ? 'opened' : 'none'));
  };
  await page.evaluate(() => openSettingsModal('preferences'));
  await page.waitForTimeout(500);
  const head = await viewerAfter('#profile-avatar');
  await page.evaluate(() => document.querySelectorAll('.nm-viewer').forEach((v) => v.remove()));
  const small = await viewerAfter('#settings-profile-btn .profile-mark');
  console.log('dblclick', JSON.stringify({ head, small }));
  if (head !== 'opened') fails.push(`profile picture: ${head}`);
  if (small !== 'opened') fails.push(`settings head picture: ${small}`);
  await browser.close();
  for (const f of fails) console.log(f);
  console.log(fails.length ? 'FAIL' : 'PASS');
  process.exitCode = fails.length ? 1 : 0;
})();
