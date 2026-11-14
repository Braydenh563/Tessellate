// L892: the diagram shelf at 390 with touch emulation: which tiles show, their size, that none runs past
// the window, the caret menu listing the rest, and the fold button.
//   BASE=http://127.0.0.1:8817 node scratchpad/ui-sweeps/docsverify-shelf.js
process.env.BASE ||= "http://127.0.0.1:8817";
process.env.SCRATCH ||= require("os").tmpdir();
const { boot } = require("./lib.js");
let bad = 0;
const ok = (n, c, d) => { if (!c) bad += 1; console.log(`${c ? "PASS" : "FAIL"}  ${n}  ${d === undefined ? "" : JSON.stringify(d)}`); };
const SRC = {
  flowchart: "flowchart TD\n  A[Start] --> B[Middle]\n  B --> C[End]\n",
  mindmap: "mindmap\n  root((Idea))\n    Branch one\n    Branch two\n",
};
(async () => {
  for (const kind of Object.keys(SRC)) {
    // A fresh page per kind: the first picture's dialog is left open otherwise.
    const { browser, page } = await boot({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
    await page.evaluate(async ([k, c]) => {
      const r = await api("/documents", { method: "POST", body: JSON.stringify({ title: `shelf ${k} ${Date.now()}`, content: "Intro\n\n```mermaid\n" + c + "```\n" }) });
      const doc = await r.json();
      switchTab("documents");
      await openDocument(doc.id);
      setDocView("live", { persist: false });
    }, [kind, SRC[kind]]);
    await page.waitForSelector(".md-mermaid-edit", { timeout: 20000 });
    await page.waitForTimeout(1200);
    await page.tap(".md-mermaid-edit");
    await page.waitForSelector(".dgm-dialog .dgm-shelf", { timeout: 20000 });
    await page.waitForTimeout(1500);
    const m = await page.evaluate(() => {
      const shelf = document.querySelector(".dgm-dialog .dgm-shelf");
      if (!shelf) return null;
      const r = (e) => { const b = e.getBoundingClientRect(); return { l: Math.round(b.left), r: Math.round(b.right), w: Math.round(b.width), h: Math.round(b.height) }; };
      const all = [...shelf.children];
      const shown = all.filter((e) => getComputedStyle(e).display !== "none");
      const sb = shelf.getBoundingClientRect();
      return {
        coarse: matchMedia("(pointer: coarse)").matches,
        total: all.length, shown: shown.length,
        hidden: all.filter((e) => getComputedStyle(e).display === "none").length,
        shelf: r(shelf), scrollW: shelf.scrollWidth, clientW: shelf.clientWidth,
        boxes: shown.map((e) => ({ n: (e.getAttribute("aria-label") || e.textContent || "").trim().slice(0, 18), ...r(e) })),
        past: shown.filter((e) => e.getBoundingClientRect().right > innerWidth + 0.5).length,
        pic: r(document.querySelector(".dgm-dialog .dgm-picture")),
        overlap: sb.bottom > document.querySelector(".dgm-dialog .dgm-picture").getBoundingClientRect().top + 0.5,
      };
    });
    console.log(`[${kind}]`, JSON.stringify(m));
    ok(`[${kind}] the shelf is drawn`, !!m);
    if (!m) { await browser.close(); continue; }
    ok(`[${kind}] touch is coarse`, m.coarse);
    ok(`[${kind}] at most 5 controls show, the rest hidden (flowchart has 6 tiles)`, m.shown <= 5 && (kind !== "flowchart" || m.hidden >= 1), [m.shown, m.hidden]);
    ok(`[${kind}] every shown control is 44 x 44 or more`, m.boxes.every((b) => b.w >= 44 && b.h >= 44), m.boxes.map((b) => [b.n, b.w, b.h]));
    ok(`[${kind}] none runs past the window`, m.past === 0 && m.shelf.r <= 390, [m.past, m.shelf.r]);
    ok(`[${kind}] the shelf does not lie over the picture`, !m.overlap, [m.shelf, m.pic]);
    // the caret opens the menu with the blocks the shelf hid
    const caret = await page.evaluate(() => { const c = [...document.querySelectorAll(".dgm-dialog .dgm-shelf > button")].filter((b) => !b.classList.contains("dgm-shelf-toggle") && !b.classList.contains("dgm-tile")).pop(); if (!c) return null; const b = c.getBoundingClientRect(); return { x: b.left + b.width / 2, y: b.top + b.height / 2 }; });
    ok(`[${kind}] a caret is on the shelf`, !!caret);
    if (caret) {
      await page.touchscreen.tap(caret.x, caret.y);
      await page.waitForTimeout(600);
      const menu = await page.evaluate(() => {
        const rows = [...document.querySelectorAll(".dgm-menu button, .menu button, [role=menu] button, .sheet-overlay .sheet-row")].filter((b) => b.getBoundingClientRect().height > 0);
        return { n: rows.length, minH: Math.min(...rows.map((b) => Math.round(b.getBoundingClientRect().height))), inView: rows.every((b) => b.getBoundingClientRect().right <= innerWidth + 0.5) };
      });
      console.log(`[${kind}] caret menu`, JSON.stringify(menu));
      ok(`[${kind}] the caret menu opens with rows`, menu.n > 0, menu);
      ok(`[${kind}] its rows are 44 tall and in the window`, menu.n > 0 && menu.minH >= 44 && menu.inView, menu);
      await page.keyboard.press("Escape");
      await page.waitForTimeout(300);
    }
    // the fold button
    const fold = await page.evaluate(() => { const b = document.querySelector(".dgm-dialog .dgm-shelf-toggle").getBoundingClientRect(); return { x: b.left + b.width / 2, y: b.top + b.height / 2 }; });
    await page.touchscreen.tap(fold.x, fold.y);
    await page.waitForTimeout(400);
    const folded = await page.evaluate(() => { const s = document.querySelector(".dgm-dialog .dgm-shelf"); return { off: s.classList.contains("dgm-shelf-off"), visible: [...s.children].filter((e) => getComputedStyle(e).display !== "none").length }; });
    ok(`[${kind}] the fold button folds it to one button`, folded.off && folded.visible === 1, folded);
    await page.touchscreen.tap(fold.x, fold.y);
    await page.waitForTimeout(300);
    await page.evaluate(() => { prefs.set("diagram.shelf", ""); });
    await browser.close();
  }
  console.log(bad ? `${bad} FAILED` : "all passed");
  process.exit(bad ? 1 : 0);
})();
