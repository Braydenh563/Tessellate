(() => {
  // whiteboard-locks.js: lock and hide: the flags, the lock badges and the locked-press hint (decision 15).
  // Moved out of whiteboard.js whole (L286) and wrapped: only what other files call goes on `window`; nothing here runs at load.
  //: --- Lock (WHITEBOARD_PLAN decision 15) ------------------------------------
  //:
  //: Excalidraw's shape: a locked item lets the pointer through, so it cannot
  //: be selected, dragged, resized, erased or typed into, and a marquee, Select
  //: all, the Tab walk and a frame's drag all pass it by. Nothing about it needs
  //: guarding one gesture at a time, because no gesture can reach it. The way
  //: back is the board's own right-click menu ("Unlock 3 locked items"), or
  //: Ctrl+Shift+L with nothing selected. A card keeps the flag in a column; a
  //: sketch and an object in their data.


  function wbIsLocked(kind, item) {
    if (!item) return false;
    if (kind === "node") return Boolean(item.locked);
    const data = kind === "object" ? item.data : kind === "sketch" ? wbSketchData(item) : null;
    return Boolean(data && (data.locked || wbNamedLayerFlag(data.layer, "locked")));
  }

  function wbLockedItems() {
    const out = [];
    for (const kind of ["node", "object", "sketch"]) {
      for (const item of wbState[WB_LIST_BY_KIND[kind]] || []) if (wbIsLocked(kind, item)) out.push([kind, item]);
    }
    return out;
  }

  //: One undo step for the lot: each item's whole state before, which the
  //: "move" entry restores (its payload carries the flag).
  async function wbSetLocked(entries, on) {
    return wbSetItemFlag(entries, on, "locked", wbIsLocked);
  }

  //: Lock and hide share this: a card keeps the flag as a field, an object and a
  //: drawn shape in their data blob; every change is saved in one request (BD2).
  async function wbSetItemFlag(entries, on, flag, isOn) {
    const undo = [];
    const rows = [];
    for (const [kind, item] of entries) {
      if (isOn(kind, item) === on) continue;
      undo.push({ action: "move", kind, id: item.id, before: WB_KIND_INFO[kind].payload(item) });
      if (kind === "node") {
        item[flag] = on;
      } else if (kind === "object") {
        const data = { ...item.data };
        if (on) data[flag] = true;
        else delete data[flag];
        item.data = data;
      } else if (!wbSketchSetProps(item, { [flag]: on || undefined })) {
        undo.pop();
        continue;
      }
      rows.push({ kind, item });
    }
    await wbCommitMoves(rows, undo);
    return undo.length;
  }

  //: **A shape's own "keep proportions"** (draw.io, Figma): stored in the
  //: item's data blob, so a corner drag holds the ratio without Shift, and it
  //: travels with the shape through undo, copy and export. Cards size from
  //: their text and have no data blob, so only objects and drawn shapes take it.
  function wbKeepsRatio(kind, item) {
    if (!item) return false;
    const data = kind === "object" ? item.data : kind === "sketch" ? wbSketchData(item) : null;
    return Boolean(data && data.keep_ratio);
  }

  async function wbSetKeepRatio(kind, item, on) {
    if (kind === "object") {
      const data = { ...item.data };
      if (on) data.keep_ratio = true;
      else delete data.keep_ratio;
      item.data = data;
      await wbSaveObject(item);
    } else if (kind === "sketch") {
      await wbSaveSketchProps(item, { keep_ratio: on || undefined });
    }
  }

  async function wbLockSelection() {
    const keys = wbMultiSelection.size
      ? [...wbMultiSelection]
      : wbSelectedItem ? [wbMultiKey(wbSelectedItem.kind, wbSelectedItem.id)] : [];
    const entries = keys.map((key) => {
      const sep = key.indexOf(":");
      const kind = key.slice(0, sep), id = Number(key.slice(sep + 1));
      const item = (wbState[WB_LIST_BY_KIND[kind]] || []).find((i) => i.id === id);
      return item ? [kind, item] : null;
    }).filter(Boolean);
    if (!entries.length) return;
    const count = await wbSetLocked(entries, true);
    clearWbSelection();
    wbScheduleRender();
    if (count) toast(`Locked ${count === 1 ? "it" : `${count} items`}. Right-click the board to unlock.`);
  }

  async function wbUnlockAll() {
    const count = await wbSetLocked(wbLockedItems(), false);
    wbScheduleRender();
    toast(count ? `Unlocked ${nounCount(count, "item")}.` : "Nothing on this board is locked.");
  }

  //: The class that lets the pointer through, from state, after every render
  //: (an element rebuilt by the render has lost it). Only what changed is
  //: touched, the selection highlight's own rule.
  //: **Hidden from the board** (decision 27, the Layers tab's eye): the class
  //: `wb-hidden` (display: none) from state after every render, and on every
  //: link with an end on a hidden item, so no line points at nothing.
  function wbSketchHiddenOnBoard(sketch) {
    if (wbItemHidden("sketch", sketch)) return true;
    const data = wbSketchData(sketch);
    if (!data || !String(data.type || "").startsWith("link-")) return false;
    const end = (id, kind) => wbItemHidden(kind || "node", wbFindItem(kind || "node", id));
    return end(data.sourceId, data.sourceKind) || end(data.targetId, data.targetKind);
  }

  function wbHiddenOnBoard(kind, item) {
    return kind === "sketch" ? wbSketchHiddenOnBoard(item) : wbItemHidden(kind, item);
  }

  function wbSetHiddenKeys() {
    const keys = new Set();
    if (wbIsMap()) return keys;
    for (const kind of ["node", "object", "sketch"]) {
      for (const item of wbState[WB_LIST_BY_KIND[kind]] || []) if (wbHiddenOnBoard(kind, item)) keys.add(wbMultiKey(kind, item.id));
    }
    return keys;
  }

  function wbPaintHidden() {
    //: After every render: an open Layers, Pages or Outline tab is drawn again.
    wbSideRefreshSoon();
    const wanted = new Set();
    for (const key of wbSetHiddenKeys()) {
      const sep = key.indexOf(":");
      const el = document.querySelector(WB_SELECTOR_BY_KIND[key.slice(0, sep)](Number(key.slice(sep + 1))));
      if (el) wanted.add(el);
    }
    document.querySelectorAll("#whiteboard-container .wb-hidden").forEach((el) => {
      if (!wanted.has(el)) el.classList.remove("wb-hidden");
    });
    for (const el of wanted) if (!el.classList.contains("wb-hidden")) el.classList.add("wb-hidden");
  }

  //: Hide or show, one undo step for the lot (`wbSetLocked`'s shape).
  async function wbSetHidden(entries, on) {
    return wbSetItemFlag(entries, on, "hidden", wbItemHidden);
  }

  function wbPaintLocks() {
    const wanted = new Set();
    if (!wbIsMap()) {
      for (const [kind, item] of wbLockedItems()) {
        const el = document.querySelector(WB_SELECTOR_BY_KIND[kind](item.id));
        if (el) wanted.add(el);
      }
    }
    document.querySelectorAll("#whiteboard-container .wb-locked").forEach((el) => {
      if (!wanted.has(el)) {
        el.classList.remove("wb-locked");
        el.removeAttribute("aria-disabled");
      }
    });
    //: A locked item says so to a screen reader too (1031 BD5), not by the pin alone.
    for (const el of wanted) {
      el.classList.add("wb-locked");
      el.setAttribute("aria-disabled", "true");
    }
    wbPaintLockBadges();
  }

  //: A locked item carries its lock all the time (audit 1028 B20), not only
  //: under the pointer: one pin per locked, visible item at its top right, in
  //: one layer rebuilt with the render that may have moved or unlocked it.
  function wbPaintLockBadges() {
    const layer = document.getElementById("wb-html-layer");
    document.getElementById("wb-lock-marks")?.remove();
    if (!layer || wbIsMap()) return;
    const host = document.createElement("div");
    host.id = "wb-lock-marks";
    host.className = "wb-comment-marks";
    const z = String(wbStackOrder().length + 3);
    for (const [kind, item] of wbLockedItems()) {
      const box = wbItemHidden(kind, item) ? null : wbItemBBox(kind, item);
      if (!box) continue;
      const pin = document.createElement("div");
      pin.className = "wb-lock-pin";
      pin.setAttribute("aria-hidden", "true");
      pin.style.left = `${box.maxX}px`;
      pin.style.top = `${box.minY}px`;
      pin.style.zIndex = z;
      pin.innerHTML = '<span class="wb-lock-mark"><i class="ph ph-lock-simple"></i></span>';
      host.append(pin);
    }
    if (host.firstChild) layer.append(host);
  }

  //: --- A locked item answers the pointer (decision 28, INBOX 557a) ----------
  //:
  //: A locked item lets the pointer through (decision 15), so nothing on it
  //: changed under the pointer and a press did nothing visible: the owner, "I
  //: couldn't tell it was locked". A lock shows at its top right all the time
  //: (`wbPaintLockBadges`), and the first press on one in a session, found by a
  //: board-level hit test, says how to unlock it.


  //: The front-most locked item whose box holds the board point, or null.
  function wbLockedItemAt(x, y) {
    let best = null;
    for (const [kind, item] of wbLockedItems()) {
      if (wbItemHidden(kind, item)) continue;
      const box = wbItemBBox(kind, item);
      if (!box || x < box.minX || x > box.maxX || y < box.minY || y > box.maxY) continue;
      //: The front-most as painted: the board's one stack order.
      if (!best || wbStackCompare({ kind, item }, best) > 0) best = { kind, item, box };
    }
    return best;
  }

  function wbBoardPointOf(e) {
    return wbClientToBoard(e.clientX, e.clientY);
  }

  //: Only where nothing else answers: over the canvas itself, or over the
  //: locked item that the pointer passes through to it.
  function wbLockPressWanted(e) {
    if (wbIsMap() || window.currentTool !== "select" || e.buttons) return false;
    const target = e.target;
    if (!target?.closest) return false;
    return !target.closest("button, input, textarea, select, [contenteditable='true'], .wb-context, .wb-sidebar, .wb-format, .wb-comment-pin")
      && (wbIsBareCanvas(target) || Boolean(target.closest(".wb-locked")));
  }

  //: The first press on a locked item in a session says how to unlock it.
  function wbOnLockPress(e) {
    if (wbBoardState.lockHintSaid || e.button !== 0 || !wbLockPressWanted({ target: e.target, buttons: 0 })) return;
    const [x, y] = wbBoardPointOf(e);
    const hit = wbLockedItemAt(x, y);
    if (!hit) return;
    wbBoardState.lockHintSaid = true;
    toast("Locked. Right-click to unlock it.");
  }

  //: The file's surface: what other files call (L286).
  Object.assign(window, { wbIsLocked, wbLockedItems, wbSetLocked, wbKeepsRatio, wbSetKeepRatio, wbLockSelection, wbUnlockAll, wbSketchHiddenOnBoard, wbHiddenOnBoard, wbPaintHidden, wbSetHidden, wbPaintLocks, wbLockedItemAt, wbOnLockPress });
})();
