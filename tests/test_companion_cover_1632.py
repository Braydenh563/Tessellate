"""INBOX 1632 (the owner): "the companion is hidden while the settings is
minimised". A minimised panel keeps its overlay open (`data-panel-min`,
panel-movable.js), so the cover check read it as a modal and hid the
companion. A minimised panel is a pill in the tray, not a cover."""

from __future__ import annotations

from tests._app_js import frontend_text

AV = frontend_text("avatars.js")
PM = frontend_text("panel-movable.js")


def test_a_minimised_panel_is_not_a_cover():
    check = AV[AV.index("function nameMarkBuddyCoverCheck(") :].split("\n}\n")[0]
    assert "dialog[open]:modal:not([data-panel-min])" in check
    assert ".modal-overlay:not(.hidden):not([data-panel-min])" in check


def test_minimise_and_restore_queue_the_check():
    assert 'host.setAttribute("data-panel-min", "")' in PM
    assert 'host.removeAttribute("data-panel-min")' in PM
    assert 'attributeFilter: ["class", "open", "data-panel-min"]' in AV
