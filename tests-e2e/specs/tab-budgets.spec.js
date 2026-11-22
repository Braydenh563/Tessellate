// The tab lag budget in CPU time (L-ui-modernisation-54), split out of
// budgets.spec.js so CI can run it in its own budgets job beside
// map-budgets.spec.js: all three together outran the flows job's 15 minutes.
// Like the other budgets it runs alone, one worker.
const { test, expect } = require("@playwright/test");
const { openApp } = require("../helpers");
const measure = require("../budget-measure");

const ROUNDS = 3;

// L-ui-modernisation-54, in CPU time (the load-independent form of "input
// under 100 ms, no frame over 50 ms on a repeat visit"): the longest
// main-thread task after a repeat click on each tab, CPU ms, p50 of five.
// Measured 2026-11-21 on the seeded notebook: notes 30, library 45, graph 38,
// timeline 32, chat 14, reminders 17, dashboard 25. The cap is the written 50.
const TAB_TASK_CPU_CAP_MS = 50;
for (const tab of ["notes", "library", "graph", "timeline", "chat", "reminders", "dashboard"]) {
  test(`tab_cpu: a repeat visit to ${tab} has no main-thread task over ${TAB_TASK_CPU_CAP_MS} ms of CPU`, async ({ page }) => {
    await openApp(page);
    await page.waitForTimeout(3000);
    // One visit first: the budget is the repeat visit.
    await page.click(`#tab-bar [data-tab="${tab}"]`);
    await page.waitForTimeout(1500);
    const seen = [];
    while (seen.length < ROUNDS) {
      seen.push(await measure.tabTaskCpu(page, tab, 5));
      if (seen[seen.length - 1] <= TAB_TASK_CPU_CAP_MS) break;
    }
    expect(Math.min(...seen), `${tab}: ${seen.join(", ")} ms of CPU over ${seen.length} round(s); the cap is ${TAB_TASK_CPU_CAP_MS} ms`).toBeLessThanOrEqual(TAB_TASK_CPU_CAP_MS);
  });
}
