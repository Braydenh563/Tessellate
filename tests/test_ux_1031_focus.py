"""Audit 1031 class 27: focus after acts and dialogs (SH2, SH5, BD13, DC11, GR6).

One pair, `focusBackTo` and `focusFirstIn` (sheets-selects.js), is what every dialog that is
not a sheet uses: an opener that is gone, hidden or `<body>` falls to a named
fallback, so a close never drops the page's focus on nothing."""

from __future__ import annotations
from tests._app_js import frontend_text

from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _src(name: str) -> str:
    return frontend_text(name) if name == "documents.js" else (JS / name).read_text(encoding="utf-8")


def test_the_pair_lives_in_app_js_and_skips_body_and_hidden_openers():
    app = _src("sheets-selects.js")
    body = app.split("function focusBackTo", 1)[1].split("function focusFirstIn", 1)[0]
    assert "document.body" in body and "getClientRects" in body and "inert" in body
    assert "function focusFirstIn(root, preferred = null)" in app


def test_notifications_take_focus_on_open_and_give_it_back_on_close():
    assert 'focusFirstIn(panel, ".notif-row button, #notif-close")' in _src("notifications.js")
    status = _src("status.js")
    close = status.split("function closeNotifications", 1)[1].split("\n}\n", 1)[0]
    assert 'focusBackTo($("notif-btn"))' in close


def test_every_overlay_closer_names_a_fallback():
    for name, fallback in (
        ("settings.js", '"#settings-btn"'),
        ("app-palette.js", "aria-selected='true'"),
        ("onboarding.js", "aria-selected='true'"),
        ("tour.js", "aria-selected='true'"),
    ):
        text = _src(name)
        assert "focusBackTo(" in text and fallback in text, name


def test_the_board_keys_sheet_returns_to_the_menu_that_opened_it():
    text = _src("whiteboard-commands.js")
    assert "wbHelpReturn.fallback" in text
    assert "focusBackTo(back, fallback)" in text


def test_the_graph_new_note_dialog_returns_focus_to_its_opener():
    text = _src("graph.js")
    assert "graphLate.newOpener = document.activeElement" in text
    assert 'focusBackTo(graphLate.newOpener, "#graph-add-node")' in text


def test_the_suggestions_chip_and_fix_all_say_what_they_count():
    text = _src("documents.js")
    assert "Fix all ${fixable.length.toLocaleString" in text
    assert '" in view"' in text and "nearby" not in text.split("docProse.hidden", 1)[1].split("chip.classList", 1)[0]
