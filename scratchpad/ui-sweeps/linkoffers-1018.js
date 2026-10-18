// Link offers: the Settings switch and the persistent Ignore (documents, 2026-10-18).
//   BASE=http://127.0.0.1:8797 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node linkoffers-1018.js
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot();
  const r = {};
  const ids = await page.evaluate(async () => {
    await api('/entries', { method: 'POST', body: JSON.stringify({ content: '# Quarterly roadmap\n\nThe plan.' }) });
    const d = await (await api('/documents', { method: 'POST', body: JSON.stringify({ title: 'Scratch', content: 'Everything hangs on the quarterly roadmap this time.' }) })).json();
    return d.id;
  });
  await page.evaluate(() => switchTab('documents')); await page.waitForTimeout(1500);
  await page.evaluate((id) => openDocument(id), ids); await page.waitForTimeout(2500);
  const count = () => page.evaluate(() => (typeof docProseFindings === 'function' ? 0 : 0) + DOC_LINK_OFFERS.findings.length);
  r.offersOn = await count();
  // switch off through the pref
  await page.evaluate(async () => { prefsCache = await apiJson('/preferences', { method: 'PUT', body: JSON.stringify({ link_offers: false }) }); });
  r.enabledAfterOff = await page.evaluate(() => docLinkOfferEnabled());
  r.serverOff = await page.evaluate(async () => (await apiJson('/preferences')).link_offers);
  await page.evaluate(async () => { prefsCache = await apiJson('/preferences', { method: 'PUT', body: JSON.stringify({ link_offers: true }) }); });
  // ignore a name
  await page.evaluate(() => docLinkOfferIgnore('Quarterly roadmap')); await page.waitForTimeout(800);
  const T = 'Everything hangs on the quarterly roadmap this time.';
  r.currentAfterIgnore = await page.evaluate((t) => docLinkOfferCurrent(t).length, T);
  r.ignoredServer = await page.evaluate(async () => (await apiJson('/preferences')).link_offer_ignored);
  await page.reload({ waitUntil: 'domcontentloaded' }); await page.waitForTimeout(2500);
  r.ignoredAfterReload = await page.evaluate(async () => { prefsCache = await apiJson('/preferences'); return [...docLinkOfferIgnoredNames()]; });
  // Settings row
  await page.evaluate(async () => { prefsCache = await apiJson('/preferences'); await lazyScript('/js/settings-rows.js'); renderLinkIgnoredRow(); });
  r.settings = await page.evaluate(() => ({ box: !!document.getElementById('pref-link-offers'), row: !document.getElementById('pref-link-ignored-row').classList.contains('hidden'), text: document.getElementById('pref-link-ignored-count').textContent }));
  await page.evaluate(() => document.getElementById('pref-link-ignored-reset').click()); await page.waitForTimeout(800);
  r.afterReset = await page.evaluate(async () => ({ server: (await apiJson('/preferences')).link_offer_ignored, rowHidden: document.getElementById('pref-link-ignored-row').classList.contains('hidden') }));
  console.log(JSON.stringify(r, null, 1));
  await browser.close();
})();
