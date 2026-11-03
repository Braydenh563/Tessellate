// P2 leftovers: drag at a narrow window height, the 120-block switch, touch zoom, phone palette.
process.env.BASE ||= "http://127.0.0.1:8781";
process.env.SCRATCH ||= require("os").tmpdir();
const { boot } = require("./lib.js");
const W = Number(process.argv[2] || 390);
const H = Number(process.argv[3] || 560);
const MODE = process.argv[4] || "drag";
(async () => {
  const phone = W < 600;
  const { browser, page } = await boot({ viewport: { width: W, height: H }, ...(phone ? { hasTouch: true, isMobile: true } : {}) });
  const out = {};
  const src = "flowchart TD\n" + Array.from({ length: 10 }, (_, i) => `  N${i}["Step ${i}"]`).join("\n") + "\n";
  await page.evaluate(async (c) => {
    const r = await api("/documents", { method: "POST", body: JSON.stringify({ title: "P2 narrow " + Date.now(), content: c, file_type: "mmd" }) });
    const doc = await r.json();
    switchTab("documents");
    await openDocument(doc.id);
  }, src);
  await page.waitForSelector(".dgm-pane", { timeout: 15000 });
  await page.waitForTimeout(1200);
  const geo = () => page.evaluate(() => {
    const r = (s) => { const e = document.querySelector(s); if (!e) return null; const b = e.getBoundingClientRect(); return [Math.round(b.top), Math.round(b.bottom), Math.round(e.scrollHeight), Math.round(e.clientHeight)]; };
    return { win: innerHeight, dock: r(".dgm-dock"), pic: r(".dgm-picture"), pane: r(".dgm-pane"), preview: r("#doc-preview"), panes: r("#doc-panes"), page: [Math.round(scrollY), document.documentElement.scrollHeight] };
  });
  out.geo = await geo(); await page.screenshot({ path: process.env.SCRATCH + `/p2-start-${W}x${H}.png` });
  const order = () => page.evaluate(() => docText().split("\n").filter((l) => /N\d/.test(l) && !/-->/.test(l)).map((l) => l.trim().slice(0, 2)).join(","));
  out.before = await order();
  // drag the first block to below the last one (reachable only by scrolling the pane while held)
  await page.evaluate(() => document.querySelector(".dgm-pane").scrollIntoView({ block: "end" }));
  await page.waitForTimeout(300);
  const first = page.locator(".dgm-block").first();
  const a = await first.boundingBox();
  await page.mouse.move(a.x + 60, a.y + a.height / 2);
  await page.mouse.down();
  await page.waitForTimeout(400);
  await page.mouse.move(a.x + 62, a.y + a.height / 2 + 8, { steps: 3 });
  const pane = await page.evaluate(() => { const b = document.querySelector(".dgm-pane").getBoundingClientRect(); const p = document.querySelector("#doc-preview").getBoundingClientRect(); return { top: b.top, bottom: Math.min(b.bottom, p.bottom, innerHeight) }; });
  const targetY = Math.min(H - 6, pane.bottom - 6);
  await page.mouse.move(a.x + 60, targetY, { steps: 12 });
  for (let i = 0; i < 40; i++) await page.waitForTimeout(50);
  out.during = await page.evaluate(() => ({ paneScroll: document.querySelector(".dgm-pane").scrollTop, pageScroll: scrollY, previewScroll: document.querySelector("#doc-preview").scrollTop, mark: !document.querySelector(".dgm-drop").classList.contains("hidden") || !!document.querySelector(".dgm-target") }));
  await page.mouse.up();
  await page.waitForTimeout(500);
  out.after = await order();
  out.moved = out.after !== out.before;
  out.geoAfter = await geo();
  console.log(JSON.stringify(out));
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
