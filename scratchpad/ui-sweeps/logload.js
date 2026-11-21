// Sustained load against the real log stream (LEDGER L607 / L967).
//
//   BASE=http://127.0.0.1:8874 DURATION=300 WORKERS=8 node scratchpad/ui-sweeps/logload.js
//
// HTTP workers hit many routes (reads, searches, 404s, validation errors, job
// kicks) so the server logs heavily, while headless Chromium sits on Settings,
// Logs and samples: the live pill, rows in the DOM, long tasks, frame gaps,
// filter latency, and the JS heap. Numbers go to stdout as JSON lines.
const { boot, BASE, PW } = require("./lib.js");
const DURATION = Number(process.env.DURATION || 120) * 1000;
const WORKERS = Number(process.env.WORKERS || 8);
const NOBROWSER = !!process.env.NOBROWSER;

const READS = ["/entries?limit=50", "/stats", "/health", "/graph/structure", "/jobs", "/jobs/last-runs",
  "/library", "/boards", "/count", "/most-accessed", "/query?q=garden", "/search?q=recipe", "/tasks",
  "/activity", "/changes", "/nope-" , "/entries/999999", "/logs/stats", "/reference-counts"];
const POSTS = [["/health/self-check", {}], ["/entries", { content: "load note " }], ["/suggest-tags", { content: "garden recipe" }],
  ["/jobs/passes/nope/run", {}], ["/entries", { content: "" }]];

async function main() {
  const r = await fetch(BASE + "/auth/unlock", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ password: PW }) });
  const token = (await r.json()).token;
  const h = { "X-Auth-Token": token, "Content-Type": "application/json" };
  const end = Date.now() + DURATION;
  const stat = { sent: 0, byStatus: {} };
  const worker = async () => {
    while (Date.now() < end) {
      try {
        let res;
        if (Math.random() < 0.15) {
          const [p, b] = POSTS[Math.floor(Math.random() * POSTS.length)];
          res = await fetch(BASE + p, { method: "POST", headers: h, body: JSON.stringify(b.content ? { content: b.content + Math.random() } : b) });
        } else {
          let p = READS[Math.floor(Math.random() * READS.length)];
          if (p.endsWith("-")) p += Math.random();
          res = await fetch(BASE + p, { headers: h });
        }
        await res.arrayBuffer();
        stat.sent++; stat.byStatus[res.status] = (stat.byStatus[res.status] || 0) + 1;
      } catch (e) { stat.byStatus.err = (stat.byStatus.err || 0) + 1; }
    }
  };
  const workers = Array.from({ length: WORKERS }, worker);

  let browserDone = Promise.resolve();
  if (!NOBROWSER) {
    browserDone = (async () => {
      const { browser, page } = await boot();
      await page.addInitScript(() => {});
      await page.evaluate(() => {
        window.__lt = { count: 0, total: 0, max: 0 }; window.__fr = { n: 0, gaps: [], last: performance.now() };
        new PerformanceObserver((l) => { for (const e of l.getEntries()) { __lt.count++; __lt.total += e.duration; __lt.max = Math.max(__lt.max, e.duration); } }).observe({ entryTypes: ["longtask"] });
        const tick = (t) => { const g = t - __fr.last; __fr.last = t; __fr.n++; if (g > 50) __fr.gaps.push(Math.round(g)); requestAnimationFrame(tick); };
        requestAnimationFrame(tick);
      });
      //: Cost per call of the log page's own hot functions while the stream feeds it.
      await page.evaluate(() => {
        window.__fn = {};
        for (const name of ["sortLogRecords", "renderLogList", "renderLogTerminal", "logMatchesFilters"]) {
          const orig = window[name]; const acc = (__fn[name] = { calls: 0, ms: 0, max: 0 });
          window[name] = function (...a) { const t = performance.now(); try { return orig.apply(this, a); } finally { const d = performance.now() - t; acc.calls++; acc.ms += d; acc.max = Math.max(acc.max, d); } };
        }
      });
      await page.evaluate(() => openSettingsModal("logs"));
      await page.waitForTimeout(1500);
      const snap = () => page.evaluate(() => {
        const mem = performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) : null;
        const lt = { ...__lt }; const gaps = __fr.gaps.splice(0);
        return {
          pill: document.getElementById("log-live")?.dataset.state, pillText: document.getElementById("log-live")?.textContent.trim(),
          records: typeof logRecords !== "undefined" ? logRecords.length : null,
          listRows: document.querySelectorAll("#log-list > li").length, termRows: document.querySelectorAll("#log-terminal > *").length,
          domNodes: document.getElementsByTagName("*").length, heapMB: mem,
          longTasks: lt.count, longTaskMs: Math.round(lt.total), longTaskMax: Math.round(lt.max),
          fn: Object.fromEntries(Object.entries(__fn).map(([k, v]) => [k, `${v.calls}x ${Math.round(v.ms)}ms max${Math.round(v.max)}`])),
          frames: __fr.n, gapsOver50: gaps.length, worstGap: gaps.length ? Math.max(...gaps) : 0,
        };
      });
      const filterProbe = () => page.evaluate(async () => {
        const out = {};
        const time = async (label, fn) => { const t = performance.now(); fn(); await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))); out[label] = Math.round(performance.now() - t); };
        const f = document.getElementById("log-filter");
        await time("typeFilterMs", () => { f.value = "GET"; f.dispatchEvent(new Event("input", { bubbles: true })); });
        await new Promise((r) => setTimeout(r, 300));
        await time("levelErrorMs", () => { const l = document.getElementById("log-level"); l.value = "error"; l.dispatchEvent(new Event("change", { bubbles: true })); });
        await time("levelResetMs", () => { const l = document.getElementById("log-level"); l.value = "all"; l.dispatchEvent(new Event("change", { bubbles: true })); f.value = ""; f.dispatchEvent(new Event("input", { bubbles: true })); });
        await time("viewTerminalMs", () => { document.querySelector('#log-view-toggle [data-view="terminal"]')?.click(); });
        await new Promise((r) => setTimeout(r, 300));
        await time("viewListMs", () => { document.querySelector('#log-view-toggle [data-view="list"]')?.click(); });
        return out;
      });
      const t0 = Date.now(); let i = 0;
      while (Date.now() < end) {
        await page.waitForTimeout(10000);
        const s = await snap();
        if (i % 3 === 1) Object.assign(s, await filterProbe());
        console.log(JSON.stringify({ t: Math.round((Date.now() - t0) / 1000), ...s, httpSent: stat.sent }));
        i++;
      }
      await browser.close();
    })();
  }
  await Promise.all([...workers, browserDone]);
  console.log(JSON.stringify({ done: true, ...stat }));
}
main().catch((e) => { console.error(e); process.exit(1); });
