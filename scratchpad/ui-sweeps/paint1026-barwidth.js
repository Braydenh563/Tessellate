// INBOX 1354 item 2: the context bar and its popups never stretch across the
// screen. Each kind of selection at W: the bar's width, its share of the
// viewport, whether it wrapped, and each popup it opens.
//   BASE=http://127.0.0.1:8861 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers W=1280 node scratchpad/ui-sweeps/paint1026-barwidth.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();
const W = Number(process.env.W || 1280);
const PHONE = W < 600;
const CAP = Number(process.env.CAP || 640);

(async () => {
  const { browser, page, errors, board } = await openBoard({
    viewport: { width: W, height: PHONE ? 844 : 900 }, boot: PHONE ? { hasTouch: true, isMobile: true } : {},
  });
  const made = await page.evaluate(async (bid) => {
    const sk = async (data) => (await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ data: JSON.stringify(data), x: 0, y: 0, z: 1, board_id: bid }) })).id;
    const ob = async (kind, x, data) => (await apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ kind, data, board_id: bid, x, y: 360, z: 1, width: 160, height: 80 }) })).id;
    const out = {
      rect: ["sketch", await sk({ d: "M 100 100 h 120 v 80 h -120 Z", shape: "rect", color: "#335599", width: 2, fill: "#ffcc00", label: "Box" })],
      line: ["sketch", await sk({ d: "M 300 140 L 460 140", shape: "line", color: "#335599", width: 2, startCap: "none", endCap: "none" })],
      arrow: ["sketch", await sk({ d: "M 520 140 L 680 140", shape: "arrow", color: "#335599", width: 2, startCap: "none", endCap: "arrow" })],
      pen: ["sketch", await sk({ d: "M 100 260 L 140 280 L 180 250", shape: "draw", color: "#335599", width: 3 })],
      text: ["object", await ob("text", 100, { content: "Text box" })],
      frame: ["object", await ob("frame", 300, { content: "Frame" })],
    };
    await fetchWhiteboardState();
    renderWhiteboardNow();
    wbZoomToFit();
    return out;
  }, board.id);
  await page.waitForTimeout(800);
  const measure = () => page.evaluate(() => {
    const bar = document.getElementById("wb-context");
    if (!bar || bar.classList.contains("hidden") || !bar.getClientRects().length) return null;
    const r = bar.getBoundingClientRect();
    return { w: Math.round(r.width), h: Math.round(r.height), left: Math.round(r.left), right: Math.round(r.right), vw: innerWidth };
  });
  const results = {};
  for (const [name, [kind, id]] of Object.entries(made)) {
    await page.evaluate(([k, i]) => { clearWbSelection(); selectWbItem(k, i); wbUpdateContextBar(); }, [kind, id]);
    await page.waitForTimeout(350);
    results[name] = await measure();
  }
  await page.evaluate((m) => {
    clearWbSelection();
    for (const [, [k, i]] of Object.entries(m)) wbMultiSelection.add(wbMultiKey(k, i));
    wbApplySelectionHighlight();
    wbUpdateContextBar();
  }, made);
  await page.waitForTimeout(350);
  results.multi = await measure();
  // The cost of opening the bar (fill, fold, place), per kind.
  const cost = await page.evaluate((m) => {
    const out = {};
    for (const [name, [k, i]] of Object.entries(m)) {
      clearWbSelection(); selectWbItem(k, i);
      const t0 = performance.now();
      for (let n = 0; n < 20; n++) wbUpdateContextBar();
      out[name] = +((performance.now() - t0) / 20).toFixed(2);
    }
    return out;
  }, made);
  console.log("bar open ms", JSON.stringify(cost));
  const cap = Math.min(CAP, W - 16);
  for (const [name, m] of Object.entries(results)) {
    console.log(name.padEnd(7), JSON.stringify(m));
    if (!m) continue;
    check(`${name}: bar at most ${cap}px`, m.w <= cap, m);
    check(`${name}: one row`, m.h <= 60, m.h);
    check(`${name}: inside the viewport`, m.left >= 0 && m.right <= m.vw, m);
  }
  // The More menu that holds what folded, for each kind that folded.
  for (const name of ["line", "arrow", "text", "rect"]) {
    await page.evaluate(([k, i]) => { clearWbSelection(); selectWbItem(k, i); wbUpdateContextBar(); }, made[name]);
    await page.waitForTimeout(300);
    const m = await page.evaluate(() => {
      const t = document.querySelector("#wb-context [data-wb-menu-toggle]");
      if (!t || !t.getClientRects().length) return null;
      t.click();
      const menu = document.getElementById("wb-context-menu");
      const r = menu.getBoundingClientRect();
      const shelf = document.getElementById("wb-context-overflow");
      const folded = shelf && !shelf.classList.contains("hidden") ? shelf.children.length : 0;
      const out = { w: Math.round(r.width), h: Math.round(r.height), left: Math.round(r.left), right: Math.round(r.right), top: Math.round(r.top), bottom: Math.round(r.bottom), vw: innerWidth, vh: innerHeight, folded, scroll: menu.scrollWidth > menu.clientWidth + 1 };
      t.click();
      return out;
    });
    console.log(`more(${name})`, JSON.stringify(m));
    if (m) check(`${name}: More is under 360 wide, in view, no sideways scroll`, m.w <= 360 && m.left >= 0 && m.right <= m.vw && !m.scroll, m);
  }
  // Every popup the bar opens for the rectangle, by its toggles.
  await page.evaluate(([k, i]) => { clearWbSelection(); selectWbItem(k, i); wbUpdateContextBar(); }, made.rect);
  await page.waitForTimeout(300);
  const toggles = await page.$$eval("#wb-context [aria-haspopup]:not(.hidden)", (els) => els.filter((e) => e.getClientRects().length).map((e) => e.getAttribute("aria-controls") || e.id).filter(Boolean));
  for (const pid of toggles) {
    await page.evaluate((p) => document.querySelector(`#wb-context [aria-controls="${p}"]`)?.click() || document.getElementById(p)?.click(), pid);
    await page.waitForTimeout(250);
    const m = await page.evaluate(() => {
      const open = [...document.querySelectorAll("#library-view-whiteboard .wb-board-menu:not(.hidden), #library-view-whiteboard [role=menu]:not(.hidden), #library-view-whiteboard .wb-popover:not(.hidden)")].filter((e) => e.getClientRects().length && e.getBoundingClientRect().width > 0);
      return open.map((e) => { const r = e.getBoundingClientRect(); return { id: e.id || e.className.slice(0, 30), w: Math.round(r.width), left: Math.round(r.left), right: Math.round(r.right), bottom: Math.round(r.bottom) }; });
    });
    for (const o of m) check(`popup ${o.id}: under 360 wide, in view`, o.w <= 360 && o.left >= 0 && o.right <= W, o);
    await page.keyboard.press("Escape");
    await page.waitForTimeout(150);
    await page.evaluate(([k, i]) => { if (!wbSelectedItem) { selectWbItem(k, i); wbUpdateContextBar(); } }, made.rect);
  }
  check("no page errors", errors.length === 0, errors.slice(0, 3));
  summary();
  await browser.close();
})();
