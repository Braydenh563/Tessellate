"""A tab press reads no layout it has just dirtied (INBOX 1534, second pass).

Measured at 4x CPU with `scratchpad/ui-sweeps/tabstyle1102.js` (the stack of
every forced style or layout pass in a press): the Dashboard press paid 21ms
of style and 14 of layout in `syncEdgeFade` and 60ms in `currentAccentHex`;
the Library press 101 to 130ms in the scroll-top button's `scrollTop` read and
93ms in the tab bar's glide `place`. Each is now told by an observer, which
reports after layout, or reads nothing."""

from __future__ import annotations

from tests._app_js import frontend_text
from tests import _js_scope


def _body(text: str, head: str) -> str:
    start = text.index(head)
    return text[start:text.index("\n}\n", start)]


def test_the_kept_accent_is_keyed_on_what_sets_it_not_on_every_attribute():
    body = _body(frontend_text("settings.js"), "function currentAccentHex(")
    assert "getAttribute(n)" in body and 'root.style.getPropertyValue("--accent")' in body
    assert "MutationObserver" not in body, "a watcher forgot it on every class flip and on a late task"
    assert "[...root.attributes]" not in body, "data-motion and the density say nothing about the colour"


def test_the_theme_default_accent_ignores_attributes_that_do_not_set_it():
    body = _body(frontend_text("settings.js"), "function themeDefaultAccent(")
    assert '["data-palette", "data-mode", "data-theme"]' in body
    assert "root.attributes" not in body


def test_the_brand_logo_is_drawn_after_the_frame_that_asked():
    body = _body(frontend_text("phone-shell.js"), "function renderBrandLogo(")
    assert body.index("renderBrandLogo.queued") < body.index("afterFrames(() => setTimeout(")
    assert body.index("afterFrames(") < body.index("getElementById(id)")


def test_the_notes_scroller_is_found_once_not_per_render():
    body = _body(frontend_text("notes-list.js"), "function notesScroller(")
    assert "notesScroller.kept?.contains(list)" in body


def test_a_strip_is_measured_by_its_observer_not_where_it_is_wired():
    wire = _body(frontend_text("shell-reminders.js"), "function edgeFadeWire(")
    #: 1672 widened the observer to the status bar's zones; the bar is still one of the boxes it observes.
    assert "const seen = new ResizeObserver(() => syncEdgeFade(bar));" in wire
    assert "for (const box of [bar, " in wire and "seen.observe(box)" in wire
    assert "  syncEdgeFade(bar);\n  bar.addEventListener" not in wire


def test_the_scroll_top_button_reads_a_scroller_only_after_it_has_scrolled():
    js = frontend_text("navigation.js")
    body = js[js.index("const update = () => {"):js.index("const scheduleUpdate")]
    assert "scrolled.has(target) ? target.scrollTop : 0" in body
    assert "scrollHeight" not in body, "Chat never shows the button: its distance is not measured"
    assert "scrolled.add(e.target)" in js


def test_the_glide_is_placed_from_the_observers_report_not_a_timer():
    js = frontend_text("shell-reminders.js")
    glide = js[js.index("function glideStrip("):js.index("function syncEdgeFade(")]
    assert "sized.unobserve(strip);\n    sized.observe(strip);" in glide
    assert "setTimeout" not in glide


def test_a_dock_with_nothing_folded_is_not_written_to_before_it_is_read():
    fit = _body(frontend_text("phone-shell.js"), "function fitDock(")
    assert fit.index("dockTight(dock)) return") < fit.index("foldDockArrange(dock, false)")


def test_the_notes_strip_token_is_written_after_the_frame_not_in_the_observers_report():
    body = _body(frontend_text("phone-shell.js"), "function initNotesSubtabHeightToken(")
    assert 'setTimeout(() => page.style.setProperty("--notes-sticky-top", h))' in body


def test_a_sheet_or_the_palette_takes_focus_after_the_first_paint():
    """The focus settled the page the press had just changed, and its focus events read more
    (Guide 203ms, the agent palette 348 to 560ms at 4x)."""
    sheet = _body(frontend_text("phone-shell.js"), "function openSheet(")
    assert sheet.index("afterFrames(() => setTimeout(() => {") < sheet.index("target.focus?.()")
    assert "card.contains(document.activeElement)) return" in sheet
    palette = _body(frontend_text("palette.js"), "function toggleAgentPalette(")
    assert "afterFrames(() => setTimeout(() => cmdPaletteOverlay.classList.contains(\"hidden\") || cmdPaletteInput.focus()), 1)" in palette


def test_the_palette_gives_focus_back_and_a_panel_is_adopted_after_the_frame():
    back = frontend_text("router-overlays.js")
    assert "afterFrames(() => setTimeout(() => {\n      const active = document.activeElement;" in back
    assert 'overlay.classList.contains("hidden") && (!active' in back, "reopened in the gap, it keeps its own focus"
    movable = frontend_text("panel-movable.js")
    assert 'afterFrames(() => setTimeout(panelAdopt, 0, p), 1)' in movable


def test_the_companion_looks_for_a_popup_after_a_frame_has_drawn_the_press():
    src = frontend_text("avatars.js")
    i = src.index('for (const type of ["click", "keyup"])')
    block = src[i:i + 1400]
    # `nmb.afterClean`: a frame and a timer, and a frame more while the page is still written to (INBOX 1587).
    assert "nmb.afterClean(look)" in block
    assert "setTimeout(afterPaint, 80)" in block and "setTimeout(afterPaint, 700)" in block


def test_the_icon_picker_and_the_equation_pane_lay_out_after_the_frame_that_opened_them():
    """Placing the picker and focusing its search forced the layout of every tile inside the
    press (874ms at 4x); the Equation pane's first focus did the same (245ms)."""
    src = _js_scope.unwrapped(frontend_text("icon-picker.js"))
    open_at = src.index("  draw();\n  document.body.appendChild(panel);")
    block = src[open_at - 200:open_at + 900]
    # Intent moved (INBOX 1716, the owner's log: "icon-picker.js BUTTON.onclick 196ms (forced layout 189ms)"): a read
    # before draw() is only clean when the press wrote nothing; the anchor is now read after the frame, beside the placing.
    assert block.index("afterFrames(() => setTimeout(() => {") < block.index("getBoundingClientRect") < block.index("placeHelpPopover(panel, anchor)"), "the anchor is read after the frame, never inside the press"
    assert block.index("afterFrames(() => setTimeout(() => {") < block.index("placeHelpPopover(panel, anchor)")
    assert block.index("placeHelpPopover(panel, anchor)") < block.index("search.focus({ preventScroll: true })")
    assert 'panel.style.visibility = "hidden"' in block
    math = frontend_text("math-editor.js")
    assert "afterFrames(() => setTimeout(() => host.isConnected && pane.start()), 1)" in math


def test_the_companions_tempo_does_not_flush_style_while_a_popup_is_arriving():
    """`getAnimations` flushes all the style a press has dirtied (nameMarkBuddyTempo, 306ms at 4x),
    so the once-a-second refresh waits out the arrival window the picker and the tabs open."""
    src = frontend_text("avatars.js")
    body = _body(src, "function nameMarkBuddyTempo(")
    assert "now - nmbTempo.seen > 1000 && now >= (window.uiSettlingUntil || 0)" in body
    assert "window.uiSettlingUntil = performance.now() + 400;" in _js_scope.unwrapped(frontend_text("icon-picker.js"))
