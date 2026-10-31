"""Independent review of the drag, copy and tray work (INBOX 1467, review
1031): the first reorder of a slice, a staged picture's key, the keys inside a
field, the hold before a drag, a paste on a mind map, the tray across spaces,
and a drop that changes nothing on screen."""

from __future__ import annotations

from tests._objmove_node import JS, needs_node, run

FILES = ["obj-ref.js", "obj-clip.js", "obj-drag.js", "obj-order.js", "obj-reorder.js", "obj-carry.js", "obj-tray.js"]
STUBS = """
const store = {};
globalThis.prefs = { json: (k, d) => (k in store ? store[k] : d), setJSON: (k, v) => { store[k] = v; return true; } };
globalThis.sessionStorage = { getItem: (k) => store[k] ?? null, setItem: (k, v) => { store[k] = v; } };
globalThis.Event = class { constructor(type) { this.type = type; } };
const toasts = []; const undos = []; const said = [];
globalThis.toast = (text) => toasts.push(text);
globalThis.announce = (text) => said.push(text);
globalThis.offerUndo = (...args) => undos.push(args);
const select = { value: "newest", dispatchEvent() {} };
globalThis.$ = (id) => (id === "note-sort" ? select : null);
const notes = (n) => Array.from({ length: n }, (_, i) => ({ id: n - i, pinned: false }));
const noteKeys = (ids) => ids.map((id) => `note:${id}`);
//: What a list shows under Custom order: the notes, ranked by the stored order.
const shown = () => { noteSort = "custom"; return sortEntries(allEntries).map((e) => e.id); };
"""


@needs_node
def test_the_first_reorder_of_a_page_keeps_the_page_where_it_was() -> None:
    """30 notes, 10 a page, no stored order: the arranged ten stay page one."""
    out = run(FILES, STUBS + """
    allEntries = notes(30);
    const page = noteKeys([30, 29, 28, 27, 26, 25, 24, 23, 22, 21]);
    const def = OBJ_SURFACES.find((d) => d.scope === "notes");
    const done = objReorderCommit(def, { title: "Thirty" }, page, 0, 4);
    __out({ done, shown: shown().slice(0, 12), select: select.value, undos: undos.length });
    """)
    assert out["done"] is True
    assert out["shown"] == [29, 28, 27, 26, 30, 25, 24, 23, 22, 21, 20, 19]
    assert out["select"] == "custom" and out["undos"] == 1


@needs_node
def test_a_filtered_slice_reorders_in_its_own_places_and_the_rest_stays() -> None:
    """A category's three notes among ten: only their places are handed out again."""
    out = run(FILES, STUBS + """
    allEntries = notes(10);
    const def = OBJ_SURFACES.find((d) => d.scope === "notes");
    objReorderCommit(def, { title: "Eight" }, noteKeys([8, 5, 2]), 2, 0);
    __out(shown());
    """)
    assert out == [10, 9, 2, 7, 6, 8, 4, 3, 5, 1], "the three swap in their own places; the other seven do not move"


@needs_node
def test_a_second_reorder_after_a_new_note_keeps_the_new_one_on_top() -> None:
    """The decision: a note the order has never seen is first, as a new note is."""
    out = run(FILES, STUBS + """
    allEntries = notes(5);
    const def = OBJ_SURFACES.find((d) => d.scope === "notes");
    objReorderCommit(def, { title: "t" }, noteKeys([5, 4, 3, 2, 1]), 0, 1);
    allEntries = [{ id: 6, pinned: false }, ...allEntries];
    const top = shown();
    objReorderCommit(def, { title: "t" }, noteKeys(top), 3, 4);
    __out({ top, after: shown() });
    """)
    assert out["top"] == [6, 4, 5, 3, 2, 1]
    assert out["after"] == [6, 4, 5, 2, 3, 1]


@needs_node
def test_every_list_names_all_its_objects_in_the_sort_it_has() -> None:
    out = run(FILES, STUBS + """
    globalThis.libraryDocsAll = [{ id: 1 }, { id: 3 }, { id: 2 }];
    globalThis.LIBRARY_DOC_SORTS = { newest: (a, b) => b.id - a.id };
    globalThis.libraryDocSort = () => "newest";
    globalThis.libraryImagesCache = [{ id: 4, _isImage: true }, { id: 9, _isImage: false }, { id: 7, _isImage: true, _isAttachment: true }];
    globalThis.LIBRARY_MEDIA_SORTS = { newest: (a, b) => b.id - a.id };
    globalThis.libraryMediaSort = () => "newest";
    globalThis.wbBoardsAll = [{ id: null, type: "board" }, { id: 2, type: "board" }, { id: 5, type: "map" }];
    globalThis.wbVisibleBoards = (boards) => [...boards].sort((a, b) => (b.id || 0) - (a.id || 0));
    const keys = (scope) => OBJ_SURFACES.find((d) => d.scope === scope).all();
    __out({ docs: keys("docs"), media: keys("media"), boards: keys("boards") });
    """)
    assert out["docs"] == ["document:3", "document:2", "document:1"]
    assert out["media"] == ["file:9", "file:7", "image:4"]
    assert out["boards"] == ["map:5", "board:2"], "the default board has no card to place"


@needs_node
def test_a_drop_that_changes_nothing_on_screen_changes_nothing_at_all() -> None:
    """Pinned notes stay on top in every order: dragging round one is not a move."""
    out = run(FILES, STUBS + """
    allEntries = notes(5).map((n) => ({ ...n, pinned: n.id === 3 }));
    noteSort = "newest";
    const def = OBJ_SURFACES.find((d) => d.scope === "notes");
    // the list as drawn: the pinned note, then the rest newest first
    const screen = noteKeys([3, 5, 4, 2, 1]);
    // 5 dragged above the pinned 3: the pin still wins
    const quiet = objReorderCommit(def, { title: "Five" }, screen, 1, 0);
    const untouched = { stored: store["order-notes"] ?? null, select: select.value, undos: undos.length };
    // 5 dragged below 4: a real move
    const real = objReorderCommit(def, { title: "Five" }, screen, 1, 2);
    __out({ quiet, untouched, real, select: select.value, undos: undos.length });
    """)
    assert out["quiet"] is False
    assert out["untouched"] == {"stored": None, "select": "newest", "undos": 0}
    assert out["real"] is True and out["select"] == "custom" and out["undos"] == 1


@needs_node
def test_alt_arrow_on_a_card_that_cannot_move_says_so_and_stores_nothing() -> None:
    out = run(FILES, STUBS + """
    allEntries = notes(3).map((n) => ({ ...n, pinned: n.id === 3 }));
    const def = OBJ_SURFACES.find((d) => d.scope === "notes");
    const result = objReorderCommit(def, { title: "x" }, noteKeys([3, 2, 1]), 1, 0);
    __out({ result, stored: store["order-notes"] ?? null, undos: undos.length });
    """)
    assert out == {"result": False, "stored": None, "undos": 0}


@needs_node
def test_a_staged_picture_is_removed_alone_by_its_key() -> None:
    out = run(["obj-ref.js"], """
      const dest = { type: "chat", el: {} };
      [1, 2, 3].forEach((n) => objRender(objRef("image", n, "p", "/m/p"), dest));
      const keys = attachedImages.map((img) => img.key);
      // chat-attach.js removes by `img.key !== image.key`
      const gone = attachedImages[1];
      const left = attachedImages.filter((img) => img.key !== gone.key);
      __out({ keys, left: left.map((img) => img.id) });
    """)
    assert out["keys"] == ["obj-1", "obj-2", "obj-3"]
    assert out["left"] == [1, 3]


@needs_node
def test_alt_arrow_inside_a_field_is_the_fields_own() -> None:
    out = run(FILES, STUBS + """
    const press = (target) => {
      let reached = false, prevented = false;
      Object.defineProperty(document, "activeElement", { configurable: true, get: () => { reached = true; return null; } });
      objReorderKey({ key: "ArrowUp", altKey: true, target, preventDefault() { prevented = true; }, stopPropagation() {} });
      return { reached, prevented };
    };
    const field = { closest: (sel) => (sel === OBJ_EDITABLE ? {} : null) };
    const card = { closest: () => null };
    __out({ field: press(field), card: press(card) });
    """)
    assert out["field"] == {"reached": False, "prevented": False}
    assert out["card"]["reached"] is True


@needs_node
def test_a_paste_of_our_text_on_a_mind_map_is_left_to_the_maps_own_paste() -> None:
    out = run(FILES, STUBS + """
    globalThis.wbCommandsLive = () => true;
    let map = true;
    globalThis.wbIsMap = () => map;
    document.activeElement = null;
    objClip = { ref: objRef("note", 5, "Five"), text: "[[Five]]" };
    const event = { clipboardData: { getData: () => "[[Five]]" }, preventDefault() { this.handled = true; }, stopPropagation() {} };
    handlers.paste.forEach((fn) => fn(event));
    const onMap = { handled: Boolean(event.handled), toasts: toasts.slice() };
    map = false;
    const dest = objPasteDestination(null);
    __out({ onMap, board: dest && dest.type });
    """)
    assert out["onMap"] == {"handled": False, "toasts": []}
    assert out["board"] == "board", "a board still takes the paste"


@needs_node
def test_the_tray_is_one_for_the_notebook_and_a_card_of_another_space_is_refused() -> None:
    # Audit 1031 Z1 moved the intent of the old "kept per space" test: a space
    # switch reloads the page, and the tray used to be emptied by it. Now the
    # tray survives the switch and each reference remembers its space.
    out = run(FILES, STUBS + """
    let space = "default";
    globalThis.activeSpaceId = () => space;
    objTray = []; objTrayAdd(objRef("note", 1, "In default"));
    space = "work";
    const kept = objTrayRead().map((r) => [objKey(r), r.space]);
    objTrayAdd(objRef("note", 2, "In work"));
    toasts.length = 0;
    objTrayPaste(objTray[0]);
    const refused = toasts.slice();
    space = "all";
    objTrayRead();
    __out({ kept, refused: refused.length, keys: Object.keys(store).filter((k) => k.startsWith("obj-tray")), n: objTrayRead().length });
    """)
    assert out["kept"] == [["note:1", "default"]]
    assert out["refused"] == 1
    assert out["keys"] == ["obj-tray"] and out["n"] == 2


def test_the_picture_stage_gives_every_picture_a_key() -> None:
    text = (JS / "obj-ref.js").read_text(encoding="utf-8")
    assert "key: `obj-${ref.id}`" in text


# --- The UX audit of the same surfaces (ux-1031b) -------------------------------------

@needs_node
def test_a_key_move_is_announced_and_undone_by_ctrl_z_without_a_toast_per_press() -> None:
    out = run(FILES, STUBS + """
    allEntries = notes(4);
    const pushed = [];
    globalThis.pushUndo = (...args) => pushed.push(args[0]);
    const def = OBJ_SURFACES.find((d) => d.scope === "notes");
    const card = { id: 3 };
    const unit = { tagName: "LI", matches: () => true, firstElementChild: null, dataset: { id: "3" } };
    const keys = noteKeys([4, 3, 2, 1]);
    const hit = { def, list: { children: [] }, unit };
    // the list's cards, as the step reads them
    globalThis.objUnitsOf = () => keys.map((k) => ({ key: k }));
    globalThis.objUnitKey = (u) => u.key;
    globalThis.objUnitRef = () => ({ kind: "note", id: 3, title: "Three" });
    objReorderStep(hit, 1);
    __out({ pushed, undos: undos.length, said });
    """)
    assert out["pushed"] == ["Move Three"] and out["undos"] == 0
    assert out["said"] == ["Moved Three to place 3 of 4. Ctrl+Z undoes it."]


@needs_node
def test_the_card_menu_has_move_rows_only_for_a_card_in_a_list() -> None:
    out = run(FILES, STUBS + """
    const rows = Object.fromEntries(OBJ_MENU_ROWS.map((r) => [r.label, r.show ? r.show({ inList: true }) : true]));
    globalThis.objSurfaceAt = (card) => (card.inList ? {} : null);
    const shownIn = OBJ_MENU_ROWS.filter((r) => r.label.startsWith("Move")).map((r) => [r.show({ inList: true }), r.show({ inList: false })]);
    __out({ labels: OBJ_MENU_ROWS.map((r) => r.label), shownIn });
    """)
    assert out["labels"] == ["Copy card", "Move up", "Move down", "Add to tray"]
    assert out["shownIn"] == [[True, False], [True, False]]


@needs_node
def test_a_tray_item_pastes_where_the_hand_last_was_even_with_no_pointer() -> None:
    out = run(FILES, STUBS + """
    const chat = { isConnected: true, getClientRects: () => [{}], closest: (sel) => (sel.includes("#chat-input") ? chat : null), matches: () => false };
    objTrayFrom = chat;
    const dest = objTrayDestination();
    objTrayFrom = { isConnected: false, closest: () => null };
    globalThis.wbCommandsLive = () => false;
    __out({ type: dest && dest.type, gone: objTrayDestination() });
    """)
    assert out == {"type": "chat", "gone": None}


@needs_node
def test_removing_a_tray_item_keeps_the_focus_in_the_tray() -> None:
    out = run(FILES, STUBS + """
    const focused = [];
    const use = (n) => ({ focus: () => focused.push(`use ${n}`) });
    let uses = [use(0), use(1), use(2)];
    const holder = { querySelectorAll: () => uses, querySelector: () => ({ focus: () => focused.push("button") }) };
    document.activeElement = { closest: () => holder };
    objTrayKeepFocus(() => { uses = [use(0), use(1)]; }, 1);
    objTrayKeepFocus(() => { uses = [use(0), use(1)]; }, 5);
    uses = [];
    globalThis.$ = () => ({ focus: () => focused.push("trigger") });
    holder.querySelector = () => null;
    objTrayKeepFocus(() => {}, 0);
    document.activeElement = { closest: () => null };
    objTrayKeepFocus(() => {}, 0);
    __out(focused);
    """)
    assert out == ["use 1", "use 1", "trigger"], "the next item, the last when it was last, the trigger when empty, nothing when the focus was elsewhere"


@needs_node
def test_a_card_already_held_says_so_and_a_second_paste_of_a_note_says_so() -> None:
    out = run(FILES, STUBS + """
    objTray = []; objTrayAdd(objRef("note", 1, "Soup"));
    OBJ_RENDERERS.tray(objRef("note", 1, "Soup"));
    OBJ_RENDERERS.tray(objRef("note", 2, "Tea"));
    attachedNoteIds.push(2);
    objPasteAt(objRef("note", 2, "Tea"), { type: "chat", el: {} });
    objPasteAt(objRef("note", 3, "Jam"), { type: "chat", el: {} });
    __out({ toasts, said, held: objTray.length });
    """)
    assert out["toasts"] == ["“Soup” is already in the tray", "Added “Tea” to the tray", "Already attached"]
    assert out["said"] == ["Attached Jam to the message."]


@needs_node
def test_ctrl_c_on_a_cards_tick_copies_the_card() -> None:
    out = run(FILES, STUBS + """
    const tick = { dataset: { id: "5" }, querySelector: () => null, matches: (sel) => sel === OBJ_TICK || sel === "#entry-list > li[data-id]" };
    const card = { dataset: { id: "5" }, querySelector: () => null, matches: (sel) => sel === "#entry-list > li[data-id]" };
    card.closest = (sel) => (sel.includes("#entry-list > li[data-id]") ? card : null);
    tick.closest = (sel) => (sel === OBJ_EDITABLE ? tick : sel.includes("#entry-list > li[data-id]") ? card : null);
    window.getSelection = () => ({ toString: () => "" });
    document.activeElement = tick;
    const event = { clipboardData: { setData() {} }, preventDefault() { this.stopped = true; } };
    handlers.copy.forEach((fn) => fn(event));
    __out({ copied: Boolean(event.stopped), toasts });
    """)
    assert out["copied"] is True and out["toasts"] == ["Copied “Five”"]


def test_carry_outlines_the_composer_box_and_the_gap_is_one_slot_everywhere() -> None:
    carry = (JS / "obj-carry.js").read_text(encoding="utf-8")
    assert 'dest.el.closest(".chat-dock")' in carry
    css = (JS.parent / "css" / "objmove-lazy.css").read_text(encoding="utf-8")
    assert "#entry-list > li.obj-gap" in css and ".obj-armed" in css


def test_the_four_lists_help_and_the_shortcut_sheet_name_the_drag_the_copy_and_the_tray() -> None:
    html = (JS.parent / "index.html").read_text(encoding="utf-8")
    sentence = "Drag a card, or press Alt+Up or Alt+Down on it, to put this list in your own order."
    assert html.count(sentence) == 4
    assert "Move the focused card one place up or down in its list" in html
    assert "Copy the focused card" in html
    features = (JS / "app-features.js").read_text(encoding="utf-8")
    assert 'name: "Tray"' in features and 'name: "Your own order"' in features


def test_the_notes_card_menu_gets_the_card_rows_and_a_links_own_menu_does_not() -> None:
    menus = (JS / "menus.js").read_text(encoding="utf-8")
    assert "window.objKebabRows?.(menu);" in menus
    clip = (JS / "obj-clip.js").read_text(encoding="utf-8")
    assert '.link-connection' in clip
