// INBOX 1321: type while an answer streams, queue, edit back, remove, and
// the queue sends in order when the answer ends. The chat's POSTs are held
// 3s so the answer is still coming when the next message is typed.
//   BASE=http://127.0.0.1:8781 node chatqueue1321.js
const { boot } = require('./lib.js');
(async () => {
  const { page, browser } = await boot({ viewport: { width: 1280, height: 800 } });
  await page.waitForTimeout(2500);
  const sent = [];
  await page.route(/\/(chat|agent)[^?]*$/, async (route) => {
    const req = route.request();
    if (req.method() === 'POST' && !/followups|recent|title/.test(req.url())) {
      try { sent.push(JSON.parse(req.postData() || '{}').question || JSON.parse(req.postData() || '{}').message || '?'); } catch { sent.push('?'); }
      await new Promise((r) => setTimeout(r, 3000));
    }
    return route.continue();
  });
  await page.evaluate(() => switchTab('chat'));
  await page.waitForTimeout(800);
  const box = page.locator('#chat-input');
  await box.fill('first question about my notes');
  await box.press('Enter');
  await page.waitForTimeout(500);
  const r = {};
  r.boxDisabled = await box.isDisabled();
  r.stopShown = await page.locator('#chat-stop').isVisible();
  await box.fill('second one');
  await box.press('Enter');
  await box.fill('third one');
  await box.press('Enter');
  await page.waitForTimeout(600);
  r.queued = await page.locator('.chat-queue-item .chat-queue-text').allTextContents();
  r.boxAfterQueue = await box.inputValue();
  // Edit the third back into the box, then remove the box text again.
  await page.locator('.chat-queue-item').nth(1).locator('button').first().click();
  r.afterEdit = { queue: await page.locator('.chat-queue-text').allTextContents(), box: await box.inputValue() };
  await box.fill('');
  const h = await page.evaluate(() => { const i = document.querySelector('.chat-queue-item'); const b = i.getBoundingClientRect(); const t = i.querySelector('.chat-queue-text'); return [Math.round(b.height), t.scrollWidth <= t.clientWidth + 1]; });
  r.itemHeightFits = h;
  await page.waitForTimeout(9000);
  r.queueLeft = await page.locator('.chat-queue-item').count();
  r.sent = sent;
  console.log(JSON.stringify(r));
  await browser.close();
})();
