//: L-graph-12: the Tessellation view beside the owner's chosen layout, one PNG.
//: BASE=http://localhost:PORT [LAYOUT=force] node scratchpad/ui-sweeps/tess-pair.js
//: Writes $OUT/tess-pair.png (the two maps at the same size, side by side) and
//: prints, per layout, the drawn notes, the share of the canvas the map's box
//: covers and the dots or cells that overlap.
const {boot, OUT} = require(process.cwd() + "/scratchpad/ui-sweeps/lib.js");
const path = require("path");
(async () => {
  const {browser, page} = await boot({viewport: {width: 1200, height: 800}, scale: 2});
  const other = process.env.LAYOUT || (await page.evaluate(() => prefs.get("graph-layout", null))) || "force";
  const shots = {};
  const numbers = {};
  for (const layout of [other === "tessellation" ? "force" : other, "tessellation"]) {
    await page.evaluate((l) => prefs.set("graph-layout", l), layout);
    await page.click("#tab-btn-notes");
    await page.waitForTimeout(400);
    await page.click("#tab-btn-graph");
    await page.waitForFunction(() => window.gcTab && gcTab.nodes && gcTab.nodes.length && (gcTab.layoutKind !== "force" || gcTab.alpha < 0.03), null, {timeout: 60000}).catch(() => {});
    await page.waitForTimeout(1500);
    numbers[layout] = await page.evaluate(() => {
      const s = gcTab;
      const pts = s.nodes.filter((n) => Number.isFinite(n.x));
      const xs = pts.map((n) => n.x), ys = pts.map((n) => n.y);
      const t = s.transform || {k: 1, x: 0, y: 0};
      const box = s.canvas.getBoundingClientRect();
      const w = (Math.max(...xs) - Math.min(...xs)) * t.k, h = (Math.max(...ys) - Math.min(...ys)) * t.k;
      let overlaps = 0;
      for (let i = 0; i < pts.length; i++) for (let j = i + 1; j < pts.length; j++) {
        if (Math.hypot(pts[i].x - pts[j].x, pts[i].y - pts[j].y) < (pts[i].r || 5) + (pts[j].r || 5)) overlaps++;
      }
      return {notes: pts.length, cover: +((w * h) / (box.width * box.height)).toFixed(2), overlaps, cells: s.tree && s.tree.tess ? s.tree.tess.cells.length : null};
    });
    shots[layout] = await page.locator("#graph-canvas").screenshot();
  }
  const [a, b] = Object.keys(shots);
  const html = `<body style="margin:0;display:flex;gap:8px;background:#888">${[a, b].map((k) => `<figure style="margin:0"><img style="width:600px" src="data:image/png;base64,${shots[k].toString("base64")}"><figcaption style="font:14px sans-serif;padding:4px">${k}</figcaption></figure>`).join("")}</body>`;
  const sheet = await browser.newPage({viewport: {width: 1208, height: 460}, deviceScaleFactor: 2});
  await sheet.setContent(html);
  const file = path.join(OUT, "tess-pair.png");
  await sheet.screenshot({path: file, fullPage: true});
  console.log(JSON.stringify({file, numbers}));
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
