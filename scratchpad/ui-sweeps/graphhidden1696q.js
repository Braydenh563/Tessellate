// INBOX 1696 (q): "raf 157ms on chat: graph-canvas.js gcRequestDraw 28 calls/s". Opens the graph, opens a
// note (so the local map pane may draw), then goes to chat and counts rAF callbacks queued from graph code.
//   BASE=http://127.0.0.1:8791 node scratchpad/ui-sweeps/graphhidden1696q.js
const { boot } = require('./lib.js');
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(() => {
    window.__raf = {};
    const raf = window.requestAnimationFrame.bind(window);
    window.requestAnimationFrame = (cb) => {
      const st = new Error().stack.split('\n').slice(2, 4).map((l) => (l.match(/at (\S+)/) || [])[1]).join('<');
      window.__raf[st] = (window.__raf[st] || 0) + 1;
      return raf(cb);
    };
  });
  const count = async (label, fn) => {
    await page.evaluate(fn);
    await page.waitForTimeout(2500);
    await page.evaluate(() => { window.__raf = {}; });
    await page.waitForTimeout(3000);
    const r = await page.evaluate(() => Object.entries(window.__raf).filter(([k]) => /gc|graph/i.test(k)).sort((a, b) => b[1] - a[1]).slice(0, 5));
    console.log(label, JSON.stringify(r));
  };
  await count('graph', () => switchTab('graph'));
  await count('chat-after-graph', () => switchTab('chat'));
  await count('notes', () => switchTab('notes'));
  await count('note-open', async () => { const e = (await apiJson('/entries?limit=1'))[0]; flashEntry(e.id); });
  await count('chat-after-note', () => switchTab('chat'));
  await count('dashboard', () => switchTab('dashboard'));
  await browser.close();
})();
