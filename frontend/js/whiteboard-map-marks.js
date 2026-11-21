(() => {
  // whiteboard-map-marks.js: map markers, dim and filter views, build-from-document and branch summaries.
  // Moved out of whiteboard-map.js whole (L286) and wrapped: only what other files call goes on `window`; nothing here runs at load.
  //: The Due and Start rows (decision 37; the Gantt view): the date-field
  //: recipe's picker (`enhanceDateField`) and Clear; Due also has a time field
  //: (L371, `due_time`, kept only with a day) and Remind me. Each field stops
  //: at the other's day (`min` and `max`), so the pair cannot be set backwards.
  function wbMapDateRow(node, parts, set, label, key) {
    const wrap = document.createElement("div");
    wrap.className = "wb-map-markers-row";
    const name = document.createElement("span");
    name.className = "wb-map-markers-label";
    name.textContent = label;
    const field = document.createElement("input");
    field.type = "date";
    field.value = parts[key] || "";
    if (key === "start" && parts.due) field.max = parts.due;
    if (key === "due" && parts.start) field.min = parts.start;
    field.setAttribute("aria-label", `${label} date`);
    field.addEventListener("change", () => set(key === "due" && !field.value ? { due: null, due_time: null } : { [key]: field.value || null }));
    wrap.append(name, field);
    enhanceDateField(field);
    if (!parts[key]) return wrap;
    if (key === "due") {
      const time = document.createElement("input");
      time.type = "time";
      time.value = parts.dueTime || "";
      time.setAttribute("aria-label", "Due time");
      time.addEventListener("change", () => set({ due_time: time.value || null }));
      wrap.append(time);
      enhanceDateField(time);
    }
    const clear = document.createElement("button");
    clear.type = "button";
    clear.className = "ghost small";
    clear.textContent = "Clear";
    clear.setAttribute("aria-label", `Clear ${label.toLowerCase()} date`);
    clear.addEventListener("click", () => set(key === "due" ? { due: null, due_time: null } : { [key]: null }));
    wrap.append(clear);
    if (key !== "due") return wrap;
    //: Remind me makes an ordinary reminder at the due time, or 9:00 with none.
    const remind = document.createElement("button");
    remind.type = "button";
    remind.className = "ghost small";
    remind.textContent = "Remind me";
    remind.title = "A reminder at the due time (9:00 with none), in Reminders";
    remind.addEventListener("click", async () => {
      const [y, m, d] = parts.due.split("-").map(Number);
      const [h, min] = (parts.dueTime || "09:00").split(":").map(Number);
      const at = new Date(y, m - 1, d, h, min, 0);
      if (at < new Date()) {
        toast("That time has gone: pick a later due date for a reminder.", "info");
        return;
      }
      try {
        const made = await apiJson("/reminders", { method: "POST", body: JSON.stringify({ text: wbMapLabel(node) || "Map topic", due_at: at.toISOString() }) });
        reminderMadeUndo(made);
        toast(`Reminder set for ${wbMapDueWords(parts.due, null, parts.dueTime).words}${parts.dueTime ? "" : ", 9:00"}.`);
      } catch (error) {
        toast(error.message || voiceLine("failed", { what: "set that reminder" }), true);
      }
    });
    wrap.append(remind);
    return wrap;
  }

  const wbMarkerUi = { pop: null, filters: new Set(), choose: null };

  function wbMapCloseMarkers({ restoreFocus = false } = {}) {
    const state = wbMarkerUi.pop;
    if (!state) return;
    wbMarkerUi.pop = null;
    document.removeEventListener("pointerdown", state.outside, true);
    state.panel.remove();
    if (restoreFocus) document.getElementById("whiteboard-container")?.focus({ preventScroll: true });
  }

  //: A row of previews, one pressed at a time (INBOX 665): each choice drawn
  //: as the mark it puts on the topic (`wbMapMarkerGlyph`), the topic bar's
  //: `.wb-map-picks` recipe. It was a `.seg` of six words ("None 1 2 3 4 5",
  //: "None 0% 25% 50% 75% Done"), the pill well the owner asked to be rid of.
  function wbMapMarkerSeg(label, options, current, choose) {
    const wrap = document.createElement("div");
    wrap.className = "wb-map-markers-row";
    const name = document.createElement("span");
    name.className = "wb-map-markers-label";
    name.textContent = label;
    const row = document.createElement("div");
    row.className = "wb-map-picks";
    row.setAttribute("role", "group");
    row.setAttribute("aria-label", label);
    for (const [value, text, title] of options) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "ghost small icon-only wb-map-pick";
      b.append(wbMapMarkerGlyph(label, value));
      const words = title ? `${text}, ${title.toLowerCase()}` : text;
      b.setAttribute("aria-label", `${label} ${words}`);
      b.title = words;
      const on = value === current;
      b.classList.toggle("active", on);
      b.setAttribute("aria-pressed", String(on));
      b.addEventListener("click", () => choose(value));
      row.appendChild(b);
    }
    wrap.append(name, row);
    return wrap;
  }

  //: A marker that is only on or off is one pressed-state button, not two
  //: previews (ledger 1546): it shows the mark it puts on the topic, and a press
  //: flips it. Same row, label and button class as `wbMapMarkerSeg`'s picks.
  function wbMapMarkerToggle(label, on, choose) {
    const wrap = document.createElement("div");
    wrap.className = "wb-map-markers-row";
    const name = document.createElement("span");
    name.className = "wb-map-markers-label";
    name.textContent = label;
    const row = document.createElement("div");
    row.className = "wb-map-picks";
    row.setAttribute("role", "group");
    row.setAttribute("aria-label", label);
    const b = document.createElement("button");
    b.type = "button";
    b.className = "ghost small icon-only wb-map-pick";
    b.append(wbMapMarkerGlyph(label, true));
    b.setAttribute("aria-label", `${label} ${on ? "on" : "off"}`);
    b.title = on ? `${label} on, press to clear` : `Mark with a ${label.toLowerCase()}`;
    b.classList.toggle("active", on);
    b.setAttribute("aria-pressed", String(on));
    b.addEventListener("click", () => choose(!on));
    row.appendChild(b);
    wrap.append(name, row);
    return wrap;
  }

  //: The mark a choice puts on the topic, drawn by the one painter
  //: (`wbMapPaintMarkers`, decision 34) into a scratch row, so the button shows
  //: exactly what pressing it does and no second copy of the marks exists.
  function wbMapMarkerGlyph(label, value) {
    if (value === null || value === false) {
      const none = document.createElement("i");
      none.className = "ph ph-prohibit";
      none.setAttribute("aria-hidden", "true");
      return none;
    }
    const host = document.createElement("span");
    host.className = "wb-map-markers wb-map-pick-mark";
    wbMapPaintMarkers(host, { [label.toLowerCase()]: value });
    host.removeAttribute("role");
    host.removeAttribute("aria-label");
    host.removeAttribute("title");
    host.setAttribute("aria-hidden", "true");
    return host;
  }

  function wbMapOpenMarkers(id, anchor = null) {
    const node = (wbState.objects || []).find((o) => o.id === id);
    if (!node) return;
    if (wbMarkerUi.pop?.id === id) {
      wbMapCloseMarkers();
      return;
    }
    wbMapCloseMarkers();
    const target = anchor?.isConnected ? anchor : document.querySelector(`.wb-object[data-id="${id}"]`);
    if (!target) return;
    const panel = document.createElement("div");
    panel.className = "help-popover wb-map-markers-pop";
    panel.id = "wb-map-markers";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", `Markers on ${wbMapLabel(node) || "this topic"}`);
    const set = async (patch) => {
      const live = (wbState.objects || []).find((o) => o.id === id);
      if (!live) return;
      await wbMapSetNodeStyle(live, patch);
      fill();
      wbMapPaintMarkerFilter();
      wbAnnounce(wbMapMarkerWords(wbMapMarkerParts(live.data)) || "No markers.");
    };
    const fill = () => {
      const live = (wbState.objects || []).find((o) => o.id === id) || node;
      const parts = wbMapMarkerParts(live.data);
      const focusedLabel = panel.contains(document.activeElement) ? document.activeElement.getAttribute("aria-label") || document.activeElement.textContent : null;
      const icons = document.createElement("div");
      icons.className = "wb-map-marker-icons";
      icons.setAttribute("role", "group");
      icons.setAttribute("aria-label", "Icons");
      for (const [icon, label] of WB_MAP_MARKER_ICONS) {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "ghost icon-only small";
        const on = parts.icons.includes(icon);
        b.setAttribute("aria-pressed", String(on));
        b.setAttribute("aria-label", label);
        b.title = label;
        const i = document.createElement("i");
        i.className = `ph ph-${icon}`;
        i.setAttribute("aria-hidden", "true");
        b.appendChild(i);
        b.addEventListener("click", () => {
          if (!on && parts.icons.length >= WB_MAP_MARKERS_MAX) {
            toast(`A topic takes ${WB_MAP_MARKERS_MAX} icons at most.`);
            return;
          }
          const next = on ? parts.icons.filter((x) => x !== icon) : [...parts.icons, icon];
          set({ markers: next.length ? next : null });
        });
        icons.appendChild(b);
      }
      const iconRow = document.createElement("div");
      iconRow.className = "wb-map-markers-row";
      const iconLabel = document.createElement("span");
      iconLabel.className = "wb-map-markers-label";
      iconLabel.textContent = "Icons";
      iconRow.append(iconLabel, icons);
      const hint = document.createElement("p");
      hint.className = "muted wb-map-markers-hint";
      hint.textContent = "View, Filter by marker shows the topics that carry one. Esc closes.";
      panel.replaceChildren(
        wbMapMarkerSeg("Priority", [[null, "None"], [1, "1", "Highest"], [2, "2"], [3, "3"], [4, "4"], [5, "5", "Lowest"]],
          parts.priority, (value) => set({ priority: value })),
        wbMapMarkerSeg("Progress", [[null, "None"], [0, "0%"], [25, "25%"], [50, "50%"], [75, "75%"], [100, "Done"]],
          parts.progress, (value) => set({ progress: value })),
        wbMapMarkerToggle("Flag", Boolean(parts.flag), (value) => set({ flag: value || null })),
        wbMapDateRow(live, parts, set, "Start", "start"),
        wbMapDateRow(live, parts, set, "Due", "due"),
        iconRow,
        hint,
      );
      //: The press that rebuilt the panel keeps its place.
      const again = focusedLabel
        ? [...panel.querySelectorAll("button")].find((b) => (b.getAttribute("aria-label") || b.textContent) === focusedLabel)
        : null;
      (again || panel.querySelector("button[aria-pressed='true']") || panel.querySelector("button"))?.focus({ preventScroll: true });
    };
    panel.addEventListener("keydown", (event) => {
      event.stopPropagation();
      if (event.key === "Escape") {
        event.preventDefault();
        wbMapCloseMarkers({ restoreFocus: true });
      }
    });
    const outside = (event) => {
      //: The Due field's calendar is a popover of its own, drawn in the page.
      if (panel.contains(event.target) || target.contains(event.target) || event.target.closest?.(".timeline-monthpop")) return;
      wbMapCloseMarkers();
    };
    document.addEventListener("pointerdown", outside, true);
    document.body.appendChild(panel);
    wbMarkerUi.pop = { id, panel, outside };
    fill();
    placeHelpPopover(panel, target);
  }

  //: --- Filter by marker ---------------------------------------------------
  //: Several at once (decision 34): a topic stays lit when it carries any of
  //: the chosen markers or labels (a label is the topic's tag); every other
  //: topic is dimmed, never hidden, so the tree stays readable around what is
  //: lit. For this visit only.
  // WB-MAP-FILTER-BEGIN
  function wbMapMarkerKeys(data) {
    const parts = wbMapMarkerParts(data);
    const keys = [];
    if (parts.priority) keys.push(`p${parts.priority}`);
    if (parts.progress != null) keys.push(parts.progress === 100 ? "done" : "going");
    if (parts.flag) keys.push("flag");
    if (parts.due) keys.push("due");
    for (const icon of parts.icons) keys.push(`i:${icon}`);
    for (const label of Array.isArray(data?.labels) ? data.labels : []) {
      if (typeof label === "string" && label.trim()) keys.push(`t:${label.trim()}`);
    }
    return keys;
  }

  function wbMapMarkerKeyWords(key) {
    if (key.startsWith("t:")) return [key.slice(2), "ph:tag"];
    if (key.startsWith("p")) return [`Priority ${key.slice(1)}`, "ph:number-circle-one"];
    if (key === "done") return ["Done", "ph:check-circle"];
    if (key === "going") return ["Under way", "ph:circle-half"];
    if (key === "flag") return ["Flagged", "ph:flag"];
    if (key === "due") return ["With a due date", "ph:calendar-dots"];
    const icon = key.slice(2);
    return [WB_MAP_MARKER_ICON_NAMES.get(icon) || icon, `ph:${icon}`];
  }

  wbMarkerUi.match = {
    //: Lit when nothing is chosen, or the topic carries any chosen key.
    lit: (keys, filters) => !filters.size || keys.some((key) => filters.has(key)),
    //: The bar's words: the first three by name, then how many more.
    words(filters) {
      const names = [...filters].map((key) => wbMapMarkerKeyWords(key)[0]);
      return names.length > 3 ? `${names.slice(0, 3).join(", ")} and ${names.length - 3} more` : names.join(", ");
    },
    //: An outline row's marker and label cells (outline columns).
    cells(row, node = row._node) {
      const data = node.data || {};
      const [marks, tags] = row.lastChild.children;
      wbMapPaintMarkers(marks, data);
      const labels = Array.isArray(data.labels) ? data.labels.filter((l) => typeof l === "string" && l.trim()) : [];
      const key = labels.join("\u0000");
      if (tags.dataset.key !== key) {
        tags.dataset.key = key;
        tags.replaceChildren(...labels.map((label) => {
          const chip = document.createElement("span");
          chip.className = "wb-map-tag";
          chip.textContent = label;
          return chip;
        }));
        tags.title = labels.length ? "Labels" : "";
      }
      row.lastChild.hidden = marks.hidden && !labels.length;
    },
  };
  // WB-MAP-FILTER-END

  function wbMapMarkersInUse() {
    const used = new Map();
    for (const node of wbMapIndex().nodes) {
      for (const key of wbMapMarkerKeys(node.data)) used.set(key, (used.get(key) || 0) + 1);
    }
    const rank = (k) => (k.startsWith("t:") ? 4 : k.startsWith("p") ? 0 : k === "flag" ? 1 : k === "going" || k === "done" ? 2 : 3);
    return [...used].sort((a, b) => rank(a[0]) - rank(b[0]) || a[0].localeCompare(b[0]));
  }

  //: A popover of pressed-or-not choices (the Markers popover's recipe), one
  //: press adds or takes away one filter and the map follows at once.
  function wbMapChooseMarkerFilter(anchor = null) {
    if (wbMarkerUi.choose) {
      wbMarkerUi.choose.close();
      return;
    }
    const used = wbMapMarkersInUse();
    if (!used.length) {
      toast("No topic on this map has a marker or a label yet. A topic's menu, Content, Markers adds one.");
      return;
    }
    const target = anchor || document.querySelector('[aria-controls="wb-view-menu"]') || document.getElementById("whiteboard-container");
    const panel = document.createElement("div");
    panel.className = "help-popover wb-map-markers-pop wb-map-filter-pop";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", "Filter by marker");
    const fill = () => {
      const chips = used.map(([key, count]) => {
        const [words, icon] = wbMapMarkerKeyWords(key);
        const b = document.createElement("button");
        b.type = "button";
        b.className = "ghost small";
        b.setAttribute("aria-pressed", String(wbMarkerUi.filters.has(key)));
        b.title = `Light the topics marked ${words.toLowerCase()}`;
        setLabel(b, `${icon} ${words} (${count})`);
        b.addEventListener("click", () => {
          if (!wbMarkerUi.filters.delete(key)) wbMarkerUi.filters.add(key);
          wbMapSetMarkerFilter(undefined);
          const again = [...panel.querySelectorAll("button")].indexOf(b);
          fill();
          panel.querySelectorAll("button")[again]?.focus({ preventScroll: true });
        });
        return b;
      });
      const group = document.createElement("div");
      group.className = "wb-map-filter-choices";
      group.setAttribute("role", "group");
      group.setAttribute("aria-label", "Markers and labels in use");
      group.append(...chips);
      const hint = document.createElement("p");
      hint.className = "muted wb-map-markers-hint";
      hint.textContent = "A topic stays lit if it has any you press. Esc closes.";
      const clear = document.createElement("button");
      clear.type = "button";
      clear.className = "ghost small";
      clear.textContent = "Show every topic";
      clear.disabled = !wbMarkerUi.filters.size;
      clear.addEventListener("click", () => {
        wbMapSetMarkerFilter(null);
        fill();
      });
      panel.replaceChildren(group, hint, clear);
    };
    panel.addEventListener("keydown", (event) => {
      event.stopPropagation();
      if (event.key === "Escape") {
        event.preventDefault();
        close();
      }
    });
    const close = () => {
      wbMarkerUi.choose = null;
      document.removeEventListener("pointerdown", outside, true);
      panel.remove();
    };
    const outside = (event) => {
      if (!panel.contains(event.target) && !target.contains?.(event.target)) close();
    };
    document.addEventListener("pointerdown", outside, true);
    document.body.appendChild(panel);
    wbMarkerUi.choose = { close };
    fill();
    placeHelpPopover(panel, target);
    panel.querySelector("button")?.focus({ preventScroll: true });
  }

  //: `null` ends the filter; `undefined` repaints for the set as it now stands.
  function wbMapSetMarkerFilter(key) {
    if (key === null) wbMarkerUi.filters.clear();
    wbMapPaintMarkerFilter();
    const bar = document.getElementById("wb-map-filter");
    const on = wbMarkerUi.filters.size > 0;
    wbAnnounce(on ? `Showing the topics marked ${wbMarkerUi.match.words(wbMarkerUi.filters).toLowerCase()}.` : "Showing every topic.");
    if (bar && !on) document.getElementById("whiteboard-container")?.focus({ preventScroll: true });
  }

  //: After every render (`wbMapAfterRender`): a class on each topic the filter
  //: leaves out, and the bar that says a filter is on.
  //: **Dim all but the selected branch** (MindNode's focus mode, the XMind and
  //: MindNode audit's item 3): the View menu's switch. The selected topic, all
  //: under it and the path up to its trunk stay lit; with nothing selected
  //: nothing is dimmed. The marker filter, when both are on, wins: it was
  //: asked for by name. Per viewer and per visit, not saved with the map.
  const wbMapDim = { on: false };

  function wbMapSetDim(on) {
    wbMapDim.on = Boolean(on);
    const box = document.getElementById("wb-map-dim");
    if (box) box.checked = wbMapDim.on;
    wbMapPaintMarkerFilter();
    wbAnnounce(wbMapDim.on ? "Dimming all but the selected branch." : "Every branch lit again.");
  }

  //: The ids lit by the dimming, or null when it dims nothing.
  function wbMapDimLit(index) {
    if (!wbMapDim.on || wbMultiSelection.size > 1) return null;
    const node = typeof wbSelectedMapNode === "function" ? wbSelectedMapNode() : null;
    if (!node || !index.byId.has(node.id)) return null;
    const lit = new Set(wbMapSubtree(index, node.id).map((o) => o.id));
    for (let up = index.byId.get(node.parent_id); up && !lit.has(up.id); up = index.byId.get(up.parent_id)) lit.add(up.id);
    return lit;
  }

  function wbMapPaintMarkerFilter() {
    const bar = document.getElementById("wb-map-filter");
    const on = wbMarkerUi.filters.size > 0 && wbIsMap();
    if (bar) {
      bar.hidden = !on;
      if (on) {
        const label = document.getElementById("wb-map-filter-label");
        if (label) label.textContent = `Marked: ${wbMarkerUi.match.words(wbMarkerUi.filters)}`;
      }
    }
    const container = document.getElementById("whiteboard-container");
    if (!container) return;
    const index = wbIsMap() ? wbMapIndex() : null;
    const lit = on ? null : index && wbMapDimLit(index);
    container.classList.toggle("wb-map-filtering", on || Boolean(lit));
    if (!on && !lit) {
      for (const el of container.querySelectorAll(".wb-map-filtered-out")) el.classList.remove("wb-map-filtered-out");
      return;
    }
    const out = (node) => (on ? !wbMarkerUi.match.lit(wbMapMarkerKeys(node.data), wbMarkerUi.filters) : !lit.has(node.id));
    for (const node of index.nodes) {
      const el = container.querySelector(`.wb-object[data-id="${node.id}"]`);
      if (el) el.classList.toggle("wb-map-filtered-out", out(node));
    }
    //: A line goes with the topic it leads into, so a lit branch is not tied
    //: to the rest by full-strength lines.
    for (const el of container.querySelectorAll(".wb-map-edge[data-child], .wb-map-edge-label[data-child]")) {
      const node = index.byId.get(Number(el.dataset.child));
      el.classList.toggle("wb-map-filtered-out", Boolean(node && out(node)));
    }
  }

  //: What follows every render of a map: the outline and the marker filter.
  function wbMapAfterRender() {
    wbOutlineSync();
    if (wbMarkerUi.filters.size || wbMapDim.on || document.getElementById("whiteboard-container")?.classList.contains("wb-map-filtering")) {
      wbMapPaintMarkerFilter();
    }
  }

  onSurface("board", () => {
    document.getElementById("wb-map-filter-clear")?.addEventListener("click", () => wbMapSetMarkerFilter(null));
    document.getElementById("wb-map-filter-item")?.addEventListener("click", () => wbMapChooseMarkerFilter());
    document.getElementById("wb-map-gantt-item")?.addEventListener("click", () => wbMapLazy.openGantt());
  });

  // --- A document's headings as a map (the audit's M5, second half) ---------
  //
  //: **"Map this document's headings"** (decision 35), the other direction of
  //: decision 31's Write as a document. One-shot, as that one is: a new map,
  //: not a twin kept in step.
  // WB-MAP-HEADINGS-BEGIN
  //: The headings as the indented list the Markdown import reads. Pure (no
  //: DOM), so node runs it (`tests/test_map_from_headings.py`). Headings inside
  //: a fenced code block are code, not headings. A document whose top level has
  //: one heading, first, makes that heading the central topic; otherwise the
  //: title is the centre and every top-level heading a branch. A skipped level
  //: (a `####` under a `##`) hangs one level down, never two, so no topic is
  //: drawn under a parent that is not there.
  function wbMapHeadingsOutline(text, title) {
    const heads = [];
    let fence = null;
    for (const line of String(text || "").split("\n")) {
      const opener = /^ {0,3}(`{3,}|~{3,})/.exec(line);
      if (opener) {
        if (!fence) fence = opener[1][0];
        else if (opener[1][0] === fence) fence = null;
        continue;
      }
      if (fence) continue;
      const m = /^ {0,3}(#{1,6})[ \t]+(.+)$/.exec(line);
      if (!m) continue;
      const words = m[2].replace(/[ \t]+#+[ \t]*$/, "").trim();
      if (words) heads.push({ level: m[1].length, words });
    }
    if (!heads.length) return null;
    const top = Math.min(...heads.map((h) => h.level));
    const single = heads[0].level === top && heads.filter((h) => h.level === top).length === 1;
    const lines = [];
    let prev = 0;
    if (!single) lines.push(`- ${String(title || "").trim() || "Untitled document"}`);
    heads.forEach((h, i) => {
      const raw = h.level - top + (single ? 0 : 1);
      const depth = single && i === 0 ? 0 : Math.max(1, Math.min(raw, prev + 1));
      prev = depth;
      lines.push(`${"  ".repeat(depth)}- ${h.words}`);
    });
    return lines.join("\n");
  }
  // WB-MAP-HEADINGS-END

  //: Made through the Markdown import (tree-right, tidied once as it opens,
  //: decision 23), with the way back as a document topic under the centre: a
  //: reference to the document, which opens it, as any document topic does.
  async function wbMapFromDocument(doc, text) {
    if (!doc?.id) return null;
    const outline = wbMapHeadingsOutline(text, doc.title);
    if (!outline) {
      toast("This document has no headings to map. Give each part a heading first.");
      return null;
    }
    let board;
    try {
      board = await apiJson("/whiteboard/boards/import", {
        method: "POST",
        body: JSON.stringify({ format: "markdown", content: outline, name: (doc.title || "Untitled document").slice(0, 100) }),
      });
    } catch (err) {
      toast(err.message || voiceLine("failed", { what: "make that map" }), true);
      return null;
    }
    try {
      const tree = await apiJson(`/whiteboard/boards/${board.id}/tree`);
      const root = tree.roots?.[0];
      if (root) {
        await apiJson(`/whiteboard/boards/${board.id}/nodes`, {
          method: "POST",
          body: JSON.stringify({ kind: "document", parent_id: root.id, ref_id: doc.id, text: "" }),
        });
      }
    } catch {
      //: The map stands without its way back; the toast below still names
      //: the document it came from.
    }
    await openWhiteboardBoard(board.id);
    await wbMapTidyFresh();
    wbBoardMadeStep(board);
    toast(`Mapped the headings of “${doc.title || "this document"}”.`);
    return board;
  }

  //: **Branches from my notes** (the features audit FEAT-13; WHITEBOARD_PLAN
  //: decision 36; MINDMAP_PLAN §12.3 item 2). Up to five children for a topic,
  //: each found in one of the person's notes and saying which
  //: (`routes_map_suggest.py`: the search engine finds the notes, the model only
  //: names a topic for one by number, and with no model the notes' titles are
  //: the suggestions). Shown in the picker dialog with the Attach picker's rows,
  //: all ticked; Add makes the ticked ones under the topic, each with its source
  //: in its note, as one Undo step, and tidies the branch as a paste does.
  //: **Summarise this branch** (the features audit, Phase G). The server reads
  //: the branch as an outline and answers with a few sentences (the model's, or
  //: the branch said plainly from its own topics when no model is running);
  //: they go into the topic's own note, open for reading and changing, and are
  //: kept when the note closes (one Undo step, `wbMapCloseNote`). Nothing is
  //: written until then, so closing it unchanged after emptying it keeps nothing.
  async function wbMapSummariseBranch(node) {
    const boardId = window.currentBoardId;
    if (!node || !boardId) return;
    wbAnnounce("Reading this branch.");
    let got = null;
    try {
      got = await apiJson(`/whiteboard/boards/${boardId}/nodes/${node.id}/summary`, { method: "POST" });
    } catch (err) {
      toast(err.message || "This branch could not be summarised.", true);
      return;
    }
    if (wbMapNoteState?.id !== node.id) wbMapOpenNote(node.id);
    const panel = wbMapNoteState?.id === node.id ? wbMapNoteState.panel : null;
    const box = panel?.querySelector("textarea");
    if (!box || !got?.summary) return;
    const had = box.value.trim();
    box.value = had ? `${had}\n\n${got.summary}` : got.summary;
    box.setSelectionRange(box.value.length, box.value.length);
    const hint = panel.querySelector(".wb-map-note-hint");
    if (hint) {
      hint.textContent = got.source === "model"
        ? "A summary of this branch, added to its note. Change it as you like; saved when you close it."
        : `This branch from its own topics${got.reason === "offline" ? " (no model is running)" : ""}. Saved when you close it.`;
    }
    wbAnnounce("The branch's summary is in the topic's note.");
  }

  async function wbMapSuggestBranches(node) {
    const boardId = window.currentBoardId;
    if (!node || !boardId) return;
    wbAnnounce("Looking through your notes for branches.");
    let got = null;
    try {
      got = await apiJson(`/whiteboard/boards/${boardId}/nodes/${node.id}/suggest`, { method: "POST" });
    } catch (err) {
      toast(err.message || "No branches could be suggested.", true);
      return;
    }
    const rows = (got?.suggestions || []).map((s, i) => ({ id: i, ...s }));
    if (!rows.length) {
      toast("None of your notes match this topic's words yet, so there is nothing to suggest.");
      return;
    }
    const said = got.source === "model"
      ? `Under "${got.topic}", from your notes.`
      : `Under "${got.topic}": your notes that match it${got.reason === "offline" ? " (no model is running, so these are their titles)" : ""}.`;
    const chosen = await wbMapBranchPicker(rows, {
      title: "Branches from your notes",
      about: said,
      node,
      meta: (row) => [`From your note "${row.note_title}"`],
    });
    await wbMapAddChosenBranches(node, boardId, chosen);
  }

  //: The file's surface: what other files call (L286).
  Object.assign(window, { wbMarkerUi, wbMapCloseMarkers, wbMapOpenMarkers, wbMapChooseMarkerFilter, wbMapSetMarkerFilter, wbMapDim, wbMapSetDim, wbMapPaintMarkerFilter, wbMapAfterRender, wbMapFromDocument, wbMapSummariseBranch, wbMapSuggestBranches });
})();
