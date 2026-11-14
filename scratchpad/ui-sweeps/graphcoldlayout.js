// The graph's controls before graph.js has arrived (a cold load).
//
// Reported by the companion agent, 2026-09-26: changing the graph layout
// threw "setGraphPhysicsEnabled is not defined". The Graph tab is drawn from
// index.html at boot and its code (graph.js, graph-canvas.js) is fetched on
// the first visit (`ensureModule`, app.js); `switchTab` reveals the page first
// and fetches second, so for as long as the fetch takes, the layout picker is
// on screen and live while the functions its listener calls (navigation.js)
// do not exist. The same window has a second door: leaving the tab before the
// fetch lands runs `graphSimulation?.stop()`, a read of a name graph.js
// declares.
//
// So the bundle is held back 2.5s here (a route that delays it), and the two
// gestures are made inside that window:
//
//   1. open Graph and change the layout at once: no page error, and once the
//      bundle lands the change has taken (stored, radio checked, physics
//      dimmed for a tree layout, the map drawn);
//   2. open Graph and leave it at once: no page error;
//   3. press the zoom and fit buttons inside the window: the page is inert
//      until the code lands (so the presses are not delivered), then live.
//
//   BASE=http://127.0.0.1:8797 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node scratchpad/ui-sweeps/graphcoldlayout.js
const { chromium } = require('playwright');

const BASE = process.env.BASE || 'http://127.0.0.1:8781';
const results = [];
const check = (label, ok, detail) => {
  results.push(Boolean(ok));
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}${detail ? '  ' + detail : ''}`);
};

async function coldPage(browser) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addInitScript(() => {
    try {
      localStorage.setItem('theme', 'light');
      localStorage.setItem('onboardingDone', '1');
      localStorage.setItem('tourDone', '1');
      localStorage.setItem('nm-buddy-hint', 'done');
      localStorage.setItem('activeTab', 'dashboard');
      localStorage.setItem('graph-layout', 'force');
    } catch (e) {}
  });
  // Hold the graph bundle back, so the window between the tab being drawn and
  // its code arriving is long enough to act in.
  await ctx.route(/\/graph(-canvas)?\.js/, async (route) => {
    await new Promise((r) => setTimeout(r, 2500));
    await route.continue();
  });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#lock-password', { state: 'visible', timeout: 20000 });
  await page.fill('#lock-password', 'testpassword123');
  await page.click('#lock-submit');
  await page.waitForTimeout(3000);
  await page.evaluate(() => document.getElementById('onboarding-overlay')?.classList.add('hidden'));
  return { ctx, page, errors };
}

(async () => {
  const browser = await chromium.launch();

  {
    const { ctx, page, errors } = await coldPage(browser);
    const before = await page.evaluate(() => typeof graphSimulation);
    await page.evaluate(() => {
      switchTab('graph');
      const radio = document.getElementById('graph-layout');
      radio.value = 'tree';
      radio.dispatchEvent(new Event('change', { bubbles: true }));
    });
    await page.waitForTimeout(6000);
    const after = await page.evaluate(() => ({
      stored: localStorage.getItem('graph-layout'),
      checked: document.getElementById('graph-layout').value === 'tree',
      dimmed: document.getElementById('graph-physics')?.classList.contains('is-disabled'),
      nodes: typeof gcTab !== 'undefined' ? gcTab.nodes.length : -1,
    }));
    check('the change was made before graph.js arrived', before === 'undefined', `typeof graphSimulation (a graph.js let) was ${before}`);
    check('changing the layout on a cold load throws nothing', errors.length === 0, errors.slice(0, 2).join(' | '));
    check('and the change took once the code landed', after.stored === 'tree' && after.checked && after.dimmed && after.nodes > 0, JSON.stringify(after));
    await ctx.close();
  }

  {
    const { ctx, page, errors } = await coldPage(browser);
    await page.evaluate(() => { switchTab('graph'); });
    await page.waitForTimeout(300);
    await page.evaluate(() => { switchTab('notes'); });
    await page.waitForTimeout(4000);
    check('leaving Graph before its code arrived throws nothing', errors.length === 0, errors.slice(0, 2).join(' | '));
    await ctx.close();
  }

  {
    // 3. A person's own presses inside the window: the zoom and fit buttons
    //    (wiring.js reads graph.js's state in both) and the refresh.
    const { ctx, page, errors } = await coldPage(browser);
    await page.evaluate(() => { switchTab('graph'); });
    await page.waitForTimeout(300);
    const during = await page.evaluate(() => document.getElementById('tab-graph').inert);
    for (const id of ['graph-zoom-in', 'graph-zoom-fit', 'graph-zoom-out']) {
      const r = await page.evaluate((i) => { const b = document.getElementById(i).getBoundingClientRect(); return { x: b.left + b.width / 2, y: b.top + b.height / 2 }; }, id);
      await page.mouse.click(r.x, r.y);
    }
    await page.waitForTimeout(5000);
    const afterInert = await page.evaluate(() => document.getElementById('tab-graph').inert);
    check('the Graph page is inert while its code is on the way, and live after', during === true && afterInert === false, `during ${during}, after ${afterInert}`);
    check('pressing zoom and fit inside the window throws nothing', errors.length === 0, errors.slice(0, 2).join(' | '));
    await ctx.close();
  }

  await browser.close();
  const failed = results.filter((x) => !x).length;
  console.log(`${results.length - failed}/${results.length} checks passed`);
  process.exit(failed ? 1 : 0);
})().catch((e) => { console.log('ERR ' + e.stack); process.exit(1); });
