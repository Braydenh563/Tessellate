// wb-1027: the context bar's ⋯ menu top is one labelled grid for every kind.
//   W=1280 H=800 BASE=http://127.0.0.1:8787 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wb1027-moremenu.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();
(async () => {
  const W = Number(process.env.W || 1280), H = Number(process.env.H || 800);
  const { browser, page, errors, board } = await openBoard({ viewport: { width: W, height: H } });
  const ids = await page.evaluate(async (bid) => {
    const rect = (x, y) => `M ${x} ${y} L ${x + 120} ${y} L ${x + 120} ${y + 70} L ${x} ${y + 70} Z`;
    const shape = async (x, y) => (await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({
      data: JSON.stringify({ d: rect(x, y), shape: "rect", color: "#335599", width: 2 }), x: 0, y: 0, z: 1, board_id: bid }) })).id;
    const a = await shape(0, 0); const b = await shape(320, 120);
    const link = (await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({
      data: JSON.stringify({ type: "link-curved", sourceId: a, sourceKind: "sketch", targetId: b, targetKind: "sketch", color: "#2a9d5c", width: 2, endCap: "triangle", label: "test Label" }),
      x: 0, y: 0, z: 1, board_id: bid }) })).id;
    const text = await wbCreateObject("text", { content: "test note" }, 100, 300, 200, 80);
    await fetchWhiteboardState(); renderWhiteboardNow(); wbZoomToFit();
    return { a, b, link, text: text.id };
  }, board.id);
  await page.waitForTimeout(800);
  const measure = async (label, kind, id) => {
    await page.evaluate(([k, i]) => { clearWbSelection(); selectWbItem(k, i); }, [kind, id]);
    await page.waitForTimeout(500);
    await page.evaluate(() => document.querySelector("#wb-context [data-wb-menu-toggle]")?.click());
    await page.waitForTimeout(400);
    const m = await page.evaluate(() => {
      const menu = document.getElementById("wb-context-menu");
      const shelf = document.getElementById("wb-context-overflow");
      const r = (el) => { const b = el.getBoundingClientRect(); return { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height) }; };
      if (!menu || menu.classList.contains("hidden")) return { open: false };
      const shelfOpen = shelf && !shelf.classList.contains("hidden");
      const unit = (el) => ({ label: el.dataset.foldLabel, ...r(el), controls: [...el.querySelectorAll("select, input, button")].filter((c) => c.getClientRects().length).map(r) });
      const rows = shelfOpen ? [...shelf.querySelectorAll(":scope > [data-fold-label], .wb-fold-row")].filter((el) => el.getClientRects().length).map(unit) : [];
      const strayRules = shelfOpen ? [...shelf.children].filter((c) => c.getClientRects().length && !c.dataset.foldLabel).length : 0;
      return { open: true, shelfOpen, menu: r(menu), shelf: shelfOpen ? r(shelf) : null, rows, strayRules, clipped: menu.scrollWidth > menu.clientWidth + 1 };
    });
    console.log(label, JSON.stringify(m));
    await page.screenshot({ path: `/tmp/claude-0/wb1027-shots/more-${label}-${W}.png` });
    await page.keyboard.press("Escape");
    await page.evaluate(() => { const m = document.getElementById("wb-context-menu"); if (m && !m.classList.contains("hidden")) document.querySelector("#wb-context [data-wb-menu-toggle]")?.click(); });
    return m;
  };
  require("fs").mkdirSync("/tmp/claude-0/wb1027-shots", { recursive: true });
  const link = await measure("connector", "sketch", ids.link);
  const shape = await measure("shape", "sketch", ids.a);
  const text = await measure("text", "object", ids.text);
  if (process.env.STRICT) {
    for (const [name, m] of [["connector", link], ["shape", shape], ["text", text]]) {
      if (!m.shelfOpen) continue;
      const lefts = new Set(m.rows.map((r) => r.x));
      check(`${name}: rows share one left edge`, lefts.size === 1, [...lefts]);
      check(`${name}: every row has a label`, m.rows.every((r) => r.label), m.rows.map((r) => r.label));
      check(`${name}: no stray rule or orphan`, m.strayRules === 0, m.strayRules);
      check(`${name}: nothing clipped`, !m.clipped);
      const xs = new Set(m.rows.flatMap((r) => r.controls.length ? [Math.min(...r.controls.map((c) => c.x))] : []));
      check(`${name}: controls start in one column`, xs.size === 1, [...xs]);
    }
  }
  check("no page errors", errors.length === 0, errors);
  summary(); await browser.close();
})();
