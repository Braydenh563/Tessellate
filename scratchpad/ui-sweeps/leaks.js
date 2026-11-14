// Does the app accumulate listeners and nodes across ordinary navigation?
//
//   BASE=http://127.0.0.1:8781 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node leaks.js
//
// This exists because one did, for a long time, and nothing in the project
// could see it. `wireEscapedActionMenu` registered a `window` resize listener
// per kebab menu, which is per card, and the Library rebuilds sixty of them
// on every render. `window` is never collected, so each closure held its menu,
// its opener and the whole detached card behind them. Measured before the fix:
// +720 live listeners and +2,025 retained nodes on every single round of
// visiting the seven tabs, dead straight, with the document itself flat.
//
// **Per round, not in aggregate**, which is the whole method. Round one is
// one-time: it renders tabs that have never been drawn, and the numbers jump.
// Two aggregate readings taken during the same session (opening Settings and
// opening the whiteboard repeatedly) looked like leaks for exactly that
// reason and were not: sampled per round they were +41 then zero, and +5 then
// zero. Only the shape after the first round means anything.
//
// The rounds are compared against round one rather than against boot, and a
// couple of nodes of jitter are allowed because a status clock and an idle
// spinner are alive throughout.
const { chromium } = require('playwright');
const BASE = process.env.BASE || 'http://127.0.0.1:8781';
const PW = 'testpassword123';
const ROUNDS = Number(process.env.ROUNDS || 5);
const TABS = ['dashboard', 'notes', 'library', 'chat', 'graph', 'timeline', 'reminders'];
//: A listener that survives a round is a listener the app meant to keep. The
//: budget is what the measured leak was two orders of magnitude above: it
//: caught +720 a round with room to spare, and leaves the handful of timers
//: and clocks that legitimately rebind alone.
const LISTENER_BUDGET = 40;
const NODE_BUDGET = 400;

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addInitScript(() => {
    try { localStorage.setItem('theme', 'light'); localStorage.setItem('onboardingDone', '1'); } catch (e) {}
  });
  const page = await ctx.newPage();
  const cdp = await ctx.newCDPSession(page);
  await cdp.send('Performance.enable');
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#lock-password', { state: 'visible', timeout: 20000 });
  await page.fill('#lock-password', PW);
  await page.click('#lock-submit');
  await page.waitForTimeout(3000);
  if (await page.$('#lock-password') && await page.isVisible('#lock-password')) {
    await page.fill('#lock-password', PW); await page.click('#lock-submit'); await page.waitForTimeout(3000);
  }
  await page.evaluate(() => { const o = document.getElementById('onboarding-overlay'); if (o) o.classList.add('hidden'); });
  // The background paging has to finish, or its arriving pages are counted
  // as growth.
  await page.waitForTimeout(4000);

  const sample = async () => {
    // Twice: the JS heap and the DOM are collected on different passes.
    for (let i = 0; i < 2; i++) {
      await cdp.send('HeapProfiler.collectGarbage').catch(() => {});
      await page.waitForTimeout(250);
    }
    const metrics = await cdp.send('Performance.getMetrics');
    const by = Object.fromEntries(metrics.metrics.map((m) => [m.name, m.value]));
    return { listeners: by.JSEventListeners, nodes: by.Nodes };
  };

  const rounds = [];
  for (let r = 0; r < ROUNDS; r++) {
    for (const tab of TABS) {
      await page.evaluate((name) => { try { switchTab(name); } catch (e) {} }, tab);
      await page.waitForTimeout(450);
    }
    rounds.push(await sample());
  }

  const first = rounds[0];
  const last = rounds[rounds.length - 1];
  const spans = rounds.length - 1;
  const perRoundListeners = spans ? (last.listeners - first.listeners) / spans : 0;
  const perRoundNodes = spans ? (last.nodes - first.nodes) / spans : 0;

  for (const [i, r] of rounds.entries()) {
    console.log(`round ${String(i + 1).padStart(2)}  listeners ${String(r.listeners).padStart(6)}  nodes ${String(r.nodes).padStart(6)}`);
  }
  console.log(`per round after the first: listeners ${perRoundListeners.toFixed(1)} (budget ${LISTENER_BUDGET}), nodes ${perRoundNodes.toFixed(1)} (budget ${NODE_BUDGET})`);

  const findings = [];
  if (perRoundListeners > LISTENER_BUDGET) {
    findings.push(`listeners grow ${perRoundListeners.toFixed(1)} a round: something registers on a target that outlives the render`);
  }
  if (perRoundNodes > NODE_BUDGET) {
    findings.push(`nodes grow ${perRoundNodes.toFixed(1)} a round after a forced GC: detached DOM is being retained`);
  }
  for (const line of findings) console.log(`    ${line}`);
  console.log(findings.length ? `FAIL: ${findings.length} findings` : 'PASS: 0 findings');
  await browser.close();
  process.exit(findings.length ? 1 : 0);
})();
