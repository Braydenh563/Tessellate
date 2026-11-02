"""A tab press reads no layout it has just dirtied (INBOX 1534, second pass).

Measured at 4x CPU with `scratchpad/ui-sweeps/tabstyle1102.js` (the stack of
every forced style or layout pass in a press): the Dashboard press paid 21ms
of style and 14 of layout in `syncEdgeFade` and 60ms in `currentAccentHex`;
the Library press 101 to 130ms in the scroll-top button's `scrollTop` read and
93ms in the tab bar's glide `place`. Each is now told by an observer, which
reports after layout, or reads nothing."""

from __future__ import annotations

from tests._app_js import frontend_text


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
    assert "new ResizeObserver(() => syncEdgeFade(bar)).observe(bar)" in wire
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
