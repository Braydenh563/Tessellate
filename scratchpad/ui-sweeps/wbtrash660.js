// **Drag to delete on a board and a map** (INBOX 660, the owner: "I want to be
// able to drag elements on the whiteboard and mindmap onto a popup delete
// button to delete them"). Each case drags with the real mouse and asserts by
// effect: the target shows only while an item is carried, turns hot over it,
// a drop there deletes what was carried as ONE undo step with a toast, Ctrl+Z
// (wbUndo) puts the whole board back as it was (compared item by item, ids
// aside, like boardundo.js), a drop elsewhere is a plain move and Escape puts
// it back. Measures the target's box and colours.
//
//   BASE=http://127.0.0.1:8802 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbtrash660.js
//   W=390 for a phone width; THEME=dark; ONLY=board, map or side (the sidebar drags); TOUCH=1 drags with
//   a finger (a touch context, CDP touch events) and runs the drop cases only.
const { boot, openBoardsTab } = require("./lib.js");

const results = [];
function check(label, ok, detail) {
  results.push(Boolean(ok));
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail ? "  " + detail : ""}`);
}
const ONLY = process.env.ONLY || "";
const W = Number(process.env.W || 1440);
const TOUCH = Boolean(process.env.TOUCH);

(async () => {
  const { browser, page } = await boot({ viewport: { width: W, height: W < 600 ? 844 : 900 }, ...(TOUCH ? { hasTouch: true, isMobile: true } : {}) });
  const cdp = TOUCH ? await page.context().newCDPSession(page) : null;
  //: One pointer, the mouse or a finger, so every case below runs on either.
  const finger = { x: 0, y: 0 };
  const touch = (type, p) => cdp.send("Input.dispatchTouchEvent", { type, touchPoints: p ? [{ x: p.x, y: p.y, id: 0 }] : [] });
  const press = async (p) => { if (!TOUCH) { await page.mouse.move(p.x, p.y); return page.mouse.down(); } Object.assign(finger, p); return touch("touchStart", p); };
  const glide = async (p, steps) => {
    if (!TOUCH) return page.mouse.move(p.x, p.y, { steps });
    const from = { ...finger };
    for (let i = 1; i <= steps; i++) await touch("touchMove", { x: from.x + ((p.x - from.x) * i) / steps, y: from.y + ((p.y - from.y) * i) / steps });
    Object.assign(finger, p);
  };
  const lift = () => (TOUCH ? touch("touchEnd", null) : page.mouse.up());
  page.on("pageerror", (e) => console.log("pageerror", e.message));
  const wait = (ms) => page.waitForTimeout(ms);
  await openBoardsTab(page);
  await page.evaluate(() => { window.confirmDialog = async () => true; });
  await wait(400);

  //: The whole board as text, ids left out (a restored row is a new row).
  const boardState = () => page.evaluate(() => {
    const strip = (o, keys) => keys.map((k) => `${k}=${JSON.stringify(o[k] ?? null)}`).join(" ");
    const objects = (wbState.objects || []).map((o) => `O ${o.kind} ${strip(o, ["x", "y", "width", "height", "rotation", "z"])} ${JSON.stringify(o.data?.content ?? "")}`);
    const nodes = (wbState.nodes || []).map((n) => `N ${strip(n, ["entry_id", "x", "y", "width", "height", "rotation"])}`);
    const sketches = (wbState.sketches || []).map((s) => { let d = s.data; try { d = JSON.stringify(typeof d === "string" ? JSON.parse(d) : d); } catch {} return `S ${d}`; });
    return [...objects, ...nodes, ...sketches].sort().join("\n");
  });
  const mapState = () => page.evaluate(() => {
    const idx = wbMapIndex();
    const name = (n) => (n ? String(wbMapLabel(n) || "").trim() : null);
    return idx.nodes.map((n) => {
      const data = { ...(n.data || {}) };
      delete data.order;
      return `${name(n)}<${name(idx.byId.get(n.parent_id)) ?? "-"} ${Math.round(n.x)},${Math.round(n.y)} ${JSON.stringify(data, Object.keys(data).sort())}`;
    }).sort().join(" | ") + ` links:${(wbState.sketches || []).length}`;
  });
  const undoDepth = () => page.evaluate(() => wbUndoStack.length);
  //: The item's centre on screen, the camera first panned to put it in the
  //: canvas's upper middle, clear of the phone's chrome and of the target.
  const centre = (selector) => page.evaluate(async (s) => {
    const el = document.querySelector(s);
    if (!el) return null;
    const c = document.getElementById("whiteboard-container");
    const host = c.getBoundingClientRect();
    const at = el.getBoundingClientRect();
    const k = d3.zoomTransform(c).k || 1;
    d3.select(c).call(wbZoom.translateBy, (host.left + host.width / 2 - (at.left + at.width / 2)) / k, (host.top + host.height * 0.4 - (at.top + at.height / 2)) / k);
    await new Promise((r) => setTimeout(r, 250));
    const b = el.getBoundingClientRect();
    return b.width || b.height ? { x: b.left + b.width / 2, y: b.top + b.height / 2 } : null;
  }, selector);
  const centre2 = (selector) => page.evaluate((q) => { const el = document.querySelector(q); if (!el) return null; el.scrollIntoView({ block: "nearest" }); const b = el.getBoundingClientRect(); return { x: b.left + b.width / 2, y: b.top + b.height / 2 }; }, selector);
  const trash = () => page.evaluate(() => {
    const el = document.querySelector(".wb-trash");
    if (!el || el.classList.contains("hidden")) return { shown: false };
    const b = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    const host = document.getElementById("whiteboard-container").getBoundingClientRect();
    return {
      shown: true, hot: el.classList.contains("wb-trash-hot"), label: el.textContent.trim(),
      box: [b.left, b.top, b.width, b.height].map(Math.round), centreOff: Math.round(b.left + b.width / 2 - (host.left + host.width / 2)),
      fromBottom: Math.round(host.bottom - b.bottom), color: cs.color, bg: cs.backgroundColor, border: cs.borderColor,
      x: b.left + b.width / 2, y: b.top + b.height / 2, ariaHidden: el.getAttribute("aria-hidden"),
    };
  });
  const toastText = () => page.evaluate(() => [...document.querySelectorAll(".toast")].map((t) => t.textContent.trim()).filter(Boolean).pop() || "");
  //: Press on `from`, travel a little (the target appears), then onto the
  //: target (or `to`), then `mid` runs, then release unless `keep`.
  const carry = async (from, { to = null, mid = null, release = true } = {}) => {
    await press(from);
    await glide({ x: from.x + 14, y: from.y + 10 }, 4);
    await wait(150);
    const shown = await trash();
    const dest = to || (shown.shown ? { x: shown.x, y: shown.y } : { x: from.x, y: from.y + 200 });
    await glide(dest, 14);
    await wait(150);
    const over = await trash();
    if (mid) await mid();
    if (release) await lift();
    await wait(900);
    return { shown, over };
  };

  if (ONLY !== "map" && ONLY !== "side") {
    const ids = await page.evaluate(async () => {
      const board = await apiJson("/whiteboard/boards", { method: "POST", body: JSON.stringify({ name: `trash ${Date.now()}`, type: "board" }) });
      await openWhiteboardBoard(board.id);
      await new Promise((r) => setTimeout(r, 900));
      const post = (body) => apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ board_id: board.id, kind: "text", ...body }) });
      const t = await post({ x: 120, y: 80, width: 160, height: 70, data: { content: "Tee" } });
      const u = await post({ x: 340, y: 80, width: 140, height: 60, data: { content: "You" } });
      const e = await apiJson("/entries", { method: "POST", body: JSON.stringify({ content: "A card for the trash", category: "General" }) });
      const n = await apiJson("/whiteboard/nodes", { method: "POST", body: JSON.stringify({ entry_id: e.id, board_id: board.id, x: 120, y: 200, z: 1, width: 200, height: 110 }) });
      const s = await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ board_id: board.id, data: JSON.stringify({ type: "rect", d: "M360 200 L460 200 L460 280 L360 280 Z", color: "#3b82f6", width: 3 }) }) });
      await fetchWhiteboardState();
      renderWhiteboardNow();
      wbSelectToolRef?.("select");
      localStorage.setItem("wb-snap", "off");
      d3.select(document.getElementById("whiteboard-container")).call(wbZoom.transform, innerWidth < 600 ? d3.zoomIdentity.scale(0.62) : d3.zoomIdentity);
      await new Promise((r) => setTimeout(r, 400));
      return { t: t.id, u: u.id, n: n.id, s: s.id };
    });
    const cases = [
      ["text box", `.wb-object[data-id="${ids.t}"]`],
      ["note card", `.node-card[data-id="${ids.n}"]`],
      ["shape", `.sketch-group[data-id="${ids.s}"] .sketch-hitbox`],
    ];
    for (const [label, selector] of cases) {
      const before = await boardState();
      const depth = await undoDepth();
      const from = await centre(selector);
      if (!from) { check(`${label}: found`, false); continue; }
      const { shown, over } = await carry(from);
      check(`${label}: target shows while carried`, shown.shown, JSON.stringify(shown.box));
      check(`${label}: hot over the target`, over.hot && /Release to delete/.test(over.label), over.label);
      const after = await boardState();
      const gone = after.split("\n").length === before.split("\n").length - 1;
      check(`${label}: dropped is deleted`, gone, `${before.split("\n").length} -> ${after.split("\n").length}`);
      check(`${label}: one undo step`, (await undoDepth()) - depth === 1, `${depth} -> ${await undoDepth()}`);
      const toast = await toastText();
      check(`${label}: toast with Undo`, /Deleted 1 item\./.test(toast) && /Undo/.test(toast), toast);
      check(`${label}: target hidden after`, !(await trash()).shown);
      await page.evaluate(async () => { await wbUndo(); });
      await wait(700);
      const back = await boardState();
      check(`${label}: Undo restores the board identically`, back === before, back === before ? "" : `\n${before}\n---\n${back}`);
    }
    // A multi-selection carried by one member: all three go, one step back.
    if (!TOUCH) {
      const before = await boardState();
      const depth = await undoDepth();
      const keys = await page.evaluate(() => {
        const t = wbState.objects.find((o) => o.data?.content === "Tee");
        const u = wbState.objects.find((o) => o.data?.content === "You");
        const s = wbState.sketches[0];
        clearWbSelection();
        for (const k of [wbMultiKey("object", t.id), wbMultiKey("object", u.id), wbMultiKey("sketch", s.id)]) wbMultiSelection.add(k);
        wbApplySelectionHighlight();
        wbUpdateSelectionBar();
        return { t: t.id };
      });
      await wait(300);
      const from = await centre(`.wb-object[data-id="${keys.t}"]`);
      await carry(from);
      const after = await boardState();
      check("multi-selection: all three deleted", after.split("\n").length === before.split("\n").length - 3, `${before.split("\n").length} -> ${after.split("\n").length}`);
      check("multi-selection: one undo step", (await undoDepth()) - depth === 1);
      check("multi-selection: toast", /Deleted 3 items\./.test(await toastText()), await toastText());
      await page.evaluate(async () => { await wbUndo(); });
      await wait(900);
      const back = await boardState();
      check("multi-selection: Undo restores identically", back === before, back === before ? "" : `\n${before}\n---\n${back}`);
      await page.evaluate(() => { clearWbSelection(); wbMultiSelection.clear(); wbApplySelectionHighlight(); });
    }
    // Dropped elsewhere: a plain move, nothing deleted, the target gone.
    {
      const before = await boardState();
      const id = await page.evaluate(() => wbState.objects.find((o) => o.data?.content === "Tee").id);
      const from = await centre(`.wb-object[data-id="${id}"]`);
      await carry(from, { to: { x: from.x + 60, y: from.y + 40 } });
      const after = await boardState();
      check("dropped elsewhere: nothing deleted", after.split("\n").length === before.split("\n").length);
      check("dropped elsewhere: it moved", after !== before);
      check("dropped elsewhere: target hidden", !(await trash()).shown);
      await page.evaluate(async () => { await wbUndo(); });
      await wait(500);
    }
    // Escape over the target: put back, nothing deleted, no step.
    if (!TOUCH) {
      const before = await boardState();
      const depth = await undoDepth();
      const id = await page.evaluate(() => wbState.objects.find((o) => o.data?.content === "Tee").id);
      const from = await centre(`.wb-object[data-id="${id}"]`);
      const { over } = await carry(from, { mid: async () => { await page.keyboard.press("Escape"); await wait(150); } });
      check("Escape: target was hot", over.hot);
      const after = await boardState();
      check("Escape over the target: nothing deleted or moved", after === before);
      check("Escape: no undo step", (await undoDepth()) === depth);
      check("Escape: target hidden", !(await trash()).shown);
    }
    // A click is not a drag: the target never shows.
    if (!TOUCH) {
      const id = await page.evaluate(() => wbState.objects.find((o) => o.data?.content === "Tee").id);
      const at = await centre(`.wb-object[data-id="${id}"]`);
      await page.mouse.move(at.x, at.y);
      await page.mouse.down();
      const shown = (await trash()).shown;
      await page.mouse.up();
      check("a press without travel shows no target", !shown);
    }
    // Measure the target, plain and hot.
    if (!TOUCH) {
      const id = await page.evaluate(() => wbState.objects.find((o) => o.data?.content === "Tee").id);
      const from = await centre(`.wb-object[data-id="${id}"]`);
      const { shown, over } = await carry(from, { mid: async () => { await page.keyboard.press("Escape"); } });
      console.log("target", JSON.stringify({ plain: { box: shown.box, centreOff: shown.centreOff, fromBottom: shown.fromBottom, color: shown.color, bg: shown.bg, aria: shown.ariaHidden }, hot: { color: over.color, bg: over.bg, border: over.border } }));
    }
  }

  if (ONLY !== "board" && ONLY !== "side") {
    const map = await page.evaluate(async () => apiJson("/whiteboard/boards/import", {
      method: "POST", body: JSON.stringify({ format: "markdown", content: "# Trash map\n- Root\n  - Alpha\n    - Beta\n  - Gamma", name: "Trash map " + Date.now() }),
    }));
    await page.evaluate(async (b) => { await openWhiteboardBoard(b); }, map.id);
    await page.waitForFunction(() => wbIsMap() && document.querySelectorAll("#whiteboard-container .wb-object").length >= 4, null, { timeout: 20000 });
    await wait(1200);
    await page.evaluate(() => { wbSelectToolRef?.("select"); });
    const id = await page.evaluate(() => wbMapIndex().nodes.find((n) => String(wbMapLabel(n)).trim() === "Alpha")?.id);
    const before = await mapState();
    const depth = await undoDepth();
    const from = await centre(`.wb-object[data-id="${id}"]`);
    const { shown, over } = await carry(from);
    check("map topic: target shows", shown.shown);
    check("map topic: hot", over.hot);
    const after = await mapState();
    const kept = after.split(" | ").map((row) => row.split("<")[0]).join(", ");
    check("map topic: the topic and its branch deleted", !/Alpha|Beta/.test(after) && /Gamma/.test(after), kept);
    check("map topic: one undo step", (await undoDepth()) - depth === 1);
    check("map topic: toast", /Deleted 2 topics\./.test(await toastText()), await toastText());
    await page.evaluate(async () => { await wbUndo(); });
    await wait(1200);
    const back = await mapState();
    check("map topic: Undo restores the map identically", back === before, back === before ? "" : `\n${before}\n---\n${back}`);
  }


  //: The sidebar's two drags (LEDGER L262): a Layers row and a Library tile of your own, dragged with the real mouse (the
  //: browser's drag and drop) onto the same target.
  if (ONLY === "side" || (ONLY === "" && !TOUCH)) {
    await page.evaluate(async () => {
      const board = await apiJson("/whiteboard/boards", { method: "POST", body: JSON.stringify({ name: `side ${Date.now()}`, type: "board" }) });
      await openWhiteboardBoard(board.id);
      await new Promise((r) => setTimeout(r, 900));
      const post = (body) => apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ board_id: board.id, kind: "text", ...body }) });
      await post({ x: 120, y: 80, width: 160, height: 70, data: { content: "Row one" } });
      await post({ x: 340, y: 80, width: 140, height: 60, data: { content: "Row two" } });
      await fetchWhiteboardState();
      renderWhiteboardNow();
      wbOpenSidebar("layers");
    });
    await wait(900);
    const layerKeys = () => page.evaluate(() => [...document.querySelectorAll("#wb-layers-tree [role='treeitem']:not([data-group])")].map((r) => r.dataset.key));
    const rowsBefore = await layerKeys();
    const depth0 = await undoDepth();
    const row = await centre2('#wb-layers-tree [role="treeitem"]:not([data-group])');
    await page.mouse.move(row.x, row.y);
    await page.mouse.down();
    await page.mouse.move(row.x + 10, row.y + 10, { steps: 4 });
    await wait(150);
    const shown = await trash();
    check("layers row: target shows while the row is carried", shown.shown, JSON.stringify(shown.box));
    await page.mouse.move(shown.x, shown.y, { steps: 14 });
    await page.mouse.move(shown.x + 3, shown.y + 1, { steps: 3 }); // the drag emulation drops the last dragover of a glide
    await wait(200);
    const hot = await trash();
    check("layers row: hot over the target", hot.hot && /Release to delete/.test(hot.label), hot.label);
    await page.mouse.up();
    await wait(1000);
    const rowsAfter = await layerKeys();
    check("layers row: that object is deleted", rowsAfter.length === rowsBefore.length - 1, `${rowsBefore.length} -> ${rowsAfter.length}`);
    check("layers row: one undo step", (await undoDepth()) - depth0 === 1, `${depth0} -> ${await undoDepth()}`);
    check("layers row: toast with Undo", /Deleted 1 item\./.test(await toastText()), await toastText());
    check("layers row: target hidden after", !(await trash()).shown);
    await page.evaluate(async () => { await wbUndo(); });
    await wait(900);
    check("layers row: Undo brings it back", (await layerKeys()).length === rowsBefore.length);

    // A tile you made: saved from a selection, dragged to the target, deleted with the existing Undo toast.
    await page.evaluate(async () => {
      const o = wbState.objects[0];
      wbMultiSelection.clear();
      wbMultiSelection.add(wbMultiKey("object", o.id));
      const payload = wbLibSelectionPayload({ quiet: true });
      await apiJson("/board-library", { method: "POST", body: JSON.stringify({ kind: "element", name: "Trash me", payload }) });
      clearWbSelection();
      wbMultiSelection.clear();
      await wbLoadLibrary({ force: true });
      wbOpenSidebar("library");
    });
    await wait(900);
    await page.fill("#wb-lib-search", "Trash me");
    await wait(700);
    const tileSel = "#wb-lib-list .wb-lib-tile";
    const countTiles = () => page.evaluate((q) => document.querySelectorAll(q).length, tileSel);
    const tile = await centre2(tileSel);
    check("library tile: found", Boolean(tile));
    const before = await countTiles();
    await page.mouse.move(tile.x, tile.y);
    await page.mouse.down();
    await page.mouse.move(tile.x + 12, tile.y + 8, { steps: 4 });
    await wait(150);
    check("library tile: target shows while the tile is carried", (await trash()).shown);
    const t2 = await trash();
    await page.mouse.move(t2.x, t2.y, { steps: 14 });
    await page.mouse.move(t2.x + 3, t2.y + 1, { steps: 3 });
    await wait(200);
    check("library tile: hot over the target", (await trash()).hot);
    const objsBefore = await page.evaluate(() => wbState.objects.length);
    await page.mouse.up();
    await wait(1300);
    check("library tile: the entry is deleted", (await countTiles()) === before - 1, `${before} -> ${await countTiles()}`);
    check("library tile: nothing was placed on the board", (await page.evaluate(() => wbState.objects.length)) === objsBefore);
    check("library tile: toast with Undo", /Deleted Trash me from the library\./.test(await toastText()), await toastText());
    check("library tile: target hidden after", !(await trash()).shown);
    await page.evaluate(async () => { await wbUndo(); });
    await wait(1100);
    check("library tile: Undo brings the entry back", (await countTiles()) === before, String(await countTiles()));
    // A built-in tile does not offer the target.
    await page.fill("#wb-lib-search", "Rectangle");
    await wait(700);
    const built = await centre2(tileSel);
    if (built) {
      await page.mouse.move(built.x, built.y);
      await page.mouse.down();
      await page.mouse.move(built.x + 12, built.y + 8, { steps: 4 });
      await wait(150);
      check("built-in tile: no delete target", !(await trash()).shown);
      await page.mouse.up();
    }
  }

  const failed = results.filter((r) => !r).length;
  console.log(`${results.length - failed}/${results.length} passed`);
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
