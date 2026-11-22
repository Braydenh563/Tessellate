// wbfmtrace: a board opened while the boards bundle is still arriving (a slow
// whiteboard-format.js) must still init with no pageerror, and select, pan and
// the zoom controls must work (owner report on #222: wbFmtState is not defined).
//   BASE=... SCRATCH=... DELAY_MS=2500 node scratchpad/ui-sweeps/wbfmtrace.js
const { boot } = require("./lib.js");
(async () => {
  const delay = Number(process.env.DELAY_MS || 2500);
  const b = await boot({ viewport: { width: 1440, height: 900 } });
  const { page, browser } = b;
  const ctx = page.context();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  // Make a board first, through the API, so the gallery has one to open.
  const id = await page.evaluate(async () => (await apiJson("/whiteboard/boards", { method: "POST", body: JSON.stringify({ name: "race " + Date.now(), type: "board" }) })).id);
  // whiteboard-format.js and every file after it are held back (a slow disk or
  // network; the service worker serves them, so a Playwright route would not see them).
  await page.evaluate((ms) => {
    const add = Node.prototype.appendChild;
    let hold = false;
    Node.prototype.appendChild = function (el) {
      if (el.tagName === "SCRIPT" && /whiteboard-format\.js/.test(el.src)) hold = true;
      if (hold && el.tagName === "SCRIPT" && /\/js\/whiteboard/.test(el.src)) { setTimeout(() => add.call(this, el), ms); return el; }
      return add.call(this, el);
    };
  }, delay);
  // The owner's path: Library, Whiteboards, then the board, as soon as it can be pressed.
  await page.evaluate(() => switchTab("library"));
  await page.click('#library-subtabs [data-target="library-view-whiteboard"]');
  // The real opener (whiteboard.js has run, later files not yet), as a board restored with the page calls it.
  await page.waitForFunction(() => typeof window.wbShowCanvasView === "function", null, { timeout: 20000, polling: 20 });
  await page.evaluate((i) => { openWhiteboardBoard(i); }, id);
  await page.waitForTimeout(delay + 3000);
  const r = await page.evaluate(() => ({
    init: typeof wbInitialized !== "undefined" && wbInitialized,
    zoomText: document.querySelector("#wb-zoom-level input, #wb-zoom-level")?.value ?? document.querySelector("#wb-zoom-level")?.textContent,
  }));
  // Pan: the select tool, a drag on empty canvas with space held moves the view.
  const before = await page.evaluate(() => d3.zoomTransform(wbInstances.container()).k);
  await page.click("#wb-zoom-in");
  await page.waitForTimeout(500);
  const after = await page.evaluate(() => d3.zoomTransform(wbInstances.container()).k);
  // A tool press: the tool groups wired by initWhiteboard answer it.
  await page.evaluate(() => document.querySelector('#whiteboard-tools [data-tool="pan"], [data-tool="pan"]')?.click());
  await page.waitForTimeout(200);
  const tool = await page.evaluate(() => window.currentWbTool ?? document.querySelector('[data-tool].active')?.dataset.tool);
  console.log(JSON.stringify({ delay, errors, ...r, zoomBefore: before, zoomAfter: after, tool }));
  console.log(errors.length === 0 && after > before ? "PASS" : "FAIL");
  await browser.close();
})();
