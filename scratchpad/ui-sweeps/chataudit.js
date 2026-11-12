// The Chat tab, measured (the 2026-09-26 overnight chat pass: CHAT_PLAN and
// WORLD_CLASS_PLAN D3). Numbers, not screenshots, for each of:
//
//   long     a saved conversation of LONG turns (default 150): how long it
//            takes to open, how many elements it leaves in the transcript,
//            and how the frames hold while it is scrolled end to end
//   stream   one answer streamed by the fake model: time to the first words,
//            frames over 50ms while it streams, whether the view stays at
//            the newest line, and how often the answer box is re-rendered
//   keys     Enter sends, Shift+Enter is a newline, Escape stops a stream,
//            focus is back in the box when the answer is done
//   actions  what each kind of message offers
//   empty    the empty state at this width
//
// The model is `scratchpad/fake_answer_server.py`, started here (as
// asktab.js does), answering in markdown with a delay between words.
//
//   BASE=http://127.0.0.1:8812 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node scratchpad/ui-sweeps/chataudit.js
// ONLY=long,stream to run some parts; LONG=300 for a longer thread; W=390.
const { boot } = require('./lib.js');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');

const ROOT = path.resolve(__dirname, '..', '..');
const PY = process.env.SWEEP_PY || require('path').resolve(__dirname, '..', '..', '.venv', 'bin', 'python');
const FAKE_PORT = Number(process.env.FAKE_PORT || 8913);
const FAKE = `http://127.0.0.1:${FAKE_PORT}/v1`;
const FAKE_DELAY_MS = Number(process.env.FAKE_DELAY_MS || 30);
const LONG = Number(process.env.LONG || 150);
const W = Number(process.env.W || 1440);
const ONLY = new Set((process.env.ONLY || 'long,stream,keys,actions,empty').split(','));
const SHOTS = process.env.SHOTS || '';

const NOTES = [
  'Kyoto trip: book the ryokan in Arashiyama six months out; the trains can wait.',
  'Sourdough, third attempt: a 20 hour cold proof gave a better crumb, the base is still pale.',
  'Half marathon week 4: easy pace is still too fast, slow the Tuesday run until it is boring.',
  'Retro: measuring before changing helped; reading the source instead of running it did not.',
  'Graph felt slow because the simulation kept ticking after leaving the tab.',
  'Questions for Thursday: who owns the migration after launch, and the old export format.',
];

function answerMarkdown(i) {
  return [
    `Here is what your notes say about item ${i}:`,
    '',
    `- **Planning**: book early, the popular places fill ${i % 7 + 2} months ahead.`,
    `- **Practice**: keep the easy runs easy, and measure before changing anything.`,
    `- **Follow-up**: ask who owns the migration, and write the answer down.`,
    '',
    '```js',
    `const turn = ${i};`,
    'console.log(turn * 2);',
    '```',
    '',
    `That is the short version; the notes have more detail on each point, turn ${i}.`,
  ].join('\n');
}

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
  const fake = spawn(PY, [path.join(ROOT, 'scratchpad', 'fake_answer_server.py'), String(FAKE_PORT)],
    { cwd: ROOT, env: { ...process.env, FAKE_DELAY_MS: String(FAKE_DELAY_MS), FAKE_STYLE: 'markdown' }, stdio: 'ignore' });
  const fakeUp = await waitForFake();
  const { page, browser } = await boot({ viewport: { width: W, height: W < 600 ? 844 : 900 }, ...(W < 600 ? { hasTouch: true, isMobile: true } : {}) });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 160)));
  const out = { width: W, fakeUp };

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

  if (ONLY.has('empty')) {
    await page.evaluate(() => newChatConversation());
    await page.waitForTimeout(800);
    out.empty = await page.evaluate(() => {
      const empty = document.querySelector('#chat-messages .chat-empty');
      const box = (el) => { if (!el) return null; const r = el.getBoundingClientRect(); return { x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height) }; };
      const messages = document.getElementById('chat-messages');
      return {
        present: Boolean(empty),
        box: box(empty),
        pane: box(messages),
        paneScrolls: messages.scrollHeight > messages.clientHeight + 2,
        starters: empty ? empty.querySelectorAll('button').length : 0,
        headings: empty ? [...empty.querySelectorAll('h2, h3, strong, .chat-empty-title')].map((h) => h.textContent.trim()).slice(0, 3) : [],
        text: empty ? empty.innerText.replace(/\s+/g, ' ').slice(0, 240) : '',
      };
    });
    if (SHOTS) await page.screenshot({ path: `${SHOTS}/empty-${W}.png` });
  }

  if (ONLY.has('stream') || ONLY.has('keys') || ONLY.has('actions')) {
    await page.evaluate(() => newChatConversation());
    await page.waitForTimeout(500);
    await page.click('#chat-input');
    await page.keyboard.type('What do my notes say about planning a trip and running?');
    //: Frames, renders and the pinned-to-bottom state, sampled from the first
    //: key press to the end of the stream.
    await page.evaluate(() => {
      window.__audit = { frames: [], long: [], pinnedFrames: 0, frameCount: 0, firstWords: null, renders: 0, start: performance.now() };
      const a = window.__audit;
      try {
        new PerformanceObserver((list) => { for (const e of list.getEntries()) a.long.push(Math.round(e.duration)); }).observe({ entryTypes: ['longtask'] });
      } catch (e) {}
      const real = window.renderMarkdown;
      window.renderMarkdown = function (...args) { a.renders += 1; return real.apply(this, args); };
      let last = performance.now();
      const tick = (now) => {
        a.frames.push(now - last);
        last = now;
        const pane = document.getElementById('chat-messages');
        const bubbles = pane.querySelectorAll('.msg.assistant');
        const lastBubble = bubbles[bubbles.length - 1];
        const text = lastBubble ? (lastBubble.querySelector('.chat-answer, .md, .answer, .timeline-answer') || lastBubble).innerText : '';
        if (a.firstWords === null && /notes say|Here is/i.test(text)) a.firstWords = Math.round(now - a.start);
        if (chatController) {
          a.frameCount += 1;
          const gap = pane.scrollHeight - pane.scrollTop - pane.clientHeight;
          if (gap < 8) a.pinnedFrames += 1;
        }
        if (!a.done) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });
    await page.keyboard.press('Enter');
    const started = Date.now();
    await page.waitForFunction(() => chatController, null, { timeout: 5000 }).catch(() => null);
    await page.waitForFunction(() => !chatController, null, { timeout: 60000, polling: 100 }).catch(() => null);
    await page.waitForTimeout(600);
    out.stream = await page.evaluate(() => {
      const a = window.__audit;
      a.done = true;
      const f = a.frames.slice(2);
      const sorted = [...f].sort((x, y) => x - y);
      return {
        firstWordsMs: a.firstWords,
        frames: f.length,
        over50: f.filter((x) => x > 50).length,
        worstFrame: Math.round(sorted[sorted.length - 1] || 0),
        p95: Math.round(sorted[Math.floor(sorted.length * 0.95)] || 0),
        longTasks: a.long.length,
        longestTask: Math.max(0, ...a.long),
        streamingFrames: a.frameCount,
        pinnedShare: a.frameCount ? Math.round((100 * a.pinnedFrames) / a.frameCount) : null,
        markdownRenders: a.renders,
        focusAfter: document.activeElement && (document.activeElement.id || document.activeElement.tagName),
      };
    });
    out.stream.wallMs = Date.now() - started;
    if (SHOTS) await page.screenshot({ path: `${SHOTS}/streamed-${W}.png` });
  }

  if (ONLY.has('keys')) {
    const keys = {};
    await page.click('#chat-input');
    await page.keyboard.type('line one');
    await page.keyboard.press('Shift+Enter');
    await page.keyboard.type('line two');
    keys.shiftEnterNewline = await page.evaluate(() => document.getElementById('chat-input').value.includes('\n'));
    await page.evaluate(() => { const i = document.getElementById('chat-input'); i.value = ''; i.dispatchEvent(new Event('input', { bubbles: true })); });
    await page.keyboard.type('Tell me more about the running notes please.');
    await page.keyboard.press('Enter');
    await page.waitForFunction(() => chatController, null, { timeout: 5000 }).catch(() => null);
    //: Pressed early, while the answer is surely still being written: the
    //: first run pressed it at 700ms and the answer ended on its own at
    //: 1,246ms, which read as Escape working when it did nothing.
    await page.waitForTimeout(250);
    keys.streamingWhenPressed = await page.evaluate(() => Boolean(chatController));
    keys.focusWhileStreaming = await page.evaluate(() => document.activeElement && (document.activeElement.id || document.activeElement.tagName));
    const t0 = Date.now();
    await page.keyboard.press('Escape');
    keys.escapeStops = await page.waitForFunction(() => !chatController, null, { timeout: 400, polling: 20 }).then(() => Date.now() - t0).catch(() => false);
    if (keys.escapeStops === false) {
      await page.keyboard.press('Control+.');
      keys.ctrlDotStops = await page.waitForFunction(() => !chatController, null, { timeout: 1500, polling: 50 }).then(() => true).catch(() => false);
      await page.waitForFunction(() => !chatController, null, { timeout: 60000, polling: 100 }).catch(() => null);
    }
    await page.waitForTimeout(500);
    keys.focusAfterStop = await page.evaluate(() => document.activeElement && (document.activeElement.id || document.activeElement.tagName));
    await page.click('#chat-input');
    await page.keyboard.press('ArrowUp');
    keys.arrowUpRecalls = await page.evaluate(() => document.getElementById('chat-input').value.slice(0, 40));
    await page.evaluate(() => { const i = document.getElementById('chat-input'); i.value = ''; i.dispatchEvent(new Event('input', { bubbles: true })); });
    out.keys = keys;
  }

  if (ONLY.has('actions')) {
    out.actions = await page.evaluate(() => {
      const pane = document.getElementById('chat-messages');
      const name = (b) => (b.getAttribute('aria-label') || b.title || b.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 30);
      const of = (sel) => { const list = pane.querySelectorAll(sel); const el = list[list.length - 1]; return el ? [...el.querySelectorAll('button, [role="menuitem"]')].map(name) : null; };
      //: A label that carries markdown syntax or the retrieval prefix is a
      //: sentence that reached a button unrendered.
      const raw = [...pane.querySelectorAll('.msg.assistant button')]
        .filter((b) => /\*\*|\[Uncategorised\]|\(similarity/.test(name(b)))
        .map((b) => `${b.className} in ${b.parentElement.className}: ${name(b)}`);
      return { user: of('.msg.user'), assistant: of('.msg.assistant'), rawLabels: raw };
    });
  }

  if (ONLY.has('long')) {
    const id = await page.evaluate(async ({ n, answers }) => {
      const first = await apiJson('/conversations', { method: 'POST', body: JSON.stringify({ question: 'Long thread, question 0', answer: answers[0] }) });
      for (let i = 1; i < n; i += 1) {
        await api(`/conversations/${first.id}/turns`, { method: 'POST', body: JSON.stringify({ question: `Question ${i}: what about item ${i}?`, answer: answers[i % answers.length] }) });
      }
      return first.id;
    }, { n: LONG, answers: Array.from({ length: 12 }, (_, i) => answerMarkdown(i)) });
    await page.evaluate(() => newChatConversation());
    await page.waitForTimeout(500);
    out.long = await page.evaluate(async (convId) => {
      const t0 = performance.now();
      await openConversation(convId);
      const opened = performance.now() - t0;
      await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
      const painted = performance.now() - t0;
      const pane = document.getElementById('chat-messages');
      const nodes = pane.querySelectorAll('*').length;
      //: Scrolled end to end in 40 steps, a frame apart, timing each frame.
      const frames = [];
      let last = performance.now();
      pane.scrollTop = 0;
      await new Promise((r) => requestAnimationFrame(r));
      for (let i = 0; i <= 40; i += 1) {
        pane.scrollTop = (pane.scrollHeight - pane.clientHeight) * (i / 40);
        await new Promise((r) => requestAnimationFrame(r));
        const now = performance.now();
        frames.push(now - last);
        last = now;
      }
      const sorted = [...frames].sort((x, y) => x - y);
      //: A person's scroll, not a jump: 120px a frame, up from the end, for
      //: 60 frames, the stretch they read back through. Timed separately
      //: from the jumps above, which draw a never-seen screen every frame.
      const wheel = [];
      pane.scrollTop = pane.scrollHeight;
      await new Promise((r) => requestAnimationFrame(r));
      last = performance.now();
      for (let i = 0; i < 60; i += 1) {
        pane.scrollTop -= 120;
        await new Promise((r) => requestAnimationFrame(r));
        const now = performance.now();
        wheel.push(now - last);
        last = now;
      }
      const wsorted = [...wheel].sort((x, y) => x - y);
      return {
        wheelOver50: wheel.filter((x) => x > 50).length,
        wheelWorst: Math.round(wsorted[wsorted.length - 1]),
        wheelP95: Math.round(wsorted[Math.floor(wsorted.length * 0.95)]),
        turns: document.querySelectorAll('#chat-messages .msg.user').length,
        openMs: Math.round(opened),
        paintedMs: Math.round(painted),
        nodes,
        scrollFrames: frames.length,
        scrollOver50: frames.filter((x) => x > 50).length,
        scrollWorst: Math.round(sorted[sorted.length - 1]),
        scrollP95: Math.round(sorted[Math.floor(sorted.length * 0.95)]),
        atEndAfterOpen: null,
      };
    }, id);
    out.long.id = id;
  }

  out.errors = errors;
  console.log(JSON.stringify(out, null, 1));
  await browser.close();
  fake.kill();
})();
