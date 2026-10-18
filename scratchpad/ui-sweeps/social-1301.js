// INBOX 1301 D5: the owner's question through Ask (UI), Chat and the popup
// (stream bodies as each surface sends them), no model.
//   BASE=http://127.0.0.1:8795 DATA=<the server's data dir> node scratchpad/ui-sweeps/social-1301.js
const { boot } = require('./lib.js');
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '..', '..');
const PY = process.env.SWEEP_PY || path.join(ROOT, '.venv', 'bin', 'python');
const FIX = JSON.parse(fs.readFileSync(path.join(ROOT, 'tests', 'fixtures', 'gold_answers.json'), 'utf8'));
const item = FIX.answers.find((a) => a.n === 22);
(async () => {
  const { page, browser } = await boot({ viewport: { width: 1440, height: 900 } });
  const ids = await page.evaluate(async (notes) => {
    const have = await apiJson('/entries?limit=500');
    const list = Array.isArray(have) ? have : have.entries || have.items || [];
    const out = [];
    for (const n of notes) {
      const found = list.find((e) => (e.content || '').trim() === n.content.trim());
      if (found) { out.push([found.id, n.date]); continue; }
      const made = await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: n.content, category: n.category, tags: n.tags }) });
      out.push([made.id, n.date]);
    }
    return out;
  }, item.notes);
  const db = fs.existsSync(path.join(process.env.DATA, 'tessellate.db')) ? path.join(process.env.DATA, 'tessellate.db') : path.join(process.env.DATA, 'memorymap.db');
  execFileSync(PY, ['-c', 'import json,sqlite3,sys\ncon=sqlite3.connect(sys.argv[1])\nfor i,d in json.loads(sys.argv[2]): con.execute("update entries set created_at=?, updated_at=? where id=?",(d+" 10:00:00.000000",d+" 10:00:00.000000",i))\ncon.commit()', db, JSON.stringify(ids)]);
  const ask = async (extra) => page.evaluate(async ({ q, extra }) => {
    const body = Object.assign({ question: q, history: [] }, extra);
    const res = await api.stream('/chat/stream', { method: 'POST', body: JSON.stringify(body) });
    const reader = res.body.getReader(); const dec = new TextDecoder(); let raw = '';
    for (;;) { const { done, value } = await reader.read(); if (done) break; raw += dec.decode(value, { stream: true }); }
    let text = '';
    for (const line of raw.split('\n')) { try { const ev = JSON.parse(line); if (ev.type === 'answer') text += ev.delta || ''; } catch (e) {} }
    return text.trim();
  }, { q: item.question, extra });
  const res = {
    ask_api: await ask({ notes_only: true, use_tools: false }),
    chat: await ask({ use_tools: false }),
    popup: await ask({ use_tools: true }),
  };
  await page.evaluate(() => { switchTab('notes'); if (window.showNotesSection) showNotesSection('ask'); });
  await page.waitForTimeout(800);
  await page.fill('#question', item.question);
  await page.evaluate(() => askQuestion());
  await page.waitForTimeout(4000);
  res.ask_ui = await page.evaluate(() => ({
    echo: !!document.getElementById('asked-question'),
    youAsked: /You asked:/.test(document.querySelector('#chat-results')?.innerText || ''),
    inputKeeps: document.getElementById('question').value,
    text: document.getElementById('ai-answer').innerText,
  }));
  console.log(JSON.stringify(res, null, 1));
  await browser.close();
})();
