// The Documents strip (#doc-toolbar) runs the same checks: one mechanism, one row, the rest behind More.
// The Capture note box's formatting toolbar (#note-toolbar) at every width, with the Connections
// column closed and open: each control inside the strip, the strip inside its box, one row until
// More is pressed, every folded control reachable behind More; the menu opener drawn like the
// buttons beside it (no filled pill, one height); and the empty box's caret one line high.
// Usage: BASE=http://127.0.0.1:8877 THEME=dark node capture-toolbar.js
const { boot } = require("./lib.js");

let bad = 0;
const ok = (name, cond, detail) => {
  if (!cond) bad += 1;
  console.log(`${cond ? "PASS" : "FAIL"}  ${name}  ${detail}`);
};
const WIDTHS = [360, 768, 1024, 1280, 1440, 1920, 2560];

//: Measured in the page: px for every claim, the strip's own and its container's right edges first.
function measure(id) {
  const bar = document.getElementById(id);
  const box = id === "note-toolbar" ? bar.closest(".note-composer") : bar.parentElement;
  const r = (el) => el.getBoundingClientRect();
  const b = r(bar);
  const c = r(box);
  const shown = (el) => el.getClientRects().length > 0;
  const kids = [...bar.children].filter(shown);
  const mid = (el) => r(el).top + r(el).height / 2;
  const first = kids.length ? mid(kids[0]) : 0;
  const outside = kids.filter((k) => r(k).right > b.right + 0.5 || r(k).left < b.left - 0.5 ||
    r(k).bottom > b.bottom + 0.5 || r(k).top < b.top - 0.5);
  const offRow = kids.filter((k) => Math.abs(mid(k) - first) > 12);
  const folded = [...bar.querySelectorAll(".doc-toolbar-over:not(.doc-toolbar-sep)")];
  const more = bar.querySelector(".doc-toolbar-more");
  const insert = bar.querySelector('[data-md="insert"]');
  const summary = bar.querySelector("summary");
  const plain = bar.querySelector('[data-md="bold"]');
  const sc = summary ? getComputedStyle(summary) : null;
  return {
    barRight: Math.round(b.right), boxRight: Math.round(c.right), barLeft: Math.round(b.left), boxLeft: Math.round(c.left),
    inBox: b.right <= c.right + 0.5 && b.left >= c.left - 0.5,
    outside: outside.map((k) => k.dataset.md || k.className || k.tagName),
    offRow: offRow.map((k) => k.dataset.md || k.className || k.tagName),
    folded: folded.length,
    moreShown: Boolean(more && !more.hidden && shown(more)),
    open: bar.classList.contains("is-more-open"),
    insertShown: Boolean(insert && shown(insert)),
    insertRight: insert && shown(insert) ? Math.round(r(insert).right) : null,
    summaryBg: sc ? sc.backgroundColor : "",
    summaryBorder: sc ? sc.borderTopColor : "",
    summaryH: summary && shown(summary) ? Math.round(r(summary).height * 10) / 10 : null,
    plainH: plain && shown(plain) ? Math.round(r(plain).height * 10) / 10 : null,
    barH: Math.round(b.height),
  };
}
const transparent = (c) => c === "rgba(0, 0, 0, 0)" || c === "transparent" || /\/ 0\)$/.test(c);

(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.evaluate(() => switchTab("notes"));
  await page.waitForTimeout(1200);
  await page.evaluate(() => showNotesSection("capture"));
  await page.waitForTimeout(800);
  await page.click("#entry-content").catch(() => {});
  await page.waitForTimeout(1500);

  for (const [id, rail] of [["note-toolbar", false], ["note-toolbar", true], ["doc-toolbar", false]]) {
    await page.evaluate((a) => {
      const [bar, on] = a;
      if (bar === "doc-toolbar") { switchTab("documents"); return; }
      switchTab("notes");
      const open = !document.getElementById("notes-rail")?.hidden;
      if (open !== on) document.getElementById("notes-rail-toggle")?.click();
    }, [id, rail]);
    if (id === "doc-toolbar") {
      await page.waitForTimeout(1500);
      if (!(await page.evaluate(() => document.getElementById("doc-toolbar").getClientRects().length))) {
        await page.evaluate(() => createDocument());
        await page.waitForTimeout(1500);
      }
      await page.evaluate(() => { prefs.set("doc-toolbar-collapsed", "0"); applyDocToolbarCollapsed(false); });
    } else await page.waitForTimeout(300);
    for (const w of WIDTHS) {
      await page.setViewportSize({ width: w, height: w === 1920 ? 1080 : 900 });
      await page.waitForTimeout(800);
      const tag = `${id === "doc-toolbar" ? "documents" : "capture"} ${w}px${id === "doc-toolbar" ? "" : " rail " + (rail ? "open" : "closed")}`;
      const closed = await page.evaluate(measure, id);
      const wasOpen = closed.open;
      ok(`${tag} strip inside its box`, closed.inBox,
        `strip ${closed.barLeft}-${closed.barRight}, box ${closed.boxLeft}-${closed.boxRight}`);
      ok(`${tag} every control inside the strip`, closed.outside.length === 0, `outside: ${closed.outside.join(",") || "none"}`);
      ok(`${tag} one row while closed`, closed.offRow.length === 0, `off the row: ${closed.offRow.join(",") || "none"}, strip ${closed.barH}px`);
      ok(`${tag} Insert on the row or behind More`, closed.insertShown || id === "doc-toolbar" && closed.outside.length === 0 && closed.folded === 0 || (closed.moreShown && closed.folded > 0),
        `insert right ${closed.insertRight}, folded ${closed.folded}, More ${closed.moreShown}`);
      ok(`${tag} menu opener has no resting fill`, transparent(closed.summaryBg) && transparent(closed.summaryBorder) || closed.summaryH === null,
        `bg ${closed.summaryBg}, border ${closed.summaryBorder}`);
      ok(`${tag} menu opener as tall as a button`, closed.summaryH === null || closed.summaryH === closed.plainH,
        `opener ${closed.summaryH}px, button ${closed.plainH}px`);
      if (closed.moreShown) {
        await page.click("#" + id + " .doc-toolbar-more");
        await page.waitForTimeout(400);
        const opened = await page.evaluate(measure, id);
        const reach = await page.evaluate((barId) => {
          const bar = document.getElementById(barId);
          const missing = [...bar.querySelectorAll(".doc-toolbar-over:not(.doc-toolbar-sep)")].filter((el) => !el.getClientRects().length);
          return missing.length;
        }, id);
        ok(`${tag} More shows every folded control inside the strip`, opened.outside.length === 0 && reach === 0 && opened.inBox,
          `outside ${opened.outside.length}, still hidden ${reach}, strip ${opened.barLeft}-${opened.barRight} of box ${opened.boxRight}`);
        if (!wasOpen) await page.click("#" + id + " .doc-toolbar-more");
        await page.waitForTimeout(300);
      }
    }
  }

  await page.evaluate(() => { switchTab("notes"); showNotesSection("capture"); });
  await page.waitForTimeout(1200);
  await page.click("#entry-content").catch(() => {});
  await page.waitForTimeout(1200);
  //: The empty box's caret: one line, not the placeholder's three.
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(600);
  const caret = await page.evaluate(async () => {
    const content = document.querySelector(".note-surface .cm-content");
    if (!content) return null;
    content.focus();
    await new Promise((res) => setTimeout(res, 400));
    const row = content.querySelector(".cm-line");
    const line = parseFloat(getComputedStyle(row).lineHeight);
    const cursor = document.querySelector(".note-surface .cm-cursor");
    //: The native caret's own height: a collapsed range at the line's start.
    const range = document.createRange();
    range.setStart(row, 0);
    range.collapse(true);
    const rects = range.getClientRects();
    return {
      line, rowH: row.getBoundingClientRect().height, empty: content.textContent.replace(/\s/g, "") === "" || Boolean(content.querySelector(".cm-placeholder")),
      cursor: cursor ? cursor.getBoundingClientRect().height : null, range: rects.length ? rects[0].height : null,
    };
  });
  ok("empty box line is one line high", Boolean(caret) && caret.empty && Math.abs(caret.rowH - caret.line) <= 2,
    `empty line ${caret && caret.rowH}px, line-height ${caret && caret.line}px`);
  ok("empty box caret is one line high", Boolean(caret) && caret.cursor !== null && caret.cursor <= caret.line + 2 && (caret.range === null || caret.range <= caret.line + 2),
    `drawn caret ${caret && caret.cursor}px, native range ${caret && caret.range}px, line-height ${caret && caret.line}px`);

  await browser.close();
  console.log(bad ? `FAILED: ${bad}` : "ALL PASS");
  process.exit(bad ? 1 : 0);
})();
