// The owner, 2026-10-10: "text gets cut off on the note sidebar in the
// whiteboard". The board sidebar's Notes tab at 1440 and 1024: every text
// element in a note row either fits (scrollWidth <= clientWidth) or ends in
// an ellipsis it draws itself (text-overflow: ellipsis with overflow hidden
// and nowrap, or a line clamp), and nothing spills out of the panel.
//   BASE=http://127.0.0.1:8783 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbnoterows.js
const { boot } = require("./lib.js");
let fails = 0, passes = 0;
const check = (ok, what) => { console.log(`${ok ? "PASS" : "FAIL"}  ${what}`); ok ? passes++ : fails++; };
(async () => {
  for (const width of [1440, 1024]) {
    const { browser, page } = await boot({ viewport: { width, height: 860 } });
    await page.evaluate(async () => {
      const long = [
        "A note whose title runs on well past the width of any sidebar row anybody would draw",
        "Quarterly planning: hiring, the roadmap, the budget and the offsite in one place",
        "Supercalifragilisticexpialidocious-and-a-very-long-unbroken-word-in-a-title",
      ];
      const have = await apiJson("/entries?limit=5").catch(() => null);
      if ((have?.items || have || []).length < 12) {
        for (const t of long) await apiJson("/entries", { method: "POST", body: JSON.stringify({ content: `# ${t}\n\nBody text for ${t}, with a sentence or two so a preview line has something to show and to cut.` }) }).catch(() => {});
      }
    });
    await page.click('[data-tab="library"]');
    await page.waitForTimeout(700);
    await page.click('#library-subtabs [data-target="library-view-whiteboard"]');
    await page.waitForFunction(() => typeof window.initWhiteboard === "function", null, { timeout: 30000 });
    const board = await page.evaluate(async () => {
      await initWhiteboard();
      return apiJson("/whiteboard/boards", { method: "POST", body: JSON.stringify({ name: "Rows " + Date.now() }) });
    });
    await page.evaluate(async (b) => { await openWhiteboardBoard(b); }, board.id);
    await page.waitForTimeout(1000);
    await page.click("#wb-side-tab-notes");
    await page.waitForTimeout(1500);
    const rows = await page.evaluate(() => {
      const panel = document.getElementById("wb-sidebar-panel");
      const pr = panel.getBoundingClientRect();
      const out = { panel: Math.round(pr.width), rows: 0, cut: [], spill: [] };
      const items = panel.querySelectorAll("[data-note-id], .wb-note-row, .wb-notes-list > *, li");
      for (const row of items) {
        const rr = row.getBoundingClientRect();
        if (!rr.width) continue;
        out.rows += 1;
        if (rr.right > pr.right + 0.5) out.spill.push(`${row.className} ${Math.round(rr.right - pr.right)}px`);
        for (const el of [row, ...row.querySelectorAll("*")]) {
          const own = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
          if (!own) continue;
          const cs = getComputedStyle(el);
          const ellipsis = cs.textOverflow === "ellipsis" && cs.overflow.includes("hidden") && cs.whiteSpace === "nowrap";
          const clamp = cs.webkitLineClamp && cs.webkitLineClamp !== "none";
          //: A clamp on a padded box paints the next line on into its bottom
          //: padding, which overflow: hidden clips at the padding edge: the
          //: sliced third line the owner saw.
          if (clamp && parseFloat(cs.paddingBottom) > 0 && el.scrollHeight > el.clientHeight + 1) out.cut.push(`${el.tagName}.${el.className} clamp over padding ${cs.paddingBottom}`);
          if (el.scrollWidth > el.clientWidth + 1 && !ellipsis) out.cut.push(`${el.tagName}.${el.className} ${el.scrollWidth}>${el.clientWidth} "${el.textContent.trim().slice(0, 30)}"`);
          else if (el.scrollHeight > el.clientHeight + 1 && cs.overflow.includes("hidden") && !clamp && !ellipsis) out.cut.push(`${el.tagName}.${el.className} h ${el.scrollHeight}>${el.clientHeight} "${el.textContent.trim().slice(0, 30)}"`);
          const er = el.getBoundingClientRect();
          if (er.right > pr.right + 0.5 && er.width) out.spill.push(`${el.tagName}.${el.className} ${Math.round(er.right - pr.right)}px`);
        }
      }
      return out;
    });
    console.log(`  ${width}: panel ${rows.panel}px, ${rows.rows} rows`);
    check(rows.rows > 0, `${width}: the Notes tab lists notes (${rows.rows})`);
    check(rows.cut.length === 0, `${width}: no text cut without an ellipsis (${rows.cut.slice(0, 4).join("; ")})`);
    check(rows.spill.length === 0, `${width}: nothing past the panel's edge (${rows.spill.slice(0, 4).join("; ")})`);
    await page.screenshot({ path: `${process.env.SCRATCH || "."}/wbnoterows-${width}.png` });
    await browser.close();
  }
  console.log(`${passes}/${passes + fails}`);
  process.exit(fails ? 1 : 0);
})();
