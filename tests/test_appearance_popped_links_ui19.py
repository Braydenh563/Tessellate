"""Source text: "Finish the Appearance panel leftovers: deep links, door, search, peek."

L-ui-modernisation-19, from appearance-1435.md: "Deep links while popped out
... lands on Settings' 'Appearance is open in its own panel' note, not on the
control; it should focus the control in the panel" and "Settings' search index
... while the panel holds them they find nothing in Settings. Searching a
setting while popped out should open the panel at that setting." Driven at
1440: a link to #ui-motion-toggle and a search for "motion" both focus the
control inside the panel's visible body with Settings closed."""

from tests._app_js import frontend_text

JS = frontend_text("settings.js")
FIND = frontend_text("settings-find.js")


def _body(name: str, text: str = JS) -> str:
    start = text.index(name)
    return text[start : start + 2400]


def test_a_link_into_appearance_lands_in_the_panel_before_the_window_opens() -> None:
    body = _body("async function openSettingsModal(")
    popped = body.index('classList.contains("appearance-popped-out")')
    assert popped < body.index("surfaceBuild(\"settings\")")
    assert "openSettingRow({ el: found, section })" in body[popped:]


def test_the_search_reads_the_panel_and_opens_a_row_there() -> None:
    scan = _body("function settingRowsScan()", FIND)
    assert '"#settings-modal .settings-section, .appearance-panel-body"' in scan
    row = _body("function openSettingRow(row)", FIND)
    assert 'row.el.closest(".appearance-panel-body")' in row
    assert "closeSettingsModal()" in row
