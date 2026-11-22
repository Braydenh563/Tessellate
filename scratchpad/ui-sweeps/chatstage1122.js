// A .py chosen in the chat is staged, not imported, until send (the owner, 2026-11-22).
// Counts /documents/import and /media/upload requests and the documents list at each step.
const { boot, BASE } = require('./lib.js');
(async () => {
  const { browser, page } = await boot();
  const posts = [];
  page.on('request', (r) => { if (r.method() === 'POST' && /\/(documents\/import|media\/upload)/.test(r.url())) posts.push(r.url().replace(BASE, '')); });
  let chatBody = '';
  page.on('request', (r) => { if (r.method() === 'POST' && /\/chat/.test(r.url()) && r.postData()?.startsWith('{"question')) chatBody = r.postData(); });
  const docs = async () => (await page.evaluate(() => apiJson('/documents'))).length ?? -1;
  const file = { name: 'staged_demo.py', mimeType: 'text/x-python', buffer: Buffer.from('def hello():\n    return 1\n') };
  await page.evaluate(() => switchTab('chat'));
  await page.waitForTimeout(800);
  const before = await docs();
  await page.setInputFiles('#chat-image-input', file);
  await page.waitForTimeout(800);
  const chip = await page.$$eval('#chat-doc-attachments > *', (els) => els.map((e) => e.textContent.trim().slice(0, 40)));
  console.log('after attach: posts', posts.length, 'docs', (await docs()) - before, 'chips', JSON.stringify(chip));
  await page.click('#chat-doc-attachments [aria-label^="Don\'t send"], #chat-doc-attachments button[title^="Don\'t send"]');
  await page.waitForTimeout(400);
  console.log('after remove: posts', posts.length, 'docs', (await docs()) - before, 'chips', await page.$$eval('#chat-doc-attachments > *', (e) => e.length));
  await page.setInputFiles('#chat-image-input', file);
  await page.waitForTimeout(500);
  await page.fill('#chat-input', 'what does this file do');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(4000);
  console.log('after send: posts', JSON.stringify(posts), 'docs', (await docs()) - before,
    'document_ids', JSON.stringify(JSON.parse(chatBody || '{}').document_ids), 'cards', await page.evaluate(() => [...document.querySelectorAll('#chat-messages .msg.user')].at(-1).previousElementSibling?.textContent.trim().slice(0, 60)));
  await browser.close();
})();
