"""INBOX 1688 (c): the desktop companion's Quick note is the dashboard Quick capture's card.

One card, three hosts: the Notes tab's bar, the dashboard widget and now the desk panel. The
panel does not carry a textarea of its own; it opens `capture-card.js` into `#desk-capture` and
answers the two functions the card saves through. Measured in a browser (desk panel 296 px wide
card against the dashboard's 306): the same title, words, tags, Note and To-do, Close and Save,
with the same computed colours, radius and font."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "frontend" / "desktop-companion.html").read_text(encoding="utf-8")
DESK = (ROOT / "frontend" / "js" / "desk-companion.js").read_text(encoding="utf-8")
ENV = (ROOT / "frontend" / "js" / "desk-env.js").read_text(encoding="utf-8")
CARD_CSS = (ROOT / "frontend" / "css" / "capture-card-lazy.css").read_text(encoding="utf-8")
SHELL_CSS = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")


def test_the_panel_hosts_the_capture_card_not_a_textarea_of_its_own():
    note = HTML.split('id="desk-note"')[1].split('id="desk-search"')[0]
    assert 'id="desk-capture" class="capture-bar"' in note
    for gone in ("<textarea", "desk-note-text", "desk-note-save", "Shift+Enter"):
        assert gone not in note, gone


def test_the_card_is_fetched_as_the_app_fetches_it_and_runs_on_its_core():
    assert '{ captureCard: ["/css/capture-card-lazy.css", "/js/att-chip.js", "/js/capture-card.js"] }[name]' in ENV
    # the pickers and menus of its second file are the app's: not here (its staging file is)
    assert 'file === "/js/capture-card-more.js" ? Promise.resolve(false) : load(file)' in ENV
    assert "/js/capture-card" not in HTML, "the card is lazy here too"


def test_the_card_saves_through_this_windows_own_request_and_undo():
    assert "createNoteSafely: createNote" in DESK and 'call("/entries", "POST"' in DESK
    assert "announceSavedNote: announceSaved" in DESK
    assert 'standaloneUndo.announce(made, "Captured a note")' in DESK and "standaloneUndo.offer(" in DESK
    assert 'openCaptureCard($("desk-capture"), "focusin")' in DESK


def test_close_and_escape_take_the_panel_with_the_card_and_its_height_is_followed():
    assert "[data-cc=\"close\"]" in DESK and 'event.key === "Escape" && rest()' in DESK
    assert 'document.addEventListener("mm:controls-changed", fit)' in DESK
    assert re.search(r"note: \[\d+, (4[5-9]\d|[5-9]\d\d)\]", DESK), "the fixed window holds the whole card"


def test_the_desk_panel_gets_the_dashboard_cards_flat_recipe():
    assert re.search(r"\.desk-panel \.capture-card,\s*\.dash-widget \.capture-card \{[^}]*position: static", CARD_CSS)
    assert re.search(r"\.desk-panel \.capture-bar,\s*\.dash-widget \.capture-bar \{[^}]*border-top: 0", SHELL_CSS)
