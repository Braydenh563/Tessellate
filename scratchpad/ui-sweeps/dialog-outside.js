// Every modal <dialog> in the page: an outside press closes it; a typed-in one stays; data-keep-open stays.
const L = require('./lib.js');
(async () => {
  const { browser, page } = await L.boot();
  const ids = await page.evaluate(() => [...document.querySelectorAll('dialog')].map((d, i) => d.id || (d.id = `anon-dialog-${i}`)));
  const rows = [];
  for (const id of ids) {
    const r = await page.evaluate((id) => { const d = document.getElementById(id); try { d.showModal(); } catch (e) { return { err: String(e) }; } const b = d.getBoundingClientRect(); return { l: b.left, t: b.top, w: b.width, h: b.height }; }, id);
    if (r.err) { rows.push(`${id}: ${r.err}`); continue; }
    const x = r.l > 12 ? 6 : Math.min(r.l + r.w + 6, 1434); const y = r.t > 12 ? 6 : 890;
    await page.mouse.click(x, y); await page.waitForTimeout(80);
    const closed = await page.evaluate((id) => !document.getElementById(id).open, id);
    let typed = 'n/a';
    if (!closed) await page.evaluate((id) => document.getElementById(id).close(), id);
    const has = await page.evaluate((id) => { const d = document.getElementById(id); d.showModal(); const f = [...d.querySelectorAll('input[type=text], input:not([type]), textarea')].find((e) => e.offsetParent); if (!f) { d.close(); return false; } f.focus(); return true; }, id);
    if (has) { await page.keyboard.type('x'); await page.mouse.click(x, y); await page.waitForTimeout(80); typed = await page.evaluate((id) => { const d = document.getElementById(id); const o = d.open; d.close(); return o ? 'stays' : 'CLOSED'; }, id); }
    rows.push(`${id}: outside ${closed ? 'closes' : 'STAYS'}; typed ${typed}`);
  }
  console.log(rows.join('\n'));
  await browser.close();
})();
