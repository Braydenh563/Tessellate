// Trace a scroll (or a typing run) and attribute its cost by trace event.
// The method that fixed the board: record a Chrome trace, add up where the
// time went, remove the work nobody sees. pass2.md, "Performance by trace".
//
//   BASE=http://127.0.0.1:8799 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     SCENE=notes node scratchpad/ui-sweeps/scrolltrace.js
//
// SCENE: notes | library | typing-note | typing-doc | open-library
// W/H: the window (default 1184x760, the owner's desktop window).
// Prints the total milliseconds per event name on the renderer's main thread
// and on its raster threads, and the frame count.
const { boot } = require('./lib.js');
const W = +(process.env.W || 1184);
const H = +(process.env.H || 760);
const SCENE = process.env.SCENE || 'notes';
const STEPS = +(process.env.STEPS || 30);

const CATS = [
  'devtools.timeline', 'disabled-by-default-devtools.timeline',
  'disabled-by-default-devtools.timeline.frame', 'blink', 'cc', 'gpu',
  'toplevel', 'v8.execute', 'disabled-by-default-cc.debug', 'viz', 'gpu.service',
];

function summarise(json) {
  const events = json.traceEvents || json;
  const threads = {};
  for (const e of events) {
    if (e.ph === 'M' && e.name === 'thread_name') threads[`${e.pid}:${e.tid}`] = e.args.name;
  }
  const main = {};
  const raster = {};
  let frames = 0;
  for (const e of events) {
    if (e.name === 'DrawFrame' || e.name === 'Graphics.Pipeline.DrawAndSwap') frames++;
    if (e.ph !== 'X' || !e.dur) continue;
    const t = threads[`${e.pid}:${e.tid}`] || '';
    const bucket = t === 'CrRendererMain' ? main : /Raster|CompositorTileWorker/.test(t) ? raster : null;
    if (!bucket) continue;
    bucket[e.name] = (bucket[e.name] || 0) + e.dur / 1000;
  }
  const top = (b, n) => Object.entries(b).sort((a, c) => c[1] - a[1]).slice(0, n)
    .map(([k, v]) => `${k} ${v.toFixed(1)}`);
  //: The rendering pipeline's own stages, named, whatever their rank: these
  //: are the numbers a change here is meant to move.
  const STAGES = ['FunctionCall', 'TimerFire', 'FireAnimationFrame', 'EventDispatch', 'UpdateLayoutTree',
    'Layout', 'PrePaint', 'Paint', 'Layerize', 'Commit', 'RasterTask', 'ImageDecodeTask'];
  const all = {};
  for (const e of events) {
    if (e.ph !== 'X' || !e.dur || !STAGES.includes(e.name)) continue;
    const t = threads[`${e.pid}:${e.tid}`] || '';
    if (!/CrRendererMain|Raster|TileWorker|Compositor/.test(t)) continue;
    all[e.name] = (all[e.name] || 0) + e.dur / 1000;
  }
  //: Layouts on the main thread, for a layouts-a-second figure (L-general-34: a row locking and unlocking as it
  //: crosses the edge of a window was a layout a frame).
  let layouts = 0;
  for (const e of events) {
    if (e.name === 'Layout' && e.ph === 'X' && /CrRendererMain/.test(threads[`${e.pid}:${e.tid}`] || '')) layouts += 1;
  }
  const stages = Object.fromEntries(STAGES.filter((k) => all[k]).map((k) => [k, +all[k].toFixed(1)]));
  //: Where the raster work lands depends on how the browser runs (in the
  //: renderer's tile workers, or out of process in the GPU process), so the
  //: raster-shaped events are summed on every thread, by thread.
  const rasterBy = {};
  for (const e of events) {
    if (e.ph !== 'X' || !e.dur || !/^(RasterTask|TileManager|RasterizerTaskImpl|GpuRasterization|RasterDecoderImpl::DoRasterCHROMIUM|Graphics\.Pipeline\.DrawAndSwap|SkiaOutputSurfaceImplOnGpu::SwapBuffers|DisplayScheduler::DrawAndSwap)/.test(e.name)) continue;
    const key = `${threads[`${e.pid}:${e.tid}`] || e.tid}/${e.name}`;
    rasterBy[key] = (rasterBy[key] || 0) + e.dur / 1000;
  }
  //: Which scripts ran, by function and line: a FunctionCall is a callback the
  //: page registered, and during a scroll every one of them is a candidate
  //: for work nobody sees.
  const calls = {};
  for (const e of events) {
    if (e.ph !== 'X' || !e.dur || (e.name !== 'FunctionCall' && e.name !== 'FireAnimationFrame' && e.name !== 'EventDispatch')) continue;
    const d = (e.args && e.args.data) || {};
    const where = d.functionName !== undefined
      ? `${d.functionName || '(anon)'}@${String(d.url || '').split('/').pop().split('?')[0]}:${d.lineNumber}`
      : `${e.name}:${d.type || d.id || ''}`;
    calls[where] = (calls[where] || 0) + e.dur / 1000;
  }
  return { layouts, stages, rasterBy: top(rasterBy, 4), main: top(main, 4), calls: top(calls, +(process.env.TOPN || 8)), frames };
}

(async () => {
  const { browser, page } = await boot({ viewport: { width: W, height: H } });
  //: CPU=4 throttles the page as the lag rows' figures were taken (CDP Emulation.setCPUThrottlingRate).
  if (Number(process.env.CPU) > 1) {
    const cdp = await page.context().newCDPSession(page);
    await cdp.send('Emulation.setCPUThrottlingRate', { rate: Number(process.env.CPU) });
  }
  const tab = SCENE.startsWith('typing-doc') ? 'documents' : SCENE.startsWith('library') || SCENE === 'open-library' ? 'dashboard' : 'notes';
  await page.evaluate((t) => switchTab(t), tab);
  await page.waitForTimeout(2000);
  if (SCENE === 'library' || SCENE === 'library-search') {
    await page.evaluate(() => switchTab('library'));
    await page.waitForTimeout(2500);
  }
  if (SCENE === 'typing-note') {
    // The longest note, opened for editing in place.
    await page.evaluate(() => {
      const lis = [...document.querySelectorAll('#entry-list > li[data-id]')];
      lis.sort((a, b) => b.textContent.length - a.textContent.length);
      lis[0].querySelector(".entry-actions [title='Edit this entry']")?.click();
    });
    await page.waitForTimeout(1200);
  }
  if (SCENE === 'typing-doc') {
    await page.evaluate(async () => {
      const docs = await apiJson('/documents');
      const list = Array.isArray(docs) ? docs : docs.documents || [];
      list.sort((a, b) => (b.words || 0) - (a.words || 0));
      openDocument(list[0].id);
    });
    await page.waitForTimeout(2500);
    await page.click('.cm-content');
    await page.keyboard.press('Control+End');
  }
  if (SCENE === 'typing-note') {
    const box = await page.$('#entry-list textarea, #entry-list .cm-content, #entry-list [contenteditable="true"]');
    if (box) await box.click();
    await page.keyboard.press('Control+End');
  }
  //: EXP_CSS: a stylesheet added before the run, for an A/B of one suspect
  //: at a time (a shadow, a blur, a background), without editing the app.
  if (process.env.EXP_CSS) {
    // A constructed sheet, because the app's CSP refuses an inline <style>.
    await page.evaluate((css) => {
      const sheet = new CSSStyleSheet();
      sheet.replaceSync(css);
      document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet];
    }, process.env.EXP_CSS);
    await page.waitForTimeout(300);
  }
  await page.mouse.move(W / 2, H / 2);
  await page.waitForTimeout(500);

  await browser.startTracing(page, { categories: CATS });
  const t0 = Date.now();
  if (SCENE === 'notes' || SCENE === 'library') {
    for (let i = 0; i < STEPS; i++) {
      await page.mouse.wheel(0, 120);
      await page.waitForTimeout(50);
    }
    await page.waitForTimeout(500);
  } else if (SCENE.startsWith('typing')) {
    await page.keyboard.type(' the quick brown fox jumps over the lazy dog'.repeat(2), { delay: 30 });
    await page.waitForTimeout(500);
  } else if (SCENE === 'library-search') {
    //: NOVT=1 takes the View Transitions API away first, for an A/B of the
    //: cross-fade every Library render runs.
    if (process.env.NOVT) await page.evaluate(() => { document.startViewTransition = undefined; });
    await page.click('#library-search');
    await page.keyboard.type('design notes', { delay: 120 });
    await page.waitForTimeout(800);
  } else if (SCENE === 'open-library') {
    await page.evaluate(() => switchTab('library'));
    await page.waitForFunction(() => document.querySelectorAll('#library-grid .library-card').length > 0);
    await page.waitForTimeout(800);
  }
  const wall = Date.now() - t0;
  const buf = await browser.stopTracing();
  const s = summarise(JSON.parse(buf.toString()));
  if (process.env.COMPACT) {
    const raster = (s.rasterBy.find((x) => x.includes('/RasterTask ')) || 'RasterTask 0').split(' ').pop();
    const st = s.stages;
    const rows = await page.evaluate(() => document.querySelectorAll('#entry-list > li').length);
    console.log(`${SCENE} ${W}x${H} rows ${rows} layouts ${s.layouts} (${(s.layouts / (wall / 1000)).toFixed(1)}/s) raster ${raster} commit ${st.Commit || 0} paint ${st.Paint || 0} layout ${st.Layout || 0} style ${st.UpdateLayoutTree || 0} script ${((st.FunctionCall || 0) + (st.FireAnimationFrame || 0)).toFixed(1)} frames ${s.frames}`);
  } else {
    console.log(JSON.stringify({ scene: SCENE, window: `${W}x${H}`, wallMs: wall, ...s }, null, 1));
  }
  await browser.close();
})();
