// whiteboard-map-marks.js: what a board item carries beside its words, out of
// whiteboard-map-more.js (the 800-line bar, L624): stamps, linked stickers, the
// affinity sort and a boundary round a lasso'd set.
//
// Loaded after whiteboard-map-more.js (`LAZY_MODULES.boards`); joins its
// `wbMapLazy` table, so callers keep one name.

(() => {
  // --- Stamps on board items ----------------------------------------------
  //
  //: The topic's reaction stamps (`WB_MAP_STAMPS`, `wbMapStampPatch`,
  //: whiteboard-map.js) on any other item the vote dots take: the same
  //: toggle per person, the same data (`stamps`, `stamped`), a row of chips
  //: under the item's bottom edge. A press on a chip is one Undo step.
  async function wbStampSet(entries, name, how) {
    const said = [];
    await wbRecordGesture(async () => {
      for (const e of entries) {
        const patch = wbMapStampPatch(e.item.data, name, how);
        if (!patch) continue;
        const data = { ...e.item.data };
        for (const key of ["stamps", "stamped"]) {
          if (patch[key]) data[key] = patch[key];
          else delete data[key];
        }
        e.item.data = data;
        said.push(patch.said);
      }
      if (said.length) await wbSaveMany(entries.map((e) => ({ kind: "object", item: e.item })));
    });
    wbScheduleRender();
    if (said.length) wbAnnounce(said[0]);
  }

  async function wbStampPress(id, name, how) {
    const item = (wbState.objects || []).find((o) => o.id === id);
    if (item && !wbIsLocked("object", item)) await wbStampSet([{ kind: "object", item }], name, how);
  }

  function wbStampPaint(el, d) {
    const held = WB_MAP_STAMPS.filter(([name]) => d.data?.stamps?.[name] > 0);
    let row = el.querySelector(":scope > .wb-stamps");
    if (!held.length) {
      row?.remove();
      return;
    }
    const mine = Array.isArray(d.data.stamped) ? d.data.stamped : [];
    const key = held.map(([name]) => `${name}${d.data.stamps[name]}${mine.includes(name) ? "m" : ""}`).join(",");
    if (!row) {
      row = document.createElement("div");
      row.className = "wb-stamps";
      //: A chip is a button on a draggable item: its presses stay its own.
      for (const type of ["pointerdown", "dblclick", "contextmenu"]) row.addEventListener(type, (event) => event.stopPropagation());
      el.appendChild(row);
    }
    if (row.dataset.key === key) return;
    row.dataset.key = key;
    row.replaceChildren(...held.map(([name, glyph, said]) => {
      const yours = mine.includes(name);
      const wrap = document.createElement("span");
      wrap.className = "wb-map-stamp-wrap";
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "wb-map-stamp";
      chip.dataset.stamp = name;
      chip.setAttribute("aria-pressed", String(yours));
      chip.title = `${said}: ${yours ? "press to take yours back" : "press to add yours"}`;
      chip.setAttribute("aria-label", `${said}, ${d.data.stamps[name]}${yours ? ", yours included" : ""}. ${yours ? "Press to take yours back." : "Press to add yours."}`);
      const icon = document.createElement("i");
      icon.className = `ph ph-${glyph}`;
      icon.setAttribute("aria-hidden", "true");
      chip.append(icon, String(d.data.stamps[name]));
      chip.addEventListener("click", () => wbStampPress(d.id, name, "toggle"));
      wrap.append(chip, kebabMenu([
        { label: "Remove one", title: "Takes one off the count", run: () => wbStampPress(d.id, name, "one") },
        { label: "Clear all", title: "Every count of this stamp; Ctrl+Z brings them back", danger: true, run: () => wbStampPress(d.id, name, "all") },
      ], `${said} stamp options`));
      return wrap;
    }));
  }

  //: "React with a stamp": a menu of the six, applied to the whole selection.
  function wbStampMenu() {
    const targets = wbVoteTargets();
    if (!targets.length) return toast("Select a note, text box, picture or frame to react to.");
    const box = (document.querySelector("#wb-html-layer .wb-object.wb-selected") || document.body).getBoundingClientRect();
    openMenuAtPoint(WB_MAP_STAMPS.map(([name, , said]) => makeMenuItem(said, `Add or take back your ${said.toLowerCase()} stamp`,
      () => wbStampSet(targets, name, "toggle"))), "Reaction stamps", box.left, box.bottom);
  }

  async function wbStampClear() {
    const held = (wbState.objects || []).filter((o) => !WB_MAP_KINDS.has(o.kind) && o.data?.stamps && !wbIsLocked("object", o));
    if (!held.length) return toast("No item on this board has a stamp.");
    await wbRecordGesture(async () => {
      for (const item of held) {
        const data = { ...item.data };
        delete data.stamps;
        delete data.stamped;
        item.data = data;
      }
      await wbSaveMany(held.map((item) => ({ kind: "object", item })));
    });
    wbScheduleRender();
    wbAnnounce(`Stamps cleared from ${nounCount(held.length, "item")}.`);
  }

  //: The chips in an SVG export: a small pill per stamp under the item (the
  //: live chip's glyph is a font, which an export lacks, so the words stand in).
  function wbStampSvg(obj) {
    let x = 0;
    return WB_MAP_STAMPS.filter(([name]) => obj.data?.stamps?.[name] > 0).map(([name, , said]) => {
      const text = `${said} ${obj.data.stamps[name]}`;
      const w = 12 + text.length * 6.5;
      const out = `<rect x="${x}" y="${obj.height + 4}" width="${w}" height="16" rx="8" fill="#eef1fb" stroke="#2f5bd3" />` +
        `<text x="${x + w / 2}" y="${obj.height + 12}" font-size="10" font-weight="600" text-anchor="middle" dominant-baseline="central" fill="#1d2433">${wbSvgEscape(text)}</text>`;
      x += w + 4;
      return out;
    }).join("");
  }


  // --- Linked stickers ------------------------------------------------------
  //
  //: MINDMAP_PLAN 14.4 (WHITEBOARD_PLAN decision 25 no longer holds for stickers):
  //: a placed icon follows by its `library_ref` (`icons/<name>`, which is also
  //: its `data.icon`) and an emoji by its glyph, since a duplicate drops the
  //: ref. An edit to the selected one is carried to every copy in one Undo step.
  function wbStickerKey(kind, item) {
    if (kind === "sketch") return wbSketchData(item)?.icon ? `icon:${wbSketchData(item).icon}` : null;
    if (kind === "object" && item?.kind === "text" && item.data?.sticker) return `emoji:${item.data.content}`;
    return null;
  }

  function wbStickerCopiesOf(key, state) {
    if (!key) return [];
    const out = [];
    for (const item of state.sketches || []) if (wbStickerKey("sketch", item) === key) out.push({ kind: "sketch", item });
    for (const item of state.objects || []) if (wbStickerKey("object", item) === key) out.push({ kind: "object", item });
    return out;
  }

  //: The selected sticker and every copy of it (itself included), or [].
  function wbStickerCopies() {
    if (wbMultiSelection.size > 1 || !wbSelectedItem) return [];
    const item = wbFindItem(wbSelectedItem.kind, wbSelectedItem.id);
    return wbStickerCopiesOf(wbStickerKey(wbSelectedItem.kind, item), wbState);
  }

  //: Make every copy look like the selected one: an icon's colour and opacity, an emoji's
  //: size and turn (kept about each copy's own centre).
  async function wbStickerMatch() {
    const copies = wbStickerCopies();
    const from = copies.find((e) => e.item.id === wbSelectedItem?.id && e.kind === wbSelectedItem?.kind);
    if (copies.length < 2 || !from) return toast("Select a placed icon or emoji that has copies first.");
    const others = copies.filter((e) => e !== from);
    await wbRecordGesture(async () => {
      for (const e of others) {
        if (e.kind === "sketch") {
          const data = wbSketchData(e.item) || {};
          const source = wbSketchData(from.item) || {};
          for (const key of ["fill", "color", "fillOpacity", "opacity"]) {
            if (source[key] === undefined) delete data[key];
            else data[key] = source[key];
          }
          e.item.data = JSON.stringify(data);
        } else {
          const cx = e.item.x + e.item.width / 2;
          const cy = e.item.y + e.item.height / 2;
          e.item.width = from.item.width;
          e.item.height = from.item.height;
          e.item.x = cx - from.item.width / 2;
          e.item.y = cy - from.item.height / 2;
          e.item.rotation = from.item.rotation ?? null;
        }
      }
      await wbSaveMany(others.map((e) => ({ kind: e.kind, item: e.item })));
    });
    wbScheduleRender();
    wbAnnounce(`${nounCount(others.length, "copy", "copies")} matched.`);
  }

  //: Swap a sticker for another everywhere it is placed. An emoji is a glyph; an
  //: icon is a path scaled to each copy, so the chosen icon's path is fitted into
  //: each copy's own box (centred, uniform) and keeps its colour and opacity.
  async function wbStickerSwap() {
    const copies = wbStickerCopies();
    if (!copies.length) return toast("Select a placed icon or emoji that has copies first.");
    const icons = copies[0].kind === "sketch";
    const choice = await pickIconOrEmoji({ anchor: document.querySelector('[aria-controls="wb-insert-menu"]'), title: icons ? "Swap this icon everywhere" : "Swap this emoji everywhere" });
    if (!choice || !choice.value) return;
    if ((choice.kind === "icon") !== icons) return toast(icons ? "Pick an icon to swap an icon." : "Pick an emoji to swap an emoji.");
    let fresh = null;
    if (icons) {
      const d = (await wbLoadIcons())[choice.value];
      const to = d && wbPathBBox(d);
      if (!to || !(to.maxX > to.minX) || !(to.maxY > to.minY)) return toast("That icon is not in the library's set.", "info");
      fresh = { d, to };
    }
    await wbRecordGesture(async () => {
      for (const e of copies) {
        if (!icons) {
          e.item.data = { ...e.item.data, content: choice.value };
          continue;
        }
        const data = wbSketchData(e.item) || {};
        const from = wbPathBBox(data.d || "");
        if (!from) continue;
        const k = Math.min((from.maxX - from.minX) / (fresh.to.maxX - fresh.to.minX), (from.maxY - from.minY) / (fresh.to.maxY - fresh.to.minY));
        const cx = (from.minX + from.maxX) / 2;
        const cy = (from.minY + from.maxY) / 2;
        const nx = (fresh.to.minX + fresh.to.maxX) / 2;
        const ny = (fresh.to.minY + fresh.to.maxY) / 2;
        data.d = wbTransformPathD(fresh.d, { sx: k, sy: k, anchorX: nx, anchorY: ny, dx: cx - nx, dy: cy - ny });
        data.icon = choice.value;
        if (data.library_ref) data.library_ref = `icons/${choice.value}`;
        e.item.data = JSON.stringify(data);
      }
      await wbSaveMany(copies.map((e) => ({ kind: e.kind, item: e.item })));
    });
    wbScheduleRender();
    wbAnnounce(`${nounCount(copies.length, "copy", "copies")} swapped.`);
  }


  // --- The affinity sort ----------------------------------------------------
  //
  //: MINDMAP_PLAN Phase G: the selected stickies, grouped by theme by
  //: `/affinity` (a model's groups, else the words they share), each sticky
  //: shown with the notes that back its place. The person ticks the groups to
  //: keep (and may rename them); each ticked one becomes a frame with its
  //: stickies laid out inside it, all in one `wbRecordGesture`, so one Undo
  //: takes the lot back. Frames go to the right of the selection, which stays
  //: where it was for the groups left unticked.
  const WB_AFFINITY_GAP = 16;
  const WB_AFFINITY_HEAD = 44;

  function wbAffinityStickies() {
    const out = [];
    for (const key of wbMultiSelection) {
      const [kind, id] = key.split(":");
      const item = kind === "object" ? wbFindItem("object", Number(id)) : null;
      if (item && item.kind === "text" && wbIsSticky(item) && String(item.data?.content || "").trim()) out.push(item);
    }
    return out;
  }

  function wbAffinityDialog(got) {
    return new Promise((resolve) => {
      const overlay = document.createElement("div");
      overlay.className = "modal-overlay confirm-overlay";
      overlay.setAttribute("role", "dialog");
      overlay.setAttribute("aria-modal", "true");
      overlay.setAttribute("aria-label", "Group these stickies by theme");
      const card = document.createElement("div");
      card.className = "card modal-card confirm-card wb-affinity-card";
      const about = document.createElement("p");
      about.className = "confirm-text";
      about.textContent = got.source === "model"
        ? `${nounCount(got.count, "sticky", "stickies")} in ${nounCount(got.groups.length, "theme")}. Tick the ones to make into frames.`
        : `${nounCount(got.count, "sticky", "stickies")} grouped by the words they share${got.reason === "offline" ? " (no model is running)" : ""}. Tick the ones to make into frames.`;
      const list = document.createElement("div");
      list.className = "wb-affinity-list";
      const picks = got.groups.map((group) => {
        const box = document.createElement("section");
        box.className = "wb-affinity-group";
        const head = document.createElement("label");
        head.className = "setting-check wb-affinity-head";
        const tick = document.createElement("input");
        tick.type = "checkbox";
        tick.checked = group.name !== "Other";
        const name = document.createElement("input");
        name.type = "text";
        name.value = group.name;
        name.maxLength = 120;
        name.setAttribute("aria-label", `Frame name for ${group.name}`);
        const count = document.createElement("span");
        count.className = "wb-affinity-count";
        count.textContent = nounCount(group.items.length, "sticky", "stickies");
        head.append(tick, name, count);
        const items = document.createElement("ul");
        items.className = "wb-affinity-items";
        for (const item of group.items) {
          const li = document.createElement("li");
          const text = document.createElement("span");
          text.textContent = item.text;
          const backed = document.createElement("span");
          backed.className = "wb-affinity-backed";
          backed.textContent = item.notes.length ? `Backed by ${item.notes.map((n) => `"${n.title}"`).join(", ")}` : "No note backs this";
          li.append(text, backed);
          items.append(li);
        }
        box.append(head, items);
        list.append(box);
        return { group, tick, name };
      });
      const close = (chosen) => {
        document.removeEventListener("keydown", onKey, true);
        overlay.remove();
        resolve(chosen);
      };
      const onKey = (event) => {
        if (event.key === "Escape") {
          event.preventDefault();
          event.stopPropagation();
          close(null);
        }
      };
      const go = smallButton("Make frames", "Make a frame for each ticked theme", () => {
        const chosen = picks.filter((p) => p.tick.checked).map((p) => ({ name: p.name.value.trim() || p.group.name, items: p.group.items }));
        close(chosen.length ? chosen : null);
      }, false);
      const row = document.createElement("div");
      row.className = "row confirm-actions";
      row.append(smallButton("Cancel", "Cancel", () => close(null)), go);
      card.append(dialogHead("Group by theme", () => close(null)), about, list, row);
      overlay.append(card);
      wireBackdropClose(overlay, () => close(null));
      document.addEventListener("keydown", onKey, true);
      document.body.append(overlay);
      go.focus();
    });
  }

  async function wbAffinityRun() {
    const boardId = window.currentBoardId;
    const stickies = wbAffinityStickies();
    if (!boardId || stickies.length < 2) return toast("Select two or more stickies with words on them first.");
    wbAnnounce("Grouping the stickies by theme.");
    let got = null;
    try {
      got = await apiJson(`/whiteboard/boards/${boardId}/affinity`, { method: "POST", body: JSON.stringify({ ids: stickies.map((s) => s.id).slice(0, 60) }) });
    } catch (err) {
      return toast(err.message || "These stickies could not be grouped.", true);
    }
    const chosen = await wbAffinityDialog(got);
    if (!chosen || window.currentBoardId !== boardId) return;
    const byId = new Map(stickies.map((s) => [s.id, s]));
    const box = stickies.reduce((b, s) => ({ x: Math.max(b.x, s.x + s.width), y: Math.min(b.y, s.y) }), { x: -Infinity, y: Infinity });
    let left = box.x + 80;
    let made = 0;
    await wbRecordGesture(async () => {
      for (const group of chosen) {
        const members = group.items.map((i) => byId.get(i.id)).filter(Boolean);
        const cell = { w: Math.max(...members.map((m) => m.width)), h: Math.max(...members.map((m) => m.height)) };
        const cols = Math.min(4, Math.ceil(Math.sqrt(members.length)));
        const rows = Math.ceil(members.length / cols);
        const width = cols * (cell.w + WB_AFFINITY_GAP) + WB_AFFINITY_GAP;
        const height = WB_AFFINITY_HEAD + rows * (cell.h + WB_AFFINITY_GAP) + WB_AFFINITY_GAP;
        const frame = await wbCreateObject("frame", { content: group.name.slice(0, 120) }, Math.round(left), Math.round(box.y), width, height);
        if (!frame) continue;
        members.forEach((m, i) => {
          m.x = left + WB_AFFINITY_GAP + (i % cols) * (cell.w + WB_AFFINITY_GAP);
          m.y = box.y + WB_AFFINITY_HEAD + WB_AFFINITY_GAP + Math.floor(i / cols) * (cell.h + WB_AFFINITY_GAP);
        });
        await wbSaveMany(members.map((item) => ({ kind: "object", item })));
        left += width + 40;
        made += 1;
      }
    });
    wbScheduleRender();
    wbAnnounce(`${nounCount(made, "frame")} made. Ctrl+Z takes them back.`);
  }


  // --- A boundary round a lasso'd set ---------------------------------------
  //
  //: MINDMAP_PLAN 12.2 item 1 (decision 19 extended): `boundary_set` on the
  //: first selected topic lists the ids; the shape is the union of those that
  //: are showing, so it follows them as they move or fold, and a deleted
  //: member just drops out. The same `boundary`, label, styles and removal.
  function wbBoundarySetBox(index, hidden, ids) {
    let box = null;
    for (const id of ids) {
      const node = index.byId.get(id);
      if (!node || hidden.has(id)) continue;
      const size = wbMapNodeSize(node);
      const r = { minX: node.x, minY: node.y, maxX: node.x + size.w, maxY: node.y + size.h };
      box = box
        ? { minX: Math.min(box.minX, r.minX), minY: Math.min(box.minY, r.minY), maxX: Math.max(box.maxX, r.maxX), maxY: Math.max(box.maxY, r.maxY) }
        : r;
    }
    return box;
  }

  //: The selected topics, lowest id first (the lead keeps the boundary).
  function wbBoundaryTargets() {
    if (!wbIsMap()) return [];
    const out = [];
    for (const key of wbMultiSelection) {
      const [kind, id] = key.split(":");
      const item = kind === "object" ? wbFindItem("object", Number(id)) : null;
      if (item && item.kind === "topic") out.push(item);
    }
    return out.sort((a, b) => a.id - b.id);
  }

  async function wbBoundaryDraw() {
    const topics = wbBoundaryTargets();
    if (topics.length < 2) return toast("Select two or more topics first.");
    await wbMapSetStructure(topics[0], { boundary: "rounded", boundary_set: topics.map((t) => t.id) },
      `Boundary drawn round ${nounCount(topics.length, "topic")}.`);
  }

  //: The file's whole surface, one object, so the shared scope gains one name rather than one per entry point.

  Object.assign(window.wbMapLazy, {
    boundaryTargets: wbBoundaryTargets,
    boundaryDraw: wbBoundaryDraw,
    stickerCopies: wbStickerCopies,
    stickerMatch: wbStickerMatch,
    stickerSwap: wbStickerSwap,
    affinitySort: wbAffinityRun,
    affinityTargets: wbAffinityStickies,
    paintStamps: wbStampPaint,
    stampMenu: wbStampMenu,
    clearStamps: wbStampClear,
    svgStamps: wbStampSvg,
    setBox: wbBoundarySetBox,
  });
})();
