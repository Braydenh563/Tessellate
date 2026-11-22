// The unsaved-work guard (navigation.js, `confirmLeavingUnsavedWork`) and
// history: with an unsaved document, go to Notes (answering Leave),
// then press the browser's Back and answer Cancel. The tab must stay Notes
// and the address, the history stack's index and the tab on screen must
// agree; before, the stack stepped back regardless and the address named the
// tab left while Notes was shown.
// Exits 1 when they disagree after the Cancel.
const { boot } = require('./lib.js');

(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  // The guard asks only for a document whose save failed now (navigation.js:
  // the capture box and a note form keep their words, so a switch is no
  // departure). A document with edits in hand and a save that does nothing
  // stands in for that.
  await page.evaluate(() => switchTab('documents'));
  await page.waitForFunction(() => typeof saveDocument === 'function', null, { timeout: 20000 });
  await page.waitForTimeout(800);
  await page.evaluate(() => { window.saveDocument = async () => {}; docDirty = true; });
  const answer = async (which) => {
    await page.waitForSelector('.confirm-overlay button', { timeout: 3000 });
    const buttons = await page.$$('.confirm-overlay .confirm-actions button, .confirm-overlay button');
    const labels = await Promise.all(buttons.map((b) => b.textContent()));
    const pick = labels.findIndex((l) => (which === 'ok' ? /leave|ok|yes|confirm|continue/i : /cancel|stay|no/i).test(l));
    await buttons[pick >= 0 ? pick : which === 'ok' ? buttons.length - 1 : 0].click();
    return labels;
  };
  const going = page.evaluate(() => switchTab('notes'));
  const labels = await answer('ok');
  await going;
  await page.waitForTimeout(600);
  const state = () => page.evaluate(() => ({ tab: localStorage.getItem('activeTab'), shown: !document.getElementById('tab-notes').classList.contains('hidden') ? 'notes' : !document.getElementById('tab-documents').classList.contains('hidden') ? 'documents' : '?', hash: location.hash, index: tabHistory.index, at: tabHistory.stack[tabHistory.index]?.tab }));
  const before = await state();
  await page.evaluate(() => history.back());
  await answer('cancel');
  await page.waitForTimeout(1200);
  const after = await state();
  console.log('buttons', JSON.stringify(labels), '\nbefore Back', JSON.stringify(before), '\nafter Cancel', JSON.stringify(after));
  const bad = after.shown !== 'notes' || after.at !== 'notes' || !/notes/.test(after.hash);
  console.log(bad ? 'FAIL' : 'PASS');
  process.exitCode = bad ? 1 : 0;
  await browser.close();
})();
