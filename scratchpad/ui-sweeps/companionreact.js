// Round 5: what the companion notices in the app, each from the real event:
// a long note opened (Show more) reads along, a private one covers its
// eyes, the graph laid out again gets a peek, a longer capture streak one
// cheer (and not the same count twice), a night tick a yawn, a toast a look.
// Also: no two within 6s, none under Reduce motion. Env: KIND (me),
// SCRATCH (shots). Exits 1 when a reaction does not come from its event, a
// rate limit or Reduce motion is not respected.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const fails = [];
  await page.evaluate((k) => { const b = $('avatar-buddy'); b.value = k; b.dispatchEvent(new Event('change', { bubbles: true })); }, process.env.KIND || 'me');
  // Two long notes to open.
  const ids = await page.evaluate(async () => {
    const body = (n) => `Long note ${n} for the companion. ${'A sentence that goes on for a while, with enough words to need a Show more. '.repeat(24)}`;
    const a = await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: body('one') }) });
    const b = await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: body('two') }) });
    return [a.id || a.entry?.id, b.id || b.entry?.id];
  });
  await page.evaluate(() => revealTab('notes'));
  await page.evaluate(() => typeof loadEntries === 'function' && loadEntries()).catch(() => {});
  await page.waitForTimeout(3000);
  // The habit reactions (read, yawn) need the companion's mind, which arrives with its lazy menu file.
  await page.evaluate(() => ensureModule('companionMenu'));
  await page.waitForFunction(() => !!nmb.mind, null, { timeout: 8000 }).catch(() => {});
  const reset = () => page.evaluate(() => { nmb.reactAt = 0; nmb.reactCool = {}; nmb.reactLog = []; nmb.reacted = ''; nameMarkBuddyAct(''); });
  const reacted = () => page.evaluate(() => nmb.reacted || '');
  const openNote = async (id) => {
    const found = await page.evaluate((i) => {
      const li = document.querySelector(`#tab-notes li[data-id="${i}"]`);
      const more = li?.querySelector('.entry-more');
      if (!more) return false;
      more.scrollIntoView({ block: 'center' });
      return true;
    }, id);
    if (!found) return false;
    await page.click(`#tab-notes li[data-id="${id}"] .entry-more`);
    await page.waitForTimeout(250);
    return true;
  };
  // A long note: reads along.
  await reset();
  if (!(await openNote(ids[0]))) fails.push('no Show more on the long note');
  const read = { kind: await reacted(), glasses: await page.evaluate(() => document.getElementById('nm-buddy').classList.contains('nmb-reading')) };
  if (read.kind !== 'read' || !read.glasses) fails.push(`long note: ${JSON.stringify(read)}`);
  if (process.env.SCRATCH) {
    const b = await page.evaluate(() => { const r = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect(); return [r.left, r.top]; });
    await page.screenshot({ path: `${process.env.SCRATCH}/react-read.png`, clip: { x: Math.max(0, b[0] - 40), y: Math.max(0, b[1] - 30), width: 150, height: 150 } });
  }
  // Too soon for another: the gap holds.
  await page.evaluate(() => { nmb.reacted = ''; });
  await page.evaluate(() => toast('Too soon'));
  await page.waitForTimeout(300);
  if (await reacted()) fails.push('a second reaction inside 6s');
  // A private note: covers its eyes.
  await reset();
  await page.evaluate((i) => { const e = allEntries.find((x) => String(x.id) === String(i)); if (e) e.is_private = true; }, ids[1]);
  // Standing in the open, so its arms are free to cover its eyes.
  await page.evaluate(() => { const b = document.getElementById('nm-buddy'); b.classList.remove('nmb-reading'); nameMarkBuddyMoveTo(b, { kind: 'air', pose: 'stand', x: 1100, y: 300 }, true); nmb.placeTimer = 1; });
  if (!(await openNote(ids[1]))) fails.push('no Show more on the second note');
  const priv = { kind: await reacted(), act: await page.evaluate(() => nmb.act) };
  if (priv.kind !== 'private' || priv.act !== 'hide') fails.push(`private note: ${JSON.stringify(priv)}`);
  if (process.env.SCRATCH) {
    await page.waitForTimeout(700);
    const b = await page.evaluate(() => { const r = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect(); return [r.left, r.top]; });
    await page.screenshot({ path: `${process.env.SCRATCH}/react-hide.png`, clip: { x: Math.max(0, b[0] - 40), y: Math.max(0, b[1] - 30), width: 150, height: 150 } });
  }
  // A toast: a look.
  await reset();
  await page.evaluate(() => toast('Something new'));
  await page.waitForTimeout(400);
  const toastKind = await reacted();
  if (toastKind !== 'toast') fails.push(`toast: ${toastKind}`);
  // Every other way to a note goes through flashEntry (search, a link, the
  // palette, the Library, the timeline): the palette's jump reads along.
  await reset();
  await page.evaluate((i) => { expandedNotes.delete(i); expandedNotes.delete(Number(i)); cmdPaletteGoToNote(Number(i)); }, ids[0]);
  await page.waitForTimeout(600);
  const jumped = await reacted();
  if (jumped !== 'read') fails.push(`palette jump to a long note: ${jumped}`);
  // The graph laid out again.
  await reset();
  await page.evaluate(() => revealTab('graph'));
  await page.waitForTimeout(2500);
  await reset();
  const changed = await page.evaluate(() => {
    const select = document.getElementById('graph-layout');
    const next = [...select.options].find((o) => o.value !== select.value);
    if (!next) return false;
    select.value = next.value;
    select.dispatchEvent(new Event('change', { bubbles: true }));
    return next.value;
  });
  await page.waitForTimeout(800);
  const graph = await reacted();
  if (!changed || graph !== 'graph') fails.push(`graph (${changed}): ${graph}`);
  // The streak: a longer one cheers once; the same count does not.
  await reset();
  const streak = await page.evaluate(() => {
    localStorage.setItem('nm-buddy-streak', '3');
    nameMarkBuddyStreak(4);
    const first = nmb.reacted;
    nmb.reacted = ''; nmb.reactAt = 0;
    nameMarkBuddyStreak(4);
    return { first, again: nmb.reacted || '' };
  });
  if (streak.first !== 'streak' || streak.again) fails.push(`streak: ${JSON.stringify(streak)}`);
  // Night: a tick yawns.
  await reset();
  // The streak's cheer before it is still on: let the companion settle (its tick passes a moving or reacting one by).
  await page.waitForTimeout(4000);
  const night = await page.evaluate(() => {
    // Its own mind may have sent it out for a while by now (nmb-away): the night tick is not asked of an absent companion.
    const buddy = document.getElementById('nm-buddy');
    nmb.away = false; nmb.absent = false; buddy.classList.remove('nmb-away');
    const orig = Date.prototype.getHours;
    Date.prototype.getHours = function () { return 23; };
    // A tick can be spent on the companion's own mind (a stroll, an errand) before the night check: up to six.
    try { for (let i = 0; i < 6 && !nmb.reacted; i += 1) { nmb.lastInput = Date.now(); nmb.sweep.nameMarkBuddyTick(true); } } finally { Date.prototype.getHours = orig; }
    return { kind: nmb.reacted || '', act: nmb.act };
  });
  if (night.kind !== 'yawn' || night.act !== 'yawn') fails.push(`night: ${JSON.stringify(night)}`);
  // Reduce motion: nothing.
  await reset();
  const still = await page.evaluate(() => {
    // The companion reads MOTION.cause (theme-boot.js), not the attribute.
    MOTION.apply('off');
    const r = ['read', 'graph', 'streak', 'yawn', 'private', 'toast'].map((k) => nameMarkBuddyReact(k));
    MOTION.apply('follow');
    return r.some(Boolean);
  });
  if (still) fails.push('a reaction under Reduce motion');
  console.log(JSON.stringify({ read, priv, toastKind, jumped, graph, streak, night, still }));
  await page.evaluate((list) => Promise.all(list.map((i) => apiJson(`/entries/${i}`, { method: 'DELETE' }).catch(() => {}))), ids);
  await browser.close();
  for (const f of fails) console.log(f);
  console.log(fails.length ? 'FAIL' : 'PASS');
  process.exitCode = fails.length ? 1 : 0;
})();
