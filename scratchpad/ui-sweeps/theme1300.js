// INBOX 1300 C21: Settings, Appearance, Themes. No hover preview; the eye
// holds a preview under an Apply / Cancel notice; closing Settings, another
// section or a hidden tab undoes it; Apply keeps it. Reads the
// preview through `settingsLook.themePreview` and the computed --accent.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const bg = () => page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--accent'));
  const state = () => page.evaluate(() => ({ preview: settingsLook.themePreview || '', notice: Boolean(document.querySelector('.theme-preview-notice:not(.is-leaving)')), pressed: [...document.querySelectorAll('#theme-presets .theme-eye[aria-pressed="true"]')].length }));
  const open = async () => { await page.evaluate(() => openSettingsModal('appearance')); await page.waitForTimeout(1200); };
  await open();
  const base = await bg();
  const cards = await page.$$('#theme-presets > .theme-card-cell');
  console.log('cards', cards.length);
  // Find a card whose preview changes the background.
  let pick = -1;
  for (let i = 0; i < cards.length && pick < 0; i++) {
    await page.click(`#theme-presets > .theme-card-cell:nth-child(${i + 1}) .theme-eye`);
    await page.waitForTimeout(300);
    if ((await bg()) !== base) pick = i; else await page.click(`#theme-presets > .theme-card-cell:nth-child(${i + 1}) .theme-eye`);
    await page.waitForTimeout(200);
  }
  if (pick >= 0) await page.click(`#theme-presets > .theme-card-cell:nth-child(${pick + 1}) .theme-eye`);
  await page.waitForTimeout(400);
  const sel = `#theme-presets > .theme-card-cell:nth-child(${pick + 1})`;
  // 1. Hover a card for 900 ms: no preview.
  await page.hover(`${sel} > .theme-card`);
  await page.waitForTimeout(900);
  console.log('hover 900ms', JSON.stringify(await state()), 'bg changed', (await bg()) !== base);
  await page.hover(`${sel} .theme-eye`);
  await page.waitForTimeout(900);
  console.log('hover eye', JSON.stringify(await state()), 'bg changed', (await bg()) !== base);
  const step = async (label, action) => {
    await page.click(`${sel} .theme-eye`);
    await page.waitForTimeout(400);
    const held = await state();
    const heldBg = (await bg()) !== base;
    const nb = await page.evaluate(() => { const n = document.querySelector('.theme-preview-notice'); if (!n) return null; const r = n.getBoundingClientRect(); return { w: Math.round(r.width), h: Math.round(r.height), text: n.querySelector('.toast-msg').textContent, buttons: [...n.querySelectorAll('button')].map((b) => b.textContent) }; });
    await action();
    await page.waitForTimeout(700);
    console.log(label, 'held', JSON.stringify(held), heldBg, JSON.stringify(nb), '-> after', JSON.stringify(await state()), 'bg back', (await bg()) === base);
  };
  await step('cancel', () => page.click('.theme-preview-notice button:has-text("Cancel")'));
  await step('eye again', () => page.click(`${sel} .theme-eye`));
  await step('section switch', () => page.evaluate(() => showSettingsSection('general')));
  await page.evaluate(() => showSettingsSection('appearance')); await page.waitForTimeout(800);
  await step('same section', () => page.evaluate(() => showSettingsSection('appearance')));
  await page.click('.theme-preview-notice button:has-text("Cancel")').catch(() => {});
  await page.waitForTimeout(500);
  await step('close settings', () => page.evaluate(() => closeSettingsModal()));
  await open();
  await step('tab hidden', () => page.evaluate(() => { Object.defineProperty(document, 'hidden', { configurable: true, get: () => true }); document.dispatchEvent(new Event('visibilitychange')); delete document.hidden; }));
  await step('escape', () => page.keyboard.press('Escape'));
  await open();
  const before = await page.evaluate(() => appearancePref('theme'));
  await step('apply', () => page.click('.theme-preview-notice button:has-text("Apply")'));
  console.log('theme pref', before, '->', await page.evaluate(() => appearancePref('theme')), 'bg kept', (await bg()) !== base);
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
