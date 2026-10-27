// **The small conventions every canvas user takes for granted** (the owner,
// 2026-09-23: "I cant do things on the whiteboard and mindmap like double
// clcike the rotate point above the top centre of an object and reset it to
// its default rotate ... small features that we as user's use all the time
// and take for granted but very much notice when they arent there").
//
// One check per convention a Figma, Miro, tldraw or Excalidraw user expects,
// each asserted by its effect as a number (a rotation, a size, a count of
// items, the depth of the undo stack, the zoom transform), never by a
// screenshot. WHITEBOARD_PLAN.md "Placed from INBOX, 2026-09-23" is the
// record; docs/roadmap/archive/agent-remaining/mapux2.md holds the checklist.
//
//   BASE=http://127.0.0.1:8795 SCRATCH=/tmp/mm-agentM \
//   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/canvasconventions.js
//
// ONLY=board or ONLY=map runs half of it.
const { boot } = require("./lib.js");

const results = [];
function check(label, ok, detail) {
  results.push({ label, ok: Boolean(ok) });
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail ? "  " + detail : ""}`);
}
const ONLY = process.env.ONLY || "";
const near = (a, b, tol = 1.5) => a != null && b != null && Math.abs(a - b) <= tol;

(async () => {
  const { browser, page } = await boot({});
  const wait = (ms) => page.waitForTimeout(ms);

  await page.click('[data-tab="library"]');
  await wait(700);
  await page.click('#library-subtabs [data-target="library-view-whiteboard"]');
  await wait(1200);
  await page.evaluate(async () => {
    const v = document.getElementById("library-view-whiteboard");
    for (const s of document.querySelectorAll('[id^="library-view-"]')) s.classList.toggle("hidden", s !== v);
    await initWhiteboard();
  });
  await wait(400);

  // Board helpers, all read from the page's own state.
  const obj = (id) => page.evaluate((id) => {
    const o = (wbState.objects || []).find((x) => x.id === id);
    return o ? { x: o.x, y: o.y, w: o.width, h: o.height, r: o.rotation || 0, g: o.group_id ?? null } : null;
  }, id);
  const node = (id) => page.evaluate((id) => {
    const o = (wbState.nodes || []).find((x) => x.id === id);
    return o ? { x: o.x, y: o.y, r: o.rotation || 0 } : null;
  }, id);
  const undoDepth = () => page.evaluate(() => wbUndoStack.length);
  const counts = () => page.evaluate(() => ({
    objects: (wbState.objects || []).length,
    sketches: (wbState.sketches || []).length,
    nodes: (wbState.nodes || []).length,
  }));
  const select = (kind, id) => page.evaluate(([k, i]) => { selectWbItem(k, i); }, [kind, id]);
  const selectMany = (keys) => page.evaluate((keys) => {
    clearWbSelection();
    for (const k of keys) wbMultiSelection.add(k);
    wbApplySelectionHighlight();
    wbUpdateSelectionBar();
  }, keys);
  const centre = (selector) => page.evaluate((s) => {
    const el = document.querySelector(s);
    if (!el) return null;
    const b = el.getBoundingClientRect();
    return b.width || b.height ? { x: b.left + b.width / 2, y: b.top + b.height / 2 } : null;
  }, selector);
  const serverObj = (id) => page.evaluate(async (id) => {
    const state = await apiJson(`/whiteboard/?board_id=${window.currentBoardId}`).catch(() => null);
    const o = (state?.objects || []).find((x) => x.id === id);
    return o ? { x: o.x, y: o.y, w: o.width, h: o.height, r: o.rotation || 0 } : null;
  }, id);
  const drag = async (from, to, { steps = 12, before, after } = {}) => {
    await page.mouse.move(from.x, from.y);
    await page.mouse.down();
    await page.mouse.move(from.x + (to.x - from.x) / 4, from.y + (to.y - from.y) / 4, { steps: 3 });
    if (before) await before();
    await page.mouse.move(to.x, to.y, { steps });
    if (after) await after();
    await page.mouse.up();
    await wait(500);
  };
  //: A point on bare canvas, found rather than assumed: the top bar, the
  //: rail, the dock and the navigator all float over the canvas, and a
  //: gesture aimed at a fixed offset lands on one of them at some widths.
  //: `fromX`/`fromY` are fractions of the canvas to start the scan at.
  const emptyPoint = (fromX = 0.5, fromY = 0.5) => page.evaluate(([fx, fy]) => {
    const r = document.getElementById("whiteboard-container").getBoundingClientRect();
    for (let ring = 0; ring < 12; ring++) {
      for (let a = 0; a < 16; a++) {
        const x = r.left + r.width * fx + Math.cos((a / 16) * Math.PI * 2) * ring * 40;
        const y = r.top + r.height * fy + Math.sin((a / 16) * Math.PI * 2) * ring * 40;
        const ok = (px, py) => {
          const el = document.elementFromPoint(px, py);
          return el && el.closest("#whiteboard-container") && !el.closest(
            ".node-card, .sketch-group, .wb-object, .wb-sketch-handle-group, .wb-resize-handle,"
            + " .wb-map-edge-group, .wb-map-edge-hit, button, input, select, .dock, [role=toolbar], #wb-topbar"
          );
        };
        if (ok(x, y) && ok(x - 110, y - 70) && ok(x + 110, y + 70) && ok(x - 110, y + 70) && ok(x + 110, y - 70)) return { x, y };
      }
    }
    // Nowhere with room around it: any bare point will do for a click.
    for (let i = 1; i < 20; i++) for (let j = 1; j < 12; j++) {
      const x = r.left + (r.width * i) / 20, y = r.top + (r.height * j) / 12;
      const el = document.elementFromPoint(x, y);
      if (el && el.closest("#whiteboard-container") && !el.closest(".node-card, .sketch-group, .wb-object, .wb-sketch-handle-group, .wb-map-edge-group, button, input, .dock, #wb-topbar")) return { x, y };
    }
    return null;
  }, [fromX, fromY]);
  const clickEmpty = async () => {
    const c = await emptyPoint(0.85, 0.75);
    if (!c) console.log("no empty point", await page.evaluate(() => {
      const r = document.getElementById("whiteboard-container").getBoundingClientRect();
      const el = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      return JSON.stringify(r) + " " + (el ? el.tagName + "." + el.className + "#" + el.id : "none");
    }));
    await page.mouse.click(c.x, c.y);
    await wait(200);
  };

  if (ONLY !== "map") {
    const ids = await page.evaluate(async () => {
      const board = await apiJson("/whiteboard/boards", {
        method: "POST", body: JSON.stringify({ name: `conventions ${Date.now()}`, type: "board" }),
      });
      await openWhiteboardBoard(board.id);
      await new Promise((r) => setTimeout(r, 900));
      const post = (body) => apiJson("/whiteboard/objects", {
        method: "POST", body: JSON.stringify({ board_id: board.id, kind: "text", ...body }),
      });
      const t = await post({ x: 200, y: 160, width: 200, height: 100, data: { content: "Tee" } });
      const u = await post({ x: 520, y: 160, width: 160, height: 80, data: { content: "You" } });
      const e = await apiJson("/entries", { method: "POST", body: JSON.stringify({ content: "A card", category: "General" }) });
      const n = await apiJson("/whiteboard/nodes", {
        method: "POST", body: JSON.stringify({ entry_id: e.id, board_id: board.id, x: 800, y: 380, z: 1, width: 220, height: 120 }),
      });
      const s = await apiJson("/whiteboard/sketches", {
        method: "POST",
        body: JSON.stringify({ board_id: board.id, data: JSON.stringify({ type: "rect", d: "M200 420 L360 420 L360 520 L200 520 Z", color: "#3b82f6", width: 3 }) }),
      });
      await fetchWhiteboardState();
      renderWhiteboardNow();
      wbSelectToolRef?.("select");
      localStorage.setItem("wb-snap", "off");
      // A fixed camera, so every client coordinate below is a known board one.
      const c = document.getElementById("whiteboard-container");
      d3.select(c).call(wbZoom.transform, d3.zoomIdentity);
      await new Promise((r) => setTimeout(r, 400));
      return { board: board.id, t: t.id, u: u.id, n: n.id, s: s.id, snap: wbSnapOn() };
    });
    console.log("board", JSON.stringify(ids));

    // --- 1. double-click the rotate handle resets the rotation ---
    await page.evaluate(async (id) => {
      const o = wbState.objects.find((x) => x.id === id);
      o.rotation = 30;
      await wbSaveObject(o);
      renderWhiteboardNow();
    }, ids.t);
    await select("object", ids.t);
    await wait(300);
    let depth = await undoDepth();
    let grip = await centre(`.wb-object[data-id="${ids.t}"] .wb-rotate-handle`);
    if (grip) await page.mouse.dblclick(grip.x, grip.y);
    await wait(700);
    let t = await obj(ids.t);
    let dDepth = (await undoDepth()) - depth;
    check("double-click the rotate handle: a text box goes back to 0 degrees", t.r === 0, `rotation ${t.r}, grip ${grip ? "found" : "missing"}`);
    check("and it is one undo step", dDepth === 1, `undo stack +${dDepth}`);
    const srvT = await serverObj(ids.t);
    check("and it is saved", srvT && srvT.r === 0, `server rotation ${srvT?.r}`);

    await page.evaluate(async (id) => {
      const o = wbState.nodes.find((x) => x.id === id);
      o.rotation = -40;
      await wbSaveNode(o);
      renderWhiteboardNow();
    }, ids.n);
    await select("node", ids.n);
    await wait(300);
    grip = await centre(`.node-card[data-id="${ids.n}"] .wb-rotate-handle`);
    if (grip) await page.mouse.dblclick(grip.x, grip.y);
    await wait(700);
    const n1 = await node(ids.n);
    check("double-click the rotate handle: a note card goes back to 0 degrees", n1.r === 0, `rotation ${n1.r}`);

    // A shape bakes its turn into its path; the grip still turns it back.
    const shapeBoxOf = () => page.evaluate((id) => {
      const s = wbState.sketches.find((x) => x.id === id);
      const b = wbPathBBox(wbSketchParsedData(s).d);
      return { w: Math.round(b.maxX - b.minX), h: Math.round(b.maxY - b.minY) };
    }, ids.s);
    const sb0 = await shapeBoxOf();
    await select("sketch", ids.s);
    await wait(300);
    grip = await centre(".wb-sketch-rotate-handle");
    const sc = await page.evaluate((id) => {
      const b = document.querySelector(`.sketch-group[data-id="${id}"] .sketch-hitbox`).getBoundingClientRect();
      return { x: b.left + b.width / 2, y: b.top + b.height / 2 };
    }, ids.s);
    if (grip) await drag(grip, { x: sc.x + 120, y: sc.y });
    await wait(400);
    const sb1 = await shapeBoxOf();
    await select("sketch", ids.s);
    await wait(300);
    grip = await centre(".wb-sketch-rotate-handle");
    if (grip) await page.mouse.dblclick(grip.x, grip.y);
    await wait(800);
    const sb2 = await shapeBoxOf();
    check("double-click the rotate handle: a shape turns back upright",
      sb1.w !== sb0.w && near(sb2.w, sb0.w, 2) && near(sb2.h, sb0.h, 2),
      `${sb0.w}x${sb0.h}, turned ${sb1.w}x${sb1.h}, back ${sb2.w}x${sb2.h}`);
    await clickEmpty();

    // --- 2. Shift while rotating snaps to 15 degrees ---
    await select("object", ids.t);
    await wait(200);
    grip = await centre(`.wb-object[data-id="${ids.t}"] .wb-rotate-handle`);
    const tc = await centre(`.wb-object[data-id="${ids.t}"]`);
    await page.keyboard.down("Shift");
    await drag(grip, { x: tc.x + 90, y: tc.y - 70 });
    await page.keyboard.up("Shift");
    t = await obj(ids.t);
    check("Shift while rotating snaps to 15 degrees", t.r !== 0 && Math.abs(t.r % 15) < 0.01, `rotation ${t.r}`);
    // back to upright for the rest
    await page.evaluate(async (id) => { const o = wbState.objects.find((x) => x.id === id); o.rotation = 0; await wbSaveObject(o); renderWhiteboardNow(); }, ids.t);
    await wait(200);

    // --- 3. Shift while resizing keeps the aspect ratio ---
    await select("object", ids.t);
    await wait(200);
    let se = await centre(`.wb-object[data-id="${ids.t}"] .wb-resize-handle[data-handle="se"]`);
    await page.keyboard.down("Shift");
    await drag(se, { x: se.x + 100, y: se.y + 8 });
    await page.keyboard.up("Shift");
    t = await obj(ids.t);
    check("Shift while resizing a corner keeps the aspect ratio (2:1 stays 2:1)", near(t.w / t.h, 2, 0.03) && t.w > 250,
      `${Math.round(t.w)} x ${Math.round(t.h)}`);

    // --- 4. double-click a resize handle fits the text ---
    se = await centre(`.wb-object[data-id="${ids.t}"] .wb-resize-handle[data-handle="s"]`);
    const hBefore = t.h;
    if (se) await page.mouse.dblclick(se.x, se.y);
    await wait(700);
    t = await obj(ids.t);
    check("double-click a resize handle fits the box to its text", t.h < hBefore, `${Math.round(hBefore)} to ${Math.round(t.h)}`);

    // --- 5. Escape cancels a resize in flight ---
    let t0 = await obj(ids.t);
    depth = await undoDepth();
    se = await centre(`.wb-object[data-id="${ids.t}"] .wb-resize-handle[data-handle="se"]`);
    await drag(se, { x: se.x + 120, y: se.y + 60 }, { after: async () => { await page.keyboard.press("Escape"); await wait(100); } });
    t = await obj(ids.t);
    check("Escape during a resize puts the size back", near(t.w, t0.w) && near(t.h, t0.h), `${Math.round(t0.w)}x${Math.round(t0.h)} to ${Math.round(t.w)}x${Math.round(t.h)}`);
    check("and leaves no undo step", (await undoDepth()) === depth, `undo +${(await undoDepth()) - depth}`);

    // --- 6. Escape cancels a rotate in flight ---
    await select("object", ids.t);
    await wait(200);
    grip = await centre(`.wb-object[data-id="${ids.t}"] .wb-rotate-handle`);
    const tc2 = await centre(`.wb-object[data-id="${ids.t}"]`);
    await drag(grip, { x: tc2.x + 120, y: tc2.y }, { after: async () => { await page.keyboard.press("Escape"); await wait(100); } });
    t = await obj(ids.t);
    const tStyle = await page.evaluate((id) => document.querySelector(`.wb-object[data-id="${id}"]`)?.style.transform || "", ids.t);
    check("Escape during a rotate puts the angle back", t.r === 0 && !/rotate\((?!0deg)/.test(tStyle), `rotation ${t.r}, ${tStyle}`);

    // --- 7. Escape cancels a move in flight ---
    let u0 = await obj(ids.u);
    depth = await undoDepth();
    let uc = await centre(`.wb-object[data-id="${ids.u}"]`);
    await drag(uc, { x: uc.x + 140, y: uc.y + 90 }, { after: async () => { await page.keyboard.press("Escape"); await wait(100); } });
    let u = await obj(ids.u);
    let srvU = await serverObj(ids.u);
    check("Escape during a move puts the item back", near(u.x, u0.x) && near(u.y, u0.y) && near(srvU.x, u0.x),
      `(${u0.x},${u0.y}) to (${u.x},${u.y}), saved (${srvU.x},${srvU.y})`);
    check("and leaves no undo step", (await undoDepth()) === depth, `undo +${(await undoDepth()) - depth}`);

    // A shape too.
    const shapeBox = async () => page.evaluate((id) => {
      const s = wbState.sketches.find((x) => x.id === id);
      const b = wbPathBBox(wbSketchParsedData(s).d);
      return { x: b.minX, y: b.minY };
    }, ids.s);
    const s0 = await shapeBox();
    const shapeAt = await page.evaluate((id) => {
      const el = document.querySelector(`.sketch-group[data-id="${id}"] .sketch-hitbox`);
      const b = el.getBoundingClientRect();
      return { x: b.left + b.width / 2, y: b.top + b.height / 2 };
    }, ids.s);
    await drag(shapeAt, { x: shapeAt.x + 80, y: shapeAt.y + 40 }, { after: async () => { await page.keyboard.press("Escape"); await wait(100); } });
    const s1 = await shapeBox();
    check("Escape during a shape's move puts it back", near(s1.x, s0.x) && near(s1.y, s0.y), `(${s0.x},${s0.y}) to (${s1.x},${s1.y})`);

    // --- 8. Shift while dragging keeps to one axis ---
    await clickEmpty();
    u0 = await obj(ids.u);
    uc = await centre(`.wb-object[data-id="${ids.u}"]`);
    await page.keyboard.down("Shift");
    await drag(uc, { x: uc.x + 130, y: uc.y + 25 });
    await page.keyboard.up("Shift");
    u = await obj(ids.u);
    check("Shift while dragging keeps the move to one axis", near(u.y, u0.y) && Math.abs(u.x - u0.x - 130) < 4,
      `moved ${Math.round(u.x - u0.x)}, ${Math.round(u.y - u0.y)}`);

    // --- 9. Alt-drag duplicates ---
    await clickEmpty();
    let c0 = await counts();
    depth = await undoDepth();
    u0 = await obj(ids.u);
    uc = await centre(`.wb-object[data-id="${ids.u}"]`);
    await page.keyboard.down("Alt");
    await drag(uc, { x: uc.x, y: uc.y + 150 });
    await page.keyboard.up("Alt");
    await wait(500);
    let c1 = await counts();
    const atStart = await page.evaluate(([x, y]) => (wbState.objects || []).filter((o) => Math.abs(o.x - x) < 1 && Math.abs(o.y - y) < 1).length, [u0.x, u0.y]);
    check("Alt-drag leaves a copy behind and moves the other", c1.objects === c0.objects + 1 && atStart === 1,
      `${c0.objects} to ${c1.objects} objects, ${atStart} at the start point`);
    check("and it is one undo step", (await undoDepth()) - depth === 1, `undo +${(await undoDepth()) - depth}`);
    await page.evaluate(() => wbUndo());
    await wait(800);
    c1 = await counts();
    u = await obj(ids.u);
    check("which one undo takes back whole", c1.objects === c0.objects && near(u.y, u0.y), `${c1.objects} objects, y ${u.y} (was ${u0.y})`);

    // --- 10. arrow keys nudge, one undo step per burst ---
    await select("object", ids.u);
    await wait(200);
    u0 = await obj(ids.u);
    depth = await undoDepth();
    for (let i = 0; i < 5; i++) await page.keyboard.press("ArrowRight");
    await page.keyboard.press("Shift+ArrowDown");
    await wait(900);
    u = await obj(ids.u);
    check("arrows nudge by 1px, Shift+arrow by 10px", near(u.x - u0.x, 5, 0.01) && near(u.y - u0.y, 10, 0.01), `moved ${u.x - u0.x}, ${u.y - u0.y}`);
    check("a burst of nudges is one undo step", (await undoDepth()) - depth === 1, `undo +${(await undoDepth()) - depth}`);
    await page.evaluate(() => wbUndo());
    await wait(800);
    u = await obj(ids.u);
    check("and one Ctrl+Z puts the whole burst back", near(u.x, u0.x) && near(u.y, u0.y), `(${u.x},${u.y}) vs (${u0.x},${u0.y})`);

    // --- 11. Ctrl+D duplicates, one item and several ---
    await select("object", ids.u);
    c0 = await counts();
    await page.keyboard.press("Control+d");
    await wait(900);
    c1 = await counts();
    check("Ctrl+D duplicates the selected item", c1.objects === c0.objects + 1, `${c0.objects} to ${c1.objects}`);
    await selectMany([`object:${ids.t}`, `sketch:${ids.s}`]);
    c0 = await counts();
    depth = await undoDepth();
    await page.keyboard.press("Control+d");
    await wait(1200);
    c1 = await counts();
    check("Ctrl+D duplicates a selection of several", c1.objects === c0.objects + 1 && c1.sketches === c0.sketches + 1,
      `objects ${c0.objects} to ${c1.objects}, shapes ${c0.sketches} to ${c1.sketches}`);
    check("as one undo step", (await undoDepth()) - depth === 1, `undo +${(await undoDepth()) - depth}`);
    const dupSel = await page.evaluate(() => wbMultiSelection.size);
    check("and the copies are what is selected afterwards", dupSel === 2, `${dupSel} selected`);
    await page.evaluate(() => wbUndo());
    await wait(900);
    c1 = await counts();
    check("one Ctrl+Z removes both copies", c1.objects === c0.objects && c1.sketches === c0.sketches, `${c1.objects} objects, ${c1.sketches} shapes`);

    // --- 12. copy and paste keep relative positions and land at the pointer ---
    await selectMany([`object:${ids.t}`, `object:${ids.u}`]);
    const rel0 = await page.evaluate(([a, b]) => {
      const A = wbState.objects.find((o) => o.id === a), B = wbState.objects.find((o) => o.id === b);
      return { dx: B.x - A.x, dy: B.y - A.y, x: Math.min(A.x, B.x), y: Math.min(A.y, B.y) };
    }, [ids.t, ids.u]);
    await page.keyboard.press("Control+c");
    await wait(200);
    const pastePoint = await emptyPoint(0.6, 0.7);
    await page.mouse.move(pastePoint.x, pastePoint.y);
    c0 = await counts();
    await page.keyboard.press("Control+v");
    await wait(1200);
    c1 = await counts();
    const pasted = await page.evaluate(() => [...wbMultiSelection].map((k) => {
      const id = Number(k.split(":")[1]);
      const o = wbState.objects.find((x) => x.id === id);
      return o ? { x: o.x, y: o.y, w: o.width, h: o.height } : null;
    }).filter(Boolean));
    check("paste of two items makes two", c1.objects === c0.objects + 2 && pasted.length === 2, `${c0.objects} to ${c1.objects}, ${pasted.length} selected`);
    if (pasted.length === 2) {
      const [a, b] = pasted.sort((p, q) => p.x - q.x);
      const pointer = await page.evaluate(([cx, cy]) => {
        const t = d3.zoomTransform(document.getElementById("whiteboard-container"));
        const r = wbCanvasOriginRect();
        return { x: (cx - r.left - t.x) / t.k, y: (cy - r.top - t.y) / t.k };
      }, [pastePoint.x, pastePoint.y]);
      check("and keeps their places relative to each other", near(b.x - a.x, rel0.dx) && near(b.y - a.y, rel0.dy), `${b.x - a.x},${b.y - a.y} vs ${rel0.dx},${rel0.dy}`);
      //: Not the pointer: a keyboard paste on the board the copy came from steps
      //: one grid square (24) down and right of the originals, then two, and so
      //: on (the owner, 2026-10-26; the pointer is "Paste here" in the menu).
      const topLeft = { x: Math.min(a.x, b.x), y: Math.min(a.y, b.y) };
      check("lands one grid square down and right of the originals", near(topLeft.x - rel0.x, 24) && near(topLeft.y - rel0.y, 24),
        `offset (${Math.round(topLeft.x - rel0.x)},${Math.round(topLeft.y - rel0.y)}), pointer (${Math.round(pointer.x)},${Math.round(pointer.y)})`);
    }

    // --- 12b. a selection low on the screen is kept clear of the bottom docks (wb5) ---
    await page.evaluate(() => clearWbSelection());
    const low = await page.evaluate((id) => {
      const o = wbState.objects.find((x) => x.id === id);
      const c = document.getElementById("whiteboard-container");
      const t = d3.zoomTransform(c), r = c.getBoundingClientRect();
      const dockTop = document.getElementById("wb-tools-panel").getBoundingClientRect().top;
      const dy = dockTop + 30 - (r.top + t.y + (o.y + o.height) * t.k);
      d3.select(c).call(wbZoom.transform, d3.zoomIdentity.translate(t.x, t.y + dy).scale(t.k));
      return { x: r.left + t.x + (o.x + o.width / 2) * t.k, y: r.top + t.y + dy + o.y * t.k + 12 };
    }, ids.t);
    await wait(500);
    await page.mouse.click(low.x, low.y);
    await wait(1000);
    const grips = await page.evaluate(() => {
      const all = [...document.querySelectorAll(".wb-selected .wb-resize-handle, .wb-selected [data-handle]")].filter((g) => g.getBoundingClientRect().width);
      const docked = all.filter((g) => { const b = g.getBoundingClientRect(); return document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2)?.closest("#wb-tools-panel, [data-panel-id='zoom']"); });
      return { all: all.length, docked: docked.length };
    });
    check("a text box low on the screen has no grip under a dock (the view slid clear of them)", grips.all >= 8 && grips.docked === 0, `${grips.docked} of ${grips.all} under a dock`);

    // --- 13. Ctrl+A selects everything, Delete removes the selection ---
    await clickEmpty();
    c0 = await counts();
    await page.keyboard.press("Control+a");
    await wait(300);
    const selAll = await page.evaluate(() => wbMultiSelection.size);
    const total = c0.objects + c0.sketches + c0.nodes;
    check("Ctrl+A selects everything on the board", selAll === total, `${selAll} of ${total}`);
    await clickEmpty();
    await select("object", ids.u);
    await wait(200);
    await page.keyboard.press("Delete");
    await wait(800);
    c1 = await counts();
    check("Delete removes the selection", c1.objects === c0.objects - 1, `${c0.objects} to ${c1.objects}`);
    await page.evaluate(() => wbUndo());
    await wait(900);

    // --- 14. Ctrl+G groups, Ctrl+Shift+G ungroups ---
    await selectMany([`object:${ids.t}`, `sketch:${ids.s}`]);
    await page.keyboard.press("Control+g");
    await wait(900);
    t = await obj(ids.t);
    check("Ctrl+G groups the selection", t.g != null, `group ${t.g}`);
    await page.keyboard.press("Control+Shift+g");
    await wait(900);
    t = await obj(ids.t);
    check("Ctrl+Shift+G ungroups it", t.g == null, `group ${t.g}`);

    // --- 14b. a group's resize: Escape puts it back, Ctrl+Z takes it back ---
    await selectMany([`object:${ids.t}`, `node:${ids.n}`]);
    await wait(400);
    //: The text box and the note card: the second text box was deleted and
    //: brought back above, under a new id.
    const groupBox = () => page.evaluate(([a, b]) => [["objects", a], ["nodes", b]].map(([list, id]) => {
      const o = wbState[list].find((x) => x.id === id);
      return `${Math.round(o.x)},${Math.round(o.y)},${Math.round(o.width)}x${Math.round(o.height)}`;
    }).join(" "), [ids.t, ids.n]);
    const g0 = await groupBox();
    const groupSe = await page.evaluate(() => {
      const all = [...document.querySelectorAll('.wb-sketch-resize-handle[data-handle="se"]')];
      const el = all[all.length - 1];
      if (!el) return null;
      const b = el.getBoundingClientRect();
      return { x: b.left + b.width / 2, y: b.top + b.height / 2 };
    });
    let gDepth = await undoDepth();
    if (groupSe) await drag(groupSe, { x: groupSe.x + 90, y: groupSe.y + 40 }, { after: async () => { await page.keyboard.press("Escape"); await wait(100); } });
    const g1 = await groupBox();
    check("Escape during a group's resize puts every member back", groupSe && g1 === g0 && (await undoDepth()) === gDepth, `${g0} to ${g1}`);
    await selectMany([`object:${ids.t}`, `node:${ids.n}`]);
    await wait(400);
    if (groupSe) await drag(groupSe, { x: groupSe.x + 90, y: groupSe.y + 40 });
    await wait(600);
    const g2 = await groupBox();
    await page.evaluate(() => wbUndo());
    await wait(900);
    const g3 = await groupBox();
    check("and one Ctrl+Z takes a group's resize back", g2 !== g0 && g3 === g0, `${g0} to ${g2}, undone ${g3}`);
    await clickEmpty();

    // --- 15. the camera: Space-drag, Ctrl+0, Shift+1, Ctrl+wheel at the pointer ---
    await clickEmpty();
    const cam = () => page.evaluate(() => {
      const t = d3.zoomTransform(document.getElementById("whiteboard-container"));
      return { x: t.x, y: t.y, k: t.k };
    });
    let k0 = await cam();
    const open = await emptyPoint(0.7, 0.4);
    await page.keyboard.down("Space");
    await drag(open, { x: open.x - 100, y: open.y + 60 });
    await page.keyboard.up("Space");
    let k1 = await cam();
    check("Space-drag pans the board", near(k1.x - k0.x, -100, 3) && near(k1.y - k0.y, 60, 3), `moved ${Math.round(k1.x - k0.x)}, ${Math.round(k1.y - k0.y)}`);
    const pivot = await emptyPoint(0.4, 0.6);
    const boardAt = async (p) => page.evaluate(([cx, cy]) => {
      const t = d3.zoomTransform(document.getElementById("whiteboard-container"));
      const r = wbCanvasOriginRect();
      return { x: (cx - r.left - t.x) / t.k, y: (cy - r.top - t.y) / t.k };
    }, [p.x, p.y]);
    const under0 = await boardAt(pivot);
    await page.mouse.move(pivot.x, pivot.y);
    await page.keyboard.down("Control");
    await page.mouse.wheel(0, -300);
    await page.keyboard.up("Control");
    await wait(500);
    k1 = await cam();
    const under1 = await boardAt(pivot);
    check("Ctrl+wheel zooms about the pointer", k1.k > k0.k * 1.05 && near(under0.x, under1.x, 2) && near(under0.y, under1.y, 2),
      `k ${k0.k.toFixed(2)} to ${k1.k.toFixed(2)}, board point drift ${Math.round(under1.x - under0.x)},${Math.round(under1.y - under0.y)}`);
    await page.evaluate(() => d3.select(document.getElementById("whiteboard-container")).call(wbZoom.transform, d3.zoomIdentity.translate(-200, -100).scale(2)));
    await wait(300);
    await page.keyboard.press("Control+0");
    await wait(600);
    k1 = await cam();
    check("Ctrl+0 zooms to 100%", near(k1.k, 1, 0.001), `k ${k1.k}`);
    await page.keyboard.press("Control+Equal");
    await wait(500);
    const kIn = (await cam()).k;
    await page.keyboard.press("Control+Minus");
    await wait(500);
    const kOut = (await cam()).k;
    check("Ctrl+= and Ctrl+- step the zoom in and out", near(kIn, 1.2, 0.01) && near(kOut, 0.96, 0.01), `1 to ${kIn.toFixed(2)} to ${kOut.toFixed(2)}`);
    await page.keyboard.press("Control+0");
    await wait(500);

    // Escape during a link draw makes no link
    const sk0 = (await counts()).sketches;
    await page.evaluate(() => wbSelectToolRef?.("link-straight"));
    const fromCard = await centre(`.wb-object[data-id="${ids.t}"]`);
    const toCard = await centre(`.node-card[data-id="${ids.n}"]`);
    if (fromCard && toCard) {
      await drag(fromCard, toCard, { after: async () => { await page.keyboard.press("Escape"); await wait(100); } });
    }
    const sk1 = (await counts()).sketches;
    const strayPath = await page.evaluate(() => document.querySelectorAll("#wb-zoom-group > path:not([class])").length);
    check("Escape during a link draw makes no link and leaves no line behind", fromCard && toCard && sk1 === sk0 && strayPath === 0,
      `links ${sk0} to ${sk1}, stray lines ${strayPath}`);
    await page.evaluate(() => wbSelectToolRef?.("select"));
    await page.evaluate(() => d3.select(document.getElementById("whiteboard-container")).call(wbZoom.transform, d3.zoomIdentity.translate(-1500, -900).scale(0.5)));
    await wait(300);
    await page.keyboard.press("Shift+!");
    await wait(900);
    const fits = await page.evaluate(() => {
      const r = document.getElementById("whiteboard-container").getBoundingClientRect();
      const all = [...document.querySelectorAll(".wb-object, .node-card")].map((e) => e.getBoundingClientRect());
      const inside = all.filter((b) => b.left >= r.left - 1 && b.right <= r.right + 1 && b.top >= r.top - 1 && b.bottom <= r.bottom + 1).length;
      return { inside, all: all.length };
    });
    check("Shift+1 fits the whole board in view", fits.inside === fits.all && fits.all > 0, `${fits.inside} of ${fits.all} in view`);

    // --- 16. a double-click and a right-click on empty board canvas ---
    await page.evaluate(() => d3.select(document.getElementById("whiteboard-container")).call(wbZoom.transform, d3.zoomIdentity));
    await wait(300);
    await clickEmpty();
    const blank = await emptyPoint(0.3, 0.75);
    await page.mouse.click(blank.x, blank.y, { button: "right" });
    await wait(500);
    const menu = await page.evaluate(() => {
      const open = [...document.querySelectorAll(".action-menu")]
        .filter((m) => !m.classList.contains("hidden") && m.getBoundingClientRect().width > 0);
      return open.length ? [...open[0].querySelectorAll("button")].map((b) => b.textContent.trim()) : [];
    });
    check("right-click on empty board canvas opens a canvas menu (paste, select all, zoom)",
      menu.some((t) => /Paste/.test(t)) && menu.some((t) => /Select all/.test(t)) && menu.some((t) => /Fit|Zoom/.test(t)),
      menu.join(" | ") || "nothing opened");
    await page.keyboard.press("Escape");
    await wait(300);
    c0 = await counts();
    await page.mouse.dblclick(blank.x, blank.y);
    await wait(1200);
    c1 = await counts();
    const editing = await page.evaluate(() => Boolean(document.activeElement?.isContentEditable));
    check("double-click on empty board canvas adds a text box, ready to type", c1.objects === c0.objects + 1 && editing,
      `${c0.objects} to ${c1.objects}, editing ${editing}`);
    await page.keyboard.press("Escape");
    await wait(300);

    // --- 17. a first-time user can find them: the help and the grips say so ---
    const taught = await page.evaluate(() => {
      //: The board's keys are its help sheet now (INBOX 566), drawn from the
      //: command table; " + " and "+" read the same.
      wbRenderHelpSheet("");
      const flat = (t) => t.replace(/\s+/g, " ").replace(/ ?\+ ?/g, "+");
      const help = flat(document.getElementById("wb-help-sections")?.textContent || "");
      const wanted = ["Alt + drag", "Shift + drag", "Shift + corner", "Ctrl+0", "Shift+1", "Shift + arrows",
        "Ctrl + Shift + G", "paste at the pointer", "Cancel a drag", "upright again", "Label a line"].map(flat);
      const grip = document.querySelector(".wb-rotate-handle")?.title || "";
      const resize = document.querySelector(".wb-resize-handle")?.title || "";
      return { missing: wanted.filter((w) => !help.includes(w)), grip, resize };
    });
    check("the board's help names every convention", taught.missing.length === 0, taught.missing.join(", ") || "all named");
    check("and the grips say what their double-click does", /double-click/.test(taught.grip) && /double-click/.test(taught.resize),
      `${taught.grip} | ${taught.resize}`);
  }

  // =========================== the mind map ===========================
  if (ONLY !== "board") {
    await page.evaluate(async () => {
      const content = ["# Conventions", "- Trunk", "  - Branch 1", "    - Leaf 1a", "  - Branch 2", "  - Branch 3"];
      const board = await apiJson("/whiteboard/boards/import", {
        method: "POST", body: JSON.stringify({ format: "markdown", content: content.join("\n"), name: "Conventions" }),
      });
      await openWhiteboardBoard(board.id);
      await new Promise((r) => setTimeout(r, 1500));
    });
    const topics = () => page.evaluate(() => wbMapIndex().nodes.length);
    const byText = (text) => page.evaluate((text) => wbMapIndex().nodes.find((n) => (n.data?.content || n.data?.text || "").trim() === text)?.id, text);
    const trunk = await byText("Trunk");
    const branch1 = await byText("Branch 1");
    check("a map to try it on", (await topics()) === 5 && trunk && branch1, `${await topics()} topics`);

    // Tab and Enter
    await select("object", branch1);
    await wait(300);
    let n0 = await topics();
    await page.keyboard.press("Tab");
    await wait(1200);
    await page.keyboard.press("Escape");
    await wait(300);
    let n1 = await topics();
    check("Tab on a topic adds a child", n1 === n0 + 1, `${n0} to ${n1}`);
    await select("object", branch1);
    await wait(300);
    await page.keyboard.press("Enter");
    await wait(1200);
    await page.keyboard.press("Escape");
    await wait(300);
    const n2 = await topics();
    check("Enter on a topic adds a sibling", n2 === n1 + 1, `${n1} to ${n2}`);

    // Arrows walk the tree
    await select("object", trunk);
    await wait(300);
    await page.keyboard.press("ArrowRight");
    await wait(300);
    const walked = await page.evaluate(() => wbSelectedItem?.id);
    const parentOfWalked = await page.evaluate((id) => wbMapIndex().byId.get(id)?.parent_id, walked);
    check("an arrow key moves the selection to the next topic", walked && walked !== trunk && parentOfWalked === trunk, `selected ${walked}`);

    // Double-click a branch line edits its label
    const lineAt = await page.evaluate((child) => {
      const hit = document.querySelector(`.wb-map-edge-hit[data-child="${child}"]`);
      if (!hit) return null;
      const len = hit.getTotalLength();
      const p = hit.getPointAtLength(len * 0.3);
      const m = hit.getScreenCTM();
      return { x: p.x * m.a + p.y * m.c + m.e, y: p.x * m.b + p.y * m.d + m.f };
    }, branch1);
    await page.evaluate(() => clearWbSelection());
    n0 = await topics();
    if (lineAt) await page.mouse.dblclick(lineAt.x, lineAt.y);
    await wait(700);
    const prompt = await page.evaluate(() => {
      const d = [...document.querySelectorAll(".prompt-card, dialog[open]")]
        .find((el) => el.getBoundingClientRect().width > 0);
      return d ? (d.textContent || "").trim().slice(0, 80) : null;
    });
    check("double-click a branch line asks for its label", prompt && /line into this topic/.test(prompt) && (await topics()) === n0,
      prompt || `no prompt, topics ${n0} to ${await topics()}`);
    if (prompt) { await page.keyboard.press("Escape"); await wait(400); }

    // Double-click the bend grip straightens the line
    await page.evaluate(async (id) => {
      const n = wbState.objects.find((o) => o.id === id);
      await wbMapSetNodeStyle(n, { edge_bend: 0.6 });
      renderWhiteboardNow();
    }, branch1);
    await select("object", branch1);
    await wait(500);
    const bendAt = await page.evaluate((child) => {
      const h = document.querySelector(`.wb-map-edge-handle[data-child="${child}"]`);
      const b = h?.getBoundingClientRect();
      return b && b.width ? { x: b.left + b.width / 2, y: b.top + b.height / 2 } : null;
    }, branch1);
    if (bendAt) await page.mouse.dblclick(bendAt.x, bendAt.y);
    await wait(900);
    const bend = await page.evaluate((id) => wbState.objects.find((o) => o.id === id)?.data?.edge_bend ?? null, branch1);
    check("double-click a branch line's bend grip straightens it", bendAt && !bend, `bend ${bend}, grip ${bendAt ? "found" : "missing"}`);

    // Escape during a topic drag puts the branch back
    await page.evaluate(() => clearWbSelection());
    const b0 = await obj(branch1);
    const leafId = await byText("Leaf 1a");
    const l0 = await obj(leafId);
    const bc = await centre(`.wb-object[data-id="${branch1}"]`);
    let mapDepth = await undoDepth();
    await drag(bc, { x: bc.x + 90, y: bc.y + 120 }, { after: async () => { await page.keyboard.press("Escape"); await wait(100); } });
    await wait(500);
    const b1 = await obj(branch1);
    const l1 = await obj(leafId);
    check("Escape during a topic drag puts the branch back", near(b1.x, b0.x) && near(b1.y, b0.y) && near(l1.x, l0.x) && near(l1.y, l0.y),
      `topic moved ${Math.round(b1.x - b0.x)},${Math.round(b1.y - b0.y)}, its child ${Math.round(l1.x - l0.x)},${Math.round(l1.y - l0.y)}`);
    check("and leaves no undo step", (await undoDepth()) === mapDepth, `undo +${(await undoDepth()) - mapDepth}`);

    // Space-drag pans on a map too
    const camM = () => page.evaluate(() => d3.zoomTransform(document.getElementById("whiteboard-container")).x);
    const x0 = await camM();
    const emptyM = await emptyPoint(0.2, 0.2);
    await page.keyboard.down("Space");
    await drag(emptyM, { x: emptyM.x + 80, y: emptyM.y });
    await page.keyboard.up("Space");
    const x1 = await camM();
    check("Space-drag pans a map", near(x1 - x0, 80, 3), `moved ${Math.round(x1 - x0)}`);
  }

  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} passed`);
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
