// L-documents-89: input-to-paint of a drag pan on the diagram picture, at 4x CPU (CDP), 390 touch or 1440 mouse.
//   BASE=http://127.0.0.1:8858 node scratchpad/ui-sweeps/diagram-pan-latency.js [width] [rate]
// A move's latency is the time from its first capture-phase listener to the frame after the next rAF
// (a MessageChannel message posted from a rAF lands after that frame's paint).
const os = require("os");
process.env.BASE ||= "http://127.0.0.1:8858";
process.env.SCRATCH ||= os.tmpdir();
const { boot } = require("./lib.js");
const W = Number(process.argv[2] || 1440), RATE = Number(process.argv[3] || 4), touch = W < 600;
const big = "flowchart TD\n  A0[Start]\n" + Array.from({ length: 59 }, (_, i) => `  A${i + 1}[Step ${i + 1}]\n  A${Math.floor(i / 2)}-->A${i + 1}`).join("\n") + "\n";
(async () => {
  const { page } = await boot({ viewport: { width: W, height: touch ? 844 : 900 }, ...(touch ? { hasTouch: true, isMobile: true } : {}) });
  await page.evaluate(async (c) => {
    const r = await api("/documents", { method: "POST", body: JSON.stringify({ title: "PL " + Date.now() + ".mmd", content: c, file_type: "mmd" }) });
    switchTab("documents");
    await openDocument((await r.json()).id);
    setDocView("canvas", { persist: false });
  }, big);
  await page.waitForSelector(".dgm-block", { state: "attached", timeout: 15000 });
  await page.waitForTimeout(2500);
  for (let i = 0; i < 4; i++) await page.click(".dgm-zoom button[aria-label='Zoom in']").catch((e) => console.log("zoom", String(e).slice(0, 80)));
  await page.waitForTimeout(500);
  await page.evaluate(() => {
    window.__lat = [];
    const fig = document.querySelector(".dgm-picture");
    const mc = new MessageChannel();
    const starts = [];
    mc.port1.onmessage = () => window.__lat.push(performance.now() - starts.shift());
    fig.addEventListener("pointermove", () => { const t = performance.now(); starts.push(t); requestAnimationFrame(() => mc.port2.postMessage(0)); }, true);
  });
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: RATE });
  const box = await page.evaluate(() => { const r = document.querySelector(".dgm-picture").getBoundingClientRect(); const top = Math.max(r.top, 0), bot = Math.min(r.bottom, innerHeight); return { x: r.x + r.width * 0.7, y: (top + bot) / 2 }; });
  const sl = () => page.evaluate(() => { const f = document.querySelector(".dgm-picture"); return [f.scrollLeft, f.scrollTop]; });
  await cdp.send("Performance.enable");
  const metrics = async () => Object.fromEntries((await cdp.send("Performance.getMetrics")).metrics.map((m) => [m.name, m.value]));
  await page.evaluate(() => {
    window.__mut = {};
    new MutationObserver((list) => { for (const r of list) { const t = r.target; const k = `${r.type}:${r.attributeName || ""}:${(t.className && t.className.baseVal === undefined ? String(t.className) : "svg").slice(0, 40)}`; window.__mut[k] = (window.__mut[k] || 0) + 1; } }).observe(document.body, { subtree: true, attributes: true, childList: true, characterData: true });
  });
  if (process.env.PROFILE) { await cdp.send("Profiler.enable"); await cdp.send("Profiler.start"); }
  const m0 = await metrics();
  const s0 = await sl();
  console.log("roomy", JSON.stringify(await page.evaluate(() => { const f = document.querySelector(".dgm-picture"); return [f.scrollWidth, f.clientWidth, f.scrollHeight, f.clientHeight]; })));
  //: 390 is a finger (CDP touch events: pointermove with pointerType touch); 1440 is the right button held (the middle button), which pans
  //: (a plain left drag is the marquee).
  if (touch) {
    await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x: box.x, y: box.y }] });
    for (let i = 1; i <= 90; i++) { await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x: box.x - i * 3, y: box.y - i * 2 }] }); await page.waitForTimeout(8); }
    await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
  } else {
    await page.mouse.move(box.x, box.y);
    await page.mouse.down({ button: "middle" });
    for (let i = 0; i < 90; i++) { await page.mouse.move(box.x - i * 3, box.y - i * 2); await page.waitForTimeout(8); }
    await page.mouse.up({ button: "middle" });
  }
  await page.waitForTimeout(700);
  const s1 = await sl();
  if (process.env.PROFILE) {
    const { profile } = await cdp.send("Profiler.stop");
    const self = new Map();
    const byId = new Map(profile.nodes.map((n) => [n.id, n]));
    const dt = profile.timeDeltas; 
    profile.samples.forEach((id, i) => { const n = byId.get(id); const k = `${n.callFrame.functionName || "(anon)"} ${n.callFrame.url.split("/").pop()}:${n.callFrame.lineNumber + 1}`; self.set(k, (self.get(k) || 0) + (dt[i] || 0)); });
    console.log("self ms", JSON.stringify([...self].sort((a, b) => b[1] - a[1]).slice(0, 12).map(([k, v]) => [k, Math.round(v / 1000)])));
  }
  const m1 = await metrics();
  const cost = Object.fromEntries(["ScriptDuration", "LayoutDuration", "RecalcStyleDuration", "TaskDuration", "LayoutCount", "RecalcStyleCount"].map((k) => [k, +((m1[k] - m0[k]) * (k.endsWith("Count") ? 1 : 1000)).toFixed(0)]));
  console.log("cost(ms or count)", JSON.stringify(cost));
  console.log("mut", JSON.stringify(await page.evaluate(() => Object.entries(window.__mut).sort((a, b) => b[1] - a[1]).slice(0, 8))));
  const lat = await page.evaluate(() => window.__lat);
  const s = [...lat].sort((a, b) => a - b);
  const q = (p) => +(s[Math.min(s.length - 1, Math.floor(s.length * p))] || 0).toFixed(1);
  console.log(JSON.stringify({ W, rate: RATE, n: s.length, p50: q(0.5), p95: q(0.95), max: q(1), scrolled: [Math.round(s1[0] - s0[0]), Math.round(s1[1] - s0[1])] }));
  process.exit(0);
})();
