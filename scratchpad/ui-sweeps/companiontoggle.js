// INBOX 430: the companion shows and hides from anywhere: Ctrl+Shift+Y, the
// command palette and Find anything. Starts with Atlas on, presses the
// chord (gone), again (back as Atlas), then runs the palette's and Find's
// action rows, whose labels say which they will do ("Hide companion" while
// it is out, "Show companion" while it is not). Then the chord typed in the
// note box (it still answers, and types nothing), the toast after a rebind
// naming the new chord, and a locked notebook (the chord does nothing).
// Exits 1 if any step leaves the companion in the wrong state.
const { boot } = require('./lib.js');

(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.evaluate(async () => { prefs.set('avatar-buddy', 'atlas'); await ensureModule('characters'); syncNameMarkBuddy(); });
  await page.waitForTimeout(1500);
  const shown = () => page.evaluate(() => !!document.getElementById('nm-buddy') && localStorage.getItem('avatar-buddy') !== 'off');
  const steps = [];
  steps.push(['start', await shown(), true]);
  await page.mouse.click(700, 450);
  await page.keyboard.press('Control+Shift+Y');
  await page.waitForTimeout(600);
  steps.push(['chord hides', await shown(), false]);
  await page.keyboard.press('Control+Shift+Y');
  await page.waitForTimeout(1200);
  steps.push(['chord shows', await shown(), true]);
  steps.push(['same one back', await page.evaluate(() => localStorage.getItem('avatar-buddy')), 'atlas']);
  // The palette's action.
  await page.keyboard.press('Control+K');
  await page.waitForTimeout(400);
  await page.keyboard.type('companion');
  await page.waitForTimeout(400);
  const paletteRow = await page.evaluate(() => [...document.querySelectorAll('#palette-overlay [role="option"]')].map((el) => el.textContent.trim()).find((t) => /companion/i.test(t) && !/call/i.test(t)) || '');
  steps.push(['palette says hide', /Hide companion/.test(paletteRow), true]);
  await page.keyboard.press('Backspace');
  await page.evaluate(() => { const i = document.querySelector('#palette-overlay input'); i.value = ''; i.dispatchEvent(new Event('input', { bubbles: true })); });
  await page.keyboard.type('hide companion');
  await page.waitForTimeout(400);
  await page.keyboard.press('Enter');
  await page.waitForTimeout(700);
  steps.push(['palette hides', await shown(), false]);
  // Find anything's.
  await page.keyboard.press('Control+P');
  await page.waitForTimeout(400);
  await page.keyboard.type('show companion');
  await page.waitForTimeout(1200);
  const row = await page.evaluate(() => [...document.querySelectorAll('#finder-results [role="option"], #finder-results li, #finder-results button')].find((el) => /companion/i.test(el.textContent))?.textContent.trim().slice(0, 60) || '');
  steps.push(['find lists it', !!row, true]);
  await page.evaluate(() => { const hit = finderHits.find((h) => h.kind === 'action' && /companion/i.test(h.title)); hit?.run(); });
  await page.waitForTimeout(1200);
  steps.push(['find shows', await shown(), true]);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);
  // While typing in a text box: a chord still answers (the dispatcher's
  // chorded branch runs in text fields), and types nothing. A box of its
  // own, so the step does not depend on which composer is open or enabled.
  await page.keyboard.press('Escape');
  await page.evaluate(() => { const t = document.createElement('textarea'); t.id = 'probe-box'; t.style.position = 'fixed'; t.style.left = '200px'; t.style.top = '300px'; t.style.zIndex = '99'; document.body.appendChild(t); t.focus(); });
  await page.keyboard.type('abc');
  await page.keyboard.press('Control+Shift+Y');
  await page.waitForTimeout(700);
  steps.push(['chord while typing hides', await shown(), false]);
  steps.push(['text box untouched', await page.evaluate(() => document.getElementById('probe-box').value), 'abc']);
  await page.evaluate(() => document.getElementById('probe-box').remove());
  // Rebound: the chord that answers and the toast both follow.
  await page.evaluate(() => { shortcuts.toggleCompanion.keys = 'Alt+Shift+C'; });
  await page.keyboard.press('Control+Shift+Y');
  await page.waitForTimeout(500);
  steps.push(['old chord does nothing once rebound', await shown(), false]);
  await page.keyboard.press('Alt+Shift+C');
  await page.waitForTimeout(1200);
  steps.push(['new chord shows', await shown(), true]);
  await page.evaluate(() => { const was = window.toast; window.__said = []; window.toast = (m, ...rest) => { window.__said.push(m); return was(m, ...rest); }; });
  await page.keyboard.press('Alt+Shift+C');
  await page.waitForTimeout(500);
  steps.push(['new chord hides', await shown(), false]);
  const said = await page.evaluate(() => window.__said.join(' | '));
  console.log('said:', said);
  steps.push(['toast names the new chord', /Alt\+Shift\+C/.test(said) && !/Ctrl\+Shift\+Y/.test(said), true]);
  await page.evaluate(() => { shortcuts.toggleCompanion.keys = 'Ctrl+Shift+Y'; });
  // Locked: no chord answers.
  await page.evaluate(() => lockNow());
  await page.waitForTimeout(800);
  await page.keyboard.press('Control+Shift+Y');
  await page.waitForTimeout(800);
  steps.push(['locked, the chord does nothing', await shown(), false]);
  let bad = errors.length > 0;
  for (const [name, got, want] of steps) {
    const ok = got === want;
    if (!ok) bad = true;
    console.log(`${ok ? 'ok  ' : 'FAIL'} ${name}: ${got}`);
  }
  if (errors.length) console.log('errors:', errors.join(' | '));
  console.log(bad ? 'FAIL' : 'PASS');
  process.exitCode = bad ? 1 : 0;
  await browser.close();
})();
