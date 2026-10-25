// dog1-1025: Settings search "phone" ranks Other devices above Microphone.
const { boot } = require('./lib.js');
(async () => {
  const { page, browser } = await boot({ viewport: { width: 1280, height: 800 } });
  await page.waitForTimeout(2500);
  await page.evaluate(() => openSettingsModal("general"));
  await page.waitForTimeout(1500);
  const r = await page.evaluate(async () => {
    const out = {};
    for (const q of ['phone', 'phones', 'microphone']) out[q] = findSettings(q, 8).map((x) => x.text || x.row?.text || JSON.stringify(Object.keys(x)));
    return out;
  });
  console.log(JSON.stringify(r, null, 1));
  await browser.close();
})();
