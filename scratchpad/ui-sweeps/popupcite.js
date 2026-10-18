// Popup agent in-text citations (BACKLOG 2026-10-12). Drives a real popup
// agent turn against the stand-in model (scratchpad/fake_answer_server.py)
// and reads the marks, the Sources rows' numbers and the note links.
//   BASE=http://127.0.0.1:8784 FAKE=http://127.0.0.1:8794/v1 \
//     PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node popupcite.js
const { boot } = require('./lib.js');
const FAKE = process.env.FAKE || 'http://127.0.0.1:8794/v1';
const NOTES = [
  'The sourdough starter is fed with rye flour every morning at seven.',
  'My hiking boots need resoling before the Snowdon trip in October.',
  'The garage door opener responds to the blue remote but not the grey one.',
];
(async () => {
  const { page, browser } = await boot({});
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 140)));
  await page.waitForTimeout(3500);
  await page.evaluate(async ({ base, notes }) => {
    for (const content of notes) await apiJson('/entries', { method: 'POST', body: JSON.stringify({ content, category: 'General' }) });
    await api('/models/provider', { method: 'POST', body: JSON.stringify({ provider: 'openai', base_url: base }) });
    await api('/models/chat-model', { method: 'POST', body: JSON.stringify({ name: 'fake-answerer' }) }).catch(() => null);
  }, { base: FAKE, notes: NOTES });
  await page.evaluate(() => toggleAgentPalette());
  await page.waitForTimeout(800);
  await page.fill('#command-palette-input', 'What do my notes say about the starter and the boots?');
  await page.keyboard.press('Enter');
  await page.waitForFunction(() => {
    const a = document.querySelector('#command-palette-results .bubble-answer');
    return a && a.textContent.trim().length > 20 && !a.classList.contains('is-streaming') && !document.querySelector('#command-palette-results .is-generating');
  }, { timeout: 90000 }).catch(() => {});
  await page.waitForTimeout(2500);
  const read = await page.evaluate(() => {
    const box = document.querySelector('#command-palette-results .bubble-answer');
    const markers = [...box.querySelectorAll('.answer-citation')].map((m) => ({
      n: m.textContent.replace(/\D/g, ''), noteId: m.dataset.noteId || null,
      before: (m.previousSibling?.textContent || '').trim().slice(-50),
    }));
    const rows = [...document.querySelectorAll('#command-palette-results .chat-source-row')].map((r) => ({
      n: r.querySelector('.chat-source-index')?.textContent || null,
      id: r.dataset.noteId, text: r.textContent.replace(/\s+/g, ' ').trim().slice(0, 50),
      cols: getComputedStyle(r).gridTemplateColumns.split(' ').length,
    }));
    return { answer: box.textContent.replace(/\s+/g, ' ').slice(0, 240), markers, rows };
  });
  console.log(JSON.stringify(read, null, 1));
  console.log('pageerrors:', errors.length, errors.join(' | '));
  const sameNumbers = read.markers.every((m) => read.rows.find((r) => r.id === m.noteId && r.n === m.n));
  console.log(read.markers.length > 0 && sameNumbers ? 'PASS: marks present, numbers match the rows' : 'FAIL');
  await browser.close();
})();
