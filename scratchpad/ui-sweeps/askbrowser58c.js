// L-chat-58 slice 3: the trail and Back. Thread chip, then Around this note, then the arrow and the browser's Back.
//   BASE=http://127.0.0.1:8795 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/askbrowser58c.js
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: Number(process.env.W || 1440), height: 900 } });
  await page.evaluate(() => { switchTab('notes'); showNotesSection('ask'); });
  await page.waitForTimeout(800);
  await page.evaluate((q) => askQuestion(q), 'What have I saved about courses & study?').catch(() => {});
  await page.waitForTimeout(6000);
  const snap = (tag) => page.evaluate((tag) => {
    const nav = document.getElementById('ask-browse-trail');
    const b = nav.getBoundingClientRect();
    const visible = [...document.querySelectorAll('#raw-results > li[data-id]')].filter((li) => !li.classList.contains('hidden')).length;
    return { tag, trail: nav.classList.contains('hidden') ? null : [...nav.querySelectorAll('.doc-crumb')].map((c) => c.textContent).join(' > '),
      h: Math.round(b.height), w: Math.round(b.width), visible, open: document.querySelectorAll('.ask-around').length,
      depth: history.state && history.state.browse || 0, len: history.length, hash: location.hash,
      back: Math.round(document.getElementById('ask-browse-back').getBoundingClientRect().height), overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth };
  }, tag);
  await page.waitForTimeout(3500); // the quick-note bundle (router-overlays.js) preloads three seconds after boot
  console.log(JSON.stringify(await snap('start')));
  await page.locator('#ask-threads .chip').first().click();
  console.log(JSON.stringify(await snap('thread')));
  await page.locator('#raw-results > li[data-id]:not(.hidden) .record-around').first().click();
  await page.waitForTimeout(800);
  console.log(JSON.stringify(await snap('note')));
  await page.goBack(); await page.waitForTimeout(600);
  console.log(JSON.stringify(await snap('browser back 1')));
  await page.goBack(); await page.waitForTimeout(600);
  console.log(JSON.stringify(await snap('browser back 2')));
  await page.locator('#ask-threads .chip').first().click();
  await page.locator('#raw-results > li[data-id]:not(.hidden) .record-around').first().click();
  await page.waitForTimeout(800);
  await page.locator('#ask-browse-back').click(); await page.waitForTimeout(600);
  console.log(JSON.stringify(await snap('arrow 1')));
  await page.locator('#ask-browse-trail .doc-crumb').first().click(); await page.waitForTimeout(600);
  console.log(JSON.stringify(await snap('crumb Answer')));
  await browser.close();
})();
