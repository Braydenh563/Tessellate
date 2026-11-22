// L-chat-167: ResizeObserver loop errors and frame gaps over two streamed answers.
// FAKE_DELAY_MS=40 fake_answer_server.py 8796; serve.sh 8795 <dir>; BASE=http://127.0.0.1:8795 node chatstutter167.js
const { boot } = require('./lib.js');
(async () => {
  const { page, browser } = await boot({ viewport: { width: 1440, height: 900 } });
  const errs = [];
  page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text().slice(0, 140)); });
  page.on('pageerror', (e) => errs.push('pageerror ' + String(e).slice(0, 140)));
  await page.evaluate(async () => {
    for (let i = 0; i < 6; i++) await api('/entries', { method: 'POST', body: JSON.stringify({ content: `# Harbor note ${i}\n\nThe Harbor launch is planned for the 14th. Beta testers number 41 and the pricing page is still waiting on sign off. Sync conflicts may surface under load.`, category: 'General' }) });
    await api('/models/provider', { method: 'POST', body: JSON.stringify({ provider: 'openai', base_url: 'http://127.0.0.1:8796/v1' }) });
    await api('/models/chat-model', { method: 'POST', body: JSON.stringify({ name: 'fake-answerer' }) }).catch(() => null);
  });
  await page.evaluate(() => switchTab('chat'));
  await page.waitForTimeout(1500);
  await page.evaluate(() => {
    window.__ro = 0; window.__gaps = [];
    window.addEventListener('error', (e) => { if (/ResizeObserver/.test(e.message || '')) window.__ro++; }, true);
    let last = performance.now();
    const tick = (t) => { window.__gaps.push(t - last); last = t; window.__raf = requestAnimationFrame(tick); };
    window.__raf = requestAnimationFrame(tick);
  });
  for (const q of ['What is the Harbor launch plan?', 'What are the launch risks?']) {
    await page.fill('#chat-input', q);
    await page.keyboard.press('Enter');
    await page.waitForTimeout(9000);
  }
  const r = await page.evaluate(() => { cancelAnimationFrame(window.__raf); const g = window.__gaps.slice(5).sort((a, b) => a - b); return { ro: window.__ro, frames: g.length, p95: g[Math.floor(g.length * 0.95)], max: g[g.length - 1], over50: g.filter((x) => x > 50).length, answers: document.querySelectorAll('#chat-messages .chat-msg.assistant, #chat-messages [data-role="assistant"]').length, text: (document.querySelector('#chat-messages')?.innerText || '').slice(-200) }; });
  console.log(JSON.stringify({ ...r, consoleErrors: errs }));
  await browser.close();
})();
