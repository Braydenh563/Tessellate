// The search-by-meaning switch once the model is on disk (INBOX 1533).
const { boot } = require('./lib.js');
(async () => {
  const ready = process.env.READY !== '0';
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.route('**/models/status*', async (route) => {
    const res = await route.fetch(); const body = await res.json();
    body.embedding_ready = ready; body.embedding_backend = 'builtin';
    route.fulfill({ response: res, json: body });
  });
  await page.evaluate(() => openSettingsModal('searchindex'));
  await page.waitForTimeout(2500);
  const got = await page.evaluate(() => ({ label: $('semantic-auto-install-label').textContent, hint: $('semantic-auto-install-hint').textContent,
    chips: [...document.querySelectorAll('#embed-choices li')].map((li) => li.querySelector('strong')?.textContent + ' | ' + [...li.querySelectorAll('.item-label')].map((c) => c.textContent.trim()).join(', ')) }));
  console.log(JSON.stringify(got, null, 1));
  await browser.close();
})();
