"""Audit 1031 classes 29 and 30: contrast, legibility and accessible names.

Class 29 (UX4, AI16, SH19): `--text-xs` is a 12 px floor, not 11.2; an Ask chart
is drawn at its card's width so its axis text keeps its size (it measured 4.9 px
in a 306 px card); an off-canvas sidebar is `inert` below 600.
Class 30 (SH4, DC5, UX7, BD4): a name starts with the words drawn on the control."""

from __future__ import annotations

from tests._app_js import frontend_text
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"


def _js(name: str) -> str:
    return frontend_text(name) if name.startswith("whiteboard") else (JS / name).read_text(encoding="utf-8")


def test_the_smallest_text_token_is_twelve_pixels():
    tokens = (ROOT / "frontend" / "css" / "00-tokens-shell.css").read_text(encoding="utf-8")
    assert float(re.search(r"--text-xs:\s*([\d.]+)rem;", tokens).group(1)) * 16 >= 12


def test_every_ask_chart_follows_its_cards_width():
    text = _js("ask-chart.js")
    assert "function askChartFollow(host, chart, onRedraw" in text
    assert "else askChartFollow(host, chart);" in text
    assert "host._chartObserver?.disconnect();" in text


def test_a_parked_phone_sidebar_is_inert_without_an_observer():
    text = _js("sheets-selects.js")
    body = text.split("function syncSidebarInert()", 1)[1].split("\n}\n", 1)[0]
    assert "aside.inert = phone && !aside.classList.contains(\"sidebar-sheet-open\")" in body
    # Every open and close is one function, so nothing watches the class.
    assert "function setSidebarSheet(aside, open)" in text
    assert "MutationObserver(syncSidebarInert" not in text + _js("phone-shell.js")
    assert 'classList.remove("sidebar-sheet-open")' not in text + _js("phone-shell.js")
    assert 'classList.toggle("sidebar-sheet-open")' not in text


def test_the_reminders_tab_is_named_by_its_words_and_badge():
    assert 'button.setAttribute("aria-label", due ? `Reminders ${due}` : "Reminders");' in _js("shell-reminders.js")


def test_the_file_type_button_and_the_zoom_button_start_with_their_visible_words():
    assert 'opener.setAttribute("aria-label", `${type.label}, file type`);' in _js("documents.js")
    # Intent moved (INBOX 1694 b, 06678b49): the board's zoom is a typeable value field, an input whose
    # visible words are its value ("100%") and whose name says what it is; Ctrl+1 is still 100%.
    assert 'label: "Zoom percent",' in _js("whiteboard.js")
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert '<span id="wb-zoom-level" class="wb-zoom-level" title="Zoom level: type a number, or pick one. Ctrl+1 is 100%"></span>' in html


def test_a_colour_field_carries_no_popup_attributes():
    text = _js("whiteboard-format.js")
    assert 'input.setAttribute("aria-haspopup"' not in text
    assert "function wbWellExpanded(el, open)" in text and 'el.type !== "color"' in text


def test_a_library_group_heading_is_named_by_its_drawn_words_and_count():
    text = _js("library.js")
    assert 'heading.append(caret, contentsGroupMark(key), name, " ", count);' in text
    assert 'heading.setAttribute("aria-label", `${label}, ${total}`)' not in text
