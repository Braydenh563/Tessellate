// The block bar must never cover text: hover every block of a long document in Read view and
// intersect the bar with every text line's rect and every block's rect (the owner, 2026-11-11).
//   BASE=http://127.0.0.1:8791 node scratchpad/ui-sweeps/blockbar-gutter.js [width]
const { boot } = require("./lib.js");
(async () => {
  const width = Number(process.argv[2] || 1440);
  const { page, browser } = await boot({ viewport: { width, height: 900 } });
  try {
    await page.setViewportSize({ width, height: 900 });
    await page.evaluate(async () => {
      const headers = { "X-Auth-Token": localStorage.getItem("token") || "", "Content-Type": "application/json" };
      const long = Array.from({ length: 12 }, (_, i) => `Sentence ${i} of a long question about advice on what I should make, manage and delete across my notes this quarter.`).join(" ");
      const text = ["Gutter probe", "", "> [!note] Box above", "> A callout whose last line the bar used to cover.", "", long, "", long, "", "Short one.", "", long].join("\n");
      const doc = await (await fetch("/documents", { method: "POST", headers, body: JSON.stringify({ title: "Gutter probe", content: text }) })).json();
      if (typeof loadDocuments === "function") await loadDocuments();
      switchTab("documents");
      await new Promise((r) => setTimeout(r, 500));
      await openDocument(doc.id);
      await new Promise((r) => setTimeout(r, 1800));
      setDocView("rendered");
      await new Promise((r) => setTimeout(r, 800));
    });
    console.log(await page.evaluate(() => { const c = getComputedStyle(document.getElementById('doc-preview')); return 'padR ' + c.paddingRight + ' gutter ' + c.getPropertyValue('--doc-block-gutter') + ' hover ' + matchMedia('(hover: hover)').matches; }));
    const n = await page.evaluate(() => [...document.querySelectorAll("#doc-preview > [data-src-line]")].length);
    let worst = 0, shown = 0;
    for (let i = 0; i < n; i += 1) {
      const pt = await page.evaluate((i) => {
        const el = [...document.querySelectorAll("#doc-preview > [data-src-line]")][i];
        el.scrollIntoView({ block: "center" });
        const r = el.getBoundingClientRect();
        return { x: r.left + r.width / 2, y: r.top + Math.min(10, r.height / 2) };
      }, i);
      await page.mouse.move(pt.x - 30, pt.y + 3);
      await page.mouse.move(pt.x, pt.y);
      await page.waitForTimeout(300);
      const res = await page.evaluate(() => {
        const bar = document.getElementById("doc-block-bar");
        if (!bar || bar.classList.contains("hidden")) return null;
        const b = bar.getBoundingClientRect();
        const hit = (r) => Math.max(0, Math.min(b.right, r.right) - Math.max(b.left, r.left)) * Math.max(0, Math.min(b.bottom, r.bottom) - Math.max(b.top, r.top));
        let over = 0;
        const preview = document.getElementById("doc-preview");
        const walker = document.createTreeWalker(preview, NodeFilter.SHOW_TEXT);
        const range = document.createRange();
        for (let t = walker.nextNode(); t; t = walker.nextNode()) {
          if (!t.nodeValue.trim()) continue;
          range.selectNodeContents(t);
          for (const r of range.getClientRects()) over += hit(r);
        }
        const blocks = [...preview.children].reduce((s, c) => s + hit(c.getBoundingClientRect()), 0);
        const dbg = [...preview.children].map((c) => { const r = c.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.right), Math.round(r.top), Math.round(r.bottom)].join(','); }).join(' | ');
        const p = preview.getBoundingClientRect();
        return { bar: [Math.round(b.left), Math.round(b.right), Math.round(b.top), Math.round(b.bottom)].join(','), dbg, over: Math.round(over), blocks: Math.round(blocks), inside: b.left >= p.left && b.right <= p.right && b.top >= p.top && b.bottom <= p.bottom, w: Math.round(b.width), h: Math.round(b.height) };
      });
      if (res) { shown += 1; worst = Math.max(worst, res.over, res.blocks); console.log(i, JSON.stringify(res)); } else console.log(i, "bar not shown");
    }
    console.log(`width ${width}: blocks ${n}, bar shown ${shown}, worst overlap px2 ${worst}`);
  } finally { await browser.close(); }
})();
