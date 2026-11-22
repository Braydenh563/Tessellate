// The browser's half of the interaction budgets (WORLD_CLASS_PLAN 25g,
// decision 54). The caps are read from `GET /models/bench/budgets`, the one
// table `tests/test_budgets.py` also holds; the timing code is
// `tests-e2e/budget-measure.js`, shared with the sweep the README's numbers
// come from. A miss is repeated up to three times before it fails, because
// the machine is shared; the failure message carries the number.
//
// The notebook here is the seeded 75-note one with the two heavy items at
// full size (a board of 500 text objects, a document of 50,000 words). The
// list shows one page of rows whatever the notebook's size, and the
// 500-note server side is `tests/test_budgets.py`.
const { test, expect } = require("@playwright/test");
const { openApp, api } = require("../helpers");
const measure = require("../budget-measure");

const ROUNDS = 3;
const WORDS = "the quick brown fox jumps over lazy dogs while writing notes about gardens budgets travel plans and reading lists".split(" ");

let caps = {};
let ids = {};

// Best of up to ROUNDS: stops at the first round inside the cap.
async function inside(key, run) {
  const seen = [];
  while (seen.length < ROUNDS) {
    seen.push(await run());
    if (seen[seen.length - 1] <= caps[key]) break;
  }
  const best = Math.min(...seen);
  expect(best, `${key}: ${seen.join(", ")} ms over ${seen.length} round(s); the cap is ${caps[key]} ms`).toBeLessThanOrEqual(caps[key]);
}

test.describe.configure({ mode: "serial" });
// Up to three rounds of a heavy interaction on a loaded machine.
test.beforeEach(() => test.setTimeout(180_000));

test.beforeAll(async ({ browser }) => {
  test.setTimeout(180_000);
  const context = await browser.newContext();
  const page = await context.newPage();
  await openApp(page);
  const table = await api(page, "/models/bench/budgets");
  caps = Object.fromEntries(table.budgets.map((b) => [b.key, b.cap_ms]));
  ids = await page.evaluate(async ({ words }) => {
    const post = async (path, body) => (await apiJson(path, { method: "POST", body: JSON.stringify(body) }));
    const board = await post("/whiteboard/boards", { name: "Budget board", type: "board" });
    for (let start = 0; start < 500; start += 20) {
      await Promise.all(Array.from({ length: 20 }, (_, k) => {
        const i = start + k;
        return post("/whiteboard/objects", {
          kind: "text", board_id: board.id, x: (i % 25) * 220, y: Math.floor(i / 25) * 140, width: 200, height: 100,
          data: { content: `Card ${i} with a few words of text on it` },
        });
      }));
    }
    let content = "";
    for (let i = 0; i < 50000; i++) content += words[i % words.length] + (i % 12 === 11 ? ".\n\n" : " ");
    const doc = await post("/documents", { title: "Budget document", content });
    return { board: board.id, document: doc.id };
  }, { words: WORDS });
  await context.close();
});

test("the six budgets are in the table", () => {
  expect(Object.keys(caps)).toEqual(["first_paint", "first_interaction", "list", "search", "board", "document"]);
});

test("first_paint and first_interaction: cold boot with the stored session", async ({ browser, baseURL, context }) => {
  const state = await context.storageState();
  const open = async () => (await browser.newContext({ storageState: state })).newPage();
  const seen = [];
  while (seen.length < ROUNDS) {
    seen.push(await measure.boot(open, baseURL));
    console.log("boot round", JSON.stringify(seen[seen.length - 1]));
    const last = seen[seen.length - 1];
    if (last.firstPaint <= caps.first_paint && last.firstInteraction <= caps.first_interaction) break;
  }
  expect(Math.min(...seen.map((r) => r.firstPaint)), `first_paint: ${JSON.stringify(seen)}; cap ${caps.first_paint} ms`).toBeLessThanOrEqual(caps.first_paint);
  expect(Math.min(...seen.map((r) => r.firstInteraction)), `first_interaction: ${JSON.stringify(seen)}; cap ${caps.first_interaction} ms`).toBeLessThanOrEqual(caps.first_interaction);
});

test("list: switching to Notes paints the first page of rows", async ({ page }) => {
  await openApp(page);
  await inside("list", () => measure.listPaint(page, 5));
});

test("search: one request", async ({ page }) => {
  await openApp(page);
  await inside("search", () => measure.search(page, ["note", "garden", "plan"], 5));
});

test("board: 500 objects open", async ({ page }) => {
  await openApp(page);
  await inside("board", () => measure.boardOpen(page, ids.board, 500, 3));
});

test("document: 50,000 words open", async ({ page }) => {
  await openApp(page);
  await inside("document", () => measure.documentOpen(page, ids.document, 3));
});

// The tab_cpu budgets (L-ui-modernisation-54) are specs/tab-budgets.spec.js, in
// CI's own budgets job beside the map's: together they did not fit this job's 15 minutes.

// L-ui-modernisation-95, in CPU time: Atlas idle may cost at most 120 ms a
// second of main thread over the page with the companion off. Medians on
// 2026-11-21: off 3.7, me 15.9, atlas 479.8 ms/s. Atlas is about four times
// over, so this is a strict expected failure (a strict xfail): when the code
// gets under the cap the test starts passing, Playwright reports it, and the
// marker comes off. Never widen the cap.
const ATLAS_IDLE_CPU_CAP_MS = 120;
test("companion_idle_cpu: Atlas idle costs at most 120 ms/s of main-thread CPU over off", async ({ page, browser }) => {
  test.fail(true, "L-ui-modernisation-95: Atlas idle is about 480 ms/s over off in CPU time");
  await openApp(page);
  // The full figure on every runner (L-ui-modernisation-201): a slow one would otherwise switch to the lite set.
  await measure.pinFullFigure(page);
  const idle = async (kind) => {
    await page.evaluate(async (k) => { localStorage.removeItem("nm-buddy-spots"); prefs.set("avatar-buddy", k); await ensureModule("characters"); syncNameMarkBuddy(); }, kind);
    await page.evaluate(() => revealTab("dashboard"));
    // 3 s to settle and 3 s read, from 6 and 4: the gap is about 480 against 120,
    // so the shorter read proves the same miss, and still fails loudly the day it passes.
    await page.waitForTimeout(3000);
    return measure.idleCpuPerSecond(browser, page, 3000);
  };
  const runs = [];
  for (let i = 0; i < 3; i++) runs.push((await idle("atlas")) - (await idle("off")));
  const delta = measure.p50(runs);
  expect(delta, `atlas idle over off: ${runs.map(Math.round).join(", ")} ms/s; the cap is ${ATLAS_IDLE_CPU_CAP_MS}`).toBeLessThanOrEqual(ATLAS_IDLE_CPU_CAP_MS);
});
