// INBOX 426 x, life: the companion's face changes with what happens and
// comes back, a swap is cheap, and it waves when you come back after a
// long idle. Env: KIND (me), SCRATCH (a shot of its faces). Exits 1 when a
// hello, a saved note, an error, thinking, being away or a drift leaves the
// face unchanged, a face does not come back, a swap to an event face
// (drawn ahead in idle time) takes over 4ms, or coming back does not wave.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(async (k) => { prefs.set('avatar-buddy', k); await ensureModule('characters'); syncNameMarkBuddy(); }, process.env.KIND || 'me');
  await page.evaluate(() => revealTab('notes'));
  await page.waitForTimeout(3500);
  const fails = [];
  const expr = () => page.evaluate(() => document.getElementById('nm-buddy').dataset.expr || '');
  // A hello.
  const face = await page.evaluate(() => { const r = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect(); return [r.left + 32, r.top + 30]; });
  await page.mouse.click(face[0], face[1]);
  await page.waitForTimeout(200);
  const hello = await expr();
  await page.waitForTimeout(3000);
  const back = await expr();
  if (hello !== 'happy' || back !== '') fails.push(`hello: ${hello} then ${back}`);
  // Cues: a saved note, an error, thinking.
  const cue = async (c, from, wait) => { await page.evaluate(([cc, ff]) => nameMarkBuddyCue(cc, ff), [c, from]); await page.waitForTimeout(wait); return expr(); };
  const cheer = await cue('cheer', '', 1700);
  if (cheer !== 'excited') fails.push(`cheer: ${cheer}`);
  await page.waitForTimeout(2600);
  const err = await cue('startle', 'error', 1700);
  if (err !== 'surprised') fails.push(`error: ${err}`);
  await page.waitForTimeout(1800);
  const think = await cue('think', '', 200);
  const rest = await cue('rest', '', 200);
  if (think !== 'serious' || rest !== '') fails.push(`think: ${think} then ${rest}`);
  // Away: drowsy after three minutes holds a sleepy face; input lifts it,
  // with a wave.
  const away = await page.evaluate(async () => {
    nmb.lastInput = Date.now() - 4 * 60 * 1000;
    nmb.lastAct = '';
    nmb.tick();
    const sleepy = document.getElementById('nm-buddy').dataset.expr || '';
    if (nmb.act) nameMarkBuddyAct('');
    nmb.lastInput = Date.now() - 4 * 60 * 1000;
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'a' }));
    return { sleepy, act: nmb.act, after: document.getElementById('nm-buddy').dataset.expr || '' };
  });
  if (away.sleepy !== 'sleepy' || away.act !== 'wave' || away.after !== 'happy') fails.push(`away: ${JSON.stringify(away)}`);
  await page.waitForTimeout(2500);
  // A drift at rest, and back.
  const drift = await page.evaluate(async () => {
    nmb.exprHold = '';
    clearTimeout(nmb.exprTimer);
    nmb.exprTimer = 0;
    nameMarkBuddyExpress('');
    nmb.inner.nameMarkBuddyDrift();
    return document.getElementById('nm-buddy').dataset.expr || '';
  });
  if (!drift) fails.push('drift: no change');
  // Cost of a swap, uncached and cached.
  // Its event faces were drawn ahead in idle time: a swap to any of them is
  // a cached picture. A face never drawn (dramatic) is reported, not judged.
  const cost = await page.evaluate(() => {
    const t = (e) => { const a = performance.now(); nameMarkBuddyExpress(e, 0); return performance.now() - a; };
    const events = nmb.inner.NMB_EXPR_EVENTS.map(t);
    t('');
    const fresh = t('dramatic');
    t('');
    return { events: +Math.max(...events).toFixed(2), fresh: +fresh.toFixed(1) };
  });
  if (cost.events > 4) fails.push(`cost: ${JSON.stringify(cost)}`);
  console.log(JSON.stringify({ hello, back, cheer, err, think, rest, away, drift, cost }));
  // Its size: Large from its menu (the figure 1.3 times, its contact line
  // where it was), then the corner handle dragged outward (kept, and shown
  // in Appearance as its own size), then Medium again.
  const size = {};
  await page.evaluate(() => {
    const buddy = document.getElementById('nm-buddy');
    nameMarkBuddyMoveTo(buddy, { kind: 'air', pose: 'stand', x: 700, y: 400 }, true);
    clearTimeout(nmb.timer);
  });
  await page.waitForTimeout(200);
  const rect = () => page.evaluate(() => { const r = document.querySelector('#nm-buddy .nm-buddy-face').getBoundingClientRect(); return { h: +r.height.toFixed(1), bottom: +r.bottom.toFixed(1), top: +r.top.toFixed(1), right: +r.right.toFixed(1), left: +r.left.toFixed(1) }; });
  size.medium = await rect();
  // The handle: hidden at rest (the pointer away), shown on hover and on
  // the keyboard's focus.
  const gripState = () => page.evaluate(() => { const cs = getComputedStyle(document.querySelector('#nm-buddy .nmb-size-grip')); return `${cs.visibility}/${cs.opacity}`; });
  await page.mouse.move(5, 5);
  await page.waitForTimeout(300);
  size.gripAtRest = await gripState();
  await page.evaluate(() => document.querySelector('#nm-buddy .nm-buddy-face').focus({ focusVisible: true }));
  await page.keyboard.press('Shift');
  await page.waitForTimeout(250);
  size.gripOnFocus = await gripState();
  await page.evaluate(() => document.activeElement?.blur());
  if (size.gripAtRest !== 'hidden/0') fails.push(`grip at rest: ${size.gripAtRest}`);
  const fc = [size.medium.left + 32, size.medium.top + 40];
  await page.mouse.click(fc[0], fc[1], { button: 'right' });
  await page.waitForTimeout(250);
  await page.evaluate(() => { [...nmb.menu.querySelectorAll('button')].find((b) => /Large/.test(b.textContent)).click(); });
  await page.waitForTimeout(250);
  size.large = await rect();
  size.largeSaved = await page.evaluate(() => localStorage.getItem('avatar-buddy-size'));
  if (Math.abs(size.large.h / size.medium.h - 1.3) > 0.02 || Math.abs(size.large.bottom - size.medium.bottom) > 3.5) fails.push(`size large: ${JSON.stringify(size)}`);
  // The handle, dragged out from its corner.
  await page.mouse.move(size.large.left + 30, size.large.top + 40);
  await page.waitForTimeout(200);
  const grip = await page.evaluate(() => { const g = document.querySelector('#nm-buddy .nmb-size-grip').getBoundingClientRect(); return { x: g.left + g.width / 2, y: g.top + g.height / 2, shown: getComputedStyle(document.querySelector('#nm-buddy .nmb-size-grip')).opacity }; });
  if (process.env.SCRATCH) await page.screenshot({ path: `${process.env.SCRATCH}/companion-size-grip.png`, clip: { x: size.large.left - 40, y: size.large.top - 30, width: 180, height: 180 } });
  await page.mouse.move(grip.x, grip.y);
  await page.mouse.down();
  for (let i = 1; i <= 6; i += 1) { await page.mouse.move(grip.x + i * 5, grip.y - i * 5); await page.waitForTimeout(16); }
  await page.mouse.up();
  await page.waitForTimeout(200);
  size.dragged = await rect();
  size.draggedSaved = await page.evaluate(() => localStorage.getItem('avatar-buddy-size'));
  size.gripShown = grip.shown;
  if (grip.shown !== '1') fails.push(`grip on hover: ${grip.shown}`);
  await page.evaluate(() => openSettingsModal('appearance'));
  await page.waitForTimeout(500);
  size.select = await page.evaluate(() => { const s = document.getElementById('avatar-buddy-size'); return s.options[s.selectedIndex]?.textContent || ''; });
  await page.evaluate(() => { const s = document.getElementById('avatar-buddy-size'); s.value = '1'; s.dispatchEvent(new Event('change', { bubbles: true })); });
  await page.keyboard.press('Escape');
  await page.waitForTimeout(250);
  size.back = await rect();
  if (!(Number(size.draggedSaved) > 1.3) || !/As you sized it/.test(size.select) || Math.abs(size.back.h - size.medium.h) > 1) fails.push(`size drag: ${JSON.stringify(size)}`);
  console.log('size', JSON.stringify(size));
  if (process.env.SCRATCH) {
    // A strip of its faces, as drawn on the companion.
    const seed = await page.evaluate(() => document.getElementById('nm-buddy').dataset.seed);
    await page.evaluate((sd) => {
      const sheet = document.createElement('div');
      sheet.id = 'expr-sheet';
      Object.assign(sheet.style, { position: 'fixed', left: '0', top: '0', zIndex: '99999', background: '#f7f6f3', display: 'flex', gap: '10px', padding: '14px', font: '12px sans-serif', color: '#222' });
      for (const e of ['', 'happy', 'laughing', 'excited', 'surprised', 'serious', 'sleepy', 'unimpressed', 'calm', 'love']) {
        const cell = document.createElement('div');
        Object.assign(cell.style, { display: 'grid', justifyItems: 'center', gap: '4px' });
        const fig = nameCharacterFigure(sd, e);
        Object.assign(fig.style, { position: 'relative', width: '64px', height: '92px', display: 'block' });
        const l = document.createElement('div');
        l.textContent = e || 'its own';
        cell.append(fig, l);
        sheet.appendChild(cell);
      }
      document.body.appendChild(sheet);
    }, seed);
    await page.waitForTimeout(400);
    await page.screenshot({ path: `${process.env.SCRATCH}/companion-expressions.png`, clip: { x: 0, y: 0, width: 760, height: 130 } });
  }
  await browser.close();
  for (const f of fails) console.log(f);
  console.log(fails.length ? 'FAIL' : 'PASS');
  process.exitCode = fails.length ? 1 : 0;
})();
