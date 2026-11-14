// wbformat2 sweep: grid size, page frames, rulers, PNG pHYs and embedded board, one-file HTML page.
//   bash scratchpad/ui-sweeps/serve.sh <port> <scratch dir>
//   BASE=http://127.0.0.1:<port> PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbformat2.js
const fs = require("fs");
const os = require("os");
const path = require("path");
const { openBoard, checker } = require("./wb1005-lib.js");

(async () => {
  const { check, summary } = checker();
  const s = await openBoard({ title: "wbformat2" });
  const { page, errors, board } = s;

  // A shape or two so there is content to export and the page view has something to tile.
  await page.evaluate(async (id) => {
    for (const [x, y] of [[100, 100], [900, 1200]]) {
      await apiJson("/whiteboard/objects", {
        method: "POST",
        body: JSON.stringify({ board_id: id, kind: "text", x, y, width: 160, height: 90, data: { content: "wbformat2" } }),
      });
    }
    await openWhiteboardBoard(id);
  }, board.id);
  await page.waitForTimeout(1200);

  // Grid: the CSS size follows the setting and the zoom.
  const gridAt = async (size, k) => page.evaluate(async ([size, k]) => {
    await wbSetBackground({ grid_size: size });
    const host = document.getElementById("whiteboard-container");
    d3.select(host).call(wbZoom.transform, d3.zoomIdentity.translate(0, 0).scale(k));
    await new Promise((r) => setTimeout(r, 300));
    const cs = getComputedStyle(host);
    return { var: cs.getPropertyValue("--wb-grid-size").trim(), bg: cs.backgroundSize };
  }, [size, k]);
  const g1 = await gridAt(48, 1);
  const g2 = await gridAt(48, 2);
  console.log("grid", JSON.stringify({ g1, g2 }));
  const px = (v) => parseFloat(v);
  check("grid size 48 at zoom 1 is 48 px apart", px(g1.bg) === 48 || px(g1.var) === 48, g1);
  check("grid size 48 at zoom 2 is 96 px apart", px(g2.bg) === 96 || px(g2.var) === 96, g2);

  // Page view: A4 portrait 794 x 1123, A3 landscape 1587 x 1123.
  const frames = async (bg) => page.evaluate(async (bg) => {
    await wbSetBackground(bg);
    await new Promise((r) => setTimeout(r, 300));
    return [...document.querySelectorAll(".wb-page-frame")].map((r) => [Number(r.getAttribute("width")), Number(r.getAttribute("height"))]);
  }, bg);
  const a4 = await frames({ page_view: true, paper: "a4", orientation: "portrait" });
  const a3 = await frames({ paper: "a3", orientation: "landscape" });
  console.log("pages", JSON.stringify({ a4: a4.slice(0, 2), a3: a3.slice(0, 2), counts: [a4.length, a3.length] }));
  check("A4 portrait frames are 794 x 1123", a4.length > 0 && a4[0][0] === 794 && a4[0][1] === 1123, a4[0]);
  check("A3 landscape frames are 1587 x 1123", a3.length > 0 && a3[0][0] === 1587 && a3[0][1] === 1123, a3[0]);

  // Rulers: label gap over value gap is the zoom, in px and in mm.
  const rulerAt = async (k, unit) => page.evaluate(async ([k, unit]) => {
    await wbSetBackground({ units: unit });
    const box = document.getElementById("wb-view-rulers");
    if (!box.checked) { box.checked = true; box.dispatchEvent(new Event("change", { bubbles: true })); }
    const host = document.getElementById("whiteboard-container");
    d3.select(host).call(wbZoom.transform, d3.zoomIdentity.translate(40, 40).scale(k));
    await new Promise((r) => setTimeout(r, 300));
    const labels = [...document.querySelectorAll("#wb-ruler-top text")].map((t) => [Number(t.getAttribute("x")) - 3, Number(t.textContent)]);
    return labels;
  }, [k, unit]);
  for (const [k, unit, ppu] of [[1, "px", 1], [2, "px", 1], [0.5, "px", 1], [1, "mm", 96 / 25.4], [2, "in", 96]]) {
    const L = await rulerAt(k, unit);
    const gaps = L.slice(1).map((l, i) => [l[0] - L[i][0], l[1] - L[i][1]]);
    const ratio = gaps.length ? gaps[0][0] / gaps[0][1] : NaN;
    const major = gaps.length ? gaps[0][0] : 0;
    console.log("ruler", JSON.stringify({ k, unit, labels: L.length, ratio, major }));
    check(`ruler ${unit} at zoom ${k}: px per unit is ${(k * ppu).toFixed(3)}`, Math.abs(ratio - k * ppu) < 0.02 * k * ppu + 0.02, { ratio });
    check(`ruler ${unit} at zoom ${k}: major gap at least 60 px`, major >= 59, { major });
  }
  await page.evaluate(async () => { await wbSetBackground({ units: "px" }); });

  // PNG: pHYs at 300 dpi is 11811 pixels per metre; the board rides in a tEXt chunk and imports back.
  const png = await page.evaluate(async () => {
    window.__saved = null;
    window.saveFile = async (name, blob) => { window.__saved = { name, bytes: [...new Uint8Array(await blob.arrayBuffer())] }; };
    prefs.set("wb-export-png", JSON.stringify({ scale: 1, transparent: false, library: false, border: 20, dpi: 300, embed: true }));
    await wbExportPng("whole");
    const bytes = new Uint8Array(window.__saved.bytes);
    const dv = new DataView(bytes.buffer);
    const chunks = [];
    for (let i = 8; i < bytes.length;) {
      const len = dv.getUint32(i);
      const type = String.fromCharCode(...bytes.slice(i + 4, i + 8));
      chunks.push({ type, at: i + 8, len });
      i += 12 + len;
    }
    const phys = chunks.find((c) => c.type === "pHYs");
    const rows = wbFmtState.exporters.rowsOf(bytes);
    return {
      size: bytes.length,
      chunks: chunks.map((c) => c.type),
      x: phys ? dv.getUint32(phys.at) : null,
      y: phys ? dv.getUint32(phys.at + 4) : null,
      unit: phys ? bytes[phys.at + 8] : null,
      rows: rows ? rows.length : null,
      dpi: wbFmtState.exporters.dpiOf(bytes),
    };
  });
  console.log("png", JSON.stringify(png));
  check("PNG pHYs is 11811 pixels per metre both ways, unit metre", png.x === 11811 && png.y === 11811 && png.unit === 1, png);
  check("PNG has pHYs before IDAT and a tEXt chunk", png.chunks.indexOf("pHYs") > 0 && png.chunks.indexOf("pHYs") < png.chunks.indexOf("IDAT") && png.chunks.includes("tEXt"), png.chunks);
  check("PNG embeds the board's rows (2 shapes)", png.rows >= 2, png.rows);
  const counts = await page.evaluate(async () => {
    const before = wbState.objects.length;
    await wbImportBoardRows(wbFmtState.exporters.rowsOf(new Uint8Array(window.__saved.bytes)));
    await new Promise((r) => setTimeout(r, 800));
    return { before, after: wbState.objects.length };
  });
  console.log("reopen", JSON.stringify(counts));
  check("importing the PNG's board adds its 2 rows back", counts.before === 2 && counts.after === 4, counts);

  // HTML: save through the real exporter, open the file in an offline context, wheel changes the viewBox.
  const html = await page.evaluate(async () => {
    window.__saved = null;
    window.saveFile = async (name, blob) => { window.__saved = { name, text: await blob.text() }; };
    await WB_EXPORT_FORMATS.find((f) => f.value === "html").run("whole");
    return window.__saved;
  });
  const file = path.join(os.tmpdir(), "wbformat2-" + Date.now() + ".html");
  fs.writeFileSync(file, html.text);
  console.log("html", JSON.stringify({ name: html.name, bytes: html.text.length, remote: (html.text.match(/(src|href)="https?:/g) || []).length }));
  check("HTML has no remote src or href", !/(src|href)="https?:/.test(html.text));
  const ctx = await page.context().browser().newContext({ offline: true, viewport: { width: 1000, height: 700 } });
  const off = await ctx.newPage();
  const offErrors = [];
  off.on("pageerror", (e) => offErrors.push(e.message));
  const requests = [];
  off.on("request", (r) => { if (!r.url().startsWith("file:") && !r.url().startsWith("data:")) requests.push(r.url()); });
  await off.goto("file://" + file);
  await off.waitForTimeout(500);
  const vb0 = await off.evaluate(() => document.querySelector("svg").getAttribute("viewBox"));
  await off.mouse.move(500, 350);
  await off.mouse.wheel(0, -400);
  await off.waitForTimeout(300);
  const vb1 = await off.evaluate(() => document.querySelector("svg").getAttribute("viewBox"));
  console.log("viewBox", JSON.stringify({ vb0, vb1, offErrors, requests }));
  check("HTML opens offline with no errors or network requests", offErrors.length === 0 && requests.length === 0, { offErrors, requests });
  check("HTML wheel zoom changes the viewBox", vb0 && vb1 && vb0 !== vb1, { vb0, vb1 });
  await ctx.close();
  fs.unlinkSync(file);

  check("no page errors", errors.length === 0, errors.slice(0, 5));
  const ok = summary();
  await s.browser.close();
  process.exit(ok ? 0 : 1);
})().catch((e) => { console.error(e); process.exit(2); });
