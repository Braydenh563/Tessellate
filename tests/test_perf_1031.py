"""Audit 1031 perf class rows (ranked 16 to 55): each test names the cost it keeps out."""

from tests._app_js import frontend_text
from tests import _js_scope


def _between(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i : text.index(end, i)]


def test_focus_settles_the_keyboard_inset_only_where_a_keyboard_can_cover_the_page():
    # Four `innerHeight` reads per focus were a forced layout of the whole page each
    # (1.2 s at 4x with the companion out) in a window that has no on-screen keyboard.
    js = frontend_text("phone-shell.js")
    body = _between(js, "function initKeyboardInset() {", "document.addEventListener(\"focusin\"")
    assert '(any-pointer: coarse)' in body
    assert "touchy.matches &&" in body.split("const settle")[1]


def test_the_rail_spy_ignores_scrollers_that_do_not_hold_the_list():
    # The capture box's own scroller woke a pick (a rect per visible card) per key.
    js = frontend_text("notes-rail-spy.js")
    block = _between(js, "document.addEventListener(\"scroll\"", "list.addEventListener(\"focusin\"")
    assert "target.contains?.(list)" in block


def test_the_palette_draws_a_window_and_listens_once():
    # 117 rows with two listeners each on every key and arrow: +1,086 nodes and +458
    # listeners per open, 12 long tasks for ten arrows at 4x.
    js = _js_scope.unwrapped(frontend_text("app-palette.js"))
    draw = _between(js, "function paletteDrawRows(upTo) {", "function renderPalette(query) {")
    assert "addEventListener" not in draw
    render = _between(js, "function renderPalette(query) {", "$(\"palette-list\").addEventListener(\"click\"")
    assert "addEventListener" not in render
    assert "paletteDrawRows(Math.max(PALETTE_WINDOW" in render
    assert 'closest?.("li[data-index]")' in js
    assert "const PALETTE_WINDOW = 24;" in js


def test_a_palette_key_is_not_a_match():
    # keydown matched the whole catalogue before the input event matched it again.
    js = _js_scope.unwrapped(frontend_text("app-palette.js"))
    keys = _between(js, "function paletteKeydown(event) {", "// Reported live")
    assert "paletteMatches(" not in keys
    arrow = _between(js, "function paletteArrow(step) {", "function paletteKeydown")
    assert "renderPalette(" not in arrow and "replaceChildren" not in arrow


def test_the_settings_rows_are_scanned_once_per_palette_open():
    # Every letter typed in the palette cloned each Settings label (49 ms at 4x).
    find = frontend_text("settings-find.js")
    body = _between(find, "function settingRows() {", "function settingRowsScan() {")
    assert "settingRows.stamp !== palette.dataset.opened" in body
    assert "palette.classList.contains(\"hidden\")" in body
    assert 'dataset.opened = String(performance.now())' in _js_scope.unwrapped(frontend_text("app-palette.js"))


def test_a_selection_is_saved_by_one_request_per_gesture():
    # Ctrl+A on 362 items and two arrow presses sent 167 PUTs (audit 1031 BD2).
    wb = frontend_text("whiteboard.js")
    for start, end in (
        ("async function wbFlushNudge() {", "function wbNudgeSelection"),
        ("async function wbSaveMultiSnapshot(rows) {", "function wbRenderMultiSelectionHandles"),
        ("async function wbSaveBulkMove(origin) {", "// Copy/paste"),
        ("async function wbFrameTurnEnd(d, primary) {", "function wbRotateGripTitle"),
    ):
        body = _between(wb, start, end)
        assert "await wbSaveMany(" in body, start
        assert "await wbSaveNode(" not in body and "await wbSaveObject(" not in body, start
    batch = _between(wb, "async function wbSaveMany(rows) {", "function wbSaveRow")
    assert "/whiteboard/items/save-many" in batch
    assert "wbTakeMoveRun(pending)" in wb  # an undo of a batch of moves is one request too
    mp = frontend_text("whiteboard-map.js")
    assert "for (const node of changed) await wbSaveObject(node)" not in mp


def test_one_note_added_to_a_big_map_does_not_heat_the_whole_map():
    # One note on 2,000 kept the layout running 15.8 s with 46 long tasks at 4x (GR5):
    # a note without a place made every render "not placed" and heated from 1.
    js = frontend_text("graph-canvas.js")
    body = _between(js, "function gcAdditionHolds(", "function gcStartWorker(")
    assert "prior.size < GC_ADD_MIN_NOTES" in body
    assert "added.length > GC_ADD_MAX" in body
    assert "s.lastForces !== gcForcesKey(s)" in body  # a changed force is a real relayout
    render = _between(js, "const heldForAdd = gcAdditionHolds(", "graphRenderStats(")  # up to the end of the force branch
    assert "alpha: heldForAdd ? GC_ADD_ALPHA" in render
    assert "freezeIds: heldForAdd ||" in render
    assert "addition: Boolean(heldForAdd)" in render


def test_the_minimap_paints_by_the_clock_while_the_layout_settles():
    # One paint in eight ticks was eight a second on a small map; each rewrites 1,400 elements.
    js = frontend_text("graph-canvas.js")
    assert "now - (s.minimapAt || 0) >= GC_MINIMAP_MS" in js
    assert "graphMinimapTick" not in js and "graphMinimapTick" not in frontend_text("graph.js")


def test_graph_search_keys_share_a_redraw():
    # 13 keys at 2,000 notes and 4x: a redraw each. The first key is still drawn at once.
    js = frontend_text("graph.js")
    body = _between(js, "function graphSearchTyped() {", "$(\"graph-search\").addEventListener(\"input\"")
    assert body.index("if (wait <= 0)") < body.index("setTimeout(")
    assert "clearTimeout(typed.timer)" in body


def test_a_widget_that_settles_clears_its_stall_timer():
    # The pending timer held the closure, and through it the widget body, for 20 s
    # after the person left: +630 detached nodes and +25 listeners a Dashboard visit.
    js = frontend_text("dashboard.js")
    body = _between(js, "function mountWidgetBody(widget, body) {", "//: **Back on the dashboard")
    assert "clearTimeout(stall)" in body
    assert "stall = setTimeout(" in body


def test_render_functions_do_not_add_page_level_listeners():
    # A listener on document or window made inside a render function is added again
    # every render and holds the closure (and what it names) for the page's life.
    # `mountDocToolbarControls` runs once at load: the one allowed.
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "frontend" / "js"
    found = []
    for path in sorted(root.glob("*.js")):
        text = path.read_text(encoding="utf-8")
        for fn in re.finditer(r"(?ms)^(?:async )?function ((?:render|draw|paint|mount)\w*)\(.*?\n\}\n", text):
            for line in fn.group(0).splitlines():
                if re.search(r"\b(document|window)\.addEventListener\(", line) and "once" not in line:
                    found.append(f"{path.name}:{fn.group(1)}")
    #: Ratcheted down (L-world-class-323): the Documents toolbar key moved to module level.
    assert found == [], found


def test_link_offers_wait_two_seconds_in_the_middle_of_a_sentence():
    # One typed line sent three POSTs, one per 700 ms pause (DC12).
    js = frontend_text("documents-prose.js")
    quiet = _between(js, "function docLinkOfferQuiet(text) {", "//: The server's own cap")
    assert "text.slice(-40)" in quiet  # the tail only: the text can be 400,000 characters
    assert "DOC_LINK_OFFER_MIDWAY_MS" in quiet and "DOC_LINK_OFFER_QUIET_MS" in quiet
    assert "docLinkOfferQuiet(text));" in js


def test_the_open_suggestions_panel_is_redrawn_at_most_every_400ms_while_typing():
    # 36 keys in a 58,000-character document with the panel open: 26 redraws of the
    # rows and 15 s of long tasks at 4x (DC3).
    js = frontend_text("documents.js")
    soon = _between(js, "function docProsePanelSoon() {", "function renderDocProsePanel() {")
    assert "docCmView?.hasFocus" in soon  # a click in the panel is not typing: at once
    assert "DOC_PROSE_PANEL_GAP_MS" in soon and "clearTimeout(soon.timer)" in soon
    render = _between(js, "function renderDocProse(", "function docProsePanelSoon() {")
    assert "docProsePanelSoon();" in render and "renderDocProsePanel();" not in render


def test_the_library_bundle_is_not_fetched_at_boot_or_by_the_password():
    # 103 scripts and 6.5 MB decoded in the first nine seconds on a tab that opened
    # nothing; now 85 and 3.6 MB. Typing the password is on the lock screen.
    js = frontend_text("app.js")
    warm = _between(frontend_text("lazy-entries.js"), "function warmLibraryAfterInput() {", "warmLibraryAfterInput();")
    assert 'event.target?.closest?.("#lock-overlay")' in warm
    # INBOX 1516: one file at a time, in a lull after the last press (not one idle
    # callback that ran all twenty scripts in a press's frames).
    assert "setTimeout(warmNext" in warm
    assert "lazyScript(files.shift())" in warm
    assert "LAZY_MODULES.library" in warm
    boot = next(row for row in js.splitlines() if '"dragEdge", "search"' in row and "setTimeout" in row)
    assert "library" not in boot


def test_a_format_turn_scale_and_fit_over_a_selection_save_once():
    # Turning 360 selected items sent 361 PUTs, fitting 98 (audit 1031 BD2).
    fmt = frontend_text("whiteboard-format.js")
    for start, end in (
        ("async function wbFmtApply(field, patch, said) {", "//: The selection's box"),
        ("async function wbFmtScaleSelection(", "//: A card, text box or picture turns"),
        ("function wbTurnSelection(degrees = 90) {", "//: One shape grown until"),
        ("function wbAutoSizeSelection() {", ".then(() => wbScheduleRender())"),
    ):
        body = _between(fmt, start, end)
        assert "await wbSaveMany(saves);" in body, start
        for single in ("await wbSaveNode(", "await wbSaveObject(", "await wbSaveSketchD(", "await wbSaveSketchProps("):
            assert single not in body, (start, single)
    assert "function wbSketchSetProps(sketch, partial) {" in frontend_text("whiteboard.js")
