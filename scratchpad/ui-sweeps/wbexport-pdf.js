// L270 and L267: a 2-frame board exports a 2-page PDF written in the app, the
// dialog offers page size, direction and pages for PDF only, and a branch's
// export dialog says "Export this branch".
//   BASE=http://127.0.0.1:8791 OUT=/path/board.pdf PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbexport-pdf.js
const fs = require("fs");
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();

(async () => {
  const { browser, page } = await openBoard({ title: "Pdf board" });
  await page.evaluate(async () => {
    await wbCreateFrame(0, 0, { x: 0, y: 0, w: 400, h: 300 });
    await wbCreateFrame(0, 0, { x: 600, y: 0, w: 400, h: 300 });
    await wbCreateSticky(40, 60);
    await wbCreateTextBox(640, 60);
  });
  await page.waitForTimeout(1200);
  const made = await page.evaluate(async () => {
    const out = {};
    for (const layout of ["fit", "frames", "tiles"]) {
      const pages = await wbPdf.pictures("whole", { size: "a4", orientation: "auto", layout });
      const bytes = wbPdf.build(pages);
      const text = new TextDecoder("latin1").decode(bytes);
      out[layout] = {
        pages: Number(/\/Type \/Pages \/Kids \[[^\]]*\] \/Count (\d+)/.exec(text)[1]),
        size: bytes.length,
        jpeg: pages.every((p) => p.image.jpeg[0] === 0xff && p.image.jpeg[1] === 0xd8),
        b64: layout === "frames" ? btoa(String.fromCharCode(...bytes)) : null,
      };
    }
    return out;
  });
  if (process.env.OUT) fs.writeFileSync(process.env.OUT, Buffer.from(made.frames.b64, "base64"));
  check("fit is 1 page", made.fit.pages === 1, made.fit);
  check("per frame is 2 pages", made.frames.pages === 2, made.frames);
  check("tiled is at least 1 page", made.tiles.pages >= 1, made.tiles);
  check("pages are JPEGs", made.frames.jpeg && made.fit.jpeg);

  await page.evaluate(() => wbExportBoard());
  await page.waitForTimeout(300);
  const dialog = await page.evaluate(() => {
    const card = document.querySelector(".wb-export-card");
    const rows = () => [...card.querySelectorAll(".wb-export-seg")].filter((s) => !s.hidden).map((s) => s.getAttribute("aria-label"));
    const before = rows();
    card.querySelector('[aria-label="Format"] [data-value="pdf"]').click();
    const after = rows();
    return { label: document.querySelector(".wb-export-overlay").getAttribute("aria-label"), before, after, overflow: card.scrollWidth > card.clientWidth + 1 };
  });
  check("the board dialog says board", dialog.label === "Export this board", dialog);
  check("PDF adds page size, direction and pages", ["Page size", "Direction", "Pages"].every((n) => dialog.after.includes(n)) && !dialog.before.includes("Page size"), dialog);
  check("no overflow", !dialog.overflow, dialog);
  await page.keyboard.press("Escape");
  const branch = await page.evaluate(() => { wbExportBoard({ branch: true }); const l = document.querySelector(".wb-export-overlay").getAttribute("aria-label"); const h = document.querySelector(".wb-export-card h2, .wb-export-card .dialog-head")?.textContent || ""; return { l, h }; });
  check("a branch dialog says branch", branch.l === "Export this branch" && /Export this branch/.test(branch.h), branch);
  await browser.close();
  process.exit(summary() ? 0 : 1);
})();
