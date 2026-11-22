"""The Web panel says SearXNG is stopped when it opens, not after a search
fails, and a failed search's ways out share the field's left edge (the owner
2026-11-22: "nothing tells the user that SearXNG isn't running until a search
fails"; Try again and Start SearXNG "start at different x positions").

Measured in the running app by `scratchpad/ui-sweeps/websearxngoff.js`; these
pin the shape that measurement depends on."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = (ROOT / "frontend" / "css" / "03-dashboard-widgets.css").read_text(encoding="utf-8")


def _fn(name: str, text: str) -> str:
    """The function's text, to its closing brace at its own indent."""
    start = text.index(f"function {name}(")
    line = text.rindex("\n", 0, start) + 1
    indent = text[line:start].replace("async ", "")
    end = text.index(f"\n{indent}}}\n", start)
    return text[start:end]


def test_the_status_refresh_draws_the_engine_notice_on_every_path():
    panel = (JS / "web-panel.js").read_text(encoding="utf-8")
    refresh = _fn("refreshWebSearxngStrip", panel)
    # Defined inside it (no new shared-scope name), then called once where no
    # backend can run it (cleared) and once with the state.
    assert refresh.count("renderWebEngineNotice(") == 3


def test_the_notice_is_the_notice_recipe_above_the_field_with_the_dots_words():
    panel = (JS / "web-panel.js").read_text(encoding="utf-8")
    body = _fn("renderWebEngineNotice", panel)
    assert '"notice web-engine-notice"' in body
    assert '.web-search-field").before(notice)' in body
    assert "webEngineWords(state, provider)" in body
    # Stopped offers Start; DuckDuckGo and absent draw nothing here.
    assert 'state === "stopped" || state === "starting"' in body
    assert 'provider !== "duckduckgo"' in body
    assert 'ensureModule("webClip").then(() => setWebSearxngRunning(true))' in body


def test_a_failed_search_is_a_message_then_one_row_of_actions():
    results = (JS / "web-results.js").read_text(encoding="utf-8")
    body = _fn("runWebSearch", results)
    assert 'status.replaceChildren(message, actions)' in body
    assert "actions.append(row)" in body
    # The old shape put Try again in the message's line and Start on a row of its own.
    assert "status.append(row)" not in body


def test_the_actions_row_is_pulled_back_like_the_toasts():
    rule = re.search(r"\.web-status-actions \{([^}]*)\}", CSS)
    assert rule and "margin-inline-start: calc(var(--space-2) * -1)" in rule.group(1)
    assert re.search(r"\.web-status-actions button \{\s*padding-inline: var\(--space-2\);", CSS)
    # An empty progress line must not take a gap before Start.
    assert re.search(r"\.searxng-down-line:empty \{\s*display: none;", CSS)
