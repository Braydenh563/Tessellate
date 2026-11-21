// The six interaction timings of WORLD_CLASS_PLAN decision 54, in one place so
// the Playwright spec (CI) and scratchpad/ui-sweeps/budgets.js (the README's
// numbers) time exactly the same thing. Every function takes a Playwright
// `page` and returns milliseconds; p50 of `runs` unless noted. No imports:
// the spec and the sweep load different copies of Playwright.

const p50 = (values) => {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
};

// The app is up: splash and lock hidden, the opening curtain gone.
const APP_UP = () => {
  const splash = document.getElementById("boot-splash");
  const lock = document.getElementById("lock-overlay");
  return (
    (!splash || splash.classList.contains("hidden")) &&
    lock && lock.classList.contains("hidden") &&
    !document.documentElement.classList.contains("shell-curtain") &&
    typeof window.apiJson === "function"
  );
};

// Boot to first paint, and boot to the first click the app answers (the Notes
// tab showing a row). `openPage` gives a page in a fresh context with the
// stored session and an empty HTTP cache: the cold start a person sees after
// closing the window. Times come from the page's own clock, which starts at
// navigation, so the goto's own overhead is not counted either way.
async function boot(openPage, baseURL) {
  const page = await openPage();
  try {
    await page.goto(baseURL + "/", { waitUntil: "domcontentloaded" });
    await page.waitForFunction(APP_UP, null, { timeout: 60_000, polling: 20 });
    await page.click("#tab-btn-notes");
    await page.waitForFunction(
      () => { const tab = document.getElementById("tab-notes"); return tab && tab.offsetParent && document.querySelector("#entry-list li"); },
      null, { timeout: 60_000, polling: 10 }
    );
    return await page.evaluate(() => {
      const paint = performance.getEntriesByName("first-contentful-paint")[0];
      return { firstPaint: paint ? Math.round(paint.startTime) : null, firstInteraction: Math.round(performance.now()) };
    });
  } finally {
    await page.context().close();
  }
}

// Tab switch to the first page of rows settled (same count on two frames).
async function listPaint(page, runs = 7) {
  const times = [];
  for (let i = 0; i < runs; i++) {
    await page.evaluate(() => switchTab("dashboard"));
    await page.waitForTimeout(700);
    times.push(await page.evaluate(() => new Promise((resolve) => {
      const began = performance.now();
      switchTab("notes");
      const tick = () => {
        const tab = document.getElementById("tab-notes");
        if (tab && !tab.classList.contains("hidden") && document.querySelectorAll("#entry-list li").length > 0) {
          requestAnimationFrame(() => resolve(Math.round(performance.now() - began)));
        } else requestAnimationFrame(tick);
      };
      tick();
    })));
  }
  return p50(times);
}

// `GET /search` through the page's own `apiJson`, p50 over the queries after
// one warm call each (the first builds the caches a person's first search pays
// for once; boot pays it in the background, so it is not this interaction).
async function search(page, queries = ["harbour", "tides quay", "Note 42"], runs = 5) {
  return page.evaluate(async ({ queries, runs }) => {
    const times = [];
    for (const q of queries) {
      const url = `/search?q=${encodeURIComponent(q)}&limit=20`;
      await apiJson(url);
      for (let i = 0; i < runs; i++) {
        const began = performance.now();
        await apiJson(url);
        times.push(performance.now() - began);
      }
    }
    times.sort((a, b) => a - b);
    return Math.round(times[Math.floor(times.length / 2)]);
  }, { queries, runs });
}

// `openWhiteboardBoard` called, to every object in the DOM plus two frames.
async function boardOpen(page, boardId, objects, runs = 5) {
  const times = [];
  for (let i = 0; i < runs; i++) {
    await page.evaluate(() => switchTab("notes"));
    await page.waitForTimeout(500);
    await page.evaluate(() => switchTab("library"));
    await page.waitForFunction(() => {
      const button = document.querySelector('#library-subtabs [data-target="library-view-whiteboard"]');
      if (!button) return false;
      if (!button.classList.contains("active")) { button.click(); return false; }
      return typeof window.initWhiteboard === "function" && typeof window.openWhiteboardBoard === "function";
    }, null, { timeout: 30_000, polling: 100 });
    times.push(await page.evaluate(async ({ id, n }) => {
      const began = performance.now();
      openWhiteboardBoard(id);
      await new Promise((resolve) => {
        const tick = () => {
          const bar = document.getElementById("wb-topbar");
          const box = document.getElementById("whiteboard-container");
          if (bar && bar.offsetParent && box && box.offsetParent && document.querySelectorAll("#whiteboard-container .wb-object").length >= n) resolve();
          else setTimeout(tick, 5);
        };
        tick();
      });
      await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
      return Math.round(performance.now() - began);
    }, { id: boardId, n: objects }));
  }
  return p50(times);
}

// `openDocument` called, to resolved plus two frames.
async function documentOpen(page, documentId, runs = 5) {
  const times = [];
  for (let i = 0; i < runs; i++) {
    await page.evaluate(() => switchTab("notes"));
    await page.waitForTimeout(500);
    await page.evaluate(() => switchTab("documents"));
    await page.waitForFunction(() => typeof window.openDocument === "function", null, { timeout: 30_000, polling: 100 });
    await page.waitForTimeout(1500);
    times.push(await page.evaluate(async (id) => {
      const began = performance.now();
      await openDocument(id);
      await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
      return Math.round(performance.now() - began);
    }, documentId));
  }
  return p50(times);
}

// L-ui-modernisation-54, in CPU time. Wall-clock input delay and frame length
// double on a busy runner and say nothing about the code; the CPU a task burns
// (`tdur` in the trace, thread time) does not. Per repeat visit to `tab`: the
// longest main-thread task, in CPU ms, in the 300 ms after the click (later
// tasks are the companion's own idle). p50 over `runs`.
async function tabTaskCpu(page, tab, runs = 5) {
  const cdp = await page.context().newCDPSession(page);
  const times = [];
  try {
    for (let i = 0; i < runs; i++) {
      // Leave the tab first: a click on the open tab does nothing, and the
      // budget is the visit that comes back to it.
      await page.click(`#tab-bar [data-tab="${tab === "reminders" ? "timeline" : "reminders"}"]`);
      await page.waitForTimeout(900);
      const events = [];
      const onData = (d) => events.push(...d.value);
      cdp.on("Tracing.dataCollected", onData);
      const done = new Promise((resolve) => cdp.once("Tracing.tracingComplete", resolve));
      await cdp.send("Tracing.start", { categories: "devtools.timeline,disabled-by-default-devtools.timeline", transferMode: "ReportEvents" });
      await page.click(`#tab-bar [data-tab="${tab}"]`);
      await page.waitForTimeout(700);
      await cdp.send("Tracing.end");
      await done;
      cdp.off("Tracing.dataCollected", onData);
      const main = events.find((e) => e.name === "thread_name" && e.args.name === "CrRendererMain" && events.some((x) => x.tid === e.tid && x.name === "RunTask"));
      const own = events.filter((e) => main && e.pid === main.pid && e.tid === main.tid && e.ph === "X");
      const click = own.find((e) => e.name === "EventDispatch" && e.args && e.args.data && e.args.data.type === "click");
      const t0 = click ? click.ts : Infinity;
      const tasks = own.filter((e) => e.name === "RunTask" && e.ts >= t0 - 1000 && e.ts < t0 + 300000);
      times.push(Math.round(Math.max(0, ...tasks.map((x) => (x.tdur || x.dur) / 1000))));
    }
  } finally { await cdp.detach(); }
  return p50(times);
}

// L-ui-modernisation-95, in CPU time: the on-CPU ms the renderers' main
// threads have burned, from /proc (Linux, where CI runs). The thread whose id
// is the process id is the main thread.
async function mainCpuMs(browser) {
  const fs = require("fs");
  const session = await browser.newBrowserCDPSession();
  const { processInfo } = await session.send("SystemInfo.getProcessInfo");
  await session.detach();
  let ns = 0;
  for (const proc of processInfo.filter((x) => x.type === "renderer")) {
    try { ns += Number(fs.readFileSync(`/proc/${proc.id}/task/${proc.id}/schedstat`, "utf8").split(" ")[0]); } catch (e) { /* ended */ }
  }
  return ns / 1e6;
}

// Main-thread CPU ms per second over `ms` of idle on `page`.
async function idleCpuPerSecond(browser, page, ms = 4000) {
  const before = await mainCpuMs(browser);
  await page.waitForTimeout(ms);
  return (await mainCpuMs(browser) - before) / (ms / 1000);
}

module.exports = { p50, boot, listPaint, search, boardOpen, documentOpen, tabTaskCpu, mainCpuMs, idleCpuPerSecond };
