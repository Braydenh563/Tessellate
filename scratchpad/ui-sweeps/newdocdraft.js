// dog1-1025 item 16: New document makes no row until the first edit; names are
// unique; the sidebar is newest edit first.
const { boot } = require('./lib.js');
(async () => {
  const { page, browser } = await boot({ viewport: { width: 1280, height: 800 } });
  await page.waitForTimeout(2500);
  const posts = [];
  page.on('request', (r) => { if (r.method() === 'POST' && /\/documents$/.test(r.url())) posts.push(r.url()); });
  await page.evaluate(() => switchTab('documents'));
  await page.waitForTimeout(1500);
  const rows = () => page.evaluate(() => [...document.querySelectorAll('#doc-list .doc-item-title')].map((e) => e.textContent));
  const before = await rows();
  await page.click('#doc-new');
  await page.waitForTimeout(800);
  const afterClick = await rows();
  const dialog = await page.evaluate(() => !!document.getElementById('doc-template-dialog')?.open);
  console.log('before', before.length, 'afterClick', afterClick.length, 'posts', posts.length, 'dialog', dialog);
  await page.keyboard.type('First draft');
  await page.waitForTimeout(2500);
  const afterType = await rows();
  console.log('afterType', JSON.stringify(afterType.slice(0, 3)), 'posts', posts.length);
  await page.click('#doc-new'); await page.waitForTimeout(600);
  await page.keyboard.type('x'); await page.waitForTimeout(2500);
  const t = await page.evaluate(() => document.getElementById('doc-title').value);
  console.log('second title', t, JSON.stringify((await rows()).slice(0, 3)));
  await page.click('#doc-new'); await page.waitForTimeout(600);
  console.log('empty draft rows', (await rows()).length);
  await browser.close();
})();
