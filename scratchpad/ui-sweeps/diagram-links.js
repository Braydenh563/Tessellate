// INBOX 1771: the builder's connector rows. Menu beside its row, a click selects both ends, first row clear of the sticky bar, labels not squeezed.
//   BASE=http://127.0.0.1:8861 THEME=dark node scratchpad/ui-sweeps/diagram-links.js
process.env.BASE ||= "http://127.0.0.1:8861";
const { boot } = require("./lib.js");
const SRC = "flowchart TD\n  A[Bug reported] --> B{Can you reproduce it?}\n  B -->|No| C[Ask for details]\n  B -->|Yes| D[Fix it]\n  C -.-> B\n";
const ALL = [[1440, 900, false], [1100, 800, false], [820, 900, false], [390, 844, true], [844, 390, true]];
const SIZES = process.env.W ? ALL.filter((s) => String(s[0]) === process.env.W) : ALL;
(async () => {
  const out = [];
  for (const [w, h, touch] of SIZES) {
    const { browser, page } = await boot({ viewport: { width: w, height: h }, ...(touch ? { isMobile: true, hasTouch: true } : {}) });
    await page.evaluate(async (src) => {
      const r = await api("/documents", { method: "POST", body: JSON.stringify({ title: "Links", content: src, file_type: "mmd" }) });
      const doc = await r.json();
      switchTab("documents");
      await openDocument(doc.id);
    }, SRC);
    await page.waitForTimeout(1500);
    if (await page.locator(".dgm-body.dgm-fold-left").count()) await page.locator('.dgm-body > button[data-side="left"]').first().click();
    if (w <= 600) await page.locator('button[title="Blocks list"]').first().click();
    await page.waitForSelector(".dgm-join", { state: "visible", timeout: 15000 });
    await page.waitForTimeout(600);
    const first = await page.evaluate(() => {
      const c = document.querySelector(".dgm-block > .dgm-card").getBoundingClientRect();
      const bar = [...document.querySelectorAll("body *")].filter((e) => getComputedStyle(e).position === "sticky" && e.getBoundingClientRect().height > 0 && !e.closest(".hidden")).map((e) => ({ cls: String(e.className).slice(0, 40), t: Math.round(e.getBoundingClientRect().top), b: Math.round(e.getBoundingClientRect().bottom) }));
      const labels = [...document.querySelectorAll(".dgm-card .dgm-label")].map((l) => ({ t: l.textContent, h: Math.round(l.getBoundingClientRect().height), sw: l.scrollWidth, cw: l.clientWidth }));
      return { cardTop: Math.round(c.top), bar, labels };
    });
    const clip = await page.evaluate(() => [...document.querySelectorAll(".dgm-label, .dgm-join-to, .dgm-join-label")].filter((e) => e.scrollWidth > e.clientWidth).map((e) => ({ cls: e.className.slice(0, 20), t: e.textContent.slice(0, 24), over: e.scrollWidth - e.clientWidth, cw: e.clientWidth })));
    // e/c: the Suggestions disclosure, closed then open: caret turn, row inset against the summary text, last outline row against the open list.
    const sug = await page.evaluate(async () => {
      const head = document.querySelector(".dgm-ai-lints-head");
      if (!head) return null;
      const turn = () => { const c = getComputedStyle(head.querySelector(".contents-caret")); return { rotate: c.rotate, expanded: head.getAttribute("aria-expanded") }; };
      const closed = turn();
      head.click();
      await new Promise((r) => setTimeout(r, 400));
      const open = turn();
      const words = head.querySelector(".dgm-ai-lints-words").getBoundingClientRect();
      const li = document.querySelector(".dgm-ai-lints li");
      const text = li && (li.querySelector(".dgm-ai-lint-text") || li);
      const list = document.querySelector(".dgm-ai-lints").getBoundingClientRect();
      const rows = [...document.querySelectorAll(".dgm-block")].filter((b) => b.getBoundingClientRect().height > 0);
      const last = rows[rows.length - 1].getBoundingClientRect();
      const box = head.closest(".dgm-ai");
      const sc = (() => { for (let e = head; e; e = e.parentElement) if (e.scrollHeight > e.clientHeight + 1 && /auto|scroll/.test(getComputedStyle(e).overflowY)) return e; return null; })();
      return { closed, open, wordsLeft: Math.round(words.left), textLeft: text ? Math.round(text.getBoundingClientRect().left) : null, listTop: Math.round(list.top), listBottom: Math.round(list.bottom), lastRowTop: Math.round(last.top), lastRowBottom: Math.round(last.bottom), lastBelowListTop: Math.round(last.bottom) > Math.round(list.top) && Math.round(last.top) < Math.round(list.bottom), boxPos: box && getComputedStyle(box).position, scroller: sc && { cls: String(sc.className).slice(0, 30), sh: sc.scrollHeight, ch: sc.clientHeight } };
    });
    await page.evaluate(() => document.querySelector(".dgm-ai-lints-head")?.click());
    await page.evaluate(() => document.querySelectorAll(".dgm-join")[1].scrollIntoView({ block: "center" }));
    const go = page.locator(".dgm-join:visible").nth(1);
    await go.click();
    await page.waitForTimeout(300);
    const went = await page.evaluate(() => ({ selected: document.querySelector('.dgm-block[aria-selected="true"]')?.getAttribute("aria-label"), arrow: document.querySelector(".dgm-edge-on")?.getAttribute("d")?.length || 0, focusOnRow: document.activeElement?.classList.contains("dgm-join") }));
    const chip = page.locator(".dgm-joinline .kebab-opener:visible").nth(1);
    // A real press at the button's centre: locator.click() scrolls the pane first, and the pane settles back 28px later at 820.
    await chip.evaluate((b) => b.scrollIntoView({ block: "center" }));
    await page.waitForTimeout(200);
    const at = await chip.boundingBox();
    await page.mouse.click(at.x + at.width / 2, at.y + at.height / 2);
    await page.waitForTimeout(400);
    // The row is the pressed button's own line, measured after the press (a nth() of the visible lines can be another one).
    const row = await chip.evaluate((b) => { const r = b.closest(".dgm-joinline").getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width, height: r.height }; });
    const menu = await page.evaluate(() => { const m = document.querySelector(".action-menu:not(.hidden):not(.submenu)"); if (!m) return null; const r = m.getBoundingClientRect(); return { x: Math.round(r.x), y: Math.round(r.y), r: Math.round(r.right), b: Math.round(r.bottom) }; });
    const overlap = menu && !(menu.r <= row.x || menu.x >= row.x + row.width || menu.b <= row.y || menu.y >= row.y + row.height);
    out.push({ w, clip, sug, went, row: [row.x, row.y, row.width, row.height].map(Math.round), menu, overlap, first });
    await browser.close();
  }
  console.log(JSON.stringify(out, null, 1));
})();
