// The note's Live, Source and Read switch in the Capture strip (L-documents-53): the strip's own buttons, not a
// `.seg` well. PASS when it is as tall as Bold, the well and the resting segments have no fill, the chosen one wears
// the accent edge, and the strip holds one row inside its box. Usage: BASE=http://127.0.0.1:8890 THEME=dark node note-view-seg.js
const { boot } = require("./lib.js");
let bad = 0;
(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.waitForTimeout(1500);
  const conf = await page.evaluate(() => { const d = document.querySelector(".confirm-overlay"); return d ? d.innerText.slice(0, 300) : null; });
  console.log("confirm:", JSON.stringify(conf));
  if (conf) { await page.keyboard.press("Escape"); await page.waitForTimeout(400); }
  await page.evaluate(() => switchTab("notes")); await page.waitForTimeout(1200);
  await page.evaluate(() => showNotesSection("capture")); await page.waitForTimeout(800); await page.click("#entry-content").catch(() => {}); await page.waitForTimeout(1500);
  for (const theme of [process.env.THEME]) {
    
    for (const w of [1280, 1440, 1920]) {
      await page.setViewportSize({ width: w, height: 900 }); await page.waitForTimeout(500);
      const m = await page.evaluate(() => {
        const bb = document.getElementById("note-toolbar"); window.__k = [...bb.children].map((k) => (k.dataset.md || k.id || k.tagName) + ":" + Math.round(k.getBoundingClientRect().width)).join(" ") + " cls=" + bb.className;
        const r = (e) => e.getBoundingClientRect();
        const seg = document.getElementById("entry-view-seg"); const bar = document.getElementById("note-toolbar");
        const box = bar.closest(".note-composer");
        const cs = getComputedStyle(seg); const b0 = seg.querySelector("button[aria-pressed=false]"); const bs = getComputedStyle(b0);
        const on = seg.querySelector('[aria-pressed="true"]'); const os = getComputedStyle(on);
        const plain = bar.querySelector('[data-md="bold"]'); const ps = getComputedStyle(plain);
        const kids = [...bar.children].filter((k) => k.getClientRects().length);
        const mid = (e) => r(e).top + r(e).height / 2; const first = mid(kids[0]);
        const ins = bar.querySelector('[data-md="insert"]');
        return { inBar: bar.contains(seg), parent: seg.parentElement.id || seg.parentElement.className, segH: r(seg).height, segW: Math.round(r(seg).width), segBg: cs.backgroundColor, segBorder: cs.borderTopWidth + " " + cs.borderTopColor, segRadius: cs.borderTopLeftRadius,
          btnH: r(b0).height, btnBg: bs.backgroundColor, onBg: os.backgroundColor, onBorder: os.borderTopWidth + " " + os.borderTopColor, onOutline: os.outlineStyle + " " + os.boxShadow.slice(0, 60),
          plainH: r(plain).height, plainBg: ps.backgroundColor, plainRadius: ps.borderTopLeftRadius,
          barRight: Math.round(r(bar).right), boxRight: Math.round(r(box).right), offRow: kids.filter((k) => Math.abs(mid(k) - first) > 12).map((k) => k.dataset.md || k.id || k.className),
          insertShown: !!(ins && ins.getClientRects().length), folded: bar.querySelectorAll(".doc-toolbar-over").length, segOver: seg.classList.contains("doc-toolbar-over"), words: [...seg.querySelectorAll(".toolbar-word")].map((s) => getComputedStyle(s).display).join(",") };
      });
      const clear = (c) => c === "rgba(0, 0, 0, 0)" || c === "transparent";
      const pass = m.segH === m.plainH && clear(m.segBg) && clear(m.btnBg) && !m.onBorder.endsWith("rgba(0, 0, 0, 0)") && m.barRight <= m.boxRight && !m.offRow.length;
      if (!pass) bad += 1;
      console.log(pass ? "PASS" : "FAIL", theme, w, `seg ${m.segH}px bold ${m.plainH}px well ${m.segBg} rest ${m.btnBg} on ${m.onBorder} strip ${m.barRight}/${m.boxRight} off-row ${m.offRow.length} folded ${m.folded}`);
    }
  }
  await browser.close();
  console.log(bad ? `${bad} FAIL` : "ALL PASS");
  process.exit(bad ? 1 : 0);
})().catch((e) => { console.error(e.message); process.exit(1); });
