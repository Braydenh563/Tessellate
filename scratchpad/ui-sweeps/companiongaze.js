// The owner: "atlas doesnt follow my mouse pointer when it is close. should
// it??" Stands the companion mid-window, then puts the pointer 20, 60 and
// 150px to its right and to its left (at head height) and reads its gaze:
// `--nmb-ex` and `--nmb-hx` and the eyes' drawn shift (the face's `.nm-eyes`
// or Atlas's `.atl-iris`). Then moves the pointer slowly past its head for a
// second and counts how often the gaze changed (followed continuously, or
// held). Then puts it to sleep and holds the pointer 50px from it for 1.5s:
// woken or not. Env: KIND (atlas|me), VW, VH.
// Exits 1 when the gaze does not point the pointer's way at 60 and 150px,
// the slow pass changes it fewer than 5 times, or a close pointer does not
// wake it.
const { boot } = require('./lib.js');
const VW = Number(process.env.VW || 1440);
const VH = Number(process.env.VH || 900);
const KIND = process.env.KIND || 'atlas';

(async () => {
  const { browser, page } = await boot({ viewport: { width: VW, height: VH } });
  await page.evaluate(async (k) => { prefs.set('avatar-buddy', k); await ensureModule('characters'); syncNameMarkBuddy(); }, KIND);
  // The setting on, by its own switch (the owner: "it doesnt follow the
  // mouse movement if i have it turned on either").
  await page.evaluate(() => { const f = document.getElementById('avatar-follow'); f.checked = true; f.dispatchEvent(new Event('change', { bubbles: true })); });
  await page.waitForTimeout(6000);
  const head = await page.evaluate(async () => {
    const buddy = document.getElementById('nm-buddy');
    nameMarkBuddyAct('');
    const bar = nameMarkBuddyLedges().bottom;
    nameMarkBuddyMoveTo(buddy, { x: Math.round(innerWidth / 2), y: Math.round((bar ? bar.top : innerHeight) - NMB_FEET + 1), pose: 'stand', kind: 'bar' }, true);
    await new Promise((r) => setTimeout(r, 1200));
    return [nmb.x + NMB_W / 2, nmb.y + NMB_HEAD / 2];
  });
  const read = () => page.evaluate(() => {
    const buddy = document.getElementById('nm-buddy');
    const cs = getComputedStyle(buddy);
    const eye = buddy.querySelector('.nm-atlas .atl-iris') || buddy.querySelector('.name-mark .nm-eyes');
    const tr = eye ? getComputedStyle(eye).translate : '';
    // The body's lean toward the pointer ("tilt their body that way while
    // still mostly facing forward"), as drawn.
    const lean = getComputedStyle(buddy.querySelector('.nm-buddy-char')).rotate;
    return { ex: Number(cs.getPropertyValue('--nmb-ex')) || 0, hx: Number(cs.getPropertyValue('--nmb-hx')) || 0, eyes: tr, lean, attend: buddy.classList.contains('nmb-attend') };
  });
  const rows = [];
  for (const side of [1, -1]) {
    for (const d of [20, 60, 150, 400]) {
      await page.mouse.move(head[0] + side * d - side * 12, head[1], { steps: 2 });
      await page.mouse.move(head[0] + side * d, head[1], { steps: 3 });
      await page.waitForTimeout(d === 400 ? 3200 : 500);
      rows.push({ d: side * d, ...(await read()) });
    }
  }
  // A slow pass across its head.
  await page.mouse.move(head[0] - 90, head[1] - 20);
  await page.waitForTimeout(400);
  await page.evaluate(() => { window.__gz = []; const buddy = document.getElementById('nm-buddy'); new MutationObserver(() => window.__gz.push(buddy.style.getPropertyValue('--nmb-ex'))).observe(buddy, { attributes: true, attributeFilter: ['style'] }); });
  for (let i = 0; i <= 30; i += 1) {
    await page.mouse.move(head[0] - 90 + i * 6, head[1] - 20);
    await page.waitForTimeout(33);
  }
  const changes = await page.evaluate(() => new Set(window.__gz).size);
  // Asleep, the pointer held close.
  await page.mouse.move(head[0] + 300, head[1] - 200);
  await page.evaluate(() => { const b = document.getElementById('nm-buddy'); nameMarkBuddyAct(''); b.classList.add('nmb-sleep'); });
  await page.waitForTimeout(300);
  for (let i = 0; i < 16; i += 1) {
    await page.mouse.move(head[0] + 50 + (i % 2) * 4, head[1]);
    await page.waitForTimeout(100);
  }
  await page.waitForTimeout(1600);
  const woke = await page.evaluate(() => ({ asleep: document.getElementById('nm-buddy').classList.contains('nmb-sleep'), ex: Number(getComputedStyle(document.getElementById('nm-buddy')).getPropertyValue('--nmb-ex')) || 0 }));
  console.log(JSON.stringify({ kind: KIND, rows, slowPassChanges: changes, woke }));
  await browser.close();
  // Within reach it looks the pointer's way; at 400px it has let go and
  // drifted back to looking ahead.
  const wrong = rows.filter((r) => (Math.abs(r.d) >= 60 && Math.abs(r.d) < 400 && Math.sign(r.ex) !== Math.sign(r.d)) || (Math.abs(r.d) === 400 && r.attend));
  process.exit(wrong.length || changes < 5 || woke.asleep ? 1 : 0);
})();
