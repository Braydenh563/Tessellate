// Connectors, third batch (WHITEBOARD_PLAN section 10): the obstacle-avoiding elbow router, square end legs, the
// connector shapes (line, double, block arrow, flex arrow, tapered, pipe, wire) and text on path.
//   BASE=http://127.0.0.1:8896 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbconnectors3.js
const { openBoard, checker } = require("./wb1005-lib.js");
const { check, summary } = checker();

(async () => {
  const { browser, page, errors, board } = await openBoard({ title: "wbconnectors3", viewport: { width: 1440, height: 900 } });
  const ids = await page.evaluate(async (bid) => {
    const rect = (x, y, w = 120, h = 70) => `M ${x} ${y} L ${x + w} ${y} L ${x + w} ${y + h} L ${x} ${y + h} Z`;
    const post = async (data) => (await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ data: JSON.stringify(data), x: 0, y: 0, z: 1, board_id: bid }) })).id;
    const shape = (x, y, w, h) => post({ d: rect(x, y, w, h), shape: "rect", color: "#335599", width: 2 });
    const a = await shape(0, 0), b = await shape(620, 0);
    //: A wall across the straight way, and 200 more boxes well off the corridor.
    const wall = await shape(300, -160, 40, 360);
    const crowd = [];
    for (let i = 0; i < 200; i++) crowd.push(await shape(-400 + (i % 20) * 90, 420 + Math.floor(i / 20) * 60, 60, 40));
    const link = await post({ type: "link-straight", route: "elbow", sourceId: a, sourceKind: "sketch", targetId: b, targetKind: "sketch", color: "#222222", width: 3, endCap: "arrow" });
    await fetchWhiteboardState();
    renderWhiteboardNow();
    wbZoomToFit();
    return { a, b, wall, link, crowd: crowd.length };
  }, board.id);
  await page.waitForTimeout(900);

  // 1. The routed elbow misses every box.
  const geo = await page.evaluate((ids) => {
    const d = document.querySelector(`.sketch-group[data-id="${ids.link}"] .sketch-path`).getAttribute("d");
    const shaft = d.split(/\s(?=M)/)[0];
    const pts = [...shaft.matchAll(/[ML] (-?[\d.]+) (-?[\d.]+)/g)].map((m) => ({ x: Number(m[1]), y: Number(m[2]) }));
    const boxes = (wbState.sketches || []).filter((s) => s.id !== ids.link).map((s) => ({ id: s.id, b: wbItemBBox("sketch", s) })).filter((o) => o.b);
    // Distance from a run to a box: 0 when it touches or crosses the inside, else the gap.
    const gap = (p, q, b) => {
      const lx = Math.min(p.x, q.x), hx = Math.max(p.x, q.x), ly = Math.min(p.y, q.y), hy = Math.max(p.y, q.y);
      const dx = Math.max(b.minX - hx, lx - b.maxX, 0), dy = Math.max(b.minY - hy, ly - b.maxY, 0);
      return Math.hypot(dx, dy);
    };
    const segs = pts.slice(1).map((q, i) => [pts[i], q]);
    //: The end boxes are touched at their own ends, so the clearance is read for the runs after the first stub.
    let min = Infinity;
    for (const o of boxes) for (const [i, [p, q]] of segs.entries()) {
      if ((o.id === ids.a && i === 0) || (o.id === ids.b && i === segs.length - 1)) continue;
      min = Math.min(min, gap(p, q, o.b));
    }
    return { n: pts.length, square: segs.every(([p, q]) => Math.abs(p.x - q.x) < 0.5 || Math.abs(p.y - q.y) < 0.5), minGap: min, last: segs.length ? segs[segs.length - 1] : null, first: segs[0] };
  }, ids);
  check("the routed elbow turns only at right angles", geo.square, geo);
  check("the routed elbow's path-to-box distance is above 0 for every box", geo.minGap > 0, geo.minGap);
  check("it goes round the wall (more than one bend)", geo.n >= 4, geo.n);

  // 2. Drag timing on a 200-item board: one repaint per frame with the end moving.
  const timing = await page.evaluate(async (ids) => {
    const parsed = JSON.parse(wbFindItem("sketch", ids.link).data);
    const ends = wbResolveLinkEndpoints(parsed);
    const times = [];
    for (let f = 0; f < 60; f++) {
      await new Promise((r) => requestAnimationFrame(r));
      const t0 = performance.now();
      const t = { ...ends.target, y: ends.target.y + (f % 7) * 3 };
      wbLinkPathD(parsed.type, ends.source, t, wbLinkCaps(parsed), parsed.width, null, wbLinkShape(parsed));
      times.push(performance.now() - t0);
    }
    times.sort((x, y) => x - y);
    return { median: times[30], p95: times[57], max: times[59], items: (wbState.sketches || []).length };
  }, ids);
  check("a drag frame stays inside 16 ms on a 200-item board (p95)", timing.p95 < 16 && timing.items > 200, timing);
  console.log("timing", JSON.stringify(timing));

  console.log("page errors:", errors.length, errors.slice(0, 3));
  check("no page errors", errors.length === 0, errors.slice(0, 3));
  await browser.close();
  process.exit(summary() ? 0 : 1);
})();
