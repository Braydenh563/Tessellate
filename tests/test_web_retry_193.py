"""L-chat-193 (the owner: "there should be a retry button for failed web searches and/or a button to auto retry when
searxng or another engine is available"): a failed web step in a chat turn carries Try again (a search runs again in
the web panel, a page is fetched again), a down SearXNG carries the start row that runs the search itself once the
engine answers (`tests/test_searxng_auto_retry_l167.py`), and the panel's own failed search has its retry."""

from __future__ import annotations

from tests._app_js import frontend_text

KIT = frontend_text("answer-kit.js")
RESULTS = frontend_text("web-results.js")


def test_a_failed_search_or_page_in_a_turn_has_try_again():
    start = KIT.index("function toolChip(")
    body = KIT[start : KIT.index("\n}\n", start)]
    assert 'event?.tool === "web_search" ? "query" : event?.tool === "read_url" ? "url"' in body
    assert "!ok && webTool && event.reason !== \"searxng_down\"" in body
    assert "runWebSearch()" in body and "/websearch/stored/refetch" in body


def test_a_down_engine_gets_the_row_that_retries_when_it_answers():
    assert 'event?.reason === "searxng_down"' in KIT and "searxngDownRow()" in KIT
    assert "watchSearxngReady(row, retry);" in RESULTS and 'now?.state === "running" && now.responding' in RESULTS


def test_the_panels_own_failed_search_has_a_retry():
    assert 'smallButton("ph:arrow-clockwise Try again", "Search again", () => runWebSearch())' in RESULTS
