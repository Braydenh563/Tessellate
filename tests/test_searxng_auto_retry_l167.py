"""L167 and L-chat-20: a failed web search goes again once, by itself, when SearXNG answers."""

from tests._app_js import frontend_text

JS = frontend_text("web-results.js")


def test_the_down_row_watches_the_engine_and_retries_once():
    assert "watchSearxngReady(row, retry);" in JS
    assert "if (retried) return;" in JS
    row = JS[JS.index("async function searxngDownRow") :]
    assert row.count("retry()") >= 1 and "onRunning();" in row


def test_the_watch_ends_with_the_row_and_after_ten_minutes():
    watch = JS[JS.index("function watchSearxngReady") :].split("\n  }\n", 1)[0]
    assert "!row.isConnected" in watch and "600000" in watch
    assert 'now?.state === "running" && now.responding' in watch
