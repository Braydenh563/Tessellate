// Reminders row (dog 2026-10-27): the date and the ⋯ must not overlap, and the
// ⋯ must take a plain click with no hover first. Run with BASE=... THEME=dark,
// W=1280 (or 390).
const { boot } = require('./lib.js');
(async () => {
  const width = Number(process.env.W || 1280);
  const { page, browser } = await boot({ viewport: { width, height: 800 } });
  await page.waitForTimeout(2000);
  const rid = await page.evaluate(async () => {
    const r = await apiJson('/reminders', { method: 'POST', body: JSON.stringify({ text: 'Kebab overlap check', due_at: new Date(Date.now() + 36e5 * 5).toISOString() }) });
    return r.id;
  });
  await page.evaluate(() => switchTab('reminders'));
  await page.waitForTimeout(1500);
  await page.mouse.move(2, 2);
  const m = await page.evaluate((id) => {
    const li = document.querySelector(`#reminder-groups li[data-id="${id}"]`);
    if (!li) return null;
    li.scrollIntoView({ block: 'center' });
    const r = (el) => { const b = el.getBoundingClientRect(); return { l: Math.round(b.left), r: Math.round(b.right), t: Math.round(b.top), b: Math.round(b.bottom) }; };
    const date = li.querySelector('.entry-date');
    const kebab = li.querySelector('.entry-actions .kebab-opener');
    const k = kebab.getBoundingClientRect();
    const hit = document.elementFromPoint(k.left + k.width / 2, k.top + k.height / 2);
    return { date: r(date), actions: r(li.querySelector('.entry-actions')), kebab: r(kebab), hitIsKebab: kebab.contains(hit), hit: hit && (hit.className || hit.tagName),
      gap: Math.round(k.left - date.getBoundingClientRect().right) };
  }, rid);
  console.log('measure', width, JSON.stringify(m));
  await page.mouse.move(2, 2);
  try {
    await page.locator(`#reminder-groups li[data-id="${rid}"] .entry-actions .kebab-opener`).click({ trial: true, timeout: 3000 });
    console.log('playwright actionability (no hover): ok');
  } catch (e) { console.log('playwright actionability (no hover): FAILED', e.message.split('\n')[0]); }
  const k = m.kebab;
  await page.mouse.click((k.l + k.r) / 2, (k.t + k.b) / 2, { delay: 20 });
  await page.waitForTimeout(400);
  console.log('menu open after a plain click:', await page.evaluate(() => !!document.querySelector('.action-menu:not(.hidden)')));
  await browser.close();
})();
