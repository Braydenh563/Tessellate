"""Source text: a scrolling tab strip brings the focused tab fully into view,
and strips in surfaces built after boot are wired too (L419).

Measured at 390: the Library sub-tabs, built from their template on first
visit, had no fade and no reveal (`fadeWired` unset), and keyboard focus left
Images half shown, its ring 15px past the strip's edge. After: the strip is
wired, Tab scrolls each tab in, and no ring in the header, the Library tabs
or the chat composer crosses an edge (0 of 6, 0 of 9, 0 of 3).
"""

from __future__ import annotations

from tests._app_js import frontend_text


def test_focus_reveals_the_tab_as_a_click_does():
    source = frontend_text("shell-reminders.js")
    wire = source[source.index("function edgeFadeWire(bar) {") :]
    wire = wire[: wire.index("\n}\n")]
    assert 'for (const type of ["click", "focusin"]) bar.addEventListener(type, reveal);' in wire


def test_a_surface_built_later_wires_its_strips():
    source = frontend_text("settings-body.js")
    build = source[source.index("function surfaceBuild(name) {") :]
    build = build[: build.index("\n}\n")]
    assert 'host.querySelectorAll?.(".edge-fade")' in build and "edgeFadeWire" in build
