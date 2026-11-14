"""L-chat-58 (INBOX 1743): the Ask tab as a smart browser. Slice 1: thread chips
filter Matching records. The behaviour is measured by
scratchpad/ui-sweeps/askbrowser58.js; these hold the shape."""

from __future__ import annotations

import re
from pathlib import Path

from tests import _js_scope

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"
BROWSER = _js_scope.unwrapped((JS / "ask-browser.js").read_text(encoding="utf-8"))
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "ask-compose-lazy.css").read_text(encoding="utf-8")


def test_the_chip_row_sits_above_the_records_and_is_not_an_act():
    row = HTML.index('id="ask-threads"')
    assert HTML.index('id="raw-results"') > row > HTML.index('id="ask-records-fold"')
    assert 'role="group"' in HTML[row - 120 : row + 200]


def test_a_thread_is_a_counted_filter_chip():
    body = BROWSER.split("function askThreadChip(", 1)[1].split("\n  }\n", 1)[0]
    assert 'chip(label, "tag graph-filter-chip", onClick)' in body
    assert "library-chip-count" in body and "aria-pressed" in body


def test_the_bundle_loads_it_after_ask_compose_and_answer_kit_calls_it():
    app = (JS / "app.js").read_text(encoding="utf-8")
    assert re.search(r'askCompose: \[[^\]]*"/js/ask-compose\.js", "/js/ask-browser\.js"\]', app)
    kit = (JS / "answer-kit.js").read_text(encoding="utf-8")
    assert "digestMore.threads(support.threads)" in kit


def test_a_press_filters_with_a_class_and_the_heading_says_n_of_m():
    assert 'classList.toggle("hidden"' in BROWSER and "of ${" in BROWSER
    assert "style." not in BROWSER
    assert 'id="ask-records-shown"' in HTML


def test_the_chip_row_has_its_own_rules_and_no_hairline_box():
    assert ".ask-threads" in CSS
