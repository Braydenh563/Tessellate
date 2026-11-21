// L-world-class-394: the search-by-meaning question on a phone, before, inside and after Settings (360x740).
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 360, height: 740 }, isMobile: true, hasTouch: true });
  const read = () => page.evaluate(() => {
    const t = document.querySelector('.toast.semantic-install-toast');
    if (!t) return null;
    const r = t.getBoundingClientRect();
    return { display: getComputedStyle(t).display, w: Math.round(r.width), h: Math.round(r.height), top: Math.round(r.top) };
  });
  //: The server here has no offer open, so its status poll would close the notice: answer as one that has.
  await page.route('**/models/status*', async (route) => {
    const res = await route.fetch();
    const body = await res.json().catch(() => ({}));
    await route.fulfill({ response: res, json: { ...body, semantic_offer: true } });
  });
  await page.evaluate(() => semanticOffer(true, null));
  await page.waitForTimeout(800);
  const before = await read();
  await page.evaluate(() => openSettingsModal('searchindex'));
  await page.waitForTimeout(1500);
  const inside = await read();
  await page.keyboard.press('Escape');
  await page.waitForTimeout(800);
  const after = await read();
  const settingsOpen = await page.evaluate(() => !document.getElementById('settings-modal').classList.contains('hidden'));
  console.log(JSON.stringify({ before, inside, after, settingsOpen }));
  await browser.close();
})();
