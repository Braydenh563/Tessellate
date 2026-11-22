"""L-chat-58 (INBOX 1743): the Ask tab as a smart browser. Slice 1: thread chips
filter Matching records. The behaviour is measured by
scratchpad/ui-sweeps/askbrowser58.js; these hold the shape."""

from __future__ import annotations

import re
from pathlib import Path

from tests import _js_scope
from tests._app_js import index_html_text

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"
BROWSER = _js_scope.unwrapped((JS / "ask-browser.js").read_text(encoding="utf-8"))
HTML = index_html_text()
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


# --- slice 2: Around this note ----------------------------------------------------------

KIT = _js_scope.unwrapped((JS / "reply-kit.js").read_text(encoding="utf-8"))


def test_an_ask_card_gains_around_this_note_and_chat_cards_do_not():
    body = KIT.split("function replyRecordCards(", 1)[1][:9000]
    assert "Around this note" in body and 'list.id !== "raw-results"' in body
    assert "digestMore.around(li, button)" in body


def test_the_neighbourhood_is_linked_and_similar_rows_under_the_card_never_cards():
    body = BROWSER.split("function around(", 1)[1].split("\n  }\n", 1)[0]
    assert "/entries/${id}/connections" in body and "/entries/${id}/related" in body
    assert "connectionRowEl(" in body and 'lazyScript("/js/connections.js")' in body and "ask-around" in body
    assert "data-id" not in body and "dataset.id =" not in body  # a row is not a Matching records card
    assert "aria-expanded" in body


def test_the_neighbourhood_is_indented_one_step_by_a_token():
    rule = re.search(r"\.ask-around \{([^}]*)\}", CSS)
    assert rule and "margin-inline-start: var(--space-4)" in rule.group(1)


# --- slice 3: the trail and Back ---------------------------------------------------------

OVERLAYS = (JS / "router-overlays.js").read_text(encoding="utf-8")


def test_the_trail_is_the_breadcrumb_recipe_with_a_back_arrow_above_the_chips():
    nav = HTML.index('id="ask-browse-trail"')
    assert HTML.index('id="ask-records-fold"') < nav < HTML.index('id="ask-threads"')
    block = HTML[nav - 40 : nav + 600]
    assert "doc-crumbs" in block and 'aria-label="Where you are' in block
    assert "doc-crumbs-list" in block and "data-holds-notebook" in block
    assert 'id="ask-browse-back"' in block and 'aria-label="Back one step"' in block


def test_the_trail_is_answer_then_thread_then_note_and_a_step_pops_the_ones_after_it():
    body = BROWSER.split("function steps(", 1)[1].split("\n  }\n", 1)[0]
    assert '"Answer"' in body and "browse.lit" in body and "browse.note" in body
    assert 'aria-current' in BROWSER and "doc-crumb" in BROWSER


def test_the_browsers_back_pops_one_step_through_router_overlays_without_a_new_global():
    hook = OVERLAYS.split("function routerBackHook(", 1)[1].split("\n}\n", 1)[0]
    assert "routerBack.browse" in hook
    assert "const routerBrowse" not in OVERLAYS
    assert "routerBack.browse = " in BROWSER and "history.pushState(" in BROWSER


def test_every_step_rewinds_what_it_pushed_so_in_app_back_keeps_its_count():
    body = BROWSER.split("function syncHistory(", 1)[1].split("\n  }\n", 1)[0]
    assert "history.go(-" in body and "browse.swallow" in body


def test_reload_keeps_the_answer_not_the_trail():
    assert "sessionStorage" not in BROWSER and "localStorage" not in BROWSER
