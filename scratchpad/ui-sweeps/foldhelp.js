// The '?' on a settings fold's head (INBOX 433): where the head and its
// help button sit, per fold, so moving the button out of the <summary>
// (axe nested-interactive, WCAG 4.1.2) can be checked against the place it
// had. Every position is relative to the fold's own box, so a before and an
// after compare directly. WIDTHS=1440,390 by default; 390 runs with touch.
// Also says whether the button is the topmost thing at its own centre, and
// whether pressing it opens a closed fold and its popover without toggling
// an open one.
const { boot } = require('./lib.js');
// [section, the help panel's id]: the fold is the panel's own <details>.
const FOLDS = [
  ['appearance', 'themes-help'],
  ['appearance', 'statusbar-help'],
  ['appearance', 'custom-css-help'],
  ['models', 'sampling-help'],
  ['skills', 'skill-tools-help'],
  ['skills', 'skill-verify-help'],
  ['shortcuts', 'always-available-help'],
  ['extras', 'packages-help'],
  ['extras', 'embedding-models-help'],
];
(async () => {
  for (const width of (process.env.WIDTHS || '1440,390').split(',').map(Number)) {
    const opts = { viewport: { width, height: 900 } };
    if (width < 600) { opts.hasTouch = true; opts.isMobile = true; }
    const { browser, page } = await boot(opts);
    await page.evaluate(() => openSettingsModal());
    await page.waitForTimeout(700);
    for (const [section, panelId] of FOLDS) {
      await page.evaluate((s) => openSettingsModal(s), section);
      await page.waitForTimeout(400);
      const r = await page.evaluate(async (id) => {
        const panel = document.getElementById(id);
        if (!panel) return 'missing';
        const fold = panel.closest('details');
        // Open every fold around this one, so it is drawn at all.
        for (let d = fold.parentElement?.closest('details'); d; d = d.parentElement?.closest('details')) d.open = true;
        const wasOpen = fold.open;
        const help = document.querySelector(`[data-help-for="${id}"]`);
        help.scrollIntoView({ block: 'center' });
        await new Promise((res) => setTimeout(res, 150));
        const box = (el) => {
          const b = el.getBoundingClientRect();
          return [b.left, b.top, b.width, b.height];
        };
        const fb = box(fold);
        const rel = (b) => b.map((v, i) => Math.round((i < 2 ? v - fb[i] : v) * 10) / 10);
        const sum = fold.querySelector(':scope > summary');
        const hb = help.getBoundingClientRect();
        const at = document.elementFromPoint(hb.left + hb.width / 2, hb.top + hb.height / 2);
        const out = {
          open: wasOpen,
          fold: [Math.round(fb[2] * 10) / 10, Math.round(fb[3] * 10) / 10],
          summary: rel(box(sum)),
          help: rel(box(help)),
          rightGap: Math.round((fb[0] + fb[2] - hb.right) * 10) / 10,
          helpOnTop: help.contains(at),
          inSummary: sum.contains(help),
        };
        // Pressing it: the popover opens, and the fold is open after.
        help.click();
        await new Promise((res) => setTimeout(res, 100));
        out.popover = !panel.classList.contains('hidden');
        out.openAfter = fold.open;
        help.click();
        fold.open = wasOpen;
        return out;
      }, panelId);
      console.log(width, panelId, JSON.stringify(r));
    }
    await browser.close();
  }
  await offsets();
})();

// INBOX 1514: the help button against its slot for every visible fold-help,
// read right after the dialog opens (its 240ms scale-in is what skewed the
// first placement) and again after a scroll, in Settings and in the
// Appearance panel; all must be 0px off. SURFACE=panel for the panel run.
async function offsets() {
  const MEASURE = () => [...document.querySelectorAll('.fold-help-wrap')].flatMap((w) => {
    const slot = w.querySelector('.fold-help-slot');
    const s = slot.getBoundingClientRect();
    for (let e = slot.parentElement; e; e = e.parentElement) {
      if (e.tagName === 'DETAILS' && !e.open && !e.querySelector(':scope > summary').contains(slot)) return [];
      if (e.hidden || e.classList.contains('hidden')) return [];
    }
    if (!s.width) return [];
    const h = w.querySelector(':scope > .fold-help').getBoundingClientRect();
    return [[w.querySelector(':scope > .fold-help').dataset.helpFor, +(h.left - s.left).toFixed(1), +(h.top - s.top).toFixed(1)]];
  });
  for (const width of [1440, 390]) {
    const opts = { viewport: { width, height: 900 } };
    if (width < 600) { opts.hasTouch = true; opts.isMobile = true; }
    const { browser, page } = await boot(opts);
    await page.evaluate(() => prefs.set(SETTINGS_FOLDS_KEY, JSON.stringify({ 'appearance-advanced': true })));
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);
    if (await page.isVisible('#lock-password')) { await page.fill('#lock-password', 'testpassword123'); await page.click('#lock-submit'); await page.waitForTimeout(2500); }
    await page.evaluate((panel) => (panel ? openAppearancePanel('advanced') : openSettingsModal('appearance')), process.env.SURFACE === 'panel');
    await page.waitForTimeout(1200);
    let worst = 0;
    for (const step of ['opened', 'scrolled']) {
      if (step === 'scrolled') {
        await page.evaluate(() => document.querySelector('[data-help-for="custom-css-help"]').scrollIntoView({ block: 'center' }));
        await page.waitForTimeout(500);
      }
      const rows = await page.evaluate(MEASURE);
      for (const [, dx, dy] of rows) worst = Math.max(worst, Math.abs(dx), Math.abs(dy));
      console.log(width, step, rows.length, 'visible, worst', worst, 'px off');
    }
    // The entrance is a race, so force it: place every '?' while the card is
    // scaled to 0.9, then let it settle and measure (the old placement: ~60px).
    const forced = await page.evaluate((MEASURE) => {
      const card = document.querySelector('#settings-modal > *, #appearance-panel');
      card.style.transition = 'none';
      card.style.scale = '0.9';
      document.querySelectorAll('.fold-help-wrap').forEach(placeFoldHelp);
      card.style.scale = '';
      card.style.transition = '';
      return eval(`(${MEASURE})`)();
    }, MEASURE.toString());
    for (const [, dx, dy] of forced) worst = Math.max(worst, Math.abs(dx), Math.abs(dy));
    console.log(width, 'placed while scaled to 0.9', forced.length, 'visible, worst', worst, 'px off');
    await browser.close();
    if (worst > 0.1) process.exitCode = 1;
  }
}
