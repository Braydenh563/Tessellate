// Ten-minute browser memory check (L-world-class-24). A scripted loop across notes, a document, a board,
// the graph, chat and the library; every SAMPLE_S seconds it logs usedJSHeapSize, CDP Runtime.getHeapUsage
// and Memory.getDOMCounters; at minutes 2 and 10 it forces a GC (HeapProfiler.collectGarbage) first.
// PASS: heap after GC at minute 10 within 20% of minute 2, and DOM nodes not growing linearly (the
// nodes slope over minutes 2 to 10 under 1% of the minute-2 count per minute).
//   BASE=http://127.0.0.1:8892 node scratchpad/ui-sweeps/memory10.js   (MINUTES=10, SAMPLE_S=30)
const { boot } = require('./lib.js');
const MINUTES = Number(process.env.MINUTES || 10);
const SAMPLE_S = Number(process.env.SAMPLE_S || 30);
process.on('unhandledRejection', (e) => { console.log('ERROR', e && e.message); process.exit(2); });
(async () => {
  const { browser, ctx, page } = await boot();
  const cdp = await ctx.newCDPSession(page);
  await cdp.send('HeapProfiler.enable');
  const ids = await page.evaluate(async () => {
    const get = (p) => apiJson(p, { silent: true }).catch(() => []);
    const post = (p, b) => apiJson(p, { method: 'POST', body: JSON.stringify(b) });
    let docs = await get('/documents'); docs = docs.items || docs;
    if (!docs.length) docs = [await post('/documents', { title: 'Memory doc', content: 'Body text. '.repeat(200) })];
    let boards = await get('/whiteboard/boards');
    if (!boards.length) boards = [await post('/whiteboard/boards', { title: 'Memory board' })];
    const c = await post('/conversations', { question: 'Memory question', answer: 'Answer. '.repeat(40) });
    return { doc: docs[0].id, board: boards[0].id, conv: c.id };
  });
  const step = async (fn) => { await page.evaluate(fn, ids).catch((e) => console.log('step failed', String(e.message).slice(0, 80))); await page.waitForTimeout(900); };
  const loop = async () => {
    await step(() => switchTab('notes'));
    await page.evaluate(() => document.querySelector('#entries-list .entry, #entry-list .entry, .entry-card')?.click()).catch(() => {});
    await page.waitForTimeout(900);
    await step((i) => { switchTab('library'); return openDocument(i.doc); });
    await step((i) => { switchTab('library'); return openWhiteboardBoard(i.board); });
    await step(() => switchTab('graph'));
    await page.waitForTimeout(1500);
    await step((i) => { switchTab('chat'); return openConversation(i.conv); });
    await step(() => { switchTab('library'); document.querySelector('#library-subtabs button[data-target="library-view-docs"]')?.click(); });
    await step(() => { document.querySelector('#library-subtabs button[data-target="library-view-whiteboard"]')?.click(); });
  };
  const sample = async (gc) => {
    if (gc) { await cdp.send('HeapProfiler.collectGarbage'); await page.waitForTimeout(500); }
    const js = await page.evaluate(() => performance.memory.usedJSHeapSize);
    const hu = await cdp.send('Runtime.getHeapUsage');
    const dc = await cdp.send('Memory.getDOMCounters');
    return { js, cdp: hu.usedSize, nodes: dc.nodes, listeners: dc.jsEventListeners, docs: dc.documents };
  };
  const mb = (n) => (n / 1048576).toFixed(1);
  const rows = []; const t0 = Date.now(); let nextS = 0; const marks = {};
  console.log('min  gc  jsHeapMB  cdpHeapMB  nodes  listeners  docs');
  while ((Date.now() - t0) / 1000 < MINUTES * 60) {
    await loop();
    const el = (Date.now() - t0) / 1000;
    if (el >= nextS) {
      const s = await sample(false); rows.push({ min: el / 60, gc: false, ...s });
      console.log(`${(el / 60).toFixed(1)}  no  ${mb(s.js)}  ${mb(s.cdp)}  ${s.nodes}  ${s.listeners}  ${s.docs}`);
      nextS += SAMPLE_S;
    }
    for (const m of [2, MINUTES]) if (!marks[m] && el >= m * 60 - 5) { marks[m] = await sample(true); console.log(`${(el / 60).toFixed(1)}  GC  ${mb(marks[m].js)}  ${mb(marks[m].cdp)}  ${marks[m].nodes}  ${marks[m].listeners}  ${marks[m].docs}`); }
  }
  if (!marks[MINUTES]) { marks[MINUTES] = await sample(true); console.log(`end GC ${mb(marks[MINUTES].js)} ${mb(marks[MINUTES].cdp)} ${marks[MINUTES].nodes} ${marks[MINUTES].listeners}`); }
  const a = marks[2]; const b = marks[MINUTES];
  const growth = (b.cdp - a.cdp) / a.cdp; const nodeSlope = ((b.nodes - a.nodes) / a.nodes) / (MINUTES - 2);
  console.log(`heap after GC: minute 2 ${mb(a.cdp)} MB, minute ${MINUTES} ${mb(b.cdp)} MB, growth ${(growth * 100).toFixed(1)}%; nodes ${a.nodes} to ${b.nodes}, ${(nodeSlope * 100).toFixed(2)}% of minute-2 count per minute`);
  const ok = growth <= 0.2 && nodeSlope < 0.01;
  console.log(ok ? 'PASS' : 'FAIL');
  await browser.close();
  process.exit(ok ? 0 : 1);
})();
