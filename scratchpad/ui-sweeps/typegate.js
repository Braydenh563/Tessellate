// L342 typing gate, read from main-thread CPU so a busy box does not move it (owner ruling
// 2026-11-21): a 20,000 word document at 4x CPU, typed at the top, in Live then Source.
// Per key: CDP Performance.getMetrics ThreadTime, TaskDuration and ScriptDuration deltas over the key's
// window (keydown to the frame after it); idle windows of the same shape give the floor (the
// probe itself and the emblem's breath). Then the same burst under a trace: long tasks (main
// thread RunTask over 50 ms of thread CPU). Gate (hub ruling 2026-11-21): net ThreadTime p95
// under 50 ms a key, net being each key's window less this run's idle-window median, no long
// task, and the idle window itself under 15 ms, in both views; a miss sets the exit code.
//
//   BASE=http://127.0.0.1:8871 node scratchpad/ui-sweeps/typegate.js
//
// Options:
//   VIEWS=live        only these views (default live,source)
//   PROFILE=1         a sampled CPU profile of the burst: self ms a key by function (top 30)
//   PROFOUT=f         keep that profile as f.<view>.cpuprofile (inclusive times, callers)
//   BUSYOUT=f.json    keep the burst trace (style, layout, recalcs a key are printed anyway)
//   TRACECATS=...     more trace categories, e.g. disabled-by-default-devtools.timeline.invalidationTracking
//   EXP_CSS="..."     an adopted sheet before typing (the CSP refuses a <style>): A/B a rule
//   BARE=1            the floor instead: a blank page with the app's CodeMirror bundle, the same
//                     document, line wrapping and markdown (MODE=wrap,md,sel adds drawSelection,
//                     history and the default keymap); no server needed
const { boot } = require("./lib.js");
const { chromium } = require("/opt/node22/lib/node_modules/playwright");
const fs = require("fs");
const P95_BUDGET_MS = 50;
const LONG_TASK_BUDGET_MS = 50;
//: The gate's own cost (two getMetrics calls and a settle frame) is subtracted, so it is capped:
//: a probe that grew would otherwise buy the page its budget.
const IDLE_FLOOR_CAP_MS = 15;
const THROTTLE = 4;
const WORDS = 20000;
const PHRASE = " the quick brown fox jumps over the lazy dog";
const KEYS = PHRASE.length;
const r1 = (x) => Math.round(x * 10) / 10;


const settle = (page) => page.evaluate(() => new Promise((r) => requestAnimationFrame(() => setTimeout(r, 0))));
const metrics = async (cdp) => {
  const m = {};
  for (const x of (await cdp.send("Performance.getMetrics")).metrics) m[x.name] = x.value;
  //: The gate reads ThreadTime, the main thread's own CPU (hub ruling 2026-11-21): TaskDuration
  //: also holds the waits inside a task, and headless those are compositor idle waits (a cold
  //: open read ThreadTime 365 against TaskDuration 968 ms). Both are printed.
  return [m["TaskDuration"] * 1000, m["ScriptDuration"] * 1000, (m["ThreadTime"] || 0) * 1000];
};
const stats = (xs) => {
  const s = xs.slice().sort((a, b) => a - b);
  const q = (f) => s[Math.min(s.length - 1, Math.floor(f * s.length))];
  return { mean: r1(s.reduce((a, b) => a + b, 0) / s.length), p50: r1(q(0.5)), p95: r1(q(0.95)), max: r1(s[s.length - 1]) };
};

async function keyWindow(page, cdp, ch) {
  const [t0, s0, c0] = await metrics(cdp);
  if (ch) await page.keyboard.type(ch);
  await settle(page);
  const [t1, s1, c1] = await metrics(cdp);
  return [t1 - t0, s1 - s0, c1 - c0];
}

async function cpuPerKey(page, cdp) {
  await cdp.send("Performance.enable", { timeDomain: "threadTicks" }).catch(() => cdp.send("Performance.enable"));
  const idle = [];
  const idleThread = [];
  for (let i = 0; i < 24; i += 1) {
    const [t, , c] = await keyWindow(page, cdp, "");
    idle.push(t);
    idleThread.push(c);
  }
  const task = [];
  const script = [];
  const thread = [];
  for (const ch of PHRASE) {
    const [t, s, c] = await keyWindow(page, cdp, ch);
    task.push(t);
    script.push(s);
    thread.push(c);
  }
  await cdp.send("Performance.disable");
  //: Net page work: each key's window less the median idle window of this run, same calls,
  //: same throttle, same page (no constant: the floor moves with the renderer and the box).
  const floor = stats(idleThread).p50;
  const net = stats(thread.map((c) => c - floor));
  return { task: stats(task), script: stats(script), thread: stats(thread), net, floor, idle: stats(idle), idleThread: stats(idleThread) };
}

function traceSummary(ev) {
  const names = ev.filter((e) => e.name === "thread_name" && e.args && e.args.name === "CrRendererMain");
  const main = names.find((n) => ev.some((x) => x.pid === n.pid && x.name === "UpdateLayoutTree")) || names[0];
  const on = ev.filter((e) => e.ph === "X" && main && e.pid === main.pid && e.tid === main.tid);
  const sum = (n) => r1(on.filter((e) => e.name === n).reduce((a, e) => a + (e.tdur ?? e.dur ?? 0), 0) / KEYS / 1000);
  const cnt = (n) => r1(on.filter((e) => e.name === n).length / KEYS);
  const tasks = on.filter((e) => e.name === "ThreadControllerImpl::RunTask" || e.name === "RunTask");
  //: Long by thread CPU (tdur), the gate's measure; by wall (dur) printed beside it.
  const cpu = (e) => (e.tdur ?? e.dur) / 1000;
  const long = tasks.filter((e) => cpu(e) > LONG_TASK_BUDGET_MS);
  return {
    longTasks: long.length, longMax: r1(Math.max(0, ...tasks.map(cpu))),
    longWall: tasks.filter((e) => e.dur / 1000 > LONG_TASK_BUDGET_MS).length, longWallMax: r1(Math.max(0, ...tasks.map((e) => e.dur / 1000))),
    perKey: { style: sum("UpdateLayoutTree"), recalcs: cnt("UpdateLayoutTree"), layout: sum("Layout"), layouts: cnt("Layout"), layerize: sum("Layerize"), prePaint: sum("PrePaint"), paint: sum("Paint"), script: sum("FunctionCall") },
  };
}

async function traced(page, cdp) {
  const ev = [];
  const on = (d) => ev.push(...d.value);
  cdp.on("Tracing.dataCollected", on);
  await cdp.send("Tracing.start", { categories: "toplevel,devtools.timeline" + (process.env.TRACECATS ? "," + process.env.TRACECATS : ""), transferMode: "ReportEvents" });
  await page.keyboard.type(PHRASE, { delay: 40 });
  await settle(page);
  await cdp.send("Tracing.end");
  await new Promise((res) => cdp.once("Tracing.tracingComplete", res));
  cdp.off("Tracing.dataCollected", on);
  if (process.env.BUSYOUT) fs.writeFileSync(process.env.BUSYOUT, JSON.stringify(ev));
  return traceSummary(ev);
}

async function profiled(page, cdp) {
  await cdp.send("Profiler.enable");
  await cdp.send("Profiler.setSamplingInterval", { interval: 200 });
  await cdp.send("Profiler.start");
  await page.keyboard.type(PHRASE, { delay: 40 });
  await settle(page);
  const { profile } = await cdp.send("Profiler.stop");
  if (process.env.PROFOUT) fs.writeFileSync(process.env.PROFOUT + "." + page.__view + ".cpuprofile", JSON.stringify(profile));
  const byId = new Map(profile.nodes.map((n) => [n.id, n]));
  const self = new Map();
  for (let i = 0; i < profile.samples.length; i += 1) {
    const f = byId.get(profile.samples[i]).callFrame;
    const k = (f.functionName || "(anon)") + " " + (f.url || "").split("/").pop().split("?")[0] + ":" + (f.lineNumber + 1);
    self.set(k, (self.get(k) || 0) + (profile.timeDeltas[i] || 0));
  }
  return [...self].sort((a, b) => b[1] - a[1]).slice(0, 30).map(([k, us]) => [k, r1(us / 1000 / KEYS)]);
}

async function burst(page, cdp, label, target) {
  await page.click(target);
  await page.keyboard.press("Control+Home");
  await page.waitForTimeout(1500);
  const cpu = await cpuPerKey(page, cdp);
  await page.waitForTimeout(1200);
  const tr = await traced(page, cdp);
  await page.waitForTimeout(1200);
  const prof = process.env.PROFILE ? await profiled(page, cdp) : null;
  const pass = cpu.net.p95 < P95_BUDGET_MS && tr.longTasks === 0 && cpu.floor < IDLE_FLOOR_CAP_MS;
  console.log(label, JSON.stringify({ taskMsPerKey: cpu.task, scriptMsPerKey: cpu.script, threadMsPerKey: cpu.thread, netThreadMsPerKey: cpu.net, idleFloorMs: cpu.floor, idleWindowMs: cpu.idle, idleThreadMs: cpu.idleThread, longTasks: tr.longTasks, longMax: tr.longMax, longWall: tr.longWall, longWallMax: tr.longWallMax, perKey: tr.perKey }));
  if (prof) for (const [k, ms] of prof) console.log("  self", ms, k);
  console.log("GATE", label, pass ? "pass" : "miss", "net thread p95", cpu.net.p95, "<", P95_BUDGET_MS, "(raw", cpu.thread.p95, "less idle floor", cpu.floor, "<", IDLE_FLOOR_CAP_MS + "; task p95", cpu.task.p95 + ") long tasks by thread CPU over", LONG_TASK_BUDGET_MS, ":", tr.longTasks);
  if (!pass) process.exitCode = 1;
}

async function bare() {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  await page.setContent("<!doctype html><html><body style='margin:0'><div id=h style='height:800px;width:760px;margin:40px auto;display:flex'></div></body></html>");
  await page.addScriptTag({ path: require("path").join(__dirname, "../../frontend/vendor/codemirror/codemirror.min.js") });
  const cdp = await ctx.newCDPSession(page);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: THROTTLE });
  await page.evaluate(([mode, words]) => {
    const CM = window.CM6;
    const w = [];
    for (let i = 0; i < words; i += 1) w.push(i % 17 === 0 ? "\n\n## Section " + i : "word" + i);
    const ext = [];
    if (mode.includes("wrap")) ext.push(CM.view.EditorView.lineWrapping);
    if (mode.includes("md")) ext.push(CM.markdown.markdown());
    if (mode.includes("sel")) ext.push(CM.view.drawSelection(), CM.commands.history(), CM.view.keymap.of(CM.commands.defaultKeymap));
    ext.push(CM.view.EditorView.theme({ "&": { height: "100%", width: "100%" }, ".cm-scroller": { overflow: "auto" } }));
    window.v = new CM.view.EditorView({ doc: "# Big document\n\n" + w.join(" "), extensions: ext, parent: document.getElementById("h") });
  }, [process.env.MODE || "wrap,md", WORDS]);
  await page.waitForTimeout(3000);
  await burst(page, cdp, "bare", ".cm-content");
  await browser.close();
}

async function app() {
  const { browser, ctx, page } = await boot({ viewport: { width: 1440, height: 900 } });
  const cdp = await ctx.newCDPSession(page);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: THROTTLE });
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
  await page.evaluate((words) => {
    const w = [];
    for (let i = 0; i < words; i += 1) w.push(i % 17 === 0 ? "\n\n## Section " + i : "word" + i);
    docSurface().text = "# Big document\n\n" + w.join(" ");
    docSurfaceInput();
  }, WORDS);
  await page.waitForTimeout(4000);
  await page.evaluate(() => docLoadWordlist());
  await page.waitForFunction(() => docWordlistReady(), null, { timeout: 20000 }).catch(() => console.log("no word list"));
  await page.evaluate(() => { docCmApplySpellcheck(); docSurfaceInput(); });
  await page.waitForTimeout(3000);
  if (process.env.EXP_CSS) {
    await page.evaluate((c) => { const sh = new CSSStyleSheet(); sh.replaceSync(c); document.adoptedStyleSheets = [...document.adoptedStyleSheets, sh]; }, process.env.EXP_CSS);
  }
  for (const view of (process.env.VIEWS || "live,source").split(",")) {
    page.__view = view;
    await page.evaluate((v) => setDocView(v), view);
    await page.waitForTimeout(1200);
    await dismiss();
    await burst(page, cdp, view, "#doc-editor .cm-content");
  }
  await browser.close();
}

(process.env.BARE ? bare() : app()).catch((e) => { console.error(e.message.slice(0, 400)); process.exit(1); });
