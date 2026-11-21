// Headless Playwright suite (roadmap ANALYSIS.md §31, ROADMAP.md §38.2).
//
// Two notebooks, two servers, two projects:
//
//   * "first-run" is a brand-new data dir: the account is made, nothing else.
//     Only `first-run.spec.js` runs there, because a fresh install is the one
//     state the other specs cannot leave alone (they all write notes).
//   * "notebook" is a realistic one, seeded by global-setup.js from
//     `fixtures/notebook.json` (75 notes in seven categories, 87 links, three
//     documents). Every other spec runs there. A notebook with filed notes is
//     what lets the no-model filing path (`ai/lexical_filing.py`) file a new
//     note at all, so capture and filing can be asserted end to end with no
//     model and no network.
//
// Why this suite grew from one smoke file (2026-10-05): the Python suite has
// thousands of tests and fakes every AI call and every browser, and the core
// flow, writing a note and having it filed, was broken for an unknown time
// without one of them failing. These specs drive the real UI against a real
// server and assert what a person would see after a reload.
//
// PLAYWRIGHT_BROWSERS_PATH, if set, is respected by Playwright itself. In CI,
// `npx playwright install --with-deps chromium` puts a browser in the default
// cache and this config works unchanged.
//
// Local knobs (all optional):
//   TESSELLATE_E2E_PORT      the notebook server's port (first-run uses +1)
//   TESSELLATE_E2E_DATA_DIR  where the two data dirs go (wiped at start)
//   TESSELLATE_PYTHON        the interpreter that runs the app
const { defineConfig, devices } = require("@playwright/test");
const os = require("os");
const path = require("path");

const PORT = Number(process.env.TESSELLATE_E2E_PORT || 8799);
const FRESH_PORT = PORT + 1;
//: TESSELLATE_E2E_URL and TESSELLATE_E2E_FRESH_URL drive servers someone else
//: started instead (each on its own empty data dir): how the same specs were
//: run against the v0.3.32 release to compare (e2e-1005.md).
const BASE_URL = process.env.TESSELLATE_E2E_URL || `http://127.0.0.1:${PORT}`;
const FRESH_URL = process.env.TESSELLATE_E2E_FRESH_URL || `http://127.0.0.1:${FRESH_PORT}`;
const DATA_ROOT = process.env.TESSELLATE_E2E_DATA_DIR || path.join(os.tmpdir(), `memorymap-e2e-${PORT}`);
const PYTHON = process.env.TESSELLATE_PYTHON || "python";

// The data dir is wiped in the server's own command, not here: this file is
// loaded again in every worker process, and a wipe at load would delete the
// notebook under a running server.
function server(port, dir) {
  return {
    command:
      `rm -rf "${dir}" && mkdir -p "${dir}" && ` +
      `${PYTHON} -m uvicorn tessellate.api.app:create_app --factory --port ${port}`,
    url: `http://127.0.0.1:${port}/auth/status`,
    reuseExistingServer: false,
    timeout: 60_000,
    cwd: path.join(__dirname, ".."),
    env: {
      ...process.env,
      PYTHONPATH: "src",
      TESSELLATE_DATA_DIR: dir,
      // Settings, Packages must not start installing extras mid-run.
      TESSELLATE_NO_AUTO_INSTALL: "1",
      // No spec asserts on a real embedding model, so it need only be fast
      // and offline: without these a runner with no cached model tries to
      // download one on the first save and HuggingFace's rate limit stalls
      // that request past every timeout here. The embed path is best effort
      // (a failed embed never fails a save), and meaning search falls back
      // to keywords, which is the no-model behaviour these specs assert.
      HF_HUB_OFFLINE: "1",
      TRANSFORMERS_OFFLINE: "1",
    },
  };
}

module.exports = defineConfig({
  testDir: "./specs",
  // One app instance per project. Files run side by side, the tests inside a
  // file in order: every test writes its own notes with its own words, so
  // two files sharing the notebook cannot see each other's work, and the one
  // spec that cannot share (first-run: restore replaces the notebook, the
  // lock ends every session) has its own server. Three workers is what keeps
  // the job inside six minutes on a four-core runner; TESSELLATE_E2E_WORKERS
  // to change it.
  fullyParallel: false,
  workers: Number(process.env.TESSELLATE_E2E_WORKERS || 3),
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  // "github" alone annotates the run but writes no report to disk; the CI
  // job uploads playwright-report/ on failure, which needs "html" too.
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  timeout: 90_000,
  expect: { timeout: 10_000 },
  globalSetup: require.resolve("./global-setup.js"),
  use: {
    headless: true,
    // A navigation that never commits fails in 30 s with its own message,
    // rather than silently spending the whole test's budget.
    navigationTimeout: 30_000,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    // Clipboard access for the paste spec; harmless everywhere else.
    permissions: ["clipboard-read", "clipboard-write"],
  },
  projects: [
    {
      name: "first-run",
      testMatch: /first-run\.spec\.js/,
      // No retry here, whatever CI sets above: these specs assert an empty
      // notebook, and attempt 1 leaves a note behind, so a retry always fails
      // on "Your notebook is empty" being hidden and buries the real failure.
      retries: 0,
      use: {
        ...devices["Desktop Chrome"],
        baseURL: FRESH_URL,
        storageState: path.join(__dirname, ".auth-fresh.json"),
      },
    },
    {
      name: "notebook",
      // CI runs the budgets alone (budgets.spec.js and map-budgets.spec.js), after the flows (TESSELLATE_E2E_BUDGETS_APART):
      // timed beside two other workers on a shared runner, a different budget
      // missed on each run while HEAD measured no slower (e2efix2, 2026-10-11).
      testIgnore: process.env.TESSELLATE_E2E_BUDGETS_APART
        ? [/first-run\.spec\.js/, /budgets\.spec\.js/]
        : /first-run\.spec\.js/,
      use: {
        ...devices["Desktop Chrome"],
        baseURL: BASE_URL,
        // Written by global-setup.js: the account made, unlocked, the
        // welcome and the updates question answered once, reused by every
        // spec so none repeats that setup.
        storageState: path.join(__dirname, ".auth-state.json"),
      },
    },
  ],
  webServer: [
    process.env.TESSELLATE_E2E_URL ? null : server(PORT, path.join(DATA_ROOT, "notebook")),
    process.env.TESSELLATE_E2E_FRESH_URL ? null : server(FRESH_PORT, path.join(DATA_ROOT, "fresh")),
  ].filter(Boolean),
});

module.exports.BASE_URL = BASE_URL;
module.exports.FRESH_URL = FRESH_URL;
module.exports.E2E_PASSWORD = "e2e-smoke-test-password";
module.exports.PORT = PORT;
module.exports.DATA_ROOT = DATA_ROOT;
module.exports.PYTHON = PYTHON;
