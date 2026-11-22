// The owner: "I cant collapse the sections below each settings page in the
// settings sidebar". Per pane: the "On this page" head folds every link away
// (mouse, then Enter), the state survives reopening, and another pane stays open.
//   BASE=http://127.0.0.1:8781 [THEME=dark] node scratchpad/ui-sweeps/settingsnavfold.js
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  let errs = 0, bad = 0;
  page.on('pageerror', (e) => { errs++; console.log('pageerror', e.message); });
  const state = () => page.evaluate(() => {
    const f = document.querySelector('#settings-nav .settings-nav-fold');
    const links = [...document.querySelectorAll('#settings-nav .settings-nav-group')];
    const head = f?.closest('.settings-nav-groups-head');
    return f && { expanded: f.getAttribute('aria-expanded'), shown: links.filter((l) => l.getClientRects().length).length,
      total: links.length, headH: Math.round(head.getBoundingClientRect().height), fold: f.textContent.trim(), focus: document.activeElement === f };
  });
  const open = async (p) => { await page.evaluate((p) => openSettingsModal(p), p); await page.waitForTimeout(1500); };
  await open('appearance');
  const a0 = await state(); console.log('open', JSON.stringify(a0));
  await page.click('#settings-nav .settings-nav-fold'); await page.waitForTimeout(300);
  const a1 = await state(); console.log('clicked', JSON.stringify(a1));
  if (!(a1.expanded === 'false' && a1.shown === 0)) bad++;
  await open('models'); const m = await state(); console.log('models', JSON.stringify(m));
  if (m && m.expanded !== 'true') bad++;
  await open('appearance'); const a2 = await state(); console.log('reopened', JSON.stringify(a2));
  if (!(a2.expanded === 'false' && a2.shown === 0)) bad++;
  await page.focus('#settings-nav .settings-nav-fold'); await page.keyboard.press('Enter'); await page.waitForTimeout(300);
  const a3 = await state(); console.log('enter', JSON.stringify(a3));
  if (!(a3.expanded === 'true' && a3.shown >= 1)) bad++;
  console.log(`bad ${bad} errors ${errs}`);
  await browser.close();
})();
