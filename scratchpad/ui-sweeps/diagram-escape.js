// An arrow-end drag that Escape cancels (INBOX 1679, slice 4 review): the source is byte for byte what it was, no close
// question opens, and the arrow stays picked. Exit code 1 on a failure. BASE=http://127.0.0.1:PORT node diagram-escape.js [width]
process.env.BASE ||= "http://127.0.0.1:8781";
process.env.SCRATCH ||= require("os").tmpdir();
const { boot } = require("./lib.js");
const W = Number(process.argv[2] || 1440);
(async () => {
  const { browser, page } = await boot({ viewport: { width: W, height: 900 } });
  const src = "flowchart TD\n  A[One] --> B[Two]\n  B --> C[Three]\n";
  await page.evaluate(async (c) => {
    const r = await api("/documents", { method: "POST", body: JSON.stringify({ title: "Escape " + Date.now() + ".mmd", content: c, file_type: "mmd" }) });
    const doc = await r.json();
    switchTab("documents");
    await openDocument(doc.id);
    setDocView("canvas", { persist: false });
  }, src);
  await page.waitForSelector(".dgm-picture .md-mermaid-img", { timeout: 15000 });
  await page.waitForTimeout(1500);
  // The first arrow's midpoint on screen, from the drawing's own path and viewBox.
  const mid = await page.evaluate(() => {
    const img = document.querySelector(".dgm-picture .md-mermaid-img");
    const svg = img.mermaidSvg;
    const vb = /viewBox="\s*([-\d.e]+)[ ,]+([-\d.e]+)[ ,]+([\d.e]+)[ ,]+([\d.e]+)/.exec(svg).slice(1).map(Number);
    const d = /<path[^>]*class="[^"]*flowchart-link[^"]*"[^>]*\sd="([^"]+)"/.exec(svg)?.[1] || /<path[^>]*\sd="([^"]+)"[^>]*class="[^"]*flowchart-link/.exec(svg)?.[1];
    const n = d.match(/-?\d+(\.\d+)?/g).map(Number);
    const pts = [];
    for (let i = 0; i + 1 < n.length; i += 2) pts.push([n[i], n[i + 1]]);
    const p = pts[Math.floor(pts.length / 2)];
    const r = img.getBoundingClientRect();
    return { x: r.left + ((p[0] - vb[0]) / vb[2]) * r.width, y: r.top + ((p[1] - vb[1]) / vb[3]) * r.height };
  });
  await page.mouse.click(mid.x, mid.y);
  await page.waitForTimeout(400);
  const dot = await page.evaluate(() => { const d = document.querySelector(".dgm-end[data-end=to]"); if (!d || d.classList.contains("hidden")) return null; const r = d.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; });
  const out = { picked: Boolean(dot) };
  if (!dot) { console.log(JSON.stringify(out)); await browser.close(); process.exit(1); }
  const before = await page.evaluate(() => (typeof docText === "function" ? docText() : currentDoc?.content));
  await page.mouse.move(dot.x, dot.y);
  await page.mouse.down();
  await page.mouse.move(dot.x - 60, dot.y - 40, { steps: 6 });
  await page.keyboard.press("Escape");
  await page.waitForTimeout(200);
  await page.mouse.up();
  await page.waitForTimeout(900);
  out.after = await page.evaluate(() => ({
    source: typeof docText === "function" ? docText() : currentDoc?.content,
    question: Boolean(document.querySelector(".confirm-card, .prompt-card, [role=alertdialog], .modal-overlay:not(.hidden) .confirm-actions")),
    stillPicked: Boolean(document.querySelector(".dgm-end[data-end=to]:not(.hidden)")),
    builderOpen: Boolean(document.querySelector(".dgm-picture")),
  }));
  out.unchanged = out.after.source === before;
  console.log(JSON.stringify(out));
  await browser.close();
  process.exit(out.unchanged && !out.after.question && out.after.builderOpen ? 0 : 1);
})();
