// The owner, 2026-10-10: "the edge arrows are still not moving and you cant
// even see the top one" (with INBOX 740 and 746). A sticky with three links
// (two out of it, one arrow into it) is dragged, resized and turned with the
// button held; at each frame end the four clone arrows must sit just outside
// the middle of each of its current, rotated sides, and every link end
// touching it must lie on its outline.
//   BASE=http://127.0.0.1:8783 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbedgegrips.js
const { boot } = require("./lib.js");
let fails = 0, passes = 0;
const check = (ok, what) => { console.log(`${ok ? "PASS" : "FAIL"}  ${what}`); ok ? passes++ : fails++; };

(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  await page.click('[data-tab="library"]');
  await page.waitForTimeout(700);
  await page.click('#library-subtabs [data-target="library-view-whiteboard"]');
  await page.waitForFunction(() => typeof window.initWhiteboard === "function", null, { timeout: 30000 });
  const board = await page.evaluate(async () => {
    await initWhiteboard();
    return apiJson("/whiteboard/boards", { method: "POST", body: JSON.stringify({ name: "Edge grips " + Date.now() }) });
  });
  await page.evaluate(async (b) => { await openWhiteboardBoard(b); }, board.id);
  await page.waitForTimeout(1200);
  const ids = await page.evaluate(async (b) => {
    const sticky = { bg: "#fff4a3", border_color: "#e8d56a", color: "#2a2a1f", font_size: 16 };
    const mk = (content, x, y) => apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ kind: "text", data: { content, ...sticky }, board_id: b, x, y, z: 1, width: 180, height: 140 }) });
    const a = await mk("A", 420, 300);
    const two = await mk("B", 820, 300);
    const three = await mk("C", 420, 640);
    const four = await mk("D", 80, 300);
    const link = (s, t) => apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ board_id: b, x: 0, y: 0, z: 0, data: JSON.stringify({ type: "link-straight", sourceKind: "object", sourceId: s, targetKind: "object", targetId: t, endCap: "arrow", width: 2 }) }) });
    const l1 = await link(a.id, two.id);
    const l2 = await link(a.id, three.id);
    const l3 = await link(four.id, a.id);
    await fetchWhiteboardState();
    renderWhiteboardNow();
    if (typeof wbFitToScreen === "function") { /* keep 1x so screen = board */ }
    return { a: a.id, links: [l1.id, l2.id, l3.id] };
  }, board.id);
  await page.waitForTimeout(800);
  await page.click(`.wb-object[data-id="${ids.a}"] .wb-text-content`, { position: { x: 20, y: 20 } }).catch(() => {});
  await page.keyboard.press("Escape").catch(() => {});
  await page.evaluate((id) => selectWbItem("object", id), ids.a);
  await page.waitForTimeout(500);

  //: Everything read in screen pixels: the four side handles are the middles
  //: of the box's current, rotated sides.
  const measure = (label) => page.evaluate(({ id, links, label }) => {
    const el = document.querySelector(`.wb-object[data-id="${id}"]`);
    const mid = (h) => {
      const r = el.querySelector(`.wb-resize-handle[data-handle="${h}"]`)?.getBoundingClientRect();
      return r && r.width ? { x: r.x + r.width / 2, y: r.y + r.height / 2 } : null;
    };
    const sides = { up: mid("n"), right: mid("e"), down: mid("s"), left: mid("w") };
    const c = sides.up && sides.down ? { x: (sides.up.x + sides.down.x) / 2, y: (sides.up.y + sides.down.y) / 2 } : null;
    const grips = {};
    for (const g of document.querySelectorAll("#wb-clone-grips .wb-clone-grip")) {
      const r = g.getBoundingClientRect();
      grips[g.dataset.dir] = { x: r.x + r.width / 2, y: r.y + r.height / 2, w: r.width };
    }
    const out = { label, sides, grips: {}, links: [] };
    for (const [dir, s] of Object.entries(sides)) {
      const g = grips[dir];
      if (!s || !c || !g) { out.grips[dir] = null; continue; }
      const nx = s.x - c.x, ny = s.y - c.y, len = Math.hypot(nx, ny) || 1;
      const ux = nx / len, uy = ny / len;
      const vx = g.x - s.x, vy = g.y - s.y;
      out.grips[dir] = { along: Math.round(vx * ux + vy * uy), lateral: Math.round(Math.abs(-vx * uy + vy * ux) * 10) / 10 };
    }
    //: Link ends against the item's outline, in board units.
    const item = wbState.objects.find((o) => o.id === id);
    const box = wbItemBBox("object", item);
    const cx = (box.minX + box.maxX) / 2, cy = (box.minY + box.maxY) / 2;
    const hw = (box.maxX - box.minX) / 2, hh = (box.maxY - box.minY) / 2;
    const rad = -((item.rotation || 0) * Math.PI) / 180;
    const off = (x, y) => {
      const dx = x - cx, dy = y - cy;
      const lx = dx * Math.cos(rad) - dy * Math.sin(rad), ly = dx * Math.sin(rad) + dy * Math.cos(rad);
      const ox = Math.abs(lx) - hw, oy = Math.abs(ly) - hh;
      if (ox > 0 || oy > 0) return Math.hypot(Math.max(ox, 0), Math.max(oy, 0));
      return Math.abs(Math.max(ox, oy));
    };
    for (const lid of links) {
      const d = document.querySelector(`.sketch-group[data-id="${lid}"] .sketch-path`)?.getAttribute("d") || "";
      const nums = (d.match(/-?\d+(?:\.\d+)?/g) || []).map(Number);
      const pts = [];
      for (let i = 0; i + 1 < nums.length; i += 2) pts.push([nums[i], nums[i + 1]]);
      out.links.push(pts.length ? Math.round(Math.min(...pts.map(([x, y]) => off(x, y))) * 10) / 10 : null);
    }
    out.rotation = Math.round(item.rotation || 0);
    return out;
  }, { id: ids.a, links: ids.links, label });

  const judge = (m) => {
    const dirs = Object.entries(m.grips);
    const shown = dirs.filter(([, g]) => g).length;
    check(shown === 4, `${m.label}: four clone arrows, one per side (${shown}: ${dirs.filter(([, g]) => g).map(([d]) => d).join(",")})`);
    for (const [dir, g] of dirs) {
      if (!g) continue;
      check(g.along >= 8 && g.along <= 70 && g.lateral <= 2.5, `${m.label}: ${dir} arrow outside its side's middle (out ${g.along}px, off-axis ${g.lateral}px)`);
    }
    m.links.forEach((dist, i) => check(dist != null && dist <= 1.5, `${m.label}: link ${i + 1} end on the outline (${dist})`));
  };

  const at = await measure("at rest");
  judge(at);
  //: The top arrow is not hidden by the rotate grip.
  const topVisible = await page.evaluate(() => {
    const g = document.querySelector('#wb-clone-grips .wb-clone-grip[data-dir="up"]');
    if (!g) return "none";
    const r = g.getBoundingClientRect();
    const top = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
    return top === g ? "on top" : (top?.className?.baseVal ?? top?.className ?? "other");
  });
  check(topVisible === "on top", `top arrow is the element under its own centre (${topVisible})`);

  //: A drag, the button held.
  const box = await page.evaluate((id) => {
    const r = document.querySelector(`.wb-object[data-id="${id}"]`).getBoundingClientRect();
    return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
  }, ids.a);
  await page.mouse.move(box.x + 40, box.y + 40);
  await page.mouse.down();
  for (let i = 1; i <= 6; i++) await page.mouse.move(box.x + 40 + i * 20, box.y + 40 + i * 10, { steps: 2 });
  await page.waitForTimeout(120);
  judge(await measure("mid-drag"));
  await page.mouse.up();
  await page.waitForTimeout(500);
  judge(await measure("after drag"));

  //: A resize from the south-east corner, held.
  const se = await page.evaluate((id) => {
    const r = document.querySelector(`.wb-object[data-id="${id}"] .wb-resize-handle[data-handle="se"]`).getBoundingClientRect();
    return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
  }, ids.a);
  await page.mouse.move(se.x, se.y);
  await page.mouse.down();
  for (let i = 1; i <= 6; i++) await page.mouse.move(se.x + i * 12, se.y + i * 8, { steps: 2 });
  await page.waitForTimeout(120);
  judge(await measure("mid-resize"));
  await page.mouse.up();
  await page.waitForTimeout(500);
  judge(await measure("after resize"));

  //: A turn, held.
  const h = await page.evaluate((id) => {
    const r = document.querySelector(`.wb-object[data-id="${id}"] .wb-rotate-handle`).getBoundingClientRect();
    const c = document.querySelector(`.wb-object[data-id="${id}"]`).getBoundingClientRect();
    return { x: r.x + r.width / 2, y: r.y + r.height / 2, cx: c.x + c.width / 2, cy: c.y + c.height / 2 };
  }, ids.a);
  await page.mouse.move(h.x, h.y);
  await page.mouse.down();
  for (let i = 1; i <= 8; i++) await page.mouse.move(h.cx + 150, h.cy - 120 + i * 12, { steps: 2 });
  await page.waitForTimeout(120);
  const turning = await measure("mid-turn");
  check(turning.rotation !== 0, `the box turned (${turning.rotation} degrees)`);
  judge(turning);
  await page.mouse.up();
  await page.waitForTimeout(600);
  judge(await measure("after turn"));
  console.log(`${passes}/${passes + fails}`);
  await browser.close();
  process.exit(fails ? 1 : 0);
})();
