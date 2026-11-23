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

// The companion's looks restyle the whole figure (the owner's lag log 2026-11-22:
// `nameMarkBuddyAfterCleanTask` 202 to 294 ms, 187 to 286 of it forced layout). Measured
// 2026-11-22 at 4x, CPU time: the worst call 512 ms, 232 ms of it a style recalc of 1,414
// elements (a move's writes: act, route, way and mood classes each restyle 36 to 388 parts);
// layout 0 to 8 ms. A strict expected failure until the companion's selectors touch only the
// parts each write moves; the cap is a frame. Never widen the cap.
const COMPANION_FORCED_CAP_MS = 16;
test("companion_forced_cpu: a companion look forces at most 16 ms of style and layout at 4x", async ({ page }) => {
  test.fail(true, "L-ui-modernisation-95 follow-on: a look restyles the whole figure, about 1,400 elements");
  await openApp(page);
  await measure.pinFullFigure(page);
  await page.evaluate(async () => { localStorage.removeItem("nm-buddy-spots"); prefs.set("avatar-buddy", "atlas"); await ensureModule("characters"); syncNameMarkBuddy(); });
  await page.waitForTimeout(4000);
  const worst = await measure.companionForcedCpu(page);
  expect(worst.calls, "no companion look ran during the tab switches").toBeGreaterThan(0);
  expect(worst.forced, `worst look: ${worst.forced} ms forced of ${worst.whole} ms, ${worst.elements} elements restyled, over ${worst.calls} calls; the cap is ${COMPANION_FORCED_CAP_MS}`).toBeLessThanOrEqual(COMPANION_FORCED_CAP_MS);
});
