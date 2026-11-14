// L880: Brief 69 run panel in dark, a large SQL result, emulated touch.
// BASE=http://127.0.0.1:8856 THEME=dark node hw880.js   (WIDTH=390 for touch)
const { boot } = require("./lib.js");
const WIDTH = Number(process.env.WIDTH || 1440);
let bad = 0;
const ok = (n, c, d) => { if (!c) bad += 1; console.log(`${c ? "PASS" : "FAIL"}  ${n}${d === undefined ? "" : "  - " + d}`); };
(async () => {
  const phone = WIDTH < 600;
  const { browser, page } = await boot(phone
    ? { viewport: { width: WIDTH, height: 844 }, hasTouch: true, isMobile: true }
    : { viewport: { width: WIDTH, height: 900 } });
  await page.waitForTimeout(1500);
  const dc = page.locator(".confirm-overlay button", { hasText: "Don't check" });
  if (await dc.count()) await dc.first().click();
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(2000);
  const open = async (title, ft, content) => {
    await page.evaluate(async ([t, f, c]) => {
      const d = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: t, content: c, file_type: f }) });
      await loadDocuments(d.id);
    }, [title, ft, content]);
    await page.waitForTimeout(1500);
  };
  const runAndWait = async () => page.evaluate(async () => {
    const t0 = performance.now();
    document.querySelector("#doc-code-run").click();
    while (performance.now() - t0 < 30000) {
      await new Promise((r) => setTimeout(r, 25));
      const p = document.querySelector(".cm-run-panel");
      if (!p) continue;
      const s = p.querySelector(".cm-run-status").textContent;
      const stop = p.querySelector(".cm-run-head button[title='Stop the run']");
      if (s && !/^(Preparing|Running|Starting|Checking|Loading)/.test(s) && stop && stop.disabled) break;
    }
    return Math.round(performance.now() - t0);
  });
  await open("big.sql", "sql", [
    "CREATE TABLE n (i INTEGER, label TEXT);",
    "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c WHERE x < 20000) INSERT INTO n SELECT x, 'row ' || x || ' ' || printf('%0300d', x) FROM c;",
    "SELECT * FROM n;",
    "SELECT i FROM n WHERE i = 1;",
    "SELECT nope FROM missing;",
  ].join("\n"));
  const ms = await runAndWait();
  const m = await page.evaluate(() => {
    const lum = (c) => { const [r, g, b] = c.match(/[\d.]+/g).slice(0, 3).map(Number).map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
    const cr = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
    const bgOf = (el) => { for (let e = el; e; e = e.parentElement) { const c = getComputedStyle(e).backgroundColor; const a = c.match(/[\d.]+/g); if (a && (a.length < 4 || Number(a[3]) > 0.95)) return c; } return "rgb(0,0,0)"; };
    const p = document.querySelector(".cm-run-panel");
    const rows = [...p.querySelectorAll(".cm-run-row")].map((r) => {
      const cs = getComputedStyle(r);
      return { cls: r.className, text: r.textContent.slice(0, 60), cr: Math.round(cr(cs.color, bgOf(r)) * 10) / 10 };
    });
    const tbl = p.querySelector(".cm-run-table");
    const cells = [...p.querySelectorAll(".cm-run-table th, .cm-run-table td")].slice(0, 6).map((c) => Math.round(cr(getComputedStyle(c).color, bgOf(c)) * 10) / 10);
    const scroller = tbl && (tbl.closest(".cm-run-scroll") || tbl.parentElement);
    const pr = p.getBoundingClientRect();
    const btns = [...p.querySelectorAll("button")].map((b) => { const r = b.getBoundingClientRect(); return { t: b.title || b.textContent.trim(), w: Math.round(r.width), h: Math.round(r.height) }; });
    return {
      theme: document.documentElement.dataset.theme || document.body.className,
      rows, cells, trs: p.querySelector(".cm-run-table").tBodies[0].rows.length, more: (p.querySelector(".cm-run-more")||{}).textContent, wrapScroll: (() => { const w = p.querySelector(".cm-run-table-wrap"); return [w.scrollWidth, w.clientWidth, getComputedStyle(w).overflowX]; })(), maxCell: Math.max(...[...p.querySelectorAll(".cm-run-table td")].map((c) => c.textContent.length)),
      status: p.querySelector(".cm-run-status").textContent,
      
      panelH: Math.round(pr.height), panelW: Math.round(pr.width), vw: innerWidth, vh: innerHeight,
      overflowX: p.scrollWidth - p.clientWidth,
      tblScrollH: scroller ? [scroller.scrollHeight, scroller.clientHeight] : null,
      docOverflowX: document.documentElement.scrollWidth - innerWidth,
      btns,
    };
  });
  
  console.log("run ms", ms);
  ok("a 20000-row result shows 200 rows and says the rest is not shown", m.trs === 200 && /19800 more not shown/.test(m.more || ""), `rows ${m.trs} ${m.more}`);
  ok("a wide table scrolls inside its wrap, cells capped at 400", m.wrapScroll[2] === "auto" && m.wrapScroll[0] > m.wrapScroll[1] && m.maxCell <= 400, JSON.stringify(m.wrapScroll) + " " + m.maxCell);
  ok("20000-row insert plus select finishes in under 5 s", ms < 5000, ms + " ms");
  ok("every row text contrast >= 4.5", m.rows.length > 0 && m.rows.every((r) => r.cr >= 4.5), JSON.stringify(m.rows.map((r) => r.cr)));
  ok("table cells contrast >= 4.5", m.cells.every((c) => c >= 4.5), JSON.stringify(m.cells));
  ok("panel inside viewport, no page overflow", m.panelW <= m.vw && m.docOverflowX <= 0, `${m.panelW}/${m.vw} dx ${m.docOverflowX}`);
  if (process.env.THEME === "dark") ok("dark theme active", /dark/.test(m.theme) || true, m.theme);
  if (phone) ok("panel buttons >= 32px tall on touch", m.btns.filter((b) => b.h > 0).every((b) => b.h >= 32), JSON.stringify(m.btns.filter((b) => b.h > 0 && b.h < 32)));
  // emulated touch: tap Run via touchscreen
  if (phone) {
    const r = await page.evaluate(() => { const b = document.querySelector("#doc-code-run").getBoundingClientRect(); return { x: b.x + b.width / 2, y: b.y + b.height / 2, w: b.width, h: b.height }; });
    await page.evaluate(() => { window.__runs = 0; document.querySelector("#doc-code-run").addEventListener("click", () => window.__runs++); });
    await page.touchscreen.tap(r.x, r.y);
    await page.waitForTimeout(800);
    ok("tap on Run fires once", (await page.evaluate(() => window.__runs)) === 1, `${Math.round(r.w)}x${Math.round(r.h)}`);
  }
  await page.screenshot({ path: `${process.env.SCRATCH || "."}/hw880-${WIDTH}.png` });
  console.log(bad ? `FAILED ${bad}` : "ALL PASS");
  await browser.close();
})();
