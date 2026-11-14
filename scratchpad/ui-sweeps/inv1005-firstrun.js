// Time to first answer (WORLD_CLASS_PLAN H6 and H9, rows 25 and 27): from an
// empty data folder, the shortest path a new person takes to a question
// answered from a note they wrote, timed end to end.
//
//   rm -rf /tmp/mm-fresh && bash scratchpad/ui-sweeps/serve.sh 8866 /tmp/mm-fresh
//   BASE=http://127.0.0.1:8866 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node scratchpad/ui-sweeps/inv1005-firstrun.js
//
// Steps, each timed: the first screen (choose a password), the welcome, a
// note typed into Capture and saved, the Ask box, the answer on screen. The
// person's own typing is not timed (it is the same in every app); the app's
// waits are. Prints each step's milliseconds and the total. Needs a data
// folder that has never been opened: it is the first run that is measured.
const { chromium } = require('playwright');

const BASE = process.env.BASE || 'http://127.0.0.1:8866';
const NOTE = 'The spare key for the shed is under the blue flower pot by the back door.';
const QUESTION = 'Where is the spare key for the shed?';

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: Number(process.env.WIDTH || 1440), height: 900 } });
  const page = await ctx.newPage();
  page.on('pageerror', (e) => console.log('PAGEERROR:', e.message));
  const steps = [];
  let mark = Date.now();
  let typing = 0;
  let typedAtLap = 0;
  //: Each step's own time, the person's typing in it taken out.
  const lap = (name) => { const now = Date.now(); steps.push([name, now - mark - (typing - typedAtLap)]); typedAtLap = typing; mark = now; };
  //: A person's pace (DELAY ms a key, 120 by default, about 80 words a
  //: minute), timed apart from the app: what the app does while someone types
  //: (a model loading, a search warming) is the point of measuring it.
  const DELAY = Number(process.env.DELAY || 120);
  const type = async (selector, text) => { const t = Date.now(); await page.click(selector); await page.type(selector, text, { delay: DELAY }); typing += Date.now() - t; };

  const start = Date.now();
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#lock-password', { state: 'visible', timeout: 30000 });
  lap('first screen');
  await page.fill('#lock-password', 'firstrun-pass-1');
  await page.click('#lock-submit');
  // A confirm field may follow on setup.
  await page.waitForTimeout(400);
  if (await page.isVisible('#lock-password').catch(() => false)) {
    await page.fill('#lock-password', 'firstrun-pass-1');
    await page.click('#lock-submit').catch(() => {});
  }
  await page.waitForFunction(() => document.getElementById('lock-overlay')?.classList.contains('hidden'), null, { timeout: 30000 });
  lap('signed in');
  // The welcome: skip it the way a person in a hurry would, if it shows.
  const welcome = await page.waitForSelector('#onboarding-overlay:not(.hidden)', { timeout: 4000 }).catch(() => null);
  if (welcome) {
    const skip = await page.$('#onboarding-overlay button.ghost, #onboarding-skip, #onboarding-overlay [data-action="skip"]');
    if (skip) await skip.click().catch(() => {});
    else await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
  }
  lap('welcome');
  await page.evaluate(() => { switchTab('notes'); showNotesSection('capture'); });
  await page.waitForSelector('#entry-content', { state: 'visible' });
  await type('#entry-content', NOTE);
  await page.click('#save-btn');
  // `allEntries` is a top-level `let` of the app's scripts: in scope, not on window.
  await page.waitForFunction((t) => (typeof allEntries !== 'undefined' ? allEntries : []).some((e) => (e.content || '').includes(t.slice(0, 20))), NOTE, { timeout: 20000 });
  lap('note saved');
  await page.evaluate(() => showNotesSection('ask'));
  await page.waitForSelector('#question', { state: 'visible' });
  await type('#question', QUESTION);
  await page.click('#ask-btn');
  // Finished, not started: the Stop button is gone again and the box no
  // longer says it is searching.
  await page.waitForTimeout(150);
  await page.waitForFunction(() => {
    const a = document.getElementById('ai-answer');
    const off = document.getElementById('ask-offline');
    const busy = !document.getElementById('stop-btn').classList.contains('hidden') || /Searching your notes|Thinking/.test(a?.innerText || '');
    return !busy && ((a && a.innerText.trim().length > 20) || (off && !off.classList.contains('hidden') && off.innerText.trim().length > 10));
  }, null, { timeout: 90000 });
  lap('answer on screen');
  const answer = await page.evaluate(() => (document.getElementById('ai-answer').innerText || document.getElementById('ask-offline').innerText).trim().slice(0, 200));
  const total = Date.now() - start;
  for (const [name, ms] of steps) console.log(`${name.padEnd(18)} ${String(ms).padStart(6)} ms`);
  console.log(`typing (not the app) ${typing} ms`);
  console.log(`total              ${String(total).padStart(6)} ms, of which the app ${total - typing} ms`);
  console.log(`answer: ${answer}`);
  console.log(`found the note: ${answer.toLowerCase().includes('blue flower pot') || answer.toLowerCase().includes('flower pot')}`);
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
