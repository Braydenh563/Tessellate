// INBOX 1322a: Format button in the whiteboard top bar. BASE=http://127.0.0.1:8793 node scratchpad/ui-sweeps/wbformatbtn.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();
(async () => {
  const { browser, page } = await openBoard({});
  const q = () => page.evaluate(() => {
    const b = document.getElementById("wb-format-btn"), l = document.getElementById("wb-add-note");
    const rb = b.getBoundingClientRect(), rl = l.getBoundingClientRect();
    return { open: !document.getElementById("wb-format").classList.contains("hidden"), pressed: b.getAttribute("aria-pressed"),
      h: rb.height, hl: rl.height, gap: rb.left - rl.right, top: rb.top - rl.top, w: rb.width,
      empty: !document.getElementById("wb-format-empty").classList.contains("hidden") };
  });
  const a = await q();
  await page.click("#wb-format-btn"); await page.waitForTimeout(300);
  const b = await q();
  await page.click("#wb-format-btn"); await page.waitForTimeout(300);
  const c = await q();
  console.log(JSON.stringify({ a, b, c }));
  check("closed at start", !a.open && a.pressed === "false");
  check("opens with empty state when nothing selected", b.open && b.pressed === "true" && b.empty);
  check("closes again", !c.open && c.pressed === "false");
  check("same height and row as Library", Math.abs(a.h - a.hl) < 1 && Math.abs(a.top) < 1 && a.gap >= 0 && a.gap < 16);
  summary(); await browser.close();
})();
