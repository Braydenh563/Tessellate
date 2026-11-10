// The chat's keys, against the fake answer model (the review of 2026-09-27):
//   hidden  an Escape in a new chat while the last chat's answer still streams
//   focus   where the focus is when an answer ends, from Stop and from elsewhere
//   peek    Enter, Tab, Escape and Space on a citation mark
//
//   BASE=http://127.0.0.1:8830 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node scratchpad/ui-sweeps/chatkeys.js        (ONLY=hidden,focus,peek)
const path = require('path');
const ROOT = path.resolve(__dirname, '..', '..');
const { boot } = require('./lib.js');
const { spawn } = require('child_process');
const http = require('http');
const PY = process.env.SWEEP_PY || require('path').resolve(__dirname, '..', '..', '.venv', 'bin', 'python');
const FAKE_PORT = Number(process.env.FAKE_PORT || 8931);
const FAKE = `http://127.0.0.1:${FAKE_PORT}/v1`;
const ONLY = new Set((process.env.ONLY || 'hidden,focus,peek').split(','));
const NOTES = [
  'Kyoto trip: book the ryokan in Arashiyama six months out; the trains can wait.',
  'Half marathon week 4: easy pace is still too fast, slow the Tuesday run until it is boring.',
  'Questions for Thursday: who owns the migration after launch, and the old export format.',
];
function waitForFake() {
  return new Promise((resolve) => {
    let tries = 0;
    const poke = () => {
      const req = http.get(`${FAKE}/models`, (res) => { res.resume(); resolve(true); });
      req.on('error', () => (++tries > 40 ? resolve(false) : setTimeout(poke, 250)));
    };
    poke();
  });
}
(async () => {
  const fake = spawn(PY, [ROOT + '/scratchpad/fake_answer_server.py', String(FAKE_PORT)],
    { cwd: ROOT, env: { ...process.env, FAKE_DELAY_MS: process.env.FAKE_DELAY_MS || '120' }, stdio: 'ignore' });
  const out = { fakeUp: await waitForFake() };
  const { page, browser } = await boot({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 160)));
  try {
    await page.evaluate(async ({ notes, base }) => {
      const have = await apiJson('/entries?limit=5').catch(() => []);
      if (!(have.items || have).length) {
        for (const content of notes) await api('/entries', { method: 'POST', body: JSON.stringify({ content }) });
      }
      await api('/models/provider', { method: 'POST', body: JSON.stringify({ provider: 'openai', base_url: base }) }).catch(() => null);
      await api('/models/chat-model', { method: 'POST', body: JSON.stringify({ name: 'fake-answerer' }) }).catch(() => null);
    }, { notes: NOTES, base: FAKE });
    await page.evaluate(() => switchTab('chat'));
    await page.waitForTimeout(1500);
    const send = async (text) => {
      await page.evaluate(() => newChatConversation());
      await page.waitForTimeout(400);
      await page.click('#chat-input');
      await page.keyboard.type(text);
      await page.keyboard.press('Enter');
      await page.waitForFunction(() => chatController, null, { timeout: 5000 }).catch(() => null);
    };
    const active = () => page.evaluate(() => { const a = document.activeElement; return a ? (a.id || a.className || a.tagName) : null; });

    if (ONLY.has('hidden')) {
      // A stream in chat A; the reader starts a new chat; Escape in the new box.
      await send('What do my notes say about the trip and the run?');
      await page.waitForTimeout(300);
      const r = { streamingBefore: await page.evaluate(() => Boolean(chatController)) };
      await page.evaluate(() => newChatConversation());
      await page.waitForTimeout(300);
      r.stopShown = await page.evaluate(() => !document.getElementById('chat-stop').classList.contains('hidden'));
      await page.click('#chat-input');
      await page.keyboard.press('Escape');
      await page.waitForTimeout(150);
      r.streamingAfterEscape = await page.evaluate(() => Boolean(chatController));
      await page.waitForFunction(() => !chatController, null, { timeout: 60000, polling: 100 }).catch(() => null);
      out.hidden = r;
    }

    if (ONLY.has('focus')) {
      await send('What do my notes say about Thursday?');
      await page.waitForTimeout(200);
      const r = { whileStreaming: await active() };
      await page.focus('#chat-new').catch(async () => { r.noSidebarSearch = true; });
      r.movedTo = await active();
      await page.waitForFunction(() => !chatController, null, { timeout: 60000, polling: 100 }).catch(() => null);
      await page.waitForTimeout(300);
      r.afterEnd = await active();
      // And from Stop: the box takes it back.
      await send('What do my notes say about the run?');
      await page.waitForTimeout(200);
      r.whileStreaming2 = await active();
      await page.waitForFunction(() => !chatController, null, { timeout: 60000, polling: 100 }).catch(() => null);
      await page.waitForTimeout(300);
      r.afterEnd2 = await active();
      out.focus = r;
    }

    if (ONLY.has('peek')) {
      await send('What do my notes say about the trip, the run and Thursday?');
      await page.waitForFunction(() => !chatController, null, { timeout: 60000, polling: 100 }).catch(() => null);
      await page.waitForTimeout(800);
      const r = { marks: await page.evaluate(() => document.querySelectorAll('#chat-messages .answer-citation-link').length) };
      if (r.marks) {
        await page.evaluate(() => document.querySelector('#chat-messages .answer-citation-link').focus());
        await page.waitForTimeout(100);
        r.openOnFocus = await page.evaluate(() => Boolean(document.getElementById('citation-peek')));
        await page.keyboard.press('Enter');
        await page.waitForTimeout(100);
        r.afterEnter = await active();
        await page.keyboard.press('Tab');
        await page.waitForTimeout(100);
        r.afterTab = await page.evaluate(() => { const a = document.activeElement; return { inPeek: Boolean(a?.closest('#citation-peek')), text: a?.textContent.trim().slice(0, 30) }; });
        await page.keyboard.press('Escape');
        await page.waitForTimeout(400);
        r.afterEscape = { focus: await active(), peekOpen: await page.evaluate(() => Boolean(document.getElementById('citation-peek'))) };
        r.streamStillNull = await page.evaluate(() => chatController === null);
        // Space on the mark, and Escape from the preview.
        await page.keyboard.press('Space');
        await page.waitForTimeout(100);
        r.afterSpace = await active();
        await page.keyboard.press('Escape');
        await page.waitForTimeout(400);
        r.afterEscape2 = { focus: await active(), peekOpen: await page.evaluate(() => Boolean(document.getElementById('citation-peek'))) };
        // Mouse click must not steal the focus into the peek.
        const box = await page.evaluate(() => { const r = document.querySelector('#chat-messages .answer-citation-link').getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; });
        await page.mouse.click(box.x, box.y);
        await page.waitForTimeout(200);
        r.afterMouse = { focus: await active(), peekOpen: await page.evaluate(() => Boolean(document.getElementById('citation-peek'))) };
      }
      out.peek = r;
    }
  } finally {
    out.errors = errors;
    console.log(JSON.stringify(out, null, 1));
    await browser.close();
    fake.kill();
  }
})();
