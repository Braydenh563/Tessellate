// What the boot splash's progress bar costs the browser, as a number.
//
// INBOX 308, the owner: "all animations for things [should be] done the
// cheapest they can be ... like using transform etc etc." The bar used to
// animate `width` in both a transition and a 2.4s keyframe, which is a
// layout on every frame of the animation; it now animates `transform:
// scaleX()`, which is not. This probe exists so that change is a measurement
// rather than a principle, and so the next person who touches the bar can
// re-run it.
//
// How it gets a window to measure. The splash is only up until
// `/auth/status` resolves, which on localhost is tens of milliseconds, far
// less than the 2.4s crawl. So the probe holds that one request open for
// `HOLD_MS` and measures the splash over the crawl's real duration. That is
// not a contrivance: a slow cold start is the case the crawl was added for
// (00-tokens-shell.css, "the splash doesn't actually progress"), so this
// measures the animation in the situation it exists to cover.
//
// What it reads. Chrome's own counters through CDP (`Performance.getMetrics`:
// LayoutCount, RecalcStyleCount and their durations) rather than frame
// timing alone, because a headless sandbox's frame deltas are noisy and a
// 176x5px bar is far too small to move paint time out of that noise. Frame
// deltas are collected too and printed, but the layout counters are the
// signal. Each measurement also runs a CONTROL pass with the bar's animation
// switched off, which gives the floor of layouts the rest of the boot causes;
// the attributable cost is the difference.
//
//   BASE=http://127.0.0.1:8808 node scratchpad/ui-sweeps/animcost.js
//
const { chromium } = require('playwright');
const BASE = process.env.BASE || 'http://127.0.0.1:8808';
const HOLD_MS = 3200;      // longer than the 2.4s crawl
const WINDOW_MS = 2400;    // the crawl's own duration
const RUNS = Number(process.env.RUNS || 3);

const median = (xs) => {
  const s = [...xs].sort((a, b) => a - b);
  return s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2;
};

async function once(browser, { control }) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  // Hold the one request that ends the splash. `route.continue()` after a
  // timer, not `route.abort()`: an aborted status call sends the app down its
  // failure path and paints a different screen than the one being measured.
  await page.route('**/auth/status*', async (route) => {
    await new Promise((r) => setTimeout(r, HOLD_MS));
    try { await route.continue(); } catch (e) { /* context closed first */ }
  });
  const cdp = await ctx.newCDPSession(page);
  await cdp.send('Performance.enable');
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.boot-splash-progress-fill', { state: 'attached', timeout: 10000 });
  if (control) {
    // The floor: everything else the boot does, with the bar standing still.
    await page.evaluate(() => {
      const el = document.querySelector('.boot-splash-progress-fill');
      el.style.animation = 'none';
      el.style.transition = 'none';
    });
  }
  const read = async () => {
    const { metrics } = await cdp.send('Performance.getMetrics');
    const m = {};
    for (const x of metrics) m[x.name] = x.value;
    return m;
  };
  const a = await read();
  await page.evaluate(() => {
    window.__frames = [];
    let last = performance.now();
    const tick = (t) => { window.__frames.push(t - last); last = t; requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  });
  await page.waitForTimeout(WINDOW_MS);
  const frames = await page.evaluate(() => window.__frames.slice(1));
  // What the bar actually looks like part way through, so a conversion that
  // is cheaper but wrong cannot pass as a win: the fill's painted box must
  // still be a fraction of its track, and still start at the track's left.
  const geom = await page.evaluate(() => {
    const fill = document.querySelector('.boot-splash-progress-fill');
    const track = document.querySelector('.boot-splash-progress');
    if (!fill || !track) return null;
    const f = fill.getBoundingClientRect(); const t = track.getBoundingClientRect();
    const cs = getComputedStyle(fill);
    return {
      trackW: +t.width.toFixed(1), fillW: +f.width.toFixed(1),
      leftGap: +(f.left - t.left).toFixed(2), height: +f.height.toFixed(2),
      transform: cs.transform, width: cs.width,
    };
  });
  const b = await read();
  await ctx.close();
  const sorted = [...frames].sort((x, y) => x - y);
  return {
    layouts: b.LayoutCount - a.LayoutCount,
    recalcs: b.RecalcStyleCount - a.RecalcStyleCount,
    layoutMs: +((b.LayoutDuration - a.LayoutDuration) * 1000).toFixed(2),
    recalcMs: +((b.RecalcStyleDuration - a.RecalcStyleDuration) * 1000).toFixed(2),
    frames: frames.length,
    frameP95: sorted.length ? +sorted[Math.floor(sorted.length * 0.95)].toFixed(2) : 0,
    frameMax: sorted.length ? +sorted[sorted.length - 1].toFixed(2) : 0,
    long: frames.filter((d) => d > 20).length,
    geom,
  };
}

(async () => {
  const browser = await chromium.launch();
  const out = { animated: [], control: [] };
  for (let i = 0; i < RUNS; i++) {
    out.animated.push(await once(browser, { control: false }));
    out.control.push(await once(browser, { control: true }));
  }
  await browser.close();
  const col = (rows, k) => median(rows.map((r) => r[k]));
  console.log(`animcost: ${RUNS} runs each, ${WINDOW_MS}ms window over the boot splash crawl`);
  for (const kind of ['animated', 'control']) {
    const r = out[kind];
    console.log(`  ${kind.padEnd(8)} layouts=${col(r, 'layouts')} recalcs=${col(r, 'recalcs')} ` +
      `layoutMs=${col(r, 'layoutMs')} recalcMs=${col(r, 'recalcMs')} ` +
      `frames=${col(r, 'frames')} p95=${col(r, 'frameP95')}ms max=${col(r, 'frameMax')}ms long>20ms=${col(r, 'long')}`);
  }
  console.log(`  attributable to the bar: layouts=${col(out.animated, 'layouts') - col(out.control, 'layouts')} ` +
    `recalcs=${col(out.animated, 'recalcs') - col(out.control, 'recalcs')} ` +
    `layoutMs=${(col(out.animated, 'layoutMs') - col(out.control, 'layoutMs')).toFixed(2)}`);
  console.log('  geometry mid-crawl:', JSON.stringify(out.animated[0].geom));

  // A verdict, not only a reading: this runs in scripts/gate.sh --sweeps, and a
  // step that can only pass measures nothing. Two findings, both of them the
  // ways this particular change comes undone.
  const findings = [];
  const attributable = col(out.animated, 'layouts') - col(out.control, 'layouts');
  // The threshold is not zero because a boot is not perfectly repeatable: the
  // control floor moved between 2 and 3 across runs on the machine this was
  // written on. It is far below the 121 a width animation costs, so a bar that
  // goes back to animating width fails this by twenty times over.
  if (attributable > 8) {
    findings.push(`the progress bar forces ${attributable} layouts over its crawl; ` +
      'it should force none. Something in .boot-splash-progress-fill is animating ' +
      'a layout property again (00-tokens-shell.css).');
  }
  const g = out.animated[0].geom;
  if (!g) findings.push('no boot splash progress bar on the page at all');
  else {
    // Cheap and wrong is not a win: the fill still has to be a fraction of its
    // track, flush with its left edge.
    if (g.leftGap > 0.5) findings.push(`the fill starts ${g.leftGap}px in from the track's left edge`);
    if (!(g.fillW > 8 && g.fillW < g.trackW)) {
      findings.push(`the fill measures ${g.fillW}px inside a ${g.trackW}px track, which is not a bar part way along`);
    }
  }
  if (findings.length) {
    console.log('FINDINGS:');
    for (const f of findings) console.log('  - ' + f);
    process.exit(1);
  }
  console.log('  0 findings');
})();
