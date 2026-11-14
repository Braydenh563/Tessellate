// L881: the flagged-word suggestion menu at 390 with touch emulation: a long press (CDP touch held 700 ms)
// on a misspelt word opens the menu, its rows are a finger's size, and choosing a candidate runs docProseFix.
// Run with Suggest changes off, then on, in the same document.
//   BASE=http://127.0.0.1:8817 node scratchpad/ui-sweeps/docsverify-suggest.js
process.env.BASE ||= "http://127.0.0.1:8817";
process.env.SCRATCH ||= require("os").tmpdir();
const { boot } = require("./lib.js");
let bad = 0;
const ok = (n, c, d) => { if (!c) bad += 1; console.log(`${c ? "PASS" : "FAIL"}  ${n}  ${d === undefined ? "" : JSON.stringify(d)}`); };
(async () => {
  const { browser, page } = await boot({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
  const cdp = await page.context().newCDPSession(page);
  const touch = (type, x, y) => cdp.send("Input.dispatchTouchEvent", { type, touchPoints: type === "touchEnd" ? [] : [{ x, y, id: 0 }] });
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(2000);
  const open = async (title, body) => {
    await page.evaluate(async ([t, c]) => {
      const d = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: t, content: c, file_type: "md" }) });
      await loadDocuments(d.id);
      setDocView("live", { persist: false });
    }, [title, body]);
    await page.waitForTimeout(2500);
  };
  const flagBox = () => page.evaluate(() => {
    const el = document.querySelector(".doc-flag, .cm-finding");
    if (!el) return null;
    el.scrollIntoView({ block: "center" });
    const b = el.getBoundingClientRect();
    return { x: b.left + b.width / 2, y: b.top + b.height / 2, text: el.textContent };
  });
  for (const mode of ["off", "on"]) {
    const title = `suggest ${mode} ${Date.now()}`;
    await open(title, "A line with a sentance that has a typo in it.\n\nSecond line.\n");
    if (mode === "on") await page.evaluate(() => setDocSuggestMode(true));
    await page.waitForFunction(() => document.querySelector(".doc-flag, .cm-finding"), null, { timeout: 15000 }).catch(() => {});
    const f = await flagBox();
    ok(`[${mode}] a word is flagged`, !!f, f);
    if (!f) continue;
    await touch("touchStart", f.x, f.y);
    await page.waitForTimeout(900);
    await touch("touchEnd");
    await page.waitForTimeout(500);
    const m = await page.evaluate(() => {
      const menu = document.getElementById("doc-suggest-menu");
      const open = menu && !menu.classList.contains("hidden");
      const items = open ? [...menu.querySelectorAll(".doc-suggest-item")] : [];
      const mb = menu.getBoundingClientRect();
      return {
        open, menu: [Math.round(mb.left), Math.round(mb.top), Math.round(mb.width), Math.round(mb.height)],
        inView: mb.left >= 0 && mb.right <= innerWidth && mb.top >= 0 && mb.bottom <= innerHeight,
        heights: items.map((e) => Math.round(e.getBoundingClientRect().height)),
        widths: items.map((e) => Math.round(e.getBoundingClientRect().width)),
        labels: items.map((e) => e.textContent.trim().slice(0, 24)),
      };
    });
    console.log(`[${mode}]`, JSON.stringify(m));
    ok(`[${mode}] the long press opens the menu`, m.open);
    ok(`[${mode}] the menu is inside the 390 window`, m.inView, m.menu);
    ok(`[${mode}] every row is at least 44 tall`, m.heights.length > 0 && Math.min(...m.heights) >= 44, m.heights);
    const before = await page.evaluate(() => docSurface().value);
    // Choose the first candidate with a tap.
    const c = await page.evaluate(() => { const b = document.querySelector("#doc-suggest-menu .doc-suggest-best, #doc-suggest-menu .doc-suggest-item"); const r = b.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2, t: b.textContent.trim() }; });
    await page.touchscreen.tap(c.x, c.y);
    await page.waitForTimeout(800);
    const after = await page.evaluate(() => ({ v: docSurface().value, open: !document.getElementById("doc-suggest-menu").classList.contains("hidden"), marks: (docSurface().value.match(/\{\+\+|\{--|\{~~|<ins|<del/g) || []).length }));
    console.log(`[${mode}] chose "${c.t}"`, JSON.stringify({ before: before.slice(0, 40), after: after.v.slice(0, 60), marks: after.marks }));
    ok(`[${mode}] the typo is gone from the text`, !/sentance/.test(after.v) || after.marks > 0, after.v.slice(0, 60));
    ok(`[${mode}] the candidate is in the text`, after.v.includes(c.t) || after.marks > 0, c.t);
    ok(`[${mode}] the menu closes`, !after.open);
  }
  console.log(bad ? `${bad} FAILED` : "all passed");
  await browser.close();
  process.exit(bad ? 1 : 0);
})();
