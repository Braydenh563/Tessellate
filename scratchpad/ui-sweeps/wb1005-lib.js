// wb1005 sweeps: boot, open the whiteboard surface and a fresh board.
//   BASE=http://127.0.0.1:8845 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wb1005-*.js
const { boot } = require("./lib.js");

async function openBoard(opts = {}) {
  const b = await boot({ viewport: opts.viewport || { width: 1440, height: 900 }, ...(opts.boot || {}) });
  const { page } = b;
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text().slice(0, 200)); });
  await page.click('[data-tab="library"]');
  await page.waitForTimeout(700);
  await page.click('#library-subtabs [data-target="library-view-whiteboard"]');
  await page.waitForFunction(() => typeof window.initWhiteboard === "function", null, { timeout: 30000 });
  // The library's scripts load lazily; on a loaded machine 1.2 s is not always enough.
  await page.waitForFunction(() => typeof initWhiteboard === "function", null, { timeout: Number(process.env.BOOT_MS || 30000) });
  await page.evaluate(async () => {
    window.confirmDialog = async () => true;
    const v = document.getElementById("library-view-whiteboard");
    for (const s of document.querySelectorAll('[id^="library-view-"]')) s.classList.toggle("hidden", s !== v);
    await initWhiteboard();
  });
  const board = await page.evaluate(async ([t, type]) => apiJson("/whiteboard/boards", {
    method: "POST", body: JSON.stringify({ name: (t || "wb1005") + " " + Date.now(), type: type || "board" }),
  }), [opts.title, opts.type]);
  await page.evaluate(async (b) => { await openWhiteboardBoard(b); }, board.id);
  await page.waitForTimeout(1200);
  return { ...b, errors, board };
}

function checker() {
  const results = [];
  const check = (label, ok, detail) => {
    results.push(Boolean(ok));
    console.log(`${ok ? "PASS" : "FAIL"}  ${label}${ok || detail === undefined ? "" : "  " + JSON.stringify(detail)}`);
  };
  const summary = () => {
    const p = results.filter(Boolean).length;
    console.log(`${p}/${results.length}`);
    return p === results.length;
  };
  return { check, summary };
}

module.exports = { openBoard, checker };
