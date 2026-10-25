// Dogfood 2026-10-25 item 11 and 22: the whiteboard bottom dock at a width,
// and a toast against the dock.
//   W=700 BASE=http://127.0.0.1:8814 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbdog1-dock.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();
(async () => {
  const W = Number(process.env.W || 700), H = Number(process.env.H || 800);
  const { browser, page } = await openBoard({ viewport: { width: W, height: H } });
  const m = await page.evaluate(() => {
    const d = document.getElementById("wb-tools-panel");
    const r = d.getBoundingClientRect();
    const hidden = [...d.querySelectorAll("button,input,summary")].filter((e) => { const b = e.getBoundingClientRect(); return b.width && (b.right > innerWidth + 1 || b.left < -1); }).map((e) => e.id || e.dataset.tool || e.title).slice(0, 12);
    const undo = document.getElementById("wb-undo").getBoundingClientRect();
    return { sw: d.scrollWidth, cw: d.clientWidth, left: Math.round(r.left), right: Math.round(r.right), top: Math.round(r.top), h: Math.round(r.height), undoX: Math.round(undo.left), undoVisible: undo.width > 0, off: hidden, more: Boolean(d.querySelector(".dock-more, .kebab, [data-more]")) };
  });
  console.log(JSON.stringify(m));
  check("dock does not overflow itself", m.sw <= m.cw, m);
  check("dock sits inside the window", m.left >= 0 && m.right <= W, m);
  check("Undo is on screen", m.undoVisible && m.undoX < W, m);
  if (process.env.TOAST) {
    await page.evaluate(() => toast("Created. A second line of the message to make it long enough to wrap on a narrow window."));
    await page.waitForTimeout(500);
    const t = await page.evaluate(() => {
      const el = document.querySelector("#toast-container .toast, .toast");
      const r = el.getBoundingClientRect();
      const d = document.getElementById("wb-tools-panel").getBoundingClientRect();
      return { toastBottom: Math.round(r.bottom), toastTop: Math.round(r.top), dockTop: Math.round(d.top), toastRight: Math.round(r.right), toastLeft: Math.round(r.left), dockLeft: Math.round(d.left), dockRight: Math.round(d.right) };
    });
    console.log(JSON.stringify(t));
    check("toast bottom sits above the dock top", t.toastBottom <= t.dockTop, t);
  }
  await browser.close();
  process.exit(summary() ? 0 : 1);
})();
