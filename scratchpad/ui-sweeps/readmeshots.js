// The README's screenshots, every one, from one notebook in one theme.
//
// INBOX 431 (g), the owner: "remake and retake the screenshots for the readme
// file ... take the screenshots in dark mode but maybe have a dark/light
// comparison image ... make sure all main features are properly shown."
//
// Against the notebook `seed-showcase.py` writes on a fresh data dir:
//
//   bash scratchpad/ui-sweeps/serve.sh 8861 /tmp/mm-a861
//   .venv/bin/python scratchpad/ui-sweeps/seed-showcase.py 8861 /tmp/mm-a861
//   BASE=http://127.0.0.1:8861 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node scratchpad/ui-sweeps/readmeshots.js
//
// Dark at 1440x900, one device pixel a CSS pixel: the README shows them at
// 850px, and two device pixels doubled every file past the 400 KB a README
// image should stay under. ONLY=graph,map retakes some; SKIP=phone leaves
// some. Three files are not a tab: `theme-split.png` (one view, both
// themes, joined down the middle), `atlas.png` (Atlas with a mood, from the
// app's own renderer) and `phone.png` (390 wide, its own context).
//
// Ask and Chat need a model. A stand-in answers them
// (`scratchpad/fake_answer_server.py`, the same one readme-ask.js used): it
// replies with a written answer, and the app grounds that answer against the
// notes it retrieved like any other, so the citation marks on screen are the
// app's own. It runs only for those two shots, so nothing else on screen
// (the dashboard's greeting, a digest) is ever written by it.
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');
const http = require('http');

const PW = 'testpassword123';
const BASE = process.env.BASE || 'http://127.0.0.1:8861';
const OUT = process.env.OUT || 'docs/screenshots';
const ROOT = path.resolve(__dirname, '..', '..');
const PY = process.env.SWEEP_PY || require('path').resolve(__dirname, '..', '..', '.venv', 'bin', 'python');
const FAKE_PORT = Number(process.env.FAKE_PORT || 8872);
const MODEL = 'local-model';
const only = new Set((process.env.ONLY || '').split(',').filter(Boolean));
const skip = new Set((process.env.SKIP || '').split(',').filter(Boolean));
const wanted = (file) => (!only.size || only.has(file)) && !skip.has(file);

const SHOTS = [
  { file: 'dashboard', tab: 'dashboard' },
  { file: 'notes', tab: 'notes', sub: 'notes' },
  { file: 'graph', tab: 'graph', sub: 'graph' },
  { file: 'library', tab: 'library' },
  { file: 'activity', tab: 'library', sub: 'activity' },
  { file: 'timeline', tab: 'timeline', sub: 'timeline' },
  { file: 'reminders', tab: 'reminders' },
  { file: 'documents', tab: 'library', sub: 'documents' },
  { file: 'focus', tab: 'library', sub: 'focus' },
  { file: 'whiteboard', tab: 'library', sub: 'board', board: 'Harbor launch board' },
  { file: 'map', tab: 'library', sub: 'board', board: 'Portugal trip' },
  { file: 'palette', tab: 'notes', sub: 'palette' },
  { file: 'features', tab: 'dashboard', sub: 'features' },
  { file: 'settings', tab: 'dashboard', sub: 'appearance' },
  { file: 'your-look', tab: 'dashboard', sub: 'your-look' },
];

//: Written in the notes' own words, because the citations have to be earned:
//: grounding scores each sentence against the notes the app retrieved.
const ASK = {
  question: 'What do I still need to book for Portugal?',
  answer: [
    'Most of the trip is booked: the flights are done (out to Lisbon, back from Porto) and so is the night at a quinta near Pinhão.',
    '',
    'Two things are still open:',
    '',
    '- **The Alfa Pendular tickets.** Lisbon to Porto takes 2h50, and tickets open 60 days ahead at half price if booked early.',
    '- **The hire car in Porto.** It is only for the Douro valley, for the river road from Régua to Pinhão.',
    '',
    'For Sintra no booking is needed beyond a timed ticket for Pena Palace.',
  ].join('\n'),
  followups: ['When do the train tickets open?', 'What is the budget for the trip?'],
};
const CHAT = {
  question: 'What is left before the Harbor launch?',
  answer: [
    'Three things stand between you and the launch on the 14th:',
    '',
    '1. **The store listing copy.** The first line has to say what it does in under ten words: notes that sort themselves, offline.',
    '2. **The launch email.** The draft is one paragraph, one screenshot and one button, sent at 9 in each time zone.',
    '3. **The pricing page.** It still needs sign-off, and it is one of the three launch risks.',
    '',
    'Beta feedback is nearly closed: 41 testers are active, and the top complaint (the nine-field sign-up) is answered by the onboarding rewrite.',
  ].join('\n'),
  followups: ['What are the launch risks?', 'Draft the store listing first line'],
};

function waitForFake() {
  return new Promise((resolve) => {
    let tries = 0;
    const poke = () => {
      const req = http.get(`http://127.0.0.1:${FAKE_PORT}/v1/models`, (res) => { res.resume(); resolve(true); });
      req.on('error', () => (++tries > 40 ? resolve(false) : setTimeout(poke, 250)));
    };
    poke();
  });
}

async function signIn(page) {
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#lock-password', { state: 'visible', timeout: 20000 });
  await page.fill('#lock-password', PW);
  await page.click('#lock-submit');
  await page.waitForTimeout(3500);
  await page.evaluate(() => document.getElementById('onboarding-overlay')?.classList.add('hidden'));
  //: The first-start "Check for updates automatically?" question (ask once,
  //: update-dialogs.js) answered the way a person answers it, "Don't check",
  //: which saves the answer so it never comes back on this data dir. Left
  //: open it sat over the dashboard shot.
  const dont = page.getByRole('button', { name: "Don't check" });
  if (await dont.isVisible().catch(() => false)) {
    await dont.click();
    await page.waitForTimeout(800);
  }
}

//: What is on screen at capture, counted: a toast, a skeleton placeholder, or
//: an open confirm/modal dialog the shot is not of. Printed per file, and a
//: non-zero count is a retake, not a caption.
const audit = (page) => page.evaluate(() => {
  const shown = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden'; };
  return {
    toasts: document.querySelectorAll('#toast-box > *').length,
    skeletons: [...document.querySelectorAll('.skeleton, [class*="skeleton"]')].filter(shown).length,
    dialogs: [...document.querySelectorAll('dialog[open], .confirm-overlay, #confirm-dialog')].filter(shown).length,
  };
});

//: **What is hidden, and why.** `#ai-status` reads "Search AI didn't load"
//: here because this sandbox never installs `sentence-transformers`
//: (CLAUDE.md section 7): an artefact of the machine, not a state a person
//: who installed the app sees. The agent monitor and a toast are closed the
//: way a person closes them. Nothing else is altered. `el.style`, because the
//: CSP refuses an injected stylesheet.
const tidy = (page) => page.evaluate(() => {
  for (const el of document.querySelectorAll('.ai-status-wrap')) el.style.visibility = 'hidden';
  document.getElementById('agent-monitor')?.classList.add('hidden');
  document.getElementById('toast-box')?.replaceChildren();
});

async function context(browser, opts = {}) {
  //: TZ_ID (default Asia/Singapore): the clock and every date on screen are
  //: the browser's local time, and this sandbox's is UTC, which put the
  //: dashboard's greeting at 5 in the morning. A person in another time
  //: zone, not a faked clock.
  const ctx = await browser.newContext({
    viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1,
    timezoneId: process.env.TZ_ID || 'Asia/Singapore', ...opts,
  });
  await ctx.addInitScript((graph) => {
    try {
      localStorage.setItem('onboardingDone', '1');
      localStorage.setItem('tourDone', '1');
      localStorage.setItem('nm-buddy-hint', 'done');
      //: The graph's own View settings, as a person sets them. Group by
      //: category off: on, each category is pulled into a tight knot of its
      //: own and the links between subjects (the webs the owner asked to
      //: see) are stretched across empty space; off, the layout follows the
      //: links, so the dense clusters, the sparse web and the loose notes
      //: each take the shape their links give them.
      localStorage.setItem('graph-spread', graph.spread);
      localStorage.setItem('graph-gravity', graph.gravity);
      localStorage.setItem('graph-group', graph.group);
    } catch (e) {}
  }, { spread: process.env.GRAPH_SPREAD || '50', gravity: process.env.GRAPH_GRAVITY || '50', group: process.env.GRAPH_GROUP || '0' });
  return ctx;
}

async function openBoard(page, name) {
  //: The way a person opens one: Boards & maps, then the card.
  await page.click('[data-target="library-view-whiteboard"]').catch(() => {});
  await page.waitForTimeout(1200);
  await page.locator('.library-board-card', { hasText: name }).first().click({ timeout: 8000 }).catch(() => {});
  await page.waitForTimeout(3500);
}

async function setBuddy(page, value) {
  await page.evaluate((v) => {
    openSettingsModal('appearance');
    const select = document.getElementById('avatar-buddy');
    select.value = v;
    select.dispatchEvent(new Event('change', { bubbles: true }));
    if (v !== 'off') {
      const size = document.getElementById('avatar-buddy-size');
      size.value = '1.3';
      size.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }, value);
  await page.waitForTimeout(800);
}

async function stage(page, shot) {
  await page.click(`[data-tab="${shot.tab}"]`).catch(() => {});
  await page.waitForTimeout(2500);
  switch (shot.sub) {
    case 'timeline':
      //: Today, the dock's own button: the feed opens on the furthest-out
      //: date, which in a notebook with reminders is a week from now.
      await page.click('#timeline-jump-today').catch(() => {});
      await page.waitForTimeout(1500);
      //: The month calendar, the view's own toggle (it sits in Options):
      //: one week of the feed read as a bare list (owner, 2026-10-12).
      await page.evaluate(() => document.getElementById('timeline-view-calendar')?.click());
      await page.waitForTimeout(1500);
      break;
    case 'notes':
      await page.evaluate(() => window.showNotesSection && showNotesSection('browse'));
      await page.waitForTimeout(1500);
      break;
    case 'graph':
      //: Labels on, the graph's own View setting: with them the clusters
      //: say what they are (Harbor, Portugal, sourdough) at a glance.
      await page.evaluate(() => {
        const box = document.getElementById('graph-labels');
        if (box && !box.checked) { box.checked = true; box.dispatchEvent(new Event('change', { bubbles: true })); }
      });
      //: The layout settles over a few seconds; the shot is of it at rest.
      await page.waitForTimeout(7000);
      break;
    case 'activity':
      await page.click('[data-target="library-view-documents"]').catch(() => {});
      await page.waitForTimeout(1200);
      await page.click('.library-chip[data-kind="activity"]').catch(() => {});
      await page.waitForTimeout(2000);
      break;
    case 'documents':
    case 'focus': {
      //: The app's own route in (`openDocument`), on the long brief.
      //: The tab first, settled: opening Documents reopens the last document
      //: by itself, and when that landed after `openDocument` the shot was of
      //: the recipe rather than the brief.
      await page.evaluate(() => switchTab('documents'));
      await page.waitForTimeout(2500);
      await page.evaluate(async () => {
        const list = await (await api('/documents')).json();
        const doc = list.find((d) => /launch brief/i.test(d.title || '')) || list[0];
        await openDocument(doc.id);
      });
      await page.waitForSelector('#doc-editor .cm-content', { state: 'visible', timeout: 15000 }).catch(() => {});
      await page.waitForTimeout(2000);
      const title = await page.evaluate(() => document.getElementById('doc-title')?.value || '');
      if (!/launch brief/i.test(title)) console.log('NOTE: documents shot opened', JSON.stringify(title));
      if (shot.sub === 'focus') {
        await page.evaluate(() => toggleDocFocus(true));
        await page.waitForTimeout(800);
        await page.evaluate(() => document.getElementById('doc-focus-prose')?.click());
        await page.waitForTimeout(2500);
      }
      break;
    }
    case 'board':
      await openBoard(page, shot.board);
      if (shot.file === 'map') {
        //: Tidy (the map's own command) lays the tree out both ways from
        //: the root, as `layout: tree-both` asks; a seeded map has the
        //: server's first-guess positions until something arranges it.
        await page.evaluate(async () => { if (window.wbMapTidy) await wbMapTidy({ quiet: true }); });
        await page.waitForTimeout(1500);
      }
      //: Fit to screen, the board's View action, as on any first look.
      await page.evaluate(() => wbZoomToFit({ animate: false }));
      await page.waitForTimeout(1500);
      break;
    case 'palette':
      await page.evaluate(() => openPalette());
      await page.waitForTimeout(700);
      //: Typed: the palette is commands and places (INBOX 666), so a word
      //: that reaches several commands, and the hand-off to Find anything.
      await page.fill('#palette-input', 'new').catch(() => {});
      await page.waitForTimeout(1500);
      break;
    case 'features':
      await page.evaluate(() => openFeatures());
      await page.waitForTimeout(2500);
      break;
    case 'appearance':
      await page.evaluate(() => openSettingsModal('appearance'));
      await page.waitForTimeout(2500);
      break;
    case 'your-look':
      await page.evaluate(() => openSettingsModal('preferences'));
      await page.waitForTimeout(1000);
      await page.evaluate(() => {
        const fold = document.querySelector('#profile-look details');
        if (fold) fold.open = true;
        const name = document.getElementById('pref-display-name');
        name.value = 'Maya';
        name.dispatchEvent(new Event('input', { bubbles: true }));
        name.dispatchEvent(new Event('change', { bubbles: true }));
      });
      await page.waitForTimeout(1200);
      break;
    default:
      break;
  }
}

async function unstage(page, shot) {
  await page.keyboard.press('Escape').catch(() => {});
  await page.waitForTimeout(500);
  if (shot.sub === 'focus') await page.evaluate(() => toggleDocFocus(false));
}

async function shoot(page, file, done, { keepFocus = false, clip } = {}) {
  await tidy(page);
  //: Nothing hovered, nothing focused: a focus ring in a picture reads as a
  //: fault. A typed-into box (the palette, the agent) keeps its focus,
  //: since blurring it closes the overlay the shot is of.
  await page.mouse.move(1439, 899);
  if (!keepFocus) await page.evaluate(() => document.activeElement && document.activeElement.blur());
  await page.waitForTimeout(600);
  const p = `${OUT}/${file}.png`;
  const seen = await audit(page);
  await page.screenshot({ path: p, ...(clip ? { clip } : {}) });
  done.push({ file, bytes: fs.statSync(p).size, ...seen });
}

(async () => {
  const browser = await chromium.launch();
  const done = [];
  const ctx = await context(browser);
  const page = await ctx.newPage();
  page.on('pageerror', (e) => console.log('PAGEERROR', e.message));
  await signIn(page);
  //: The theme through the app, the call the Appearance panel's own button
  //: makes: the stored server-side preference wins over localStorage.
  await page.evaluate(() => applyThemeChoice('dark', true));
  await page.waitForTimeout(900);
  await tidy(page);

  for (const shot of SHOTS.filter((s) => wanted(s.file))) {
    await stage(page, shot);
    await shoot(page, shot.file, done, { keepFocus: shot.sub === 'palette' || shot.sub === 'agent' });
    await unstage(page, shot);
  }

  //: Light and dark of the same view, cut down the middle and joined: the
  //: left half from the light theme, the right from the dark, in a canvas on
  //: a blank page. Same data, same scroll, only the theme between them.
  if (wanted('theme-split')) {
    await page.click('[data-tab="dashboard"]');
    await page.waitForTimeout(3000);
    await tidy(page);
    await page.mouse.move(1439, 899);
    const dark = await page.screenshot({ type: 'png' });
    await page.evaluate(() => applyThemeChoice('light', true));
    await page.waitForTimeout(2500);
    await tidy(page);
    const light = await page.screenshot({ type: 'png' });
    await page.evaluate(() => applyThemeChoice('dark', true));
    await page.waitForTimeout(900);
    const join = await (await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 })).newPage();
    await join.setContent('<body style="margin:0;background:#000"><canvas id="c" width="1440" height="900"></canvas></body>');
    await join.evaluate(async ({ a, b }) => {
      const load = (src) => new Promise((ok) => { const img = new Image(); img.onload = () => ok(img); img.src = src; });
      const [left, right] = await Promise.all([load(a), load(b)]);
      const c = document.getElementById('c').getContext('2d');
      c.drawImage(left, 0, 0, 720, 900, 0, 0, 720, 900);
      c.drawImage(right, 720, 0, 720, 900, 720, 0, 720, 900);
      //: A hairline where they meet, so the seam reads as intended.
      c.fillStyle = 'rgba(127,127,127,0.85)';
      c.fillRect(719, 0, 2, 900);
    }, { a: 'data:image/png;base64,' + light.toString('base64'), b: 'data:image/png;base64,' + dark.toString('base64') });
    const p = `${OUT}/theme-split.png`;
    await join.screenshot({ path: p });
    done.push({ file: 'theme-split', bytes: fs.statSync(p).size });
    await join.context().close();
  }

  //: Ask and Chat, against the stand-in model.
  if (['ask', 'agent', 'chat', 'companion'].some(wanted)) {
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'readme-shots-'));
    const answerFile = path.join(tmp, 'answer.md');
    const followFile = path.join(tmp, 'followups.txt');
    const write = (x) => { fs.writeFileSync(answerFile, x.answer); fs.writeFileSync(followFile, x.followups.join('\n')); };
    write(ASK);
    const fake = spawn(PY, [path.join(ROOT, 'scratchpad', 'fake_answer_server.py'), String(FAKE_PORT)], {
      cwd: ROOT,
      env: { ...process.env, FAKE_ANSWER_FILE: answerFile, FAKE_FOLLOWUPS_FILE: followFile, FAKE_DELAY_MS: '10', FAKE_MODEL: MODEL },
      stdio: 'ignore',
    });
    try {
      console.log('fake up', await waitForFake());
      await page.evaluate(async ({ base, model }) => {
        await api('/models/provider', { method: 'POST', body: JSON.stringify({ provider: 'openai', base_url: base }) });
        await api('/models/chat-model', { method: 'POST', body: JSON.stringify({ name: model }) }).catch(() => null);
        refreshModelStatus();
      }, { base: `http://127.0.0.1:${FAKE_PORT}/v1`, model: MODEL });
      await page.waitForTimeout(1500);
      if (wanted('ask')) {
        await page.evaluate(() => switchTab('notes'));
        await page.evaluate(() => showNotesSection('ask'));
        await page.waitForTimeout(900);
        await page.fill('#question', ASK.question);
        await page.click('#ask-btn');
        await page.waitForFunction(() => !document.getElementById('ai-answer').classList.contains('is-generating'), null, { timeout: 60000 }).catch(() => null);
        await page.waitForTimeout(3500);
        await page.fill('#question', ASK.question);
        await shoot(page, 'ask', done);
      }
      //: The popup agent as it opens over Notes, with a model connected:
      //: without one it opens on "No model is connected".
      if (wanted('agent')) {
        await page.evaluate(() => { switchTab('notes'); showNotesSection('browse'); });
        await page.waitForTimeout(1500);
        await page.evaluate(() => toggleAgentPalette());
        await page.waitForTimeout(1500);
        await shoot(page, 'agent', done, { keepFocus: true });
        await page.keyboard.press('Escape');
        await page.waitForTimeout(600);
      }
      if (wanted('chat')) {
        write(CHAT);
        await page.evaluate(() => switchTab('chat'));
        await page.waitForTimeout(1500);
        //: Chat's own New button: a fresh conversation, not a turn on
        //: whichever chat was open last.
        await page.click('#chat-new').catch(() => {});
        await page.waitForTimeout(800);
        await page.fill('#chat-input', CHAT.question);
        await page.keyboard.press('Enter');
        await page.waitForTimeout(9000);
        await shoot(page, 'chat', done);
      }
      //: The corner companion, on Chat with a model connected (without one
      //: the composer carries a "No model is connected" bar). Chat is the
      //: page with the most open room, so the companion's own spot is beside
      //: the writing rather than on a list: on Notes it settled over the
      //: Categories heading.
      if (wanted('companion')) {
        if (!wanted('chat')) {
          await page.evaluate(async () => {
            switchTab('chat');
            const list = await (await api('/conversations')).json();
            const rows = Array.isArray(list) ? list : list.items || [];
            if (rows[0]) await openConversation(rows[0].id);
          });
          await page.waitForTimeout(1500);
        }
        await setBuddy(page, 'atlas');
        await page.keyboard.press('Escape');
        //: It walks to its own spot and settles; the shot is of it at rest.
        await page.waitForTimeout(9000);
        const where = await page.evaluate(() => {
          const r = document.getElementById('nm-buddy')?.getBoundingClientRect();
          return r ? [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)] : null;
        });
        console.log('companion at', JSON.stringify(where));
        await shoot(page, 'companion', done);
        await setBuddy(page, 'off');
        await page.keyboard.press('Escape');
      }
    } finally {
      fake.kill();
    }
  }

  //: Phone width, dark, its own context (a viewport is fixed per context).
  if (wanted('phone')) {
    const phone = await context(browser, { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
    const tab = await phone.newPage();
    await signIn(tab);
    await tab.evaluate(() => applyThemeChoice('dark', true));
    await tab.evaluate(() => switchTab('notes'));
    await tab.waitForTimeout(3000);
    await shoot(tab, 'phone', done);
    await phone.close();
  }

  //: Atlas, delighted, drawn by the app's own renderer (`atlasDraw`,
  //: atlas.js) through the avatar lab the app serves, on a night tile: its
  //: body is pale light, which vanishes on GitHub's white page without one.
  if (wanted('atlas')) {
    const lab = await (await browser.newContext({ viewport: { width: 900, height: 900 }, deviceScaleFactor: 2 })).newPage();
    await lab.goto(`${BASE}/tools/avatar-lab.html`, { waitUntil: 'domcontentloaded' });
    await lab.waitForTimeout(1500);
    await lab.evaluate((mood) => {
      try { localStorage.setItem('atlas-look', 'masculine'); } catch (e) {}
      const holder = document.createElement('div');
      holder.id = 'readme-atlas';
      Object.assign(holder.style, {
        position: 'fixed', left: '0', top: '0', zIndex: '999', display: 'inline-block',
        padding: '18px 26px', borderRadius: '32px',
        background: 'radial-gradient(circle at 50% 40%, #33366e, #161730 72%)',
      });
      holder.append(atlasDraw(260, mood, 'full'));
      //: The shared drawing hosts (`svg` at the top of the body) stay: the
      //: eyes and gradients are drawn from them.
      for (const el of document.body.children) if (el.tagName.toLowerCase() !== 'svg') el.style.visibility = 'hidden';
      document.body.append(holder);
      for (const el of [document.documentElement, document.body]) { el.style.background = 'transparent'; el.style.backgroundImage = 'none'; }
    }, process.env.ATLAS_MOOD || 'delighted');
    await lab.waitForTimeout(1500);
    const p = `${OUT}/atlas.png`;
    await lab.locator('#readme-atlas').screenshot({ path: p, omitBackground: true });
    done.push({ file: 'atlas', bytes: fs.statSync(p).size });
    await lab.context().close();
  }

  console.log(JSON.stringify(done));
  await browser.close();
})().catch((e) => { console.log('ERR', e.message); process.exit(1); });
