"""Audit 1031 perf class rows (ranked 16 to 55): each test names the cost it keeps out."""

from tests._app_js import frontend_text


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
    js = frontend_text("app-palette.js")
    draw = _between(js, "function paletteDrawRows(upTo) {", "function renderPalette(query) {")
    assert "addEventListener" not in draw
    render = _between(js, "function renderPalette(query) {", "$(\"palette-list\").addEventListener(\"click\"")
    assert "addEventListener" not in render
    assert "paletteDrawRows(Math.max(PALETTE_WINDOW" in render
    assert 'closest?.("li[data-index]")' in js
    assert "const PALETTE_WINDOW = 24;" in js


def test_a_palette_key_is_not_a_match():
    # keydown matched the whole catalogue before the input event matched it again.
    js = frontend_text("app-palette.js")
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
    assert 'dataset.opened = String(performance.now())' in frontend_text("app-palette.js")


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
