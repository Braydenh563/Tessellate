"""INBOX 1465 (the owner's lag log, 2026-10-31): a key, a scroll and the boot
paid for geometry they never needed. Each test names the cost it keeps out."""

from tests._app_js import frontend_text


def _between(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i : text.index(end, i)]


def test_a_key_typed_in_a_field_returns_before_any_layout_read():
    # `activeOverlay()` is a getClientRects() per dialog: 158 to 314 ms of forced
    # layout on a dashboard keydown. The typing guard now returns first.
    js = frontend_text("settings-wiring.js")
    handler = js[js.index("const typingBurst = { at: 0 };") :]
    handler = handler[: handler.index('document.addEventListener("pointerdown"')]
    guard = handler.index('if (e.key !== "Escape") return;')
    assert guard < handler.index("activeOverlay()", handler.index("const el = document.activeElement;"))
    assert "el.isContentEditable" not in handler and "activeElement?.isContentEditable" not in handler
    assert "inEditable(el)" in handler


def test_the_overlay_test_waits_for_a_matching_bare_key():
    js = frontend_text("settings-wiring.js")
    loop = _between(js, "if (!burst && singleKeys && !boardOwns) {", "e.preventDefault();")
    assert loop.index("matchesShortcut(e, def.keys)") < loop.index("activeOverlay()")
    assert "dialog[open]" in loop and "break;" in loop


def test_editable_is_read_from_markup_not_from_style():
    js = frontend_text("settings-wiring.js")
    body = _between(js, "const inEditable = (el) =>", "\n")
    assert "closest" in body and "isContentEditable" not in body


def test_scroll_top_button_hears_only_its_own_scroller():
    # Capture hears every scroller; the timeline's list alone woke it 20 times a second.
    js = frontend_text("navigation.js")
    block = _between(js, "const scheduleUpdate = () => {", "window.addEventListener(\"resize\"")
    assert "e.target === scrollTopTargetEl()" in block
    assert block.count("scheduleUpdate()") == 1


def test_the_constellation_reads_its_width_from_the_observer_entry():
    js = frontend_text("dashboard.js")
    resync = _between(js, "const resync = (entries) => {", "const observer = new ResizeObserver(resync);")
    assert "entries?.[0]?.contentRect.width" in resync
    assert resync.index("contentRect") < resync.index("holder.clientWidth")


def test_a_closed_select_menu_builds_no_rows_at_boot():
    # 117 selects at boot: rows are built on open (the opener's click rebuilds).
    js = frontend_text("sheets-selects.js")
    body = _between(js, "function enhanceSelect(select) {", "\ndocument.addEventListener(\"dblclick\"")
    assert "wireMenuKeyboard(menu, opener);\n  syncValue();" in body


def test_a_select_with_a_name_never_clones_its_label():
    js = frontend_text("sheets-selects.js")
    body = _between(js, "const named =", "const label =")
    assert body.index('select.getAttribute("aria-label")') < body.index("select.labels")
    assert "named ? null :" in body


def test_the_keyboard_inset_is_not_written_at_init():
    # `innerHeight` at boot forced the whole page's first layout; 0px is the stylesheet's own.
    js = frontend_text("phone-shell.js")
    body = _between(js, "function initKeyboardInset() {", "const fieldSelector")
    assert 'viewport.addEventListener("scroll", write);\n  write();' not in body
