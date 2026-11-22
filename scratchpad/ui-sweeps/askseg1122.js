// Chat mode switch (the owner, 2026-11-22: "can't switch to Ask, Agent stays selected").
// Clicks Ask then Agent then Ask, reading aria-pressed, the tools checkbox and the saved preference each time.
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: +(process.env.W || 1440), height: 900 } });
  await page.evaluate(() => switchTab('chat'));
  await page.waitForTimeout(800);
  if (process.env.AGENT_OK) await page.evaluate(() => { window.agentModeAvailable = () => true; renderChatModeSeg(); });
  const read = (label) => page.evaluate(async (label) => {
    const b = (m) => document.querySelector(`#chat-mode-seg [data-chat-mode="${m}"]`);
    const prefs = await apiJson('/preferences', { silent: true }).catch(() => ({}));
    const ask = b('chat');
    const r = ask.getBoundingClientRect();
    const top = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
    return { label, ask: ask.getAttribute('aria-pressed'), agent: b('agent').getAttribute('aria-pressed'),
      tools: document.getElementById('tools-toggle').checked, saved: prefs.tools_enabled,
      visible: r.width > 0, hitIsAsk: !!top && ask.contains(top), hit: top ? (top.id || top.className).toString().slice(0, 60) : null };
  }, label);
  console.log(JSON.stringify(await read('start')));
  for (const m of ['agent', 'chat', 'agent', 'chat']) {
    await page.click(`#chat-mode-seg [data-chat-mode="${m}"]`, { timeout: 5000 }).catch((e) => console.log('click failed', m, e.message.slice(0, 200)));
    await page.waitForTimeout(500);
    console.log(JSON.stringify(await read(`after ${m}`)));
  }
  await browser.close();
})();
