"""INBOX 1415 (speed and smoothness): the forced layouts the owner's lag log
named stay out. Source-shape pins; the measured numbers are in HISTORY.md
("Moved from the plans", INBOX 1415)."""

from __future__ import annotations

import re

from _app_js import frontend_text


def _body(js: str, head: str) -> str:
    start = js.index(head)
    return js[start : js.index("\n}\n", start)]


def test_a_zoom_keypress_writes_one_property_and_reads_no_layout():
    """Ctrl+plus used to run all of `applyAppearance`, whose font probe
    (`measureLabelOptics`) is a forced layout, on every repeat."""
    panes = frontend_text("settings-panes.js")
    zoom = _body(panes, "function setZoom(")
    assert "applyAppearance" not in zoom
    assert "requestAnimationFrame" in zoom and "applyZoomVar()" in zoom
    settings = frontend_text("settings.js")
    assert 'function applyZoomVar() {' in settings
    assert "applyZoomVar();" in _body(settings, "function applyAppearance(")


def test_the_font_probe_is_measured_again_only_when_its_answer_can_change():
    settings = frontend_text("settings.js")
    probe = _body(settings, "function measureLabelOptics(")
    assert "labelOpticsKey" in probe and "force !== true" in probe


def test_the_dashboard_map_card_is_sized_from_the_observer_entry():
    src = frontend_text("dash-boards.js")
    body = _body(src, "function dashMapFeature(")
    assert "contentRect.width" in body
    assert "lastHeight" in body
    assert "requestAnimationFrame(size)" not in body


def test_ocr_words_are_read_together_then_written_together():
    lib = frontend_text("library.js")
    body = _body(lib, "function ocrFitLiveText(")
    last_read = body.rindex("getBoundingClientRect")
    first_write = body.index("setProperty")
    assert last_read < first_write, "a write between two reads is a layout per word"


def test_a_pinch_zooms_once_per_frame():
    lib = frontend_text("library.js")
    start = lib.index('$("ocr-page-pane")?.addEventListener("wheel"')
    wheel = lib[start : lib.index("{ passive: false });", start)]
    assert "ocrWheelPending" in wheel and "requestAnimationFrame" in wheel
    assert wheel.count("ocrZoomAbout(") == 1


def test_emblem_slots_are_asked_before_any_is_drawn():
    shell = frontend_text("phone-shell.js")
    body = _body(shell, "function renderBrandLogo(")
    asks = [m.start() for m in re.finditer(r"getClientRects", body)]
    draws = [m.start() for m in re.finditer(r"renderEmblemWhenShown\(", body)]
    assert asks and draws and max(asks) < min(draws)


def test_the_toast_yield_skips_buttons_the_page_has_not_drawn():
    """188 layouts and 1.4 s (4x CPU) on Settings, Help: each button inside a
    `content-visibility` window that was skipped was laid out alone."""
    status = frontend_text("status.js")
    body = _body(status, "function toastYield(")
    assert "checkVisibility({ contentVisibilityAuto: true })" in body
    assert body.index("checkVisibility") < body.index("getBoundingClientRect()", body.index("rects ||="))
