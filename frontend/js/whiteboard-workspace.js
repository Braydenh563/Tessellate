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

  function paint() {
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

  function enter(chain) {
    if (!chain?.length || (chain.length === prefix.length && chain.every((s, i) => s === prefix[i]))) return false;
    prefix = [...chain];
    paint();
    wbAnnounce("Editing inside the group. Escape leaves it.");
    return true;
  }

  function leave() {
    if (!prefix.length) return false;
    prefix = [];
    paint();
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
    return enter(chain);
  }

  function onKey(e) {
    if (e.key !== "Escape" || !prefix.length || e.defaultPrevented) return;
    const active = document.activeElement;
    const tag = (active?.tagName || "").toLowerCase();
    //: Escape in a field or a menu is that field's or menu's.
    if (active && (tag === "input" || tag === "textarea" || tag === "select" || active.isContentEditable)) return;
    if (e.target?.closest?.("[role=menu], [role=dialog], dialog")) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    leave();
  }
  window.addEventListener("keydown", onKey, true);

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
  function snapshot() {
    return {
      props: !document.getElementById("library-view-whiteboard")?.classList.contains("wb-hide-context"),
      overview: open("wb-navigator"),
      search: open("wb-search-bar"),
      format: open("wb-format"),
      side: open("wb-sidebar-panel") ? wbSideState().tab || "library" : "",
    };
  }

  //: Puts the panels as a snapshot has them, pressing only the ones that differ.
  function apply(snap) {
    const box = document.getElementById("wb-panel-props");
    if (box && snap.props !== undefined && box.checked !== Boolean(snap.props)) {
      box.checked = Boolean(snap.props);
      box.dispatchEvent(new Event("change"));
    }
    if (Boolean(snap.overview) !== open("wb-navigator")) document.getElementById("wb-navigator-toggle")?.click();
    if (Boolean(snap.search) !== open("wb-search-bar")) document.getElementById("wb-search-toggle")?.click();
    if (Boolean(snap.format) !== open("wb-format")) wbFormatToggle();
    if (snap.side) wbOpenSidebar(snap.side, { focus: false });
    else if (open("wb-sidebar-panel")) wbCloseSidebar();
  }

  const saved = () => prefs.json(KEY, []).filter((w) => w && typeof w.name === "string" && w.panels);
  const store = (list) => prefs.set(KEY, JSON.stringify(list));

  function use(name) {
    const found = saved().find((w) => w.name === name);
    if (!found) return false;
    apply(found.panels);
    current = name;
    wbAnnounce(`Workspace ${name}.`);
    mount();
    return true;
  }

  async function save(name) {
    const clean = String(name ?? (await promptDialog("Name this workspace", current || "", { confirmLabel: "Save" })) ?? "").trim().slice(0, 40);
    if (!clean) return false;
    const list = saved().filter((w) => w.name !== clean);
    if (list.length >= MAX) {
      toast(`Keep at most ${MAX} workspaces; delete one first.`, "info");
      return false;
    }
    list.push({ name: clean, panels: snapshot() });
    store(list);
    current = clean;
    wbAnnounce(`Workspace ${clean} saved.`);
    mount();
    return true;
  }

  function remove(name) {
    store(saved().filter((w) => w.name !== name));
    if (current === name) current = "";
    mount();
  }

  //: The menu's rows: one to switch to each workspace, one to save the panels now, one to delete each.
  function rows() {
    const list = saved();
    return [
      ...list.map((w) => ({ label: `ph:layout ${w.name}`, title: "Open the panels this workspace was saved with", current: w.name === current, run: () => use(w.name) })),
      { label: "ph:floppy-disk Save the open panels as a workspace…", group: "manage", run: () => save() },
      ...list.map((w) => ({ label: `ph:trash Delete ${w.name}`, group: "manage", danger: true, run: () => remove(w.name) })),
    ];
  }

  //: The View menu's Workspaces row holds a ⋯ menu (the shared kebab recipe), built again when the list changes.
  function mount() {
    const slot = document.getElementById("wb-workspaces");
    if (!slot || typeof kebabMenu !== "function") return;
    slot.querySelector(".menu-wrap")?.remove();
    slot.append(kebabMenu(rows(), "Workspaces"));
  }

  onSurface("board", mount);

  wbFmtState.isolate = { outside, depth: () => prefix.length, enter, leave, paint, enterSelection, active: () => prefix.length > 0, onKey };
  wbFmtState.workspaces = { snapshot, apply, save, use, remove, rows, saved };
})();
