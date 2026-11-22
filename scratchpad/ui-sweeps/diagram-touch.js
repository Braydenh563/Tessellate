// P2 leftovers at 390 with touch: the Add sheet replaces the palette, the picture pinches and pans.
process.env.BASE ||= "http://127.0.0.1:8781";
process.env.SCRATCH ||= require("os").tmpdir();
const { boot } = require("./lib.js");
const W = Number(process.argv[2] || 390);
(async () => {
  const { browser, page } = await boot({ viewport: { width: W, height: 844 }, hasTouch: true, isMobile: true });
  const out = {};
  const src = "flowchart TD\n  A[Start] --> B[Middle]\n  B --> C[End]\n  C --> D[More]\n  D --> E[Last]\n";
  await page.evaluate(async (c) => {
    const r = await api("/documents", { method: "POST", body: JSON.stringify({ title: "P2 touch " + Date.now(), content: "Intro\n\n```mermaid\n" + c + "```\n" }) });
    const doc = await r.json();
    switchTab("documents");
    await openDocument(doc.id);
    setDocView("live", { persist: false });
  }, src);
  await page.waitForSelector(".md-mermaid-edit", { timeout: 20000 });
  await page.waitForTimeout(1500);
  await page.tap(".md-mermaid-edit");
  await page.waitForSelector(".dgm-dialog .dgm-block", { state: "attached" }); // the list is a sheet on a phone (dgm-listless)
  await page.waitForSelector(".dgm-dialog .dgm-picture img");
  await page.waitForTimeout(1200);
  const box = (s) => page.evaluate((sel) => { const e = document.querySelector(sel); if (!e) return null; const b = e.getBoundingClientRect(); return [Math.round(b.left), Math.round(b.top), Math.round(b.width), Math.round(b.height)]; }, s);
  out.dock = await box(".dgm-dialog .dgm-dock");
  out.add = await box(".dgm-dialog .dgm-addcaret");
  out.palette = await page.evaluate(() => ((e) => e ? getComputedStyle(e).display : "absent")(document.querySelector(".dgm-dialog .dgm-palette")));
  await page.screenshot({ path: process.env.SCRATCH + `/p2-touch-${W}.png` });
  const before = await page.evaluate(() => document.querySelectorAll(".dgm-dialog .dgm-block").length);
  await page.tap(".dgm-dialog .dgm-addcaret");
  await page.waitForSelector(".action-menu-escaped [role=menuitem]");
  await page.waitForTimeout(400);
  out.sheet = await page.evaluate(() => {
    const rows = [...document.querySelectorAll(".action-menu-escaped [role=menuitem]")];
    const b = rows[0].getBoundingClientRect();
    const top = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2);
    return { rows: rows.map((r) => r.textContent.trim()), hit: rows[0].contains(top), glyph: !!rows[0].querySelector("svg, .dgm-shape, .ph"), h: Math.round(b.height) };
  });
  await page.screenshot({ path: process.env.SCRATCH + `/p2-sheet-${W}.png` });
  await page.locator(".action-menu-escaped [role=menuitem]").nth(1).tap();
  await page.waitForTimeout(700);
  out.added = await page.evaluate(() => document.querySelectorAll(".dgm-dialog .dgm-block").length) - before;
  await page.waitForTimeout(1200); out.sheetGone = await page.evaluate(() => [...document.querySelectorAll(".sheet-overlay")].map((o) => o.className));
  // pinch the picture with two touch points (CDP), then pan with one, then double tap
  const cdp = await page.context().newCDPSession(page);
  const fig = await box(".dgm-dialog .dgm-picture");
  const cx = fig[0] + fig[2] / 2;
  const cy = fig[1] + fig[3] / 2;
  const state = () => page.evaluate(() => { const f = document.querySelector(".dgm-dialog .dgm-picture"); const i = f.querySelector("img"); return { zoom: f.dataset.zoom, imgW: Math.round(i.getBoundingClientRect().width), sw: f.scrollWidth, cw: f.clientWidth, sl: Math.round(f.scrollLeft), st: Math.round(f.scrollTop) }; });
  out.fit = await state();
  const touch = (type, pts) => cdp.send("Input.dispatchTouchEvent", { type, touchPoints: pts.map(([x, y], id) => ({ x, y, id })) });
  await touch("touchStart", [[cx - 20, cy], [cx + 20, cy]]);
  for (let i = 1; i <= 8; i++) await touch("touchMove", [[cx - 20 - i * 10, cy], [cx + 20 + i * 10, cy]]);
  await touch("touchEnd", []);
  await page.waitForTimeout(300);
  out.pinched = await state();
  // a new block redraws the picture; the zoom stays
  await page.tap(".dgm-dialog .dgm-addcaret");
  await page.waitForSelector(".action-menu-escaped [role=menuitem]");
  await page.locator(".action-menu-escaped [role=menuitem]").nth(0).tap();
  await page.waitForTimeout(1500);
  out.redrawn = await state();
  // one finger pan, from a point no handle covers (a new block is selected, its handles sit in the overlay)
  out.underPan = await page.evaluate(([x, y]) => { const e = document.elementFromPoint(x, y); return e.className?.baseVal ?? e.className; }, [cx, cy]);
  const [px, py] = await page.evaluate(([l, t, w, h]) => { for (let y = t + 20; y < t + h - 20; y += 12) for (let x = l + 20; x < l + w - 20; x += 12) { const e = document.elementFromPoint(x, y); if (e && !e.closest(".dgm-overlay > *") && e.closest(".dgm-picture")) return [x, y]; } return [l + w / 2, t + h / 2]; }, fig);
  out.panAt = [px, py];
  await touch("touchStart", [[px + 90, py + 30]]);
  for (let i = 1; i <= 6; i++) await touch("touchMove", [[px + 90 - i * 15, py + 30 - i * 4]]);
  await touch("touchEnd", []);
  await page.waitForTimeout(300);
  out.panned = await state();
  out.selectedByPan = await page.evaluate(() => document.querySelectorAll(".dgm-dialog .dgm-block.selected, .dgm-dialog .dgm-block[aria-selected=true]").length);
  // double tap fits
  await touch("touchStart", [[px, py]]); await touch("touchEnd", []);
  await page.waitForTimeout(80);
  await touch("touchStart", [[px, py]]); await touch("touchEnd", []);
  await page.waitForTimeout(300);
  out.doubleTap = await state();
  await page.screenshot({ path: process.env.SCRATCH + `/p2-pinch-${W}.png` });
  console.log(JSON.stringify(out));
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
