"""INBOX 1467 parts 4 and 5: carrying a card and the tray (obj-carry.js,
obj-tray.js, the mode hand-over in obj-drag.js)."""

from __future__ import annotations

from tests._objmove_node import JS, needs_node, run

FILES = ["obj-ref.js", "obj-clip.js", "obj-drag.js", "obj-reorder.js", "obj-carry.js", "obj-tray.js"]
STUBS = """
const store = {};
globalThis.sessionStorage = { getItem: (k) => store[k] ?? null, setItem: (k, v) => { store[k] = v; } };
const toasts = []; const undos = [];
globalThis.toast = (text) => toasts.push(text);
globalThis.offerUndo = (...args) => undos.push(args);
const ref = (id) => objRef("note", id, `Note ${id}`);
"""


@needs_node
def test_the_tray_holds_each_object_once_in_the_order_added() -> None:
    out = run(FILES, STUBS + """
    objTrayAdd(ref(1)); objTrayAdd(ref(2)); objTrayAdd(ref(1));
    __out({ held: objTray.map(objKey), stored: JSON.parse(store["obj-tray"]).map((r) => r.id) });
    """)
    assert out == {"held": ["note:1", "note:2"], "stored": [1, 2]}


@needs_node
def test_a_full_tray_refuses_one_more_and_says_so() -> None:
    out = run(FILES, STUBS + """
    for (let i = 1; i <= 30; i++) objTrayAdd(ref(i));
    const extra = objTrayAdd(ref(99));
    OBJ_RENDERERS.tray(ref(98));
    __out({ extra, held: objTray.length, toasts });
    """)
    assert out["extra"] is False and out["held"] == 30
    assert out["toasts"] == ["The tray is full. Take something out first."]


@needs_node
def test_the_tray_reads_back_what_was_stored_and_survives_garbage() -> None:
    out = run(FILES, STUBS + """
    store["obj-tray"] = JSON.stringify([{ kind: "note", id: 3, title: "Kept" }, { kind: "tag", id: 1 }, { nonsense: true }]);
    const kept = objTrayRead().map(objKey);
    store["obj-tray"] = "{not json";
    __out({ kept, bad: objTrayRead() });
    """)
    assert out == {"kept": ["note:3"], "bad": []}


@needs_node
def test_a_storage_that_throws_leaves_the_tray_working_from_memory() -> None:
    out = run(FILES, STUBS + """
    globalThis.sessionStorage = { getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("blocked"); } };
    __out({ read: objTrayRead(), added: objTrayAdd(ref(7)), held: objTray.map(objKey) });
    """)
    assert out == {"read": [], "added": True, "held": ["note:7"]}


@needs_node
def test_clearing_the_tray_offers_undo_and_undo_puts_it_back() -> None:
    out = run(FILES, STUBS + """
    objTrayAdd(ref(1)); objTrayAdd(ref(2));
    objTrayClear();
    const cleared = objTray.length;
    undos[0][2]();
    const restored = objTray.map(objKey);
    objTrayClear(); objTrayClear();
    __out({ cleared, restored, offers: undos.length });
    """)
    assert out == {"cleared": 0, "restored": ["note:1", "note:2"], "offers": 2}


@needs_node
def test_a_drop_on_the_tray_control_adds_and_an_add_to_tray_row_exists() -> None:
    out = run(FILES, STUBS + """
    const dest = objDestinationAt({ closest: (sel) => (sel.includes("#status-tray") ? {} : null) });
    objRender(ref(5), dest);
    __out({ type: dest.type, held: objTray.map(objKey), rows: OBJ_MENU_ROWS.map((row) => row.label) });
    """)
    assert out == {"type": "tray", "held": ["note:5"], "rows": ["Copy", "Add to tray"]}


@needs_node
def test_a_carried_card_is_valid_over_fields_that_hold_a_link_and_no_others() -> None:
    out = run(FILES, STUBS + """
    const over = (part, matches) => {
      const el = { matches: (sel) => matches && sel === OBJ_CARRY_EDIT, closest: (sel) => (sel.includes(part) ? el : null) };
      document.elementFromPoint = () => el;
      return objCarryTarget({ x: 1, y: 1 })?.type || null;
    };
    __out({ composer: over("#chat-input", false), reminder: over("#reminder-magic", false), tray: over("#status-tray", false),
      editor: over("textarea", true), searchBox: over("input[type='text']", false), nowhere: over("nothing", false) });
    """)
    assert out == {"composer": "chat", "reminder": "reminder", "tray": "tray", "editor": "text", "searchBox": None, "nowhere": None}


@needs_node
def test_a_card_leaving_its_list_is_carried_and_coming_back_reorders() -> None:
    out = run(FILES, STUBS + """
    const list = { getBoundingClientRect: () => ({ left: 0, right: 300, top: 0, bottom: 600 }) };
    const g = { surface: { list, unit: { isConnected: true } }, x: 100, y: 100 };
    const verdicts = [];
    verdicts.push(objReorderRoute(g));
    g.x = 310; verdicts.push(objReorderRoute(g));   // inside the 24px margin
    g.x = 330; verdicts.push(objReorderRoute(g));   // outside it
    verdicts.push(objCarryRoute(g));                // carried, not back yet
    g.x = 200; verdicts.push(objCarryRoute(g));     // back over the list
    verdicts.push(objCarryRoute({ x: 1, y: 1 }));   // no home list: always carried
    __out(verdicts);
    """)
    assert out == ["reorder", "reorder", "carry", "carry", "reorder", "carry"]


@needs_node
def test_the_engine_hands_the_gesture_between_modes_and_ends_the_old_one() -> None:
    out = run(FILES, STUBS + """
    const calls = [];
    OBJ_MODES.one = { cancel: () => calls.push("one.cancel"), begin: () => calls.push("one.begin"), route: () => "two" };
    OBJ_MODES.two = { cancel: () => calls.push("two.cancel"), begin: () => calls.push("two.begin"), route: () => "two" };
    const g = { mode: "one" };
    objDragRoute(g); objDragRoute(g);
    __out({ calls, mode: g.mode });
    """)
    assert out == {"calls": ["one.cancel", "two.begin"], "mode": "two"}


def test_the_tray_control_and_panel_are_in_the_page_and_the_settings_list() -> None:
    html = (JS.parent / "index.html").read_text(encoding="utf-8")
    assert 'id="status-tray"' in html and 'data-status-slot="tray"' in html and 'id="obj-tray"' in html
    controls = (JS / "settings-controls.js").read_text(encoding="utf-8")
    assert 'key: "tray"' in controls
    ref = (JS / "obj-ref.js").read_text(encoding="utf-8")
    assert '"/js/obj-carry.js", "/js/obj-tray.js"' in ref
