(() => {
  // whiteboard-workspace.js: Edit inside a group (L-whiteboard-7) and board workspace presets (L-whiteboard-8,
  // WHITEBOARD_PLAN). Both change what the board shows rather than what it holds, so neither writes to the
  // board: the group is a mode kept in memory, the workspaces are named lists of open panels kept on this device.

  // --- Edit inside a group ---------------------------------------------------------------------------------
  //: The chain of group ids that is open ([] for none). Items whose chain does not start with it are dimmed
  //: (`.wb-dimmed`, out of reach of the pointer) and `isolate.outside` (called from whiteboard.js) keeps them out of Select
  //: all, a sweep and the Tab walk. Nothing is saved: a reload, or another board, leaves the group.
  let prefix = [];
  let painted = false;

  const inside = (item) => {
    const chain = wbGroupChain(item);
    return prefix.every((seg, i) => chain[i] === seg);
  };
  //: A connector joining two members of the open group belongs to the edit too (L-whiteboard-19): it has no group of its
  //: own, so it is judged by its two ends, both of which must be attached and inside. One with a free end stands back.
  const joinsMembers = (sketch) => {
    if (!wbIsLinkSketch(sketch)) return false;
    const data = wbSketchData(sketch) || {};
    return ["source", "target"].every((end) => {
      const id = data[`${end}Id`];
      const ends = id == null ? null : wbFindItem(data[`${end}Kind`] || "node", id);
      return Boolean(ends) && inside(ends);
    });
  };
  const outside = (kind, item) => prefix.length > 0 && !inside(item) && !(kind === "sketch" && joinsMembers(item));

  function paintIsolation() {
    //: A group whose members are gone (ungrouped, deleted, another board) is left rather than kept open on nothing.
    if (prefix.length && !wbItemsWithGroupPrefix(prefix).length) prefix = [];
    if (!prefix.length && !painted) return;
    document.getElementById("library-view-whiteboard")?.classList.toggle("wb-isolating", prefix.length > 0);
    for (const [kind, list] of Object.entries(WB_LIST_BY_KIND)) {
      for (const item of wbState[list] || []) {
        document.querySelector(WB_SELECTOR_BY_KIND[kind](item.id))?.classList.toggle("wb-dimmed", outside(kind, item));
      }
    }
    painted = prefix.length > 0;
  }

  function enterGroup(chain) {
    if (!chain?.length || (chain.length === prefix.length && chain.every((s, i) => s === prefix[i]))) return false;
    prefix = [...chain];
    paintIsolation();
    wbAnnounce("Editing inside the group. Escape leaves it.");
    return true;
  }

  function leaveGroup() {
    if (!prefix.length) return false;
    prefix = [];
    paintIsolation();
    wbAnnounce("Left the group.");
    return true;
  }

  //: The group the selection sits in: the ids every selected item shares, deeper than the one already open.
  function selectionChain() {
    const items = wbFmtEntries().map((e) => e.item);
    return items.length ? wbCommonGroupPrefix(items) : [];
  }

  //: The command: opens the innermost group the whole selection shares.
  function enterSelection() {
    const chain = selectionChain();
    if (chain.length <= prefix.length) {
      toast("Select a grouped item first.", "info");
      return false;
    }
    return enterGroup(chain);
  }

  function onGroupKey(e) {
    if (e.key !== "Escape" || !prefix.length || e.defaultPrevented) return;
    const active = document.activeElement;
    const tag = (active?.tagName || "").toLowerCase();
    //: Escape in a field or a menu is that field's or menu's.
    if (active && (tag === "input" || tag === "textarea" || tag === "select" || active.isContentEditable)) return;
    if (e.target?.closest?.("[role=menu], [role=dialog], dialog")) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    leaveGroup();
  }
  window.addEventListener("keydown", onGroupKey, true);

  // --- Workspaces ------------------------------------------------------------------------------------------
  const KEY = "wb-workspaces";
  const MAX = 8;
  let current = "";

  const open = (id) => {
    const el = document.getElementById(id);
    return Boolean(el) && !el.classList.contains("hidden");
  };

  //: Which panels are open now: the context bar, the overview, the search bar, the Format panel, and the sidebar
  //: with the tab it shows (Library, Layers, Pages, Notes or Outline), "" when it is closed.
  function panelSnapshot() {
    return {
      props: !document.getElementById("library-view-whiteboard")?.classList.contains("wb-hide-context"),
      overview: open("wb-navigator"),
      search: open("wb-search-bar"),
      format: open("wb-format"),
      side: open("wb-sidebar-panel") ? wbSideState().tab || "library" : "",
    };
  }

  //: Puts the panels as a snapshot has them, pressing only the ones that differ.
  function applyPanels(snap) {
    const box = document.getElementById("wb-panel-props");
    if (box && snap.props !== undefined && box.checked !== Boolean(snap.props)) {
      box.checked = Boolean(snap.props);
      box.dispatchEvent(new Event("change"));
    }
    if (Boolean(snap.overview) !== open("wb-navigator")) wbToggleNavigator();
    if (Boolean(snap.search) !== open("wb-search-bar")) (open("wb-search-bar") ? wbCloseBoardSearch() : wbOpenBoardSearch());
    if (Boolean(snap.format) !== open("wb-format")) wbFormatToggle();
    if (snap.side) wbOpenSidebar(snap.side, { focus: false });
    else if (open("wb-sidebar-panel")) wbCloseSidebar();
  }

  const saved = () => prefs.json(KEY, []).filter((w) => w && typeof w.name === "string" && w.panels);
  const store = (list) => prefs.set(KEY, JSON.stringify(list));

  function useWorkspace(name) {
    const found = saved().find((w) => w.name === name);
    if (!found) return false;
    applyPanels(found.panels);
    current = name;
    wbAnnounce(`Workspace ${name}.`);
    mountWorkspaces();
    return true;
  }

  async function saveWorkspace(name) {
    const clean = String(name ?? (await promptDialog("Name this workspace", current || "", { confirmLabel: "Save" })) ?? "").trim().slice(0, 40);
    if (!clean) return false;
    const list = saved().filter((w) => w.name !== clean);
    if (list.length >= MAX) {
      toast(`Keep at most ${MAX} workspaces; delete one first.`, "info");
      return false;
    }
    list.push({ name: clean, panels: panelSnapshot() });
    store(list);
    current = clean;
    wbAnnounce(`Workspace ${clean} saved.`);
    mountWorkspaces();
    return true;
  }

  function removeWorkspace(name) {
    store(saved().filter((w) => w.name !== name));
    if (current === name) current = "";
    mountWorkspaces();
  }

  //: The menu's rows: one to switch to each workspace, one to save the panels now, one to delete each.
  function workspaceRows() {
    const list = saved();
    return [
      ...list.map((w) => ({ label: `ph:layout ${w.name}`, title: "Open the panels this workspace was saved with", current: w.name === current, run: () => useWorkspace(w.name) })),
      { label: "ph:floppy-disk Save the open panels as a workspace…", group: "manage", run: () => saveWorkspace() },
      ...list.map((w) => ({ label: `ph:trash Delete ${w.name}`, group: "manage", danger: true, run: () => removeWorkspace(w.name) })),
    ];
  }

  //: The View menu's Workspaces row holds a ⋯ menu (the shared kebab recipe), built again when the list changes.
  function mountWorkspaces() {
    const slot = document.getElementById("wb-workspaces");
    if (!slot || typeof kebabMenu !== "function") return;
    slot.querySelector(".menu-wrap")?.remove();
    slot.append(kebabMenu(workspaceRows(), "Workspaces"));
  }

  onSurface("board", mountWorkspaces);

  wbFmtState.isolate = { outside, depth: () => prefix.length, enter: enterGroup, leave: leaveGroup, paint: paintIsolation, enterSelection, active: () => prefix.length > 0, onKey: onGroupKey };
  wbFmtState.workspaces = { snapshot: panelSnapshot, apply: applyPanels, save: saveWorkspace, use: useWorkspace, remove: removeWorkspace, rows: workspaceRows, saved };
})();
