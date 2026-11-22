// The OCR workspace's text column at laptop heights (L806, the owner
// 2026-11-12): "its bottom scroll section is crushed very short by the
// sections above it (caption, description, model read)". One picture with a
// long caption, a vision reading of many sections and a Tesseract reading
// beside it; per viewport the section list must keep a usable height
// (>= 160px, about four sections) or the column must scroll as one.
//
//   BASE=http://127.0.0.1:8791 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/ocrpanelfit.js
const { boot } = require("./lib.js");

const SIZES = [[1366, 768], [1280, 720], [1440, 900]];
let failures = 0;
function check(label, ok, detail) {
  if (!ok) failures += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail ? "  " + detail : ""}`);
}

(async () => {
  for (const [w, h] of SIZES) {
    const { browser, page } = await boot({ viewport: { width: w, height: h } });
    try {
      await page.evaluate(() => switchTab("library"));
      await page.waitForFunction(() => typeof openOcrWorkspace === "function", null, { timeout: 90000 });
      await page.evaluate(async () => {
        const c = document.createElement("canvas");
        c.width = 400; c.height = 300;
        const g = c.getContext("2d");
        g.fillStyle = "#246"; g.fillRect(0, 0, 400, 300);
        const blob = await new Promise((r) => c.toBlob(r, "image/png"));
        const fd = new FormData();
        fd.append("file", new File([blob], `panelfit-${Date.now()}.png`, { type: "image/png" }));
        fd.append("direct", "true");
        const r = await fetch("/media/upload", { method: "POST", body: fd, headers: { "X-Auth-Token": authToken(), "X-Workspace-ID": activeSpaceId() } });
        const m = await r.json();
        const sections = Array.from({ length: 14 }, (_, i) => `Section ${i + 1}\n\nA paragraph the model read from the page, long enough to wrap twice in the column.`).join("\n\n");
        await apiJson(`/media/${m.id}/caption`, { method: "POST", body: JSON.stringify({ text: "A whiteboard photo from the planning meeting, with the goals, the people and the tests in three columns, and arrows between them. ".repeat(3) }) });
        await apiJson(`/media/${m.id}/vision-ocr`, { method: "POST", body: JSON.stringify({ text: sections }) });
        await apiJson(`/media/${m.id}/ocr`, { method: "POST", body: JSON.stringify({ text: "Goals People Tests arrows between them read by Tesseract. ".repeat(12) }) });
        const row = await apiJson(`/media/meta/${encodeURIComponent(m.url.split("/").pop())}`);
        const sel = document.getElementById("ocr-reader");
        const model = [...(sel?.options || [])].find((o) => o.value !== "tesseract");
        if (sel && model) sel.value = model.value;
        openOcrWorkspace({ ...row, _isImage: true }, [{ ...row, _isImage: true }]);
        return m;
      });
      await page.waitForTimeout(2500);
      const m = await page.evaluate(() => {
        const hgt = (sel) => { const el = document.querySelector(sel); if (!el) return null; const r = el.getBoundingClientRect(); return Math.round(r.height); };
        const col = document.querySelector("#ocr-workspace .ocr-regions");
        const list = document.getElementById("ocr-region-list");
        return {
          column: hgt("#ocr-workspace .ocr-regions"), caption: hgt("#ocr-caption:not(.hidden)"), others: hgt("#ocr-other-readings:not(.hidden)"),
          list: hgt("#ocr-region-list"), sections: list ? list.children.length : 0,
          listScrolls: list ? list.scrollHeight > list.clientHeight + 1 : false,
          columnScrolls: col ? col.scrollHeight > col.clientHeight + 1 && getComputedStyle(col).overflowY !== "visible" : false,
          columnClipped: col ? col.scrollHeight > col.clientHeight + 1 && getComputedStyle(col).overflowY === "visible" : false,
        };
      });
      console.log(`  ${w}x${h}: ${JSON.stringify(m)}`);
      check(`${w}x${h}: the section list keeps a usable height`, (m.list || 0) >= 160, `list ${m.list}px of a ${m.column}px column (caption ${m.caption}, other readings ${m.others}), ${m.sections} sections`);
      check(`${w}x${h}: nothing in the column is cut off`, !m.columnClipped, `column scrolls ${m.columnScrolls}`);
      await page.screenshot({ path: `${process.env.SCRATCH || "/tmp"}/ocrpanelfit-${w}.png` });
    } finally {
      await browser.close();
    }
  }
  console.log(failures ? `${failures} failed` : "all passed");
  process.exit(failures ? 1 : 0);
})();
