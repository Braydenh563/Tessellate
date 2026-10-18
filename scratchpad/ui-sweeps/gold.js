// The gold answers side by side (CHAT_PLAN decision 70, INBOX 812: "you keep
// saying youve improved it but i still cant see much"). Every question in
// tests/fixtures/gold_answers.json is asked of the running app the way its
// surface asks it (the Ask box: notes only; Chat: the full turn), with no
// model, and the answer is laid beside the hand-written gold on one page,
// scored by tests/_gold.py. Then the Ask box itself is captured on the
// owner's question, so the report shows the answer as the owner sees it.
//
//   BASE=http://127.0.0.1:8872 DATA=<the server's data dir> TAG=after \
//     PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/gold.js
//
// Writes $SCRATCH/shots/gold-<TAG>.png (the side by side), ask-<TAG>.png (the
// Ask box) and gold-<TAG>.json (texts and scores). The notebook is seeded
// once per data dir and its days set from the fixture (DATA is needed for
// that: the API stamps a note with the day it is made).
const { boot, OUT } = require('./lib.js');
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const PY = process.env.SWEEP_PY || '/home/user/MemoryMap-AI/.venv/bin/python';
const TAG = process.env.TAG || 'now';
const FIXTURE = JSON.parse(fs.readFileSync(path.join(ROOT, 'tests', 'fixtures', 'gold_answers.json'), 'utf8'));

function backdate(ids) {
  const db = path.join(process.env.DATA || '', fs.existsSync(path.join(process.env.DATA || '', 'tessellate.db')) ? 'tessellate.db' : 'memorymap.db');
  if (!process.env.DATA || !fs.existsSync(db)) return 'no DATA: notes keep today';
  const rows = FIXTURE.notes.map((n) => [ids[n.key], `${n.date} 10:00:00.000000`]).filter((r) => r[0]);
  execFileSync(PY, ['-c', [
    'import json, sqlite3, sys',
    'con = sqlite3.connect(sys.argv[1])',
    'for i, d in json.loads(sys.argv[2]): con.execute("update entries set created_at = ?, updated_at = ? where id = ?", (d, d, i))',
    'con.commit()',
  ].join('\n'), db, JSON.stringify(rows)]);
  return `backdated ${rows.length}`;
}

function esc(s) {
  return String(s).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
}

function md(s) {
  return esc(s).replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>').replace(/\n/g, '<br>');
}

(async () => {
  const { page, browser } = await boot({ viewport: { width: 1440, height: 900 } });
  const seeded = await page.evaluate(async (notes) => {
    const have = await apiJson('/entries?limit=500');
    const list = Array.isArray(have) ? have : have.entries || have.items || [];
    const ids = {};
    for (const n of notes) {
      const found = list.find((e) => (e.content || '').trim() === n.content);
      if (found) { ids[n.key] = found.id; continue; }
      const made = await apiJson('/entries', {
        method: 'POST',
        body: JSON.stringify({ content: n.content, category: n.category, tags: n.tags }),
      });
      ids[n.key] = made.id;
    }
    return ids;
  }, FIXTURE.notes);
  const dated = backdate(seeded);

  const texts = {};
  for (const item of FIXTURE.answers) {
    //: An answer with its own notebook (n 21) is scored by the test only:
    //: its note would change the shared notebook's answers.
    if (item.notes) continue;
    texts[item.n] = await page.evaluate(async ({ question, ask }) => {
      const body = { question, history: [], use_tools: false };
      if (ask) Object.assign(body, { notes_only: true });
      const res = await api.stream('/chat/stream', { method: 'POST', body: JSON.stringify(body) });
      //: Read as the app reads it (`streamChatEvents`): `api.stream` has
      //: already looked at the response, so `.text()` refuses.
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let raw = '';
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        raw += decoder.decode(value, { stream: true });
      }
      let text = '';
      for (const line of raw.split('\n')) {
        if (!line.trim()) continue;
        try {
          const ev = JSON.parse(line);
          if (ev.type === 'answer') text += ev.delta || '';
        } catch (e) { /* a partial line */ }
      }
      return text.trim();
    }, { question: item.question, ask: item.surface === 'ask' });
  }
  const scores = JSON.parse(execFileSync(PY, [path.join(ROOT, 'tests', '_gold.py')], { input: JSON.stringify(texts), cwd: ROOT }).toString());
  const byN = Object.fromEntries(scores.map((s) => [s.n, s]));
  const mean = (k) => (scores.reduce((a, s) => a + s[k], 0) / scores.length);
  const summary = { tag: TAG, dated, total: Math.round(mean('total')), sim: +mean('sim').toFixed(3), shape: +mean('shape').toFixed(3) };
  fs.writeFileSync(path.join(OUT, `gold-${TAG}.json`), JSON.stringify({ summary, texts, scores }, null, 1));

  const rows = FIXTURE.answers.filter((a) => !a.notes).map((a) => {
    const s = byN[a.n];
    return `<tr><td class="q"><b>${a.n}. ${esc(a.question)}</b><div class="m">${a.surface}, ${a.type}</div>
      <div class="sc">${s.total}</div><div class="m">sim ${s.sim}, shape ${s.shape}</div><div class="f">${esc(s.failed.join(', '))}</div></td>
      <td>${md(texts[a.n] || '(empty)')}</td><td class="g">${md(a.gold)}</td></tr>`;
  }).join('');
  const html = `<!doctype html><meta charset="utf-8"><style>
    body{font:13px/1.45 system-ui,sans-serif;margin:16px;color:#1d1d1f;background:#fff}
    h1{font-size:16px;margin:0 0 8px} table{border-collapse:collapse;width:100%}
    td,th{border-top:1px solid #ddd;vertical-align:top;padding:8px;text-align:left}
    td.q{width:180px} td.g{background:#f6f8f4} .m{color:#666;font-size:11px}
    .sc{font-size:22px;font-weight:600} .f{color:#a33;font-size:11px}
  </style><h1>Gold answers, ${TAG}: mean ${summary.total} (sim ${summary.sim}, shape ${summary.shape})</h1>
  <table><tr><th></th><th>The app, no model</th><th>Gold</th></tr>${rows}</table>`;
  const side = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await side.setContent(html);
  await side.screenshot({ path: path.join(OUT, `gold-${TAG}.png`), fullPage: true });

  //: The Ask box as the owner sees it, on the owner's question.
  await page.evaluate(() => { switchTab('notes'); if (window.showNotesSection) showNotesSection('ask'); });
  await page.waitForTimeout(800);
  await page.fill('#question', FIXTURE.answers[0].question);
  await page.evaluate(() => askQuestion());
  await page.waitForTimeout(3500);
  const ui = await page.evaluate(() => {
    const box = document.getElementById('ai-answer');
    const grounding = document.getElementById('ai-answer-grounding');
    const vis = (el) => !!el && !el.classList.contains('hidden') && el.getBoundingClientRect().height > 0;
    return {
      citations: box ? box.querySelectorAll('.answer-citation').length : -1,
      quoteBars: box ? box.querySelectorAll('.composed-said, .said, blockquote').length : -1,
      groundedChips: vis(grounding) ? grounding.querySelectorAll('button, a, .chip').length : 0,
      supportCount: /\d+ of \d+ from your notes/.test(document.body.innerText),
      bracketDates: box ? (box.innerText.match(/\[your note[^\]]*\]/g) || []).length : -1,
      bold: box ? box.querySelectorAll('strong, b').length : -1,
      text: box ? box.innerText.slice(0, 600) : '',
    };
  });
  await page.screenshot({ path: path.join(OUT, `ask-${TAG}.png`) });
  console.log(JSON.stringify({ summary, ui, shots: [`${OUT}/gold-${TAG}.png`, `${OUT}/ask-${TAG}.png`] }, null, 1));
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
