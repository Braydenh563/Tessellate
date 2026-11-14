(() => {
  // whiteboard-undo.js: the board's undo and redo stacks, the per-board history swap, and the one-gesture-one-step recorder.
  // Moved out of whiteboard.js (L-whiteboard-52), wrapped: the stacks and depth are this file's own `let`s, read elsewhere through `wbStacks`, so a reassigned stack is never a shared top-level binding.

  //: **A hundred steps, not twenty** (INBOX 445). Building a sixty-topic map
  //: by keys pushes two entries a topic (the create and the rename), so twenty
  //: reached back ten topics; Excalidraw keeps about a hundred and tldraw more.
  //: An entry is a payload of one row (a deleted map branch, its rows), so the
  //: whole stack stays well under a megabyte at a hundred.
  const WB_UNDO_MAX = 100;
  // {action: "delete"|"create", kind: "sketch"|"node", payload, id}. Bounded so an hour of erasing doesn't grow this forever; only the newest matters.
  let wbUndoStack = [];
  // A redo stack, the same shape as the sketch pad's own history: cleared whenever a fresh action is pushed onto the undo stack, since redoing something that predates a new action would resurrect a version of the board the newer action never saw.
  let wbRedoStack = [];

  //: **Each board and map keeps its own history** (the owner, 2026-10-05: "undo
  //: and redo history for specific documents, whiteboards, mindmaps"). One pair
  //: of stacks served every board, so Ctrl+Z on a second board replayed the
  //: first board's steps against rows it could not see, or re-made them there.
  //: The pair is swapped by board on every read, kept for the session.
  const wbHistoryByBoard = new Map();
  let wbHistoryBoard = null;

  function wbHistoryFor() {
    const key = String(window.currentBoardId ?? "default");
    if (key === wbHistoryBoard) return;
    if (wbHistoryBoard !== null) wbHistoryByBoard.set(wbHistoryBoard, { undo: wbUndoStack, redo: wbRedoStack });
    const kept = wbHistoryByBoard.get(key);
    wbUndoStack = kept ? kept.undo : [];
    wbRedoStack = kept ? kept.redo : [];
    wbHistoryBoard = key;
    if (!kept) wbHistoryRestore(key);
  }

  //: **And across a reload** (INBOX 553(b), decision 17 as amended): a board
  //: met for the first time this session takes back what was stored for it
  //: (undo-store.js), unless a step has been taken on it in the meantime.
  //: Nothing is written for a board until its stored history has been read,
  //: so an open that is quicker than the read cannot overwrite it with nothing.
  const wbHistoryRead = new Set();

  function wbHistoryRestore(key) {
    if (key === "default" || typeof undoStoreGet !== "function") {
      wbHistoryRead.add(key);
      return;
    }
    undoStoreGet(`board:${key}`).then((stored) => {
      wbHistoryRead.add(key);
      if (wbHistoryBoard !== key || !stored || wbUndoStack.length || wbRedoStack.length) return;
      wbUndoStack = Array.isArray(stored.undo) ? stored.undo : [];
      wbRedoStack = Array.isArray(stored.redo) ? stored.redo : [];
      wbUpdateUndoRedoButtons();
    });
  }

  function wbUpdateUndoRedoButtons() {
    wbHistoryFor();
    //: Only the page board writes the stored copy: an embed of the same board would replace it with its own stack (L-whiteboard-66).
    if (typeof undoStorePut === "function" && !wbInstances.active.container && wbHistoryRead.has(wbHistoryBoard) && wbHistoryBoard !== "default") {
      undoStorePut(`board:${wbHistoryBoard}`, undoStoreBoardValue(wbUndoStack, wbRedoStack));
    }
    const undoBtn = document.getElementById("wb-undo");
    const redoBtn = document.getElementById("wb-redo");
    if (undoBtn) undoBtn.disabled = wbUndoStack.length === 0;
    if (redoBtn) redoBtn.disabled = wbRedoStack.length === 0;
    //: The status bar's pair is the same pair, one floor down (`renderUndoBar`
    //: reads `wbCanUndo`/`wbCanRedo` while a board is open), so it is repainted
    //: with these rather than left showing the app stack's state.
    //: Once a frame, not on the press (OPEN 813): the repaint reads layout, and
    //: run inline it made every add wait for a flush.
    if (typeof scheduleUndoBar === "function") scheduleUndoBar();
  }

  function wbDropUndoEntry(entry) {
    const at = wbUndoStack.lastIndexOf(entry);
    if (at !== -1) wbUndoStack.splice(at, 1);
    //: An eraser swipe folds its deletes into one batch (L-whiteboard-35), so a failed one is found inside it.
    else for (const top of wbUndoStack) if (top.action === "batch" && top.entries.includes(entry)) top.entries.splice(top.entries.indexOf(entry), 1);
    wbUpdateUndoRedoButtons();
  }

  //: A delete the server refused: the undo entry goes, the redo history the
  //: push wiped comes back, and the user is told (audit B8; it was a console line).
  function wbDeleteFailed(entry, redoBefore, e, retry) {
    wbDropUndoEntry(entry);
    if (!wbRedoStack.length) wbRedoStack = redoBefore;
    wbUpdateUndoRedoButtons();
    toast(voiceLine("failed", { what: "delete that" }), true, { action: ["Try again", retry] });
  }

  function wbPushUndo(entry) {
    wbHistoryFor();
    //: A lane marked Stack stacks its children after any change; the moves join this step (outside a gesture, which does it itself).
    if (wbRecordDepth === 0) entry = wbBoardState.lane?.settle(entry) || entry;
    wbUndoStack.push(entry);
    if (wbUndoStack.length > WB_UNDO_MAX) wbUndoStack.shift();
    // A fresh action makes whatever redo history existed unreachable, the
    // same rule the sketch pad's own `sketchSaveSnapshot` already follows.
    wbRedoStack = [];
    wbUpdateUndoRedoButtons();
    wbInstances.changed();
  }

  //: **Restored topics have new ids, so every history entry that names an old
  //: one is rewritten** (INBOX 445, second audit). A branch deleted and then
  //: brought back by Undo is made again by `POST`, which hands out fresh ids; an
  //: older entry ("undo the creation of topic 7", "put topic 7 back under 3")
  //: still said 7 and went to a row that no longer existed, so one more Ctrl+Z
  //: after a restore failed or did nothing. Called by `wbMapRestoreRows` with the
  //: ids it just minted, over both stacks, and over a link's two ends because a
  //: link sketch names its topics by id as well. Original ids cannot be reused
  //: instead: the create route assigns them.
  //: Cards and shapes too (INBOX 537): a link names a card or a shape by id as
  //: well, and a card brought back by Undo is a new row like any other.
  //: **Each id is translated once per Undo or Redo** (INBOX 898, found by the
  //: live check: Ctrl+Z, Ctrl+Shift+Z, Ctrl+Z on a Mermaid import left a shape
  //: behind). Items brought back are new rows, and the table hands out the ids it
  //: has free, which are often the very ids that were just deleted: topic 9 comes
  //: back as 8 and topic 8 as 9. Applied one item at a time, a step that named 9
  //: was changed to 8 and then, by the next item, to 9 again. Every field that
  //: has been translated is remembered here until the history step is over, and
  //: is not translated a second time.
  let wbRemapSeen = new WeakMap();

  function wbRemapUndoIds(objects, sketches = new Map(), nodes = new Map()) {
    if (!objects.size && !sketches.size && !nodes.size) return;
    //: A single translation outside a batch has nothing to collide with.
    if (!wbHistoryInFlight.length) wbRemapSeen = new WeakMap();
    const obj = (id) => (objects.has(id) ? objects.get(id) : id);
    const sketch = (id) => (sketches.has(id) ? sketches.get(id) : id);
    const node = (id) => (nodes.has(id) ? nodes.get(id) : id);
    const byKind = { object: obj, sketch, node };
    const once = (holder, key, map) => {
      let keys = wbRemapSeen.get(holder);
      if (!keys) wbRemapSeen.set(holder, (keys = new Set()));
      if (keys.has(key)) return;
      const was = holder[key];
      holder[key] = map(was);
      if (holder[key] !== was) keys.add(key);
    };
    //: A link names its two topics, cards or shapes inside its JSON.
    const linkEnds = (holder) => {
      const text = holder.data;
      if (typeof text !== "string" || !text.includes("link-")) return;
      try {
        const data = JSON.parse(text);
        if (!data || typeof data !== "object" || !String(data.type || "").startsWith("link-")) return;
        const ends = { sourceId: data.sourceKind, targetId: data.targetKind };
        const done = wbRemapSeen.get(holder) || new Set();
        let changed = false;
        for (const [field, kind] of Object.entries(ends)) {
          if (done.has(`data.${field}`)) continue;
          const mapped = byKind[kind || "node"]?.(data[field]) ?? data[field];
          if (mapped !== data[field]) {
            data[field] = mapped;
            done.add(`data.${field}`);
            changed = true;
          }
        }
        if (changed) {
          holder.data = JSON.stringify(data);
          wbRemapSeen.set(holder, done);
        }
      } catch {
        // Not JSON: nothing to translate.
      }
    };
    const walk = (entry) => {
      if (!entry) return;
      if (entry.action === "batch") {
        entry.entries.forEach(walk);
        return;
      }
      if (entry.kind === "object") {
        if (entry.id != null) once(entry, "id", obj);
        if (entry.parentId != null) once(entry, "parentId", obj);
        if (Array.isArray(entry.ids)) entry.ids.forEach((_, at) => once(entry.ids, at, obj));
        for (const row of entry.rows || []) {
          once(row, "id", obj);
          if (row.parent_id != null) once(row, "parent_id", obj);
        }
      }
      if (entry.kind === "sketch" && entry.id != null) once(entry, "id", sketch);
      if (entry.kind === "node" && entry.id != null) once(entry, "id", node);
      for (const key of ["payload", "before"]) {
        if (entry.kind === "sketch" && entry[key]) linkEnds(entry[key]);
      }
      for (const link of entry.links || []) {
        once(link, "id", sketch);
        linkEnds(link);
      }
    };
    wbUndoStack.forEach(walk);
    wbRedoStack.forEach(walk);
    for (const list of wbHistoryInFlight) list.forEach(walk);
  }

  //: The steps of a batch being replayed right now, and the reverses it has made
  //: so far (`wbApplyHistoryEntry`), so an id remap reaches them too.
  const wbHistoryInFlight = [];

  //: **One gesture, one Undo step, read off what it changed** (INBOX 537: "the
  //: undo and redo across the application needs to cover EVERYTHING"). A
  //: gesture in `WB_RECORDED` (the end of this file) snapshots every row and the
  //: map's settings, runs, and pushes the difference as one batch in place of
  //: whatever it pushed itself, so a write nobody recorded by hand (a fold, a
  //: tidy, a parent unfolded on the way, a theme) cannot be left out.
  let wbRecordDepth = 0;

  function wbBoardRows() {
    const rows = new Map();
    for (const kind of ["node", "sketch", "object"]) {
      const { list, payload } = WB_KIND_INFO[kind];
      for (const item of wbState?.[list] || []) {
        rows.set(`${kind}:${item.id}`, { kind, id: item.id, parent: item.parent_id ?? null, json: JSON.stringify(payload(item)) });
      }
    }
    return rows;
  }

  function wbBoardSettings() {
    const s = wbIsMap() ? window.wbMapState : null;
    return s ? JSON.stringify({ layout: s.layout ?? null, numbered: Boolean(s.numbered), theme: s.theme || {} }) : null;
  }

  const wbIsLinkRow = (row) => row.kind === "sketch" && /"type"\s*:\s*"link-/.test(JSON.parse(row.json).data || "");

  //: The steps that take the board from now back to `was`, in the order that
  //: works: lost rows back first (a map's topics as one branch, parents first),
  //: then topics back under their old parents (all lifted to the top first when
  //: several moved, so no step can make a ring `/move` refuses), then what the
  //: gesture made goes (links first, children before parents), then every
  //: changed row is written back whole.
  function wbHistoryFromRows(was, wasBoard) {
    const now = wbBoardRows();
    const lost = [], made = [], reparent = [], change = [];
    for (const [key, row] of was) {
      const cur = now.get(key);
      if (!cur) { lost.push(row); continue; }
      if (cur.json !== row.json) change.push({ action: "move", kind: row.kind, id: row.id, before: JSON.parse(row.json) });
      if (row.kind === "object" && cur.parent !== row.parent) reparent.push(row);
    }
    for (const [key, row] of now) if (!was.has(key)) made.push(row);
    const steps = [];
    const board = wbBoardSettings();
    if (board !== wasBoard && wasBoard) steps.push({ action: "board", before: wasBoard });
    const isTopic = (row) => row.kind === "object" && WB_MAP_KINDS.has(JSON.parse(row.json).kind) && wbIsMap();
    const topics = lost.filter(isTopic).map((row) => ({ ...JSON.parse(row.json), id: row.id, parent_id: row.parent }));
    const byId = new Map(topics.map((t) => [t.id, t]));
    const depth = (t, n = 0) => (n < 500 && byId.has(t.parent_id) ? depth(byId.get(t.parent_id), n + 1) + 1 : 0);
    topics.sort((a, b) => depth(a) - depth(b));
    if (topics.length) steps.push({ action: "subtree", kind: "object", rows: topics, links: [] });
    const restore = lost.filter((row) => !isTopic(row)).sort((a, b) => wbIsLinkRow(a) - wbIsLinkRow(b));
    for (const row of restore) steps.push({ action: "delete", kind: row.kind, payload: JSON.parse(row.json), oldId: row.id });
    if (reparent.length > 1) for (const row of reparent) steps.push({ action: "reparent", kind: "object", id: row.id, parentId: null });
    for (const row of reparent) steps.push({ action: "reparent", kind: "object", id: row.id, parentId: row.parent });
    const order = { sketch: 0, node: 1, object: 2 };
    const madeDepth = (row) => { let d = 0, p = row.parent; while (p != null && d < 500) { d += 1; p = now.get(`object:${p}`)?.parent ?? null; } return d; };
    made.sort((a, b) => wbIsLinkRow(b) - wbIsLinkRow(a) || order[a.kind] - order[b.kind] || madeDepth(b) - madeDepth(a));
    for (const row of made) steps.push({ action: "create", kind: row.kind, id: row.id });
    return [...steps, ...change];
  }

  async function wbRecordGesture(run, args = []) {
    if (wbRecordDepth > 0 || !wbState) return run(...args);
    wbHistoryFor();
    const boardId = window.currentBoardId;
    const rows = wbBoardRows();
    const board = wbBoardSettings();
    const had = new Set(wbUndoStack);
    wbRecordDepth += 1;
    try {
      const out = await run(...args);
      await wbBoardState.lane?.settleNow();
      return out;
    } finally {
      wbRecordDepth -= 1;
      if (window.currentBoardId === boardId) {
        //: A note's own steps cannot be read off the board's rows, so they stay.
        const notes = [];
        for (let i = wbUndoStack.length - 1; i >= 0; i -= 1) {
          if (had.has(wbUndoStack[i])) continue;
          const [inner] = wbUndoStack.splice(i, 1);
          if (/^note/.test(inner.action || "")) notes.unshift(inner);
        }
        const steps = [...wbHistoryFromRows(rows, board), ...notes];
        if (steps.length) wbPushUndo(steps.length === 1 ? steps[0] : { action: "batch", entries: steps });
        else wbUpdateUndoRedoButtons();
      }
    }
  }


  //: The stacks and the depth as a get/set surface: the stacks are swapped by board (`wbHistoryFor`), so a caller must read them at the moment of use and never keep the array.
  window.wbStacks = {
    get undo() { return wbUndoStack; },
    set undo(list) { wbUndoStack = list; },
    get redo() { return wbRedoStack; },
    set redo(list) { wbRedoStack = list; },
    get depth() { return wbRecordDepth; },
    set depth(n) { wbRecordDepth = n; },
    get remapSeen() { return wbRemapSeen; },
    set remapSeen(map) { wbRemapSeen = map; },
    //: Swapped with the stacks by each board instance.
    get historyBoard() { return wbHistoryBoard; },
    set historyBoard(key) { wbHistoryBoard = key; },
  };
  //: The file's surface: what other files call (L-whiteboard-52).
  Object.assign(window, { wbHistoryFor, wbUpdateUndoRedoButtons, wbDropUndoEntry, wbDeleteFailed, wbRemapUndoIds, wbHistoryInFlight, wbBoardRows, wbBoardSettings, wbRecordGesture, wbPushUndo });
})();
