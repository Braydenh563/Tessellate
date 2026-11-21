// The mind map's perf budgets, in CPU time (L-ui-modernisation-61 and -97).
//
// mapperf.js times frames on the wall clock, which a loaded runner skews by 3x
// to 8x. This reads the renderer thread's CPU time per task from a CDP trace under
// a 4x CPU throttle (tests-e2e/map-cpu-measure.js says why and how), so a busy
// neighbour cannot fail it and a slower code path still does. The budgets are
// the ones written in the ledger rows: open to painted at 500 topics under 1s,
// the worst pan, zoom task under 50ms at 50, 200 and 500, and 300 link sketches
// not doubling the worst task of a branch drag at 50 and 200 (and 500). Each
// figure is the median of three passes. Like the other budgets it runs alone.
const { test, expect } = require("@playwright/test");
const { openApp } = require("../helpers");
const measure = require("../map-cpu-measure");

test.describe.configure({ mode: "serial" });
// The runner's own trace takes a DOM snapshot around every mouse move, which put
// 60 to 110ms of CPU into the pan and zoom tasks of a 50 topic map (measured: 75 and
// 113ms with it, 11 and 12ms without), so the budget reads with it off.
test.use({ trace: "off", screenshot: "off", video: "off" });

let page;
let cdp;

test.beforeAll(async ({ browser }) => {
  test.setTimeout(120_000);
  const context = await browser.newContext();
  page = await context.newPage();
  await openApp(page);
  await page.evaluate(() => switchTab("library"));
  await page.waitForFunction(() => {
    const button = document.querySelector('#library-subtabs [data-target="library-view-whiteboard"]');
    if (!button) return false;
    if (!button.classList.contains("active")) { button.click(); return false; }
    return typeof window.initWhiteboard === "function" && typeof window.openWhiteboardBoard === "function";
  }, null, { timeout: 30_000, polling: 100 });
  await page.evaluate(() => initWhiteboard());
  cdp = await context.newCDPSession(page);
});

test.afterAll(async () => {
  if (page) await page.context().close();
});

for (const n of [50, 200, 500]) {
  test(`map CPU budgets at ${n} topics`, async () => {
    test.setTimeout(420_000);
    const { rows, ...med } = await measure.mapCpuMedians(page, cdp, n, { rate: 4, rounds: 3 });
    console.log("map cpu", JSON.stringify(med), "rounds", JSON.stringify(rows.map((r) => [r.openCpu, r.panWorst, r.zoomWorst, r.branchPlain, r.branchLinked])));
    expect(measure.failures(med), JSON.stringify(med)).toEqual([]);
    expect(med.links, "the link sketches were made").toBeGreaterThanOrEqual(300);
  });
}
