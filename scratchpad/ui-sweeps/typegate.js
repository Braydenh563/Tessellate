// L342 typing gate: a 20,000 word document at 4x CPU, typed at the top, in Live then Source.
// Prints, per view, keydown/input event durations (mean, p50, p95, max) and long tasks inside
// the burst (ltIn, ltInMax); the gate is p95 under 50 ms and no long task over 50 ms.
//
//   BASE=http://127.0.0.1:8871 node scratchpad/ui-sweeps/typegate.js
//
// Options:
//   VIEWS=live        only these views (default live,source)
//   BUSY=1            a burst trace: main-thread ms a key by event (style, layout, recalcs ...)
//   BUSYOUT=f.json    keep that trace (read it with chrome://tracing or a short script)
//   EXP_CSS="..."     an adopted sheet before typing (the CSP refuses a <style>): A/B a rule
//   BARE=1            the floor instead: a blank page with the app's CodeMirror bundle, the same
//                     document, line wrapping and markdown (MODE=wrap,md,sel adds drawSelection,
//                     history and the default keymap); no server needed
// Measured with it (L342, 2026-11-21): bare p95 24 to 40, main thread 11 to 14 ms a key; the app
// 41 ms; the emblem's breath paused, event mean 43 to 33 ms.
const { boot } = require("./lib.js");
const { chromium } = require("/opt/node22/lib/node_modules/playwright");
const fs = require("fs");
const PHRASE = " the quick brown fox jumps over the lazy dog";
const KEYS = PHRASE.length;

function busySummary(busy) {
  const main = busy.find((e) => e.name === "thread_name" && e.args && e.args.name === "CrRendererMain" && busy.some((x) => x.pid === e.pid && x.name === "UpdateLayoutTree"));
  const ev = busy.filter((e) => e.ph === "X" && main && e.pid === main.pid && e.tid === main.tid && typeof e.tdur === "number");
  const sum = (n) => Math.round(ev.filter((e) => e.name === n).reduce((a, e) => a + e.tdur, 0) / KEYS / 10) / 100;
  const cnt = (n) => Math.round((ev.filter((e) => e.name === n).length / KEYS) * 10) / 10;
  return { task: sum("ThreadControllerImpl::RunTask") || sum("RunTask"), style: sum("UpdateLayoutTree"), recalcs: cnt("UpdateLayoutTree"), layout: sum("Layout"), layouts: cnt("Layout"), layerize: sum("Layerize"), prePaint: sum("PrePaint"), paint: sum("Paint") };
}

const ARM = () => {
  window.__evt = []; window.__lt = []; window.__t0 = null; window.__t1 = null;
  if (window.__po) window.__po.disconnect();
  if (window.__po2) window.__po2.disconnect();
  window.__po = new PerformanceObserver((l) => { for (const e of l.getEntries()) if (e.name === "keydown" || e.name === "input") { window.__evt.push(e.duration); window.__t0 = Math.min(window.__t0 ?? 1e12, e.startTime); window.__t1 = Math.max(window.__t1 ?? 0, e.startTime + e.duration); } });
  window.__po.observe({ type: "event", durationThreshold: 16, buffered: false });
  window.__po2 = new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__lt.push([e.startTime, e.duration]); });
  window.__po2.observe({ type: "longtask", buffered: false });
};
const READ = () => {
  const ds = window.__evt.slice().sort((a, b) => a - b);
  const p = (q) => (ds.length ? ds[Math.min(ds.length - 1, Math.floor(q * ds.length))] : 0);
  const lt = window.__lt.filter(([s]) => s >= window.__t0 && s <= window.__t1);
  return { mean: Math.round(ds.reduce((a, b) => a + b, 0) / (ds.length || 1)), n: ds.length, p50: Math.round(p(0.5)), p95: Math.round(p(0.95)), max: Math.round(ds[ds.length - 1] || 0), ltIn: lt.length, ltInMax: Math.round(Math.max(0, ...lt.map((x) => x[1]))) };
};

async function burst(page, cdp, label, target) {
  await page.click(target);
  await page.keyboard.press("Control+Home");
  await page.waitForTimeout(1500);
  let busy = null;
  if (process.env.BUSY) {
    busy = [];
    const on = (d) => busy.push(...d.value);
    cdp.on("Tracing.dataCollected", on);
    busy.off = () => cdp.off("Tracing.dataCollected", on);
    await cdp.send("Tracing.start", { categories: "toplevel,devtools.timeline,v8.execute", transferMode: "ReportEvents" });
  }
  await page.evaluate(ARM);
  await page.keyboard.type(PHRASE, { delay: 40 });
  if (busy) {
    await page.waitForTimeout(300);
    await cdp.send("Tracing.end");
    await new Promise((res) => cdp.once("Tracing.tracingComplete", res));
    busy.off();
    if (process.env.BUSYOUT) fs.writeFileSync(process.env.BUSYOUT, JSON.stringify(busy));
    console.log("busy", JSON.stringify(busySummary(busy)));
  }
  await page.waitForTimeout(1200);
  console.log(label, JSON.stringify(await page.evaluate(READ)));
}

async function bare() {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  await page.setContent("<!doctype html><html><body style='margin:0'><div id=h style='height:800px;width:760px;margin:40px auto;display:flex'></div></body></html>");
  await page.addScriptTag({ path: require("path").join(__dirname, "../../frontend/vendor/codemirror/codemirror.min.js") });
  const cdp = await ctx.newCDPSession(page);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
  await page.evaluate((mode) => {
    const CM = window.CM6;
    const w = [];
    for (let i = 0; i < 20000; i += 1) w.push(i % 17 === 0 ? "\n\n## Section " + i : "word" + i);
    const ext = [];
    if (mode.includes("wrap")) ext.push(CM.view.EditorView.lineWrapping);
    if (mode.includes("md")) ext.push(CM.markdown.markdown());
    if (mode.includes("sel")) ext.push(CM.view.drawSelection(), CM.commands.history(), CM.view.keymap.of(CM.commands.defaultKeymap));
    ext.push(CM.view.EditorView.theme({ "&": { height: "100%", width: "100%" }, ".cm-scroller": { overflow: "auto" } }));
    window.v = new CM.view.EditorView({ doc: "# Big document\n\n" + w.join(" "), extensions: ext, parent: document.getElementById("h") });
  }, process.env.MODE || "wrap,md");
  await page.waitForTimeout(3000);
  await burst(page, cdp, "bare", ".cm-content");
  await browser.close();
}

async function app() {
  const { browser, ctx, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const cdp = await ctx.newCDPSession(page);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
  const dismiss = async () => {
    const open = await page.evaluate(() => !!document.querySelector(".confirm-overlay"));
    if (open) { await page.keyboard.press("Escape"); await page.waitForTimeout(500); }
  };
  await page.evaluate(async () => {
    const r = await api("/documents", { method: "POST", body: JSON.stringify({ title: "Typing latency", content: "" }) });
    const doc = await r.json();
    switchTab("documents");
    await openDocument(doc.id);
  });
  await page.waitForTimeout(2500);
  await page.evaluate(() => {
    const w = [];
    for (let i = 0; i < 20000; i += 1) w.push(i % 17 === 0 ? "\n\n## Section " + i : "word" + i);
    docSurface().text = "# Big document\n\n" + w.join(" ");
    docSurfaceInput();
  });
  await page.waitForTimeout(4000);
  await page.evaluate(() => docLoadWordlist());
  await page.waitForFunction(() => docWordlistReady(), null, { timeout: 20000 }).catch(() => console.log("no word list"));
  await page.evaluate(() => { docCmApplySpellcheck(); docSurfaceInput(); });
  await page.waitForTimeout(3000);
  if (process.env.EXP_CSS) {
    await page.evaluate((c) => { const sh = new CSSStyleSheet(); sh.replaceSync(c); document.adoptedStyleSheets = [...document.adoptedStyleSheets, sh]; }, process.env.EXP_CSS);
  }
  for (const view of (process.env.VIEWS || "live,source").split(",")) {
    await page.evaluate((v) => setDocView(v), view);
    await page.waitForTimeout(1200);
    await dismiss();
    await burst(page, cdp, view, "#doc-editor .cm-content");
  }
  await browser.close();
}

(process.env.BARE ? bare() : app()).catch((e) => { console.error(e.message.slice(0, 400)); process.exit(1); });
