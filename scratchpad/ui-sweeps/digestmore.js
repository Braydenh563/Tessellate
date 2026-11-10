// Short by default, More expands (CHAT_PLAN B5): adds ten notes on one
// topic, asks the Ask box about it with no model, and measures the fold: how
// many lines show, the button's words, the lines it holds hidden, that a
// press shows them and moves focus, and that hovering a mark peeks at the
// note's own sentence. The notes it added are deleted after.
//
//   BASE=http://127.0.0.1:8872 DATA=<the server's data dir> SCRATCH=<dir> PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/digestmore.js
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const { boot } = require('./lib.js');

const PY = process.env.SWEEP_PY || require('path').resolve(__dirname, '..', '..', '.venv', 'bin', 'python');

//: A day apart in September, so the answer groups them by what they say
//: rather than folding one day's ten notes into a line (needs DATA).
function backdate(ids) {
  const db = path.join(process.env.DATA || '', 'memorymap.db');
  if (!process.env.DATA || !fs.existsSync(db)) return 'no DATA: notes keep today';
  const rows = ids.map((id, i) => [id, `2026-09-${String(i + 1).padStart(2, '0')} 10:00:00.000000`]);
  execFileSync(PY, ['-c', [
    'import json, sqlite3, sys',
    'con = sqlite3.connect(sys.argv[1])',
    'for i, d in json.loads(sys.argv[2]): con.execute("update entries set created_at = ?, updated_at = ? where id = ?", (d, d, i))',
    'con.commit()',
  ].join('\n'), db, JSON.stringify(rows)]);
  return `backdated ${rows.length}`;
}

const NOTES = [
  'Pottery class: centring the clay is the hard part.', 'Pottery: trimmed my first bowl today.',
  'Pottery glaze test came out blue-green, not the blue I wanted.', 'Pottery kiln firing is on Saturday at 10am.',
  'Bought a set of pottery tools for $45.', 'Pottery wheel speed: slower when pulling walls.',
  'Pottery teacher said wedge the clay longer before throwing.', 'Pottery: my mug handle cracked in the kiln.',
  'Signed up for the advanced pottery term in November.', 'Pottery studio is open Thursdays until 9pm.',
];

(async () => {
  const { browser, page } = await boot();
  const ids = await page.evaluate(async (notes) => {
    const out = [];
    for (const content of notes) out.push((await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content: `${content} #pottery` }) })).id);
    return out;
  }, NOTES);
  const dated = backdate(ids);
  await page.waitForTimeout(1500);
  await page.evaluate(() => { switchTab('notes'); if (window.showNotesSection) showNotesSection('ask'); });
  await page.waitForTimeout(600);
  await page.fill('#question', 'what have I saved about pottery?');
  await page.evaluate(() => askQuestion());
  await page.waitForSelector('#ai-answer .digest-more', { timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(600);
  const before = await page.evaluate(() => {
    const a = document.querySelector('#ai-answer');
    const ps = [...a.querySelectorAll(':scope > p')];
    return {
      shown: ps.filter((p) => !p.hidden).length,
      hidden: ps.filter((p) => p.hidden).length,
      button: a.querySelector('.digest-more')?.textContent.trim() || null,
      expanded: a.querySelector('.digest-more')?.getAttribute('aria-expanded'),
      marks: a.querySelectorAll('.answer-citation').length,
      height: Math.round(a.getBoundingClientRect().height),
      text: a.innerText.slice(0, 600),
    };
  });
  await page.locator('#ai-answer').screenshot({ path: `${process.env.SCRATCH}/shots/digest-more-before.png` });
  let after = null;
  if (before.button) {
    await page.click('#ai-answer .digest-more');
    await page.waitForTimeout(300);
    after = await page.evaluate(() => {
      const a = document.querySelector('#ai-answer');
      return {
        hidden: [...a.querySelectorAll(':scope > p')].filter((p) => p.hidden).length,
        button: !!a.querySelector('.digest-more'),
        focus: document.activeElement?.tagName + ':' + (document.activeElement?.textContent || '').slice(0, 40),
        height: Math.round(a.getBoundingClientRect().height),
      };
    });
    await page.locator('#ai-answer').screenshot({ path: `${process.env.SCRATCH}/shots/digest-more-after.png` });
  }
  const mark = page.locator('#ai-answer .answer-citation-link').first();
  await mark.hover();
  await page.waitForTimeout(900);
  const peek = await page.evaluate(() => {
    const p = document.querySelector('#citation-peek');
    return p && !p.hidden ? { text: p.innerText.slice(0, 300), mark: p.querySelector('mark')?.textContent || null } : null;
  });
  await page.screenshot({ path: `${process.env.SCRATCH}/shots/digest-peek.png` });
  await page.evaluate(async (ids) => { for (const id of ids) await api(`/entries/${id}`, { method: 'DELETE' }); }, ids);
  console.log(JSON.stringify({ added: ids.length, dated, before, after, peek }, null, 1));
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
