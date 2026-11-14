// **Every board and map gesture is one Undo step that puts everything back**
// (INBOX 537, the owner: "the undo and redo across the application needs to
// cover EVERYTHING"; and "local undos and redos ... for specific documents,
// whiteboards, mindmaps"). Each case: do it, Undo, compare the whole board to
// before; Redo where the redo is the risky half; then a reload for the truth.
//   BASE=http://127.0.0.1:8812 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/boardundo.js
const { boot } = require("./lib.js");
const results = [];
function check(label, ok, detail) {
  results.push(Boolean(ok));
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${ok || !detail ? "" : "  " + detail}`);
}

(async () => {
  const { browser, page } = await boot({ viewport: { width: 1440, height: 900 } });
  page.on("pageerror", (e) => console.log("pageerror", e.message));
  await page.click('[data-tab="library"]');
  await page.waitForTimeout(700);
  await page.click('#library-subtabs [data-target="library-view-whiteboard"]');
  await page.waitForFunction(() => typeof window.initWhiteboard === "function", null, { timeout: 30000 });
  await page.evaluate(async () => {
    window.confirmDialog = async () => true;
    const v = document.getElementById("library-view-whiteboard");
    for (const s of document.querySelectorAll('[id^="library-view-"]')) s.classList.toggle("hidden", s !== v);
    await initWhiteboard();
  });
  const map = await page.evaluate(async () => apiJson("/whiteboard/boards/import", {
    method: "POST", body: JSON.stringify({ format: "markdown", content: "# Undo map\n- Root\n  - Alpha\n    - Beta\n  - Gamma", name: "Undo map " + Date.now() }),
  }));
  const open = async (id) => {
    await page.evaluate(async (b) => { await openWhiteboardBoard(b); }, id);
    await page.waitForTimeout(1200);
  };
  await open(map.id);
  // The whole map: shape, every row's look and place, and the map's settings.
  const state = () => page.evaluate(() => {
    const idx = wbMapIndex();
    const name = (n) => (n ? String(wbMapLabel(n) || "").trim() : null);
    const rows = idx.nodes.map((n) => {
      const data = { ...(n.data || {}) };
      delete data.order;
      return `${name(n)}<${name(idx.byId.get(n.parent_id)) ?? "-"} ${Math.round(n.x)},${Math.round(n.y)} ${JSON.stringify(data, Object.keys(data).sort())}`;
    }).sort();
    const s = window.wbMapState || {};
    return rows.join(" | ") + ` || ${s.layout} ${Boolean(s.numbered)} ${JSON.stringify(s.theme || {})} links:${(wbState.sketches || []).length}`;
  });
  const shape = () => page.evaluate(() => {
    const idx = wbMapIndex();
    const name = (n) => (n ? String(wbMapLabel(n) || "").trim() : null);
    return idx.nodes.map((n) => `${name(n)}<${name(idx.byId.get(n.parent_id)) ?? "-"}`).sort().join(" | ");
  });
  const id = (label) => page.evaluate((l) => wbMapIndex().nodes.find((n) => String(wbMapLabel(n)).trim() === l)?.id, label);
  const undo = async () => { await page.evaluate(async () => { await wbUndo(); }); await page.waitForTimeout(400); };
  const redo = async () => { await page.evaluate(async () => { await wbRedo(); }); await page.waitForTimeout(400); };
  const roundTrip = async (label, act, { redoCheck = true } = {}) => {
    const before = await state();
    await act();
    await page.waitForTimeout(400);
    const during = await state();
    const changed = during !== before;
    await undo();
    const undone = await state();
    check(`${label}: one Undo puts the map back`, changed && undone === before, `changed=${changed}\n  before ${before}\n  after  ${undone}`);
    if (redoCheck) {
      await redo();
      const redone = await shape();
      const want = during.split(" || ")[0].split(" | ").map((r) => r.replace(/ -?\d+,-?\d+ .*$/, "")).sort().join(" | ");
      check(`${label}: Redo does it again`, redone === want, `${redone}\n  want ${want}`);
      await undo();
      check(`${label}: and Undo again`, (await state()) === before, await state());
    }
  };

  await roundTrip("Delete key on a topic with a branch", async () => {
    const a = await id("Alpha");
    await page.evaluate(async (x) => { await wbDeleteObjectRef((wbState.objects || []).find((o) => o.id === x)); }, a);
  });
  await roundTrip("fold a branch", async () => { const a = await id("Alpha"); await page.evaluate((x) => wbMapToggleCollapse(x), a); });
  await roundTrip("theme field", () => page.evaluate(() => wbMapSetTheme({ edge_dashed: true })), { redoCheck: false });
  await roundTrip("number the branches", () => page.evaluate(() => wbMapSetNumbered(true)), { redoCheck: false });
  await roundTrip("change the layout", () => page.evaluate(() => wbMapSetLayout("tree-down")), { redoCheck: false });
  await roundTrip("detach a branch", async () => { const a = await id("Alpha"); await page.evaluate((x) => wbMapSever(x), a); });
  await roundTrip("remove a topic, keep its branch", async () => { const a = await id("Alpha"); await page.evaluate((x) => wbMapRemoveKeepingBranch(x), a); });
  await roundTrip("turn a line around", async () => { const a = await id("Alpha"); await page.evaluate((x) => wbMapReverseEdge(x), a); });
  await roundTrip("copy a branch", async () => { const a = await id("Alpha"); await page.evaluate((x) => wbMapCopyBranch(x), a); });
  await roundTrip("add a child (Tab)", async () => {
    const g = await id("Gamma");
    await page.evaluate(async (x) => { await wbMapAddChild(x); }, g);
    await page.keyboard.press("Escape");
  });
  {
    const a = await id("Alpha");
    await page.evaluate(async (x) => { const n = wbState.objects.find((o) => o.id === x); n.data = { ...n.data, collapsed: true }; await wbSaveObject(n); }, a);
  }
  await roundTrip("expand all", () => page.evaluate(() => wbMapExpandAll()), { redoCheck: false });
  // the fold set up for that case is its own state now; open it plainly
  await page.evaluate(async () => { for (const n of wbState.objects) if (n.data?.collapsed) { n.data = { ...n.data, collapsed: false }; await wbSaveObject(n); } });
  {
    const a = await id("Alpha");
    await page.evaluate(async (x) => { const n = wbState.objects.find((o) => o.id === x); n.data = { ...n.data, color: "#ff0000" }; await wbSaveObject(n); }, a);
  }
  await roundTrip("back to the map's style, every topic", () => page.evaluate(() => wbMapClearEveryTopic()), { redoCheck: false });
  await page.evaluate(async () => { for (const n of wbState.objects) if (n.data?.color) { const d = { ...n.data }; delete d.color; n.data = d; await wbSaveObject(n); } });
  await roundTrip("clear the map to one topic", () => page.evaluate(() => wbMapClearToOneTopic()));

  // A topic made by Tab that gains a branch some other way (an agent, another
  // tab): taking the Tab back must keep the branch, and Redo bring it all.
  {
    const before = await shape();
    const g = await id("Gamma");
    const made = await page.evaluate(async (x) => (await wbMapAddChild(x))?.id, g);
    await page.keyboard.press("Escape");
    await page.evaluate(async ({ boardId, parent }) => {
      await apiJson(`/whiteboard/boards/${boardId}/nodes`, { method: "POST", body: JSON.stringify({ kind: "topic", parent_id: parent, text: "Grandchild" }) });
      await fetchWhiteboardState();
    }, { boardId: map.id, parent: made });
    await undo();
    check("a topic that gained a branch elsewhere: Undo takes both", (await shape()) === before, await shape());
    await redo();
    check("and Redo brings the branch back with it", /Grandchild<New topic/.test(await shape()), await shape());
    await undo();
  }

  // Each board keeps its own history.
  const board = await page.evaluate(async () => apiJson("/whiteboard/boards", { method: "POST", body: JSON.stringify({ name: "Undo board " + Date.now() }) }));
  await page.evaluate(async () => { await wbMapSetNumbered(true); });
  const mapCanUndo = await page.evaluate(() => wbCanUndo());
  await open(board.id);
  check("a second board starts with its own empty history", mapCanUndo && !(await page.evaluate(() => wbCanUndo())));

  // Board: two boxes and a link between them.
  const boardState = () => page.evaluate(() => {
    const boxes = (wbState.objects || []).map((o) => `${o.data?.content}@${o.x},${o.y}:${o.group_id || ""}`).sort();
    const byId = new Map((wbState.objects || []).map((o) => [o.id, o.data?.content]));
    const links = (wbState.sketches || []).map((s) => { const d = JSON.parse(s.data); return `${byId.get(d.sourceId)}->${byId.get(d.targetId)}`; }).sort();
    return boxes.join(",") + " | " + links.join(",");
  });
  await page.evaluate(async (b) => {
    const mk = (content, x) => apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ kind: "text", data: { content }, board_id: b, x, y: 100, z: 1, width: 160, height: 80 }) });
    const one = await mk("One", 100);
    const two = await mk("Two", 400);
    await apiJson("/whiteboard/sketches", { method: "POST", body: JSON.stringify({ board_id: b, x: 0, y: 0, z: 0, data: JSON.stringify({ type: "link-straight", sourceKind: "object", sourceId: one.id, targetKind: "object", targetId: two.id }) }) });
    await fetchWhiteboardState();
    renderWhiteboardNow();
  }, board.id);
  const boardBefore = await boardState();
  check("the board has two boxes and a link", /One->Two/.test(boardBefore), boardBefore);
  await page.evaluate(async () => { await wbDeleteObjectRef(wbState.objects.find((o) => o.data.content === "One")); });
  await undo();
  check("a deleted box comes back with its link", (await boardState()) === boardBefore, await boardState());
  await redo();
  await undo();
  check("and again after a Redo", (await boardState()) === boardBefore, await boardState());
  await page.evaluate(() => { for (const o of wbState.objects) wbMultiSelection.add(wbMultiKey("object", o.id)); deleteWbSelection(); });
  await page.waitForTimeout(1200);
  const emptied = await boardState();
  await undo();
  check("a deleted selection is one Undo step", emptied.startsWith(" |") && (await boardState()) === boardBefore, `${emptied} / ${await boardState()}`);
  await page.evaluate(async () => { for (const o of wbState.objects) wbMultiSelection.add(wbMultiKey("object", o.id)); await wbGroupSelection(); wbMultiSelection.clear(); });
  const grouped = await boardState();
  await undo();
  check("grouping is one Undo step", grouped !== boardBefore && (await boardState()) === boardBefore, grouped);
  await page.evaluate(() => wbClearBoard());
  await page.waitForTimeout(1500);
  await undo();
  await page.waitForTimeout(800);
  check("clearing the board is one Undo step", (await boardState()) === boardBefore, await boardState());
  await open(board.id);
  check("the board after a reload is the board before", (await boardState()) === boardBefore, await boardState());

  // Brief 77 row 3: an agent's write (straight to the server, as a chat tool
  // writes, then the stream's `mm:board-changed`) is one step on the stack.
  const depth = () => page.evaluate(() => wbUndoStack.length);
  const d0 = await depth();
  await page.evaluate(async (b) => {
    await fetch("/whiteboard/objects", { method: "POST", headers: { "Content-Type": "application/json", "X-Auth-Token": authToken(), "X-Workspace-ID": activeSpaceId() },
      body: JSON.stringify({ kind: "text", data: { content: "Agent" }, board_id: b, x: 700, y: 100, z: 1, width: 160, height: 80 }) });
    document.dispatchEvent(new CustomEvent("mm:board-changed", { detail: { source: "Atlas" } }));
  }, board.id);
  await page.waitForFunction(() => /^Atlas/.test(wbUndoStack[wbUndoStack.length - 1]?.label || ""), null, { timeout: 5000 }).catch(() => {});
  const agentLabel = await page.evaluate(() => wbUndoStack[wbUndoStack.length - 1]?.label || "");
  const agentDepth = (await depth()) - d0;
  await undo();
  await page.waitForTimeout(600);
  check("an agent's change is one Undo step, and Undo takes it back", agentDepth === 1 && /^Atlas changed 1 item$/.test(agentLabel) && (await boardState()) === boardBefore,
    `${agentDepth} ${agentLabel} ${await boardState()}`);

  // And another tab's: a second page on the same board writes; this one hears.
  const other = await page.context().newPage();
  await other.goto(page.url(), { waitUntil: "domcontentloaded" });
  await other.waitForFunction(() => typeof apiJson === "function" && localStorage.getItem("token"), null, { timeout: 15000 });
  const d1 = await depth();
  await other.evaluate(async (b) => {
    await ensureModule("library");
    const wait = (ms) => new Promise((r) => setTimeout(r, ms));
    for (let i = 0; i < 100 && typeof wbTakeChangeFromElsewhere !== "function"; i++) await wait(100);
    window.currentBoardId = b;
    await apiJson("/whiteboard/objects", { method: "POST", body: JSON.stringify({ kind: "text", data: { content: "Tab" }, board_id: b, x: 900, y: 100, z: 1, width: 160, height: 80 }) });
  }, board.id).catch((e) => console.log("other tab:", e.message));
  await page.waitForFunction(() => /^Another tab/.test(wbUndoStack[wbUndoStack.length - 1]?.label || ""), null, { timeout: 5000 }).catch(() => {});
  const tabLabel = await page.evaluate(() => wbUndoStack[wbUndoStack.length - 1]?.label || "");
  const tabDepth = (await depth()) - d1;
  await undo();
  await page.waitForTimeout(600);
  check("another tab's change is one Undo step, and Undo takes it back", tabDepth === 1 && /^Another tab changed 1 item$/.test(tabLabel) && (await boardState()) === boardBefore,
    `${tabDepth} ${tabLabel} ${await boardState()}`);
  await other.close();

  // Back to the map: its history waited for it.
  await open(map.id);
  check("the map's history is still there after visiting another board", await page.evaluate(() => wbCanUndo()));
  await undo();
  check("and its Undo is the map's own last step", await page.evaluate(() => !window.wbMapState.numbered));

  // The owner's report: a loose branch, moved, "straight up disappeared".
  // Dropped onto a folded topic, it must stay in sight.
  const loose = await page.evaluate(async (boardId) => {
    const idx = wbMapIndex();
    const find = (l) => idx.nodes.find((n) => String(wbMapLabel(n)).trim() === l);
    const alpha = find("Alpha"), gamma = find("Gamma");
    await apiJson(`/whiteboard/boards/${boardId}/nodes/${alpha.id}/move`, { method: "PUT", body: JSON.stringify({ parent_id: null }) });
    gamma.data = { ...gamma.data, collapsed: true };
    await wbSaveObject(gamma);
    await openWhiteboardBoard(boardId);
    await new Promise((r) => setTimeout(r, 1000));
    wbZoomToFit({ animate: false });
    await new Promise((r) => setTimeout(r, 400));
    const box = (n) => document.querySelector(`#wb-html-layer .wb-map-node[data-id="${n}"]`)?.getBoundingClientRect();
    const a = box(alpha.id), g = box(gamma.id);
    return a && g ? { id: alpha.id, from: { x: a.left + a.width / 2, y: a.top + a.height / 2 }, to: { x: g.left + g.width / 2, y: g.top + g.height / 2 } } : null;
  }, map.id);
  if (loose) {
    await page.mouse.move(loose.from.x, loose.from.y);
    await page.mouse.down();
    for (let i = 1; i <= 16; i++) {
      await page.mouse.move(loose.from.x + (loose.to.x - loose.from.x) * i / 16, loose.from.y + (loose.to.y - loose.from.y) * i / 16);
    }
    await page.waitForTimeout(150);
    await page.mouse.up();
    await page.waitForTimeout(1500);
    const seen = await page.evaluate((x) => {
      const el = document.querySelector(`#wb-html-layer .wb-map-node[data-id="${x}"]`);
      const r = el?.getBoundingClientRect();
      const c = document.getElementById("whiteboard-container").getBoundingClientRect();
      return { inState: wbState.objects.some((o) => o.id === x), drawn: Boolean(el && r.width), onScreen: Boolean(r && r.right > c.left && r.left < c.right && r.bottom > c.top && r.top < c.bottom) };
    }, loose.id);
    check("a loose branch dropped on a folded topic stays in sight", seen.inState && seen.drawn && seen.onScreen, JSON.stringify(seen) + " " + (await shape()));
    await undo();
    check("and Undo puts it back loose", /Alpha<- /.test((await shape()) + " "), await shape());
  } else check("the loose branch is drawn", false);

  await browser.close();
  const failed = results.filter((r) => !r).length;
  console.log(`${results.length - failed}/${results.length}`);
  process.exit(failed ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(1); });
