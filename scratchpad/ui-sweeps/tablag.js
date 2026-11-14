// Per-tab lag budget (UI_MODERNISATION_PLAN 1249 (6)): input under 100 ms and no frame over 50 ms
// on a repeat visit to each tab. Event Timing for the press, long-animation-frame for frames.
//   BASE=http://127.0.0.1:8781/ node scratchpad/ui-sweeps/tablag.js   (exit 1 when a tab is over)
const { chromium } = require("playwright");
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
  await p.goto(process.env.BASE || "http://127.0.0.1:8781/", { waitUntil: "domcontentloaded" });
  await p.waitForSelector("#lock-password", { timeout: 20000 }).catch(() => {});
  if (await p.$("#lock-password")) { await p.fill("#lock-password", "testpassword123"); await p.click("#lock-submit"); }
  await p.waitForTimeout(5000);
  await p.evaluate(() => {
    window.__lag = { events: [], frames: [] };
    new PerformanceObserver((l) => l.getEntries().forEach((e) => window.__lag.events.push([e.name, e.duration]))).observe({ type: "event", durationThreshold: 16, buffered: false });
    new PerformanceObserver((l) => l.getEntries().forEach((e) => window.__lag.frames.push(e.duration))).observe({ type: "long-animation-frame", buffered: false });
  });
  const tabs = ["notes", "library", "graph", "timeline", "chat", "reminders", "dashboard"];
  const out = {};
  for (let round = 0; round < 2; round++) for (const t of tabs) {
    await p.evaluate(() => { window.__lag.events = []; window.__lag.frames = []; });
    await p.click(`#tab-bar [data-tab="${t}"]`);
    await p.waitForTimeout(1500);
    const r = await p.evaluate(() => ({ input: Math.max(0, ...window.__lag.events.filter((e) => /pointer|click|mouse/.test(e[0])).map((e) => e[1])), frame: Math.max(0, ...window.__lag.frames) }));
    out[`${t}${round ? "" : "@first"}`] = [Math.round(r.input), Math.round(r.frame)];
  }
  console.log(JSON.stringify(out));
  const over = Object.entries(out).filter(([k, [input, frame]]) => !k.endsWith("@first") && (input > 100 || frame > 50));
  for (const [k, v] of over) console.log(`FAIL ${k}: input ${v[0]} ms, frame ${v[1]} ms`);
  await b.close();
  process.exit(over.length ? 1 : 0);
})();
