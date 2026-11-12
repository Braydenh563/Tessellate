// L272: the export SVG of a fixed sample board and a fixed sample map, so a
// rewrite of wbBuildExportSvg can be shown behaviour-neutral. `OUTFILE` is
// written on every run; with `COMPARE=<file>` the run is compared to it: the
// same elements (count per tag), the same bounding boxes (rounded), and the
// same string once clip ids are stripped.
//   BASE=http://127.0.0.1:8791 OUTFILE=/path/a.json PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbexport-parity.js
const fs = require("fs");
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();

async function snapshot(page) {
  return page.evaluate(() => {
    const out = {};
    for (const scope of ["board", "selection"]) {
      if (scope === "selection") selectWbItem("object", wbState.objects[0].id);
      const { svg, width, height } = wbBuildExportSvg(scope);
      const doc = new DOMParser().parseFromString(svg, "image/svg+xml");
      const tags = {};
      for (const el of doc.documentElement.querySelectorAll("*")) tags[el.tagName] = (tags[el.tagName] || 0) + 1;
      const holder = document.createElement("div");
      holder.style.cssText = "position:fixed;left:-99999px;top:0;visibility:hidden";
      holder.innerHTML = svg;
      document.body.appendChild(holder);
      const boxes = [...holder.querySelectorAll("svg *")].map((el) => {
        if (!el.getBBox) return null;
        try { const b = el.getBBox(); return [el.tagName, Math.round(b.x), Math.round(b.y), Math.round(b.width), Math.round(b.height)]; } catch { return null; }
      }).filter(Boolean);
      holder.remove();
      out[scope] = { width, height, tags, boxes, svg: svg.replace(/wb-export-clip-\d+/g, "clip").replace(/ data-(id|parent|child)="\d+"/g, "") };
    }
    return out;
  });
}

(async () => {
  const result = {};
  {
    const { browser, page } = await openBoard({ title: "Parity board" });
    await page.evaluate(async () => {
      await wbCreateFrame(0, 0, { x: 0, y: 0, w: 400, h: 300 });
      await wbCreateFrame(0, 0, { x: 600, y: 0, w: 400, h: 300 });
      await wbCreateSticky(40, 60);
      await wbCreateTextBox(640, 60);
      await wbInsertTable(3, 3);
      await wbCreateObject("text", { content: "# Heading\n**bold** text", color: "#aa3300", font_size: 18 }, 100, 400, 260, 120);
      for (const d of [
        { d: "M 0 500 L 200 560 L 320 500 Z", shape: "custom", color: "#2255aa", width: 3, label: "Triangle" },
        { d: "M 420 500 L 700 500", shape: "line", color: "#118844", width: 4, dash: "dashed" },
      ]) {
        const made = await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ data: JSON.stringify(d), x: 0, y: 0, z: wbStackNewZ("sketch"), board_id: window.currentBoardId }) });
        wbState.sketches.push(made);
      }
      wbScheduleRender();
    });
    await page.waitForTimeout(1500);
    result.board = await snapshot(page);
    await browser.close();
  }
  {
    const { browser, page } = await openBoard({ title: "Parity map", type: "map" });
    await page.evaluate(async () => {
      const root = await wbMapAddRootAt(0, 0);
      await wbMapAddChild(root.id);
      await wbMapAddChild(root.id);
      wbScheduleRender();
    });
    await page.waitForTimeout(2000);
    result.map = await snapshot(page);
    await browser.close();
  }
  fs.writeFileSync(process.env.OUTFILE || "/dev/null", JSON.stringify(result));
  for (const k of ["board", "map"]) for (const s of ["board", "selection"]) {
    const r = result[k][s];
    check(`${k}/${s} has elements`, Object.keys(r.tags).length > 1 && r.boxes.length > 0, { tags: r.tags });
  }
  if (process.env.COMPARE) {
    const base = JSON.parse(fs.readFileSync(process.env.COMPARE, "utf8"));
    for (const k of ["board", "map"]) for (const s of ["board", "selection"]) {
      const a = base[k][s], b = result[k][s];
      check(`${k}/${s} same element counts`, JSON.stringify(a.tags) === JSON.stringify(b.tags), { a: a.tags, b: b.tags });
      check(`${k}/${s} same bounding boxes`, JSON.stringify(a.boxes) === JSON.stringify(b.boxes));
      check(`${k}/${s} same size`, a.width === b.width && a.height === b.height);
      check(`${k}/${s} same svg text`, a.svg === b.svg);
    }
  }
  process.exit(summary() ? 0 : 1);
})();
