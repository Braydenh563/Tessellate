// MINDMAP_PLAN.md §12.1 item 5's third: **the control points on a curve drag
// to reshape it**, which the plan held back because a tree edge is derived
// from `parent_id` and has no row of its own to store a control point on.
//
// What is worth measuring here is not that a dot appeared. It is that the dot
// is *on the line* and that dragging it *moves the drawn path*, for each of
// the three line shapes item 4 added. So nothing here is a screenshot:
//
//   - the path is sampled with `getPointAtLength` before and after each drag,
//     in board units, and the middle sample has to move;
//   - the handle's own centre is compared against the closest point on the
//     path, which is what "the handle sits on the line" means as a number;
//   - the default curve is a filled ribbon, not a stroke, so it is measured
//     separately: a bend that moved the centreline and left the ribbon alone
//     would be the control doing nothing on most of a real map;
//   - and the stored pair is read back off the server, since two `data` fields
//     on the child is the whole storage design.
//
// At VIEWPORT=390x844 all 14 pass (L-mindmap-15: the map is zoomed to fit; a
// click on the dot no longer reaches the canvas, which had cleared the
// selection and stood the `+` over the dot between a double-click's clicks).
//
//   BASE=http://127.0.0.1:8793 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//   timeout 110 node scratchpad/ui-sweeps/mindmapcurve.js
const { boot, OUT } = require("./lib.js");

const VIEWPORT = (() => {
  const raw = process.env.VIEWPORT;
  if (!raw) return { width: 1440, height: 900 };
  const [w, h] = raw.split("x").map(Number);
  return { width: w || 1440, height: h || 900 };
})();

//: A point on the canvas that is neither a line nor a topic, kept inside the viewport (1380,860 is off screen at 390).
//: Above the phone's tab bar: at 390x844 the old corner was its More button.
const EMPTY = VIEWPORT.width < 700 ? { x: 12, y: VIEWPORT.height - 140 } : { x: Math.min(1380, VIEWPORT.width - 12), y: Math.min(860, VIEWPORT.height - 12) };
const results = [];
function check(label, ok, detail) {
  results.push({ label, ok: Boolean(ok) });
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail ? "  " + detail : ""}`);
}

// The measurement, run in the page: one edge, read three ways.
const READ = `(childId) => {
  const vis = document.querySelector(\`.wb-map-edge[data-child="\${childId}"]\`);
  const hit = document.querySelector(\`.wb-map-edge-hit[data-child="\${childId}"]\`);
  const grip = document.querySelector(\`.wb-map-edge-handle[data-child="\${childId}"]\`);
  const plus = document.querySelector(\`.wb-map-edge-plus[data-child="\${childId}"]\`);
  const at = (path, t) => {
    const p = path.getPointAtLength(path.getTotalLength() * t);
    return [+p.x.toFixed(2), +p.y.toFixed(2)];
  };
  let onLine = null;
  if (hit && grip) {
    const cx = +grip.getAttribute("cx");
    const cy = +grip.getAttribute("cy");
    const total = hit.getTotalLength();
    let best = Infinity;
    for (let i = 0; i <= 4000; i++) {
      const p = hit.getPointAtLength((total * i) / 4000);
      best = Math.min(best, Math.hypot(p.x - cx, p.y - cy));
    }
    onLine = +best.toFixed(3);
  }
  // Board units to client pixels, exactly, through the SVG's own matrix: the
  // canvas is panned and zoomed, so no arithmetic on rects can stand in.
  const toClient = (x, y) => {
    const svg = hit ? hit.ownerSVGElement : null;
    if (!svg) return null;
    const p = svg.createSVGPoint();
    p.x = x; p.y = y;
    const m = p.matrixTransform(hit.getScreenCTM());
    return { x: +m.x.toFixed(1), y: +m.y.toFixed(1) };
  };
  const along = (t) => {
    if (!hit) return null;
    const p = hit.getPointAtLength(hit.getTotalLength() * t);
    return toClient(p.x, p.y);
  };
  // How far the mid-line + sits from the handle, and how far it is from the
  // line itself: the two controls have to be apart, and both have to be on it.
  let plusGap = null;
  let plusOffLine = null;
  if (plus && grip && hit) {
    const px = parseFloat(plus.style.left) + 12;
    const py = parseFloat(plus.style.top) + 12;
    plusGap = +Math.hypot(px - +grip.getAttribute("cx"), py - +grip.getAttribute("cy")).toFixed(2);
    const total = hit.getTotalLength();
    let best = Infinity;
    for (let i = 0; i <= 4000; i++) {
      const q = hit.getPointAtLength((total * i) / 4000);
      best = Math.min(best, Math.hypot(q.x - px, q.y - py));
    }
    plusOffLine = +best.toFixed(3);
  }
  const cs = grip ? getComputedStyle(grip) : null;
  const box = grip ? grip.getBoundingClientRect() : null;
  return {
    d: vis ? vis.getAttribute("d") : null,
    cls: vis ? vis.getAttribute("class") : null,
    mid: hit ? at(hit, 0.5) : null,
    quarter: hit ? at(hit, 0.25) : null,
    ribbonMid: vis ? at(vis, 0.25) : null,
    cx: grip ? +grip.getAttribute("cx") : null,
    cy: grip ? +grip.getAttribute("cy") : null,
    onLine,
    opacity: cs ? +cs.opacity : null,
    pointer: cs ? cs.pointerEvents : null,
    box: box ? { w: +box.width.toFixed(1), h: +box.height.toFixed(1), x: +(box.x + box.width / 2).toFixed(1), y: +(box.y + box.height / 2).toFixed(1) } : null,
    plusGap,
    plusOffLine,
    quarterAt: along(window.innerWidth < 700 ? 0.4 : 0.2), // zoomed out, 0.2 along sits under the trunk topic
    onTop: box ? (() => {
      const top = document.elementFromPoint(box.x, box.y);
      return top ? top.tagName + "." + (top.getAttribute("class") || "").split(" ")[0] : null;
    })() : null,
  };
}`;

(async () => {
  const { page, browser } = await boot({ viewport: VIEWPORT });
  //: At a phone's width Library is behind More, and its sheet then sits over every click.
  if (VIEWPORT.width < 700) await page.evaluate(() => switchTab("library"));
  else await page.click('[data-tab="library"]');
  await page.waitForTimeout(800);
  await page.click('#library-subtabs [data-target="library-view-whiteboard"]');
  await page.waitForTimeout(1500);

  const built = await page.evaluate(async () => {
    const view = document.getElementById("library-view-whiteboard");
    for (const s of document.querySelectorAll('[id^="library-view-"]')) s.classList.toggle("hidden", s !== view);
    await initWhiteboard();
    const board = await apiJson("/whiteboard/boards", {
      method: "POST",
      body: JSON.stringify({ name: `curves ${Date.now()}`, type: "map" }),
    });
    window.currentBoardId = board.id;
    wbShowCanvasView();
    await fetchWhiteboardState(board.id);
    const mk = async (x, y, text, parent, data = {}) => {
      const made = await apiJson("/whiteboard/objects", {
        method: "POST",
        body: JSON.stringify({
          board_id: board.id, kind: "topic", x, y, width: 170, height: 52,
          data: { content: text, ...data },
        }),
      });
      if (parent) {
        Object.assign(made, await apiJson(`/whiteboard/boards/${board.id}/nodes/${made.id}/move`, {
          method: "PUT", body: JSON.stringify({ parent_id: parent }),
        }));
      }
      return made;
    };
    // One child per line shape: the waypoint has to compose with all three
    // (the plan's own note on this item), and they bend in three ways. The
    // elbow's child is well below its trunk so the turn has a real crossing
    // leg to be dragged along; a sibling at the trunk's own height would make
    // a "right angle" with no corner in it and measure nothing.
    // The three children are staggered in x as well as y on purpose. Every
    // line on a map leaves its trunk from the same anchor, and a hit stroke is
    // 16 units wide: three siblings in a column put one line's handle inside
    // another line's target, and the first run of this probe measured exactly
    // that (a drag meant for the straight line landed on the elbow's own
    // crossing leg). The map is kept inside one screen for the same practical
    // reason: a handle below the fold cannot be pointed at.
    const root = await mk(140, 380, "Trunk");
    const curved = await mk(600, 140, "Curved", root.id);
    const straight = await mk(520, 470, "Straight", root.id, { edge_style: "straight" });
    const elbow = await mk(660, 620, "Elbow", root.id, { edge_style: "elbow" });
    await fetchWhiteboardState(board.id);
    renderWhiteboardNow();
    await new Promise((r) => setTimeout(r, 700));
    return { board: board.id, root: root.id, curved: curved.id, elbow: elbow.id, straight: straight.id };
  });

  //: At a phone's width the 800-unit map is wider than the screen, so its handles sat off screen (the old 11 of 14).
  //: Fitting the map to the view puts every handle on screen; drags are in client pixels so they still reshape.
  if (VIEWPORT.width < 700) {
    await page.evaluate(() => window.wbZoomToFit && window.wbZoomToFit({ animate: false }));
    await page.waitForTimeout(700);
  }
  const read = (id) => page.evaluate(`(${READ})(${id})`);
  const select = async (id) => {
    await page.click(`.wb-object[data-id="${id}"] .wb-map-text`, { position: { x: 8, y: 8 } });
    await page.waitForTimeout(350);
  };
  const park = async () => {
    // Somewhere that is neither a line nor a topic, so a "resting" reading is
    // a resting reading.
    await page.mouse.move(EMPTY.x, EMPTY.y);
    await page.waitForTimeout(200);
  };
  // Point at the line first, then at the dot on it: that is the gesture, and
  // it is also the only order that proves the hover route works, since the
  // handle is inert until the line under it is pointed at.
  const grab = async (id) => {
    const at = await read(id);
    await page.mouse.move(at.quarterAt.x, at.quarterAt.y);
    await page.waitForTimeout(150);
    //: What pointing at the line alone does, before the pointer goes on to the dot: zoomed out (a phone) the mid-line
    //: `+` is 24px wide and covers the dot, so the pointer leaves the line on the way and only a selection reaches it.
    //: The grips are built on that first hover (L-ui-modernisation-61), so the
    //: dot is aimed at from this reading, not the one taken at rest.
    const byLine = await read(id);
    const aim = byLine.box || at.box;
    await page.mouse.move(aim.x, aim.y);
    await page.waitForTimeout(150);
    // Read again, with the pointer on it: the first reading is what the line
    // looks like at rest, and the point of this helper is what it looks like
    // once it has been pointed at.
    return { ...(await read(id)), byLine };
  };
  const dragHandle = async (id, dx, dy, { selected = false } = {}) => {
    const before = selected ? await read(id) : await grab(id);
    if (selected) await page.mouse.move(before.box.x, before.box.y);
    await page.mouse.down();
    await page.mouse.move(before.box.x + dx, before.box.y + dy, { steps: 12 });
    await page.mouse.up();
    await page.waitForTimeout(900);
    const after = await read(id);
    await park();
    return { before, after };
  };

  await park();
  const resting = await read(built.curved);
  // The hover route, which is the one that needs nothing selected.
  const hovered = await grab(built.curved);
  await park();
  // At rest again, now that pointing at it has built the handle.
  const rested = await read(built.curved);
  // And the selection route, which is what a keyboard selection reaches.
  await select(built.curved);
  const woken = await read(built.curved);

  const curve = await dragHandle(built.curved, 0, -110, { selected: true });
  await page.mouse.click(EMPTY.x, EMPTY.y);
  await page.waitForTimeout(300);
  const straight = await dragHandle(built.straight, 0, 120);
  const elbow = await dragHandle(built.elbow, 95, 0);

  // What the server kept, which is the storage half of the item: two fields
  // on the child, no row of its own.
  const stored = await page.evaluate(async (ids) => {
    const state = await apiJson(`/whiteboard/?board_id=${ids.board}`);
    const of = (id) => {
      const obj = state.objects.find((o) => o.id === id) || {};
      return { bend: obj.data?.edge_bend ?? null, slide: obj.data?.edge_slide ?? null };
    };
    return { curved: of(ids.curved), elbow: of(ids.elbow), straight: of(ids.straight) };
  }, built);

  // And back to the line it was, from the handle's own double-click.
  //: Zoomed out the `+` covers the dot unless the topic is selected (which stands it aside), so a phone selects first.
  const gripAt = VIEWPORT.width < 700 ? (await select(built.curved), await read(built.curved)) : await grab(built.curved);
  await page.mouse.dblclick(gripAt.box.x, gripAt.box.y);
  await page.waitForTimeout(900);
  const straightened = await read(built.curved);

  const moved = (a, b) => +Math.hypot(b.mid[0] - a.mid[0], b.mid[1] - a.mid[1]).toFixed(2);

  //: Not built at all until first pointed at (L-ui-modernisation-61), and
  //: invisible and inert at rest once it has been.
  check("a line's handle is neither shown nor pressable until the line is pointed at",
    resting.cx === null && rested.opacity === 0 && rested.pointer === "none" && rested.cx !== null,
    `before ${resting.cx === null ? "not built" : "built"}; after opacity ${rested.opacity}, pointer-events ${rested.pointer}, at ${rested.cx},${rested.cy}`);
  check("pointing at the line reveals it, with nothing selected",
    hovered.byLine.opacity === 1 && hovered.byLine.pointer === "auto" && hovered.box.w > 8,
    `opacity ${hovered.opacity}, ${hovered.box.w}x${hovered.box.h}px at ${hovered.box.x},${hovered.box.y}, top element ${hovered.onTop}`);
  check("selecting the topic reveals it too",
    woken.opacity === 1 && woken.pointer === "auto",
    `opacity ${woken.opacity}, pointer-events ${woken.pointer}`);
  check("the mid-line + sits beside the handle, not on it, and stays on the line",
    rested.plusGap >= 19 && rested.plusGap <= 30 && rested.plusOffLine < 1.5,
    `${rested.plusGap} board units apart, + is ${rested.plusOffLine} off the line`);

  check("dragging the handle reshapes the curve",
    curve.after.d !== curve.before.d && moved(curve.before, curve.after) > 60,
    `centreline middle ${JSON.stringify(curve.before.mid)} -> ${JSON.stringify(curve.after.mid)}, moved ${moved(curve.before, curve.after)}`);
  check("the ribbon bends with it, not only the centreline",
    curve.after.cls.includes("wb-map-edge-ribbon") &&
      Math.hypot(curve.after.ribbonMid[0] - curve.before.ribbonMid[0],
                 curve.after.ribbonMid[1] - curve.before.ribbonMid[1]) > 30,
    `ribbon quarter ${JSON.stringify(curve.before.ribbonMid)} -> ${JSON.stringify(curve.after.ribbonMid)}`);
  check("the handle is on the curve, not near it",
    curve.after.onLine !== null && curve.after.onLine < 0.5,
    `${curve.after.onLine} board units from the closest point on the path`);

  check("dragging the handle moves an elbow's turn",
    elbow.after.d !== elbow.before.d && moved(elbow.before, elbow.after) > 20,
    `${elbow.before.d} -> ${elbow.after.d}`);
  check("the handle is on the elbow",
    elbow.after.onLine !== null && elbow.after.onLine < 0.5,
    `${elbow.after.onLine} board units off the path`);

  check("dragging the handle kinks a straight line",
    straight.after.d !== straight.before.d && moved(straight.before, straight.after) > 40,
    `${straight.before.d} -> ${straight.after.d}`);
  check("the handle is on the straight line",
    straight.after.onLine !== null && straight.after.onLine < 0.5,
    `${straight.after.onLine} board units off the path`);

  check("the shape is stored on the child, as two fractions",
    Math.abs(stored.curved.bend || 0) > 0.05 &&
      Math.abs(stored.straight.bend || 0) > 0.05 &&
      Math.abs(stored.elbow.slide || 0) > 0.05,
    JSON.stringify(stored));
  check("a fraction is inside the bounds the schema holds it to",
    [stored.curved, stored.elbow, stored.straight].every(
      (row) => Math.abs(row.slide || 0) <= 0.45 && Math.abs(row.bend || 0) <= 4),
    JSON.stringify(stored));
  check("double-clicking the handle puts the line back",
    straightened.d === curve.before.d,
    `${straightened.d.slice(0, 60)}...`);

  await page.screenshot({ path: `${OUT}/mindmapcurve-${process.env.THEME || "light"}.png` });
  const bad = results.filter((r) => !r.ok);
  console.log(`\n${results.length - bad.length}/${results.length} passed  ${OUT}/mindmapcurve-${process.env.THEME || "light"}.png`);
  await browser.close();
  process.exit(bad.length ? 1 : 0);
})();
