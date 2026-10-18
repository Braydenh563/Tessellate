// INBOX 1300 C33 (the owner: "stacking notifications need to be cleaned up
// and not as intrusive and obscuring"): four notices in a row, then the
// stack's box and its shown cards at rest (pointer away), with the pointer
// on it, and with the keyboard in it. Env: BASE, W (default 1440).
const { boot } = require('./lib.js');
(async () => {
  const W = Number(process.env.W || 1440);
  const { browser, page } = await boot({ viewport: { width: W, height: 900 } });
  await page.evaluate(() => { for (const m of ['Saved the note.', 'Moved 3 notes to the bin.', 'Finished reading this file.', 'Copied the link.']) toast(m); });
  await page.waitForTimeout(700);
  await page.mouse.move(200, 300);
  const read = () => page.evaluate(() => {
    const box = document.getElementById('toast-box');
    const shown = [...box.children].filter((t) => t.getClientRects().length);
    const r = shown.reduce((a, t) => { const b = t.getBoundingClientRect(); return { l: Math.min(a.l, b.left), t: Math.min(a.t, b.top), r: Math.max(a.r, b.right), b: Math.max(a.b, b.bottom) }; }, { l: 1e9, t: 1e9, r: -1e9, b: -1e9 });
    return { cards: shown.filter((t) => !t.classList.contains('toast-more')).length, pill: [...(shown.find((t) => t.classList.contains('toast-more'))?.querySelectorAll('span') || [])].filter((s) => s.getClientRects().length).map((s) => s.textContent).join('|'), w: Math.round(r.r - r.l), h: Math.round(r.b - r.t) };
  });
  const rest = await read();
  const newest = await page.evaluate(() => { const live = toastLive(document.getElementById('toast-box')); const b = live[0].getBoundingClientRect(); return [b.left + 20, b.top + b.height / 2]; });
  await page.mouse.move(newest[0], newest[1]);
  await page.waitForTimeout(400);
  const hover = await read();
  await page.mouse.move(200, 300);
  await page.waitForTimeout(400);
  await page.evaluate(() => toastLive(document.getElementById('toast-box'))[0].querySelector('button')?.focus());
  await page.waitForTimeout(300);
  const keys = await read();
  console.log(JSON.stringify({ rest, hover, keys }));
  await browser.close();
})();
