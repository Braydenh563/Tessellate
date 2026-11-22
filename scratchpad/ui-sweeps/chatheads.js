// Each assistant reply wears the face of the persona that answered it (the
// owner, 2026-09-27). Seeds a chat of TURNS turns whose replies were written
// by the default persona, by no recorded persona (an older turn) and by
// Coach in turn, opens it, and measures: open time, how many p5 canvases the
// transcript holds (should be 0), how many distinct drawings (the heads are
// copies), whether each reply's head matches its writer (Atlas's bust for
// the app's voice, the generated face for Coach), and a screenshot.
//
//   BASE=... TURNS=150 THEME=dark node chatheads.js
//
// Exits 1 on a p5 canvas in a reply head, a head that does not match its
// writer, or an empty head.
const fs = require('fs');
const { boot, OUT } = require('./lib.js');
const TURNS = Number(process.env.TURNS || 150);

(async () => {
  const { browser, page } = await boot({ viewport: { width: Number(process.env.W || 1440), height: 900 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.evaluate(() => switchTab('chat'));
  await page.waitForTimeout(1500);
  const id = await page.evaluate(async (n) => {
    const who = (i) => (i % 3 === 0 ? null : i % 3 === 1 ? undefined : 'Coach');
    const turn = (i) => {
      const t = { question: `Question ${i}: what about item ${i}?`, answer: `Answer ${i}. Some **markdown** and a list:\n\n- one\n- two` };
      const p = who(i);
      if (p !== undefined) t.persona = p;
      return t;
    };
    const first = await apiJson('/conversations', { method: 'POST', body: JSON.stringify(turn(0)) });
    for (let i = 1; i < n; i += 1) {
      await api(`/conversations/${first.id}/turns`, { method: 'POST', body: JSON.stringify(turn(i)) });
    }
    return first.id;
  }, TURNS);
  await page.evaluate(() => newChatConversation());
  await page.waitForTimeout(500);
  const r = await page.evaluate(async (convId) => {
    const t0 = performance.now();
    await openConversation(convId);
    const opened = performance.now() - t0;
    await new Promise((res) => requestAnimationFrame(() => requestAnimationFrame(res)));
    const pane = document.getElementById('chat-messages');
    const replies = [...pane.querySelectorAll('.msg.assistant')];
    const heads = replies.map((m) => m.querySelector('.msg-avatar'));
    const canvases = pane.querySelectorAll('.msg-avatar canvas').length;
    const empty = heads.filter((h) => !h || !h.firstElementChild).length;
    const mismatch = [];
    replies.forEach((m, i) => {
      const head = heads[i]?.firstElementChild;
      const writer = m.dataset.persona;
      const atlas = writer === aiNameNow();
      // Older replies' Atlas heads are retired to a shared-symbol copy (atl-rest, atlas.js retireOlder).
      const isAtlas = !!head && (head.classList.contains('nm-atlas') || head.classList.contains('atl-rest'));
      if (atlas !== isAtlas) mismatch.push(`${i}:${writer}:${head?.getAttribute('class')}`);
    });
    const distinct = new Set(heads.map((h) => h?.innerHTML.length)).size;
    return { turns: replies.length, openMs: Math.round(opened), paintedMs: Math.round(performance.now() - t0), canvases, empty, mismatch: mismatch.slice(0, 5), mismatches: mismatch.length, distinct, nodes: pane.querySelectorAll('*').length, headNodes: heads.reduce((n, h) => n + (h ? h.querySelectorAll('*').length : 0), 0) };
  }, id);
  await page.evaluate(() => { const pane = document.getElementById('chat-messages'); pane.scrollTop = 0; });
  await page.waitForTimeout(300);
  await page.screenshot({ path: `${OUT}/chatheads-${process.env.THEME || 'light'}-${process.env.W || 1440}.png` });
  r.errors = errors;
  console.log(JSON.stringify(r, null, 1));
  const bad = r.canvases > 0 || r.mismatches > 0 || r.empty > 0 || errors.length > 0;
  console.log(bad ? 'FAIL' : 'PASS');
  process.exitCode = bad ? 1 : 0;
  fs.writeFileSync(`${OUT}/chatheads.json`, JSON.stringify(r, null, 1));
  await browser.close();
})();
