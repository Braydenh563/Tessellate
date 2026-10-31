// What each background style costs, measured inside the page: paint time
// per frame, what it allocates, and whether "Still" really leaves nothing
// running. Screenshots of each style in light and dark to look at.
//
// `bgart.js` measures the frame *interval*, which in headless Chromium sits
// on the 16.7ms vsync floor for every style that fits in a frame, so it
// cannot tell a 2ms style from a 12ms one. This wraps the p5 instance's own
// `draw` in `performance.now()` for SECONDS instead, and reads one pixel back
// after each draw: the draw call only records canvas commands and Chromium
// rasterises them later, off this stack, so without the read the old mesh
// (thirty screen-sized translucent circles) timed at 0.2ms.
//
// Allocations: the sampling heap profiler over ALLOC_SECONDS, keeping the
// objects the GC has already collected (they are the churn), attributed to
// the art's own files (bg-art.js, settings.js, p5.min.js) by the allocating
// frame's URL. Bytes are the profiler's sampled estimate.
//
// Still: the page's requestAnimationFrame callbacks are counted over two
// seconds with the art held still, next to the same count with the art off.
//
//   BASE=http://127.0.0.1:8797 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     SHOTS=/tmp/shots node scratchpad/ui-sweeps/bgartcost.js
//
// STYLES narrows the list, THEMES picks light and/or dark, SECONDS the paint
// window, ALLOC_SECONDS the allocation window (0 skips it), STILL=0 skips the
// still check. THROTTLE=4 slows the page's CPU fourfold through CDP
// (Emulation.setCPUThrottlingRate), the nearest a sweep gets to a cheap
// university laptop. Each row also gives the frames actually drawn per
// second and the main thread's busy time per second (CDP's TaskDuration,
// everything the page's thread did, the CSS styles' style and layout work
// included), next to the same figure with the art off, and the CPU time of
// every browser process together (read from /proc: the renderer, the GPU
// process and the compositor, so a CSS style's compositing, which the main
// thread never sees, is counted too; headless composites in software, so
// this is the upper bound a machine with a GPU pays). FAST=1 reports a
// larger machine (eight cores, eight gigabytes), whose art runs at 30 frames
// a second: this sandbox has four cores, which the art reads as small and
// holds to 20.
const { chromium } = require('/opt/node22/lib/node_modules/playwright');

const PW = 'testpassword123';
const BASE = process.env.BASE || 'http://127.0.0.1:8797';
const STYLES = (process.env.STYLES || 'aurora,constellation,waves,bubbles,mesh,microbes,mycelium,dusk,ripples,fireflies,rain').split(',');
const THEMES = (process.env.THEMES || 'light,dark').split(',');
const SECONDS = Number(process.env.SECONDS || 5);
const ALLOC_SECONDS = Number(process.env.ALLOC_SECONDS ?? 10);
const STILL = process.env.STILL !== '0';
const SHOTS = process.env.SHOTS || '';
const INTENSITY = process.env.INTENSITY || '90';

async function boot(browser, prefs) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  await ctx.addInitScript((p) => {
    try {
      localStorage.setItem('onboardingDone', '1');
      // A marked browser keeps its own values over the notebook's copy
      // (seedUiStateFromServer), so a fresh data dir does not reset the style.
      localStorage.setItem('ui-synced', '{}');
      // CPU=1: the art's canvas is CPU-backed, so the raster is timed on
      // this thread as a machine without GPU canvas would do it, instead
      // of timing a GPU readback (which is what the one-pixel read costs
      // on an accelerated canvas, and which no real frame pays).
      if (p.__cpu) window.__bgArtCpu = true;
      if (p.__fast) {
        Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
        Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
      }
      for (const [k, v] of Object.entries(p)) if (!k.startsWith('__')) localStorage.setItem(k, v);
    } catch (e) { /* private window: the app copes */ }
    // Count the requestAnimationFrame callbacks the page runs, and
    // separately the ones the art requested (p5 or bg-art.js on the stack
    // when it asked): the app has loops of its own, so the page total alone
    // cannot say whether the art is still running.
    const raf = window.requestAnimationFrame.bind(window);
    window.__rafCount = 0;
    window.__rafArt = 0;
    window.requestAnimationFrame = (cb) => {
      const art = /p5\.min\.js|bg-art\.js/.test(new Error().stack || '');
      return raf((ts) => { window.__rafCount++; if (art) window.__rafArt++; cb(ts); });
    };
  }, prefs);
  // OVERRIDE_JS=/path/bg-art.js serves that file in place of the app's own,
  // so a "before" is measured on the same server, minutes apart.
  if (process.env.OVERRIDE_JS) {
    const body = require('fs').readFileSync(process.env.OVERRIDE_JS, 'utf8');
    await ctx.route('**/bg-art.js*', (route) => route.fulfill({ body, contentType: 'application/javascript' }));
  }
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#lock-password', { state: 'visible', timeout: 20000 });
  await page.fill('#lock-password', PW);
  await page.click('#lock-submit');
  await page.waitForTimeout(3000);
  await page.evaluate(() => {
    const o = document.getElementById('onboarding-overlay');
    if (o) o.classList.add('hidden');
  });
  await page.waitForTimeout(1500);
  return { ctx, page, errors };
}

async function drawCost(page, s) {
  return page.evaluate((secs) => new Promise((resolve) => {
    // eslint-disable-next-line no-undef
    const inst = typeof bgArtInstance !== 'undefined' ? bgArtInstance : null;
    if (!inst || typeof inst.draw !== 'function') { resolve(null); return; }
    const orig = inst.draw;
    const times = [];
    const g = inst.drawingContext;
    const js = [];
    inst.draw = function wrapped() {
      const a = performance.now();
      orig.call(this);
      const b = performance.now();
      g.getImageData(0, 0, 1, 1);
      js.push(b - a);
      times.push(performance.now() - a);
    };
    setTimeout(() => {
      inst.draw = orig;
      times.sort((x, y) => x - y);
      const mean = times.reduce((t, v) => t + v, 0) / Math.max(1, times.length);
      const jsMean = js.reduce((t, v) => t + v, 0) / Math.max(1, js.length);
      resolve({
        fps: +(times.length / secs).toFixed(1),
        n: times.length,
        mean: +mean.toFixed(2),
        js: +jsMean.toFixed(2),
        p95: +(times[Math.floor(times.length * 0.95)] || 0).toFixed(2),
        // The median: this sandbox is shared, and a frame preempted by
        // another process lands in the mean and the p95, not here.
        med: +(times[Math.floor(times.length / 2)] || 0).toFixed(2),
      });
    }, secs * 1000);
  }), s);
}

async function allocations(page, secs) {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('HeapProfiler.enable');
  await cdp.send('HeapProfiler.collectGarbage');
  await cdp.send('HeapProfiler.startSampling', {
    samplingInterval: 1024,
    includeObjectsCollectedByMajorGC: true,
    includeObjectsCollectedByMinorGC: true,
  });
  await page.waitForTimeout(secs * 1000);
  const { profile } = await cdp.send('HeapProfiler.stopSampling');
  let art = 0, total = 0;
  const top = new Map();
  const walk = (node, inArt) => {
    const url = node.callFrame.url || '';
    const mine = inArt || /bg-art\.js|settings\.js|p5\.min\.js/.test(url);
    total += node.selfSize;
    if (mine) art += node.selfSize;
    if (node.selfSize) {
      const key = `${node.callFrame.functionName || '(anon)'} ${url.split('/').pop().split('?')[0]}:${node.callFrame.lineNumber + 1}`;
      top.set(key, (top.get(key) || 0) + node.selfSize);
    }
    for (const c of node.children) walk(c, mine);
  };
  walk(profile.head, false);
  await cdp.detach();
  if (process.env.ALLOC_TOP) {
    const rows = [...top.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8);
    for (const [k, v] of rows) console.log(`    ${Math.round(v / 1024)}KB ${k}`);
  }
  return { artKB: Math.round(art / 1024), totalKB: Math.round(total / 1024) };
}

// Main-thread busy milliseconds per second over `secs`, from CDP's own
// accounting of the renderer's tasks.
async function busy(page, secs) {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Performance.enable');
  const read = async () => {
    const { metrics } = await cdp.send('Performance.getMetrics');
    return metrics.find((m) => m.name === 'TaskDuration').value;
  };
  const a = await read();
  await page.waitForTimeout(secs * 1000);
  const b = await read();
  await cdp.detach();
  return +(((b - a) * 1000) / secs).toFixed(1);
}

// CPU milliseconds per second of the whole browser (every process under
// `root`, not counting `root` itself), from /proc.
function treeTicks(root) {
  const fs = require('fs');
  const kids = new Map();
  for (const d of fs.readdirSync('/proc')) {
    if (!/^\d+$/.test(d)) continue;
    try {
      const st = fs.readFileSync(`/proc/${d}/stat`, 'utf8');
      const f = st.slice(st.lastIndexOf(')') + 2).split(' ');
      kids.set(Number(d), { ppid: Number(f[1]), ticks: Number(f[11]) + Number(f[12]) });
    } catch (e) { /* gone */ }
  }
  let total = 0;
  const walk = (pid) => {
    const me = kids.get(pid);
    if (me && pid !== root) total += me.ticks;
    for (const [k, v] of kids) if (v.ppid === pid) walk(k);
  };
  walk(root);
  return total;
}

async function browserCpu(page, pid, secs) {
  const a = treeTicks(pid);
  await page.waitForTimeout(secs * 1000);
  const b = treeTicks(pid);
  return Math.round(((b - a) * 10) / secs); // 100 ticks a second
}

// Resident memory of every process under `root` together, in MB.
function treeRss(root) {
  const fs = require('fs');
  const kids = new Map();
  for (const d of fs.readdirSync('/proc')) {
    if (!/^\d+$/.test(d)) continue;
    try {
      const st = fs.readFileSync(`/proc/${d}/stat`, 'utf8');
      const f = st.slice(st.lastIndexOf(')') + 2).split(' ');
      kids.set(Number(d), { ppid: Number(f[1]), pages: Number(f[21]) });
    } catch (e) { /* gone */ }
  }
  let total = 0;
  const walk = (pid) => {
    const me = kids.get(pid);
    if (me && pid !== root) total += me.pages;
    for (const [k, v] of kids) if (v.ppid === pid) walk(k);
  };
  walk(root);
  return Math.round((total * 4096) / 1048576);
}

// PAUSE=1 (INBOX 1436): what a paused style costs. A hidden tab, read at
// once, three seconds in and after PAUSE_WAIT seconds (default 24, past the
// 20 s at which the canvas becomes a picture): canvases and pictures in the
// DOM, art rAF callbacks in two seconds, JS heap, browser RSS, then the
// resume. `STYLES`, `THEMES` and `CPU` apply as above.
async function pauseRun(browser, theme, style) {
  const { ctx, page, errors } = await boot(browser, {
    theme, bgArt: 'on', 'bg-style': style, 'bg-motion': 'moving', 'bg-intensity': INTENSITY,
    __cpu: process.env.CPU === '1',
  });
  const pid = process.pid;
  const snap = async () => ({
    ...(await page.evaluate(() => ({
      canvases: document.querySelectorAll('canvas.bg-art-canvas').length,
      stills: document.querySelectorAll('.bg-art-still').length,
      heap: performance.memory ? +(performance.memory.usedJSHeapSize / 1048576).toFixed(1) : null,
    }))),
    raf: (await rafCount(page)).split(' ')[0],
    rss: treeRss(pid),
  });
  const hide = (h) => page.evaluate((v) => {
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => v });
    document.dispatchEvent(new Event('visibilitychange'));
  }, h);
  const fmt = (o) => `canvas ${o.canvases} still ${o.stills} rAF ${o.raf}/2s heap ${o.heap}MB rss ${o.rss}MB`;
  const moving = await snap();
  await hide(true);
  await page.waitForTimeout(1500);
  const early = await snap();
  await page.waitForTimeout(Number(process.env.PAUSE_WAIT || 24) * 1000);
  const long = await snap();
  await hide(false);
  await page.waitForTimeout(1500);
  const back = await snap();
  console.log(`${theme.padEnd(5)} ${style.padEnd(13)} moving: ${fmt(moving)} | paused 3s: ${fmt(early)} | paused long: ${fmt(long)} | resumed: ${fmt(back)}`
    + (errors.length ? '  ERRORS: ' + errors.join(' | ') : ''));
  await ctx.close();
}

async function throttle(page) {
  const rate = Number(process.env.THROTTLE || 1);
  if (rate <= 1) return;
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Emulation.setCPUThrottlingRate', { rate });
}

async function rafCount(page) {
  return page.evaluate(() => new Promise((resolve) => {
    const start = window.__rafCount, art = window.__rafArt;
    setTimeout(() => resolve(`${window.__rafArt - art} art (${window.__rafCount - start} page)`), 2000);
  }));
}

(async () => {
  const browser = await chromium.launch({ args: ['--enable-precise-memory-info'] });
  // Playwright spawns the browser from this process, so the browser's
  // processes are this one's descendants (this one's own ticks excluded).
  const pid = process.pid;
  if (process.env.PAUSE === '1') {
    for (const theme of THEMES) for (const style of STYLES) await pauseRun(browser, theme, style);
    await browser.close();
    return;
  }
  if (STILL) {
    // The baseline: the app on its own still requests animation frames and
    // allocates (the header emblem is a p5 sketch too, which is why p5's
    // frames count as "art" in both numbers), so each style's figures are
    // read against these.
    const off = await boot(browser, { theme: 'light', bgArt: 'off', __fast: process.env.FAST === '1' });
    await throttle(off.page);
    console.log(`art off: main thread ${await busy(off.page, SECONDS)}ms/s; browser CPU ${await browserCpu(off.page, pid, SECONDS)}ms/s`);
    const offAlloc = ALLOC_SECONDS ? await allocations(off.page, ALLOC_SECONDS) : null;
    console.log(`art off: ${await rafCount(off.page)} rAF callbacks in 2s`
      + (offAlloc ? `; alloc ${offAlloc.artKB}KB art-attributed / ${offAlloc.totalKB}KB page in ${ALLOC_SECONDS}s` : ''));
    await off.ctx.close();
  }
  for (const theme of THEMES) {
    for (const style of STYLES) {
      const { ctx, page, errors } = await boot(browser, {
        theme, bgArt: 'on', 'bg-style': style, 'bg-motion': 'moving', 'bg-intensity': INTENSITY,
        __cpu: process.env.CPU === '1', __fast: process.env.FAST === '1',
      });
      await throttle(page);
      const cost = await drawCost(page, SECONDS);
      const busyMs = await busy(page, SECONDS);
      const cpuMs = pid ? await browserCpu(page, pid, SECONDS) : '?';
      const actual = await page.evaluate(() => (typeof bgArtStyle === 'function' ? bgArtStyle() : '?'));
      const alloc = ALLOC_SECONDS ? await allocations(page, ALLOC_SECONDS) : null;
      if (SHOTS) {
        await page.screenshot({ path: `${SHOTS}/${style}-${theme}.png` });
        const data = await page.evaluate(() => {
          const c = document.getElementById('bg-art-canvas');
          return c ? c.toDataURL('image/png') : null;
        });
        if (data) require('fs').writeFileSync(`${SHOTS}/${style}-${theme}-canvas.png`, Buffer.from(data.split(',')[1], 'base64'));
        // The art alone over the page's own background, at its real
        // opacity: every element but the art hidden for one capture.
        await page.evaluate(() => {
          for (const el of document.body.children) {
            if (!el.classList.contains('bg-art-canvas')) { el.dataset.artHid = el.style.visibility || '-'; el.style.visibility = 'hidden'; }
          }
        });
        await page.screenshot({ path: `${SHOTS}/${style}-${theme}-art.png` });
        await page.evaluate(() => {
          for (const el of document.body.children) {
            if (el.dataset.artHid) { el.style.visibility = el.dataset.artHid === '-' ? '' : el.dataset.artHid; delete el.dataset.artHid; }
          }
        });
      }
      let still = '';
      if (STILL) {
        const s = await boot(browser, { theme, bgArt: 'on', 'bg-style': style, 'bg-motion': 'still', 'bg-intensity': INTENSITY });
        await s.page.waitForTimeout(1500);
        const n = await rafCount(s.page);
        const state = await s.page.evaluate(() => ({
          // eslint-disable-next-line no-undef
          instance: typeof bgArtInstance !== 'undefined' && bgArtInstance !== null,
          canvas: !!document.getElementById('bg-art-canvas'),
          image: (document.getElementById('bg-art-still') || {}).style?.backgroundImage?.slice(0, 9) || 'none',
        }));
        if (SHOTS) await s.page.screenshot({ path: `${SHOTS}/${style}-${theme}-still.png` });
        still = `; still: ${n} rAF in 2s, instance ${state.instance}, canvas ${state.canvas}, image ${state.image}`
          + `${s.errors.length ? ' ERRORS: ' + s.errors.join(' | ') : ''}`;
        await s.ctx.close();
      }
      console.log(
        `${theme.padEnd(5)} ${style.padEnd(13)} (${actual}) `
        + (cost ? `script ${cost.js}ms, script+raster ${cost.mean}ms median ${cost.med}ms p95 ${cost.p95}ms, ${cost.fps}fps` : 'no canvas loop (CSS)')
        + `; main thread ${busyMs}ms/s; browser CPU ${cpuMs}ms/s`
        + (alloc ? `; alloc ${alloc.artKB}KB art / ${alloc.totalKB}KB page in ${ALLOC_SECONDS}s` : '')
        + still
        + (errors.length ? '  ERRORS: ' + errors.join(' | ') : ''),
      );
      await ctx.close();
    }
  }
  await browser.close();
})();
