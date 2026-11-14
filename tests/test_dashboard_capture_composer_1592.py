"""INBOX 1592: the dashboard's Quick capture is the Notes tab's composer, not a second one.

The owner: "should you improve the quick capture widget to be like the quick
capture section at the top of your notes page?" Decision (taken): one
composer. The dashboard card makes a copy of the Notes tab's bar
(`newCaptureBar`), the card opens in place from either bar (`openCaptureCard`
moves the one card into the bar that was used), and the old textarea and its
own save code are gone. These are the guards for that: grep-based, because the
module has to stay the only one; the end-to-end save is
tests-e2e/specs/capture-filing.spec.js.
"""

from __future__ import annotations

from tests._help_text import help_more_text
import re
from pathlib import Path

from tests import _js_scope
from tests._css_paths import FORMER_08

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = ROOT / "frontend" / "css"


def _js(name: str) -> str:
    #: a lazy script like capture-card.js is one closure now (ranked row 37a); the tests slice or run its private functions, so they read it as it was before it was wrapped (`_js_scope.unwrapped`): same code, same assertions.
    return _js_scope.unwrapped((JS / name).read_text(encoding="utf-8"))


def _css(name: str) -> str:
    return re.sub(r"/\*.*?\*/", "", (CSS / name).read_text(encoding="utf-8"), flags=re.S)


def _function(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    return source[start : source.index("\n}\n", start)]


def test_the_dashboard_card_mounts_the_notes_bar_and_has_no_composer_of_its_own():
    body = _function(_js("dashboard.js"), "renderQuickCaptureWidget")
    # the copy of the Notes bar is made here, in the lazy file, and wired by notes-list.js's `captureBar`
    # (it moved out of the boot file to keep the app scripts under their gzip ratchet)
    assert "captureBar(bar)" in body and 'removeAttribute("id")' in body
    for old in ("textarea", "createNoteSafely", "smallButton", "Ctrl+Enter", "apiJson", "watchFiling", "loadEntries"):
        assert old not in body, f"the dashboard card still has its own {old}"


def test_one_save_path_for_a_composed_note_and_it_is_the_cards():
    # `createNoteSafely` is how a quick note goes in (quick-note.js); the dashboard calls it nowhere.
    assert "createNoteSafely(" not in _js("dashboard.js")
    card = _js("capture-card.js")
    assert card.count("createNoteSafely(") == 1 and "async function saveCaptureCard(" in card
    assert "Ctrl+Enter" in card and 'event.key === "Enter" && (event.ctrlKey || event.metaKey)' in card


def test_both_bars_are_wired_by_the_same_function():
    notes = _js("notes-list.js")
    bar = _function(notes, "captureBar")
    assert 'if ($("capture-bar")) captureBar($("capture-bar"));' in notes
    assert "openCaptureCard(event.target, event.type)" in bar
    assert 'typeof captureCard !== "undefined"' in bar and "captureCard.adopt(bar)" in bar


def test_the_card_has_no_idea_which_bar_it_is_in():
    card = _js("capture-card.js")
    assert '$("capture-bar")' not in card and '$("capture-bar-input")' not in card
    assert "captureCard.host" in card and 'closest?.(".capture-bar")' in _function(card, "openCaptureCard")
    place = card[card.index("captureCard.place = ") : card.index("captureCard.adopt = ")]
    assert "host.append(captureCard.root)" in place and "keepCaptureDraft();" in place


def test_a_dashboard_redraw_while_the_card_is_open_hands_it_to_the_new_bar():
    card = _js("capture-card.js")
    adopt = card[card.index("captureCard.adopt = ") : card.index("captureCard.settle = ")]
    assert "captureCard.root.isConnected" in adopt and "captureCard.place(host)" in adopt and "restoreCaptureDraft()" in adopt


def test_the_colour_row_is_one_line_and_none_is_not_alone_on_one():
    css = _css("capture-card-lazy.css")
    row = "\n".join(b for s, b in re.findall(r"(?:(?<=[{}])|\A)([^{}]+)\{([^{}]*)\}", css) if ".capture-card-colours .swatch-picker" in s)
    assert "display: flex" in row and "flex-wrap: nowrap" in row and "overflow-x: auto" in row
    assert "grid-template-columns" not in row, "a grid row put None on its own line (it spans every column)"


def test_the_card_sits_in_the_dashboard_card_flow_not_over_what_is_below():
    assert re.search(r"\.dash-widget \.capture-card \{[^}]*position: static", _css("capture-card-lazy.css"))
    assert re.search(r"\.dash-widget \.capture-bar\.is-open \.capture-bar-row \{[^}]*display: none", "\n".join(_css(n) for n in FORMER_08))


def test_atlas_is_asked_to_step_aside_when_the_card_changes_its_box():
    card = _js("capture-card.js")
    settle = card[card.index("captureCard.settle = ") : card.index("function captureCardEl(")]
    assert 'scrollIntoView({ block: "nearest" })' in settle and 'new Event("mm:controls-changed")' in settle
    # the card says so by event (avatars.js is a lazy bundle: no call, no typeof guard, no wake source)
    assert "queueNameMarkBuddyCheck" not in card and "ResizeObserver" not in card
    avatars = _js("avatars.js")
    assert 'document.addEventListener("mm:controls-changed", () => {\n  nameMarkBuddyIndexReset();\n  queueNameMarkBuddyCheck();' in avatars
    for name in ("setCaptureMode", "closeCaptureCard"):
        assert "captureCard.settle()" in _function(card, name), name
    more = _js("capture-card-more.js")
    for name in ("syncCaptureExtras", "renderCaptureSuggestions"):
        assert "captureCard.settle()" in _function(more, name), name
    assert "captureCard.settle()" in _function(_js("capture-stage.js"), "renderCaptureStage")


def test_the_guide_and_the_widget_list_say_what_the_card_is_now():
    guide = help_more_text()
    assert "same take-a-note bar as the top of" in guide
    assert "take-a-note bar" in _js("dashboard.js")


def test_the_e2e_spec_saves_a_to_do_from_the_dashboard_card():
    spec = (ROOT / "tests-e2e" / "specs" / "capture-filing.spec.js").read_text(encoding="utf-8")
    assert ".dash-widget .capture-bar" in spec and "- [ ] rail pass printout" in spec
