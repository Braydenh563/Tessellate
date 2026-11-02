"""Audit 1029 row 38 (X15, H12): Settings built its Help topics on every open.

The 191 topic rows are about 2,040 nodes, drawn into a pane nobody was looking
at (the modal went from 3,290 to 5,330 nodes, and the page kept them after
Settings closed). They are drawn when Help is shown or when Settings is
searched (the topics are findable settings). Numbers are in the commit, from a
Playwright run; these are source pins for where the call sits.
"""

from __future__ import annotations

from pathlib import Path

JS = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "settings.js").read_text(encoding="utf-8")


def _body(name: str) -> str:
    start = JS.index(f"function {name}(")
    return JS[start : JS.index("\n}\n", start) + 2]


def test_opening_settings_no_longer_draws_the_help_topics() -> None:
    assert "renderHelpTopics" not in _body("openSettingsModal")


def test_showing_help_draws_them() -> None:
    show = _body("showSettingsSection")
    # `window.x?.()`, not a typeof guard: the guard count only falls
    # (test_global_scope_ratchet). The intent is unchanged.
    assert 'if (name === "help") window.renderHelpTopics?.();' in show


def test_the_first_search_draws_them_and_asks_again() -> None:
    find = _body("filterSettings")
    warm = find.index('$("help-topics")?.hasAttribute("aria-busy")')
    # Before the matching, and only until they are drawn (the drawing clears aria-busy
    # on success and on failure, so a failed fetch cannot loop).
    assert warm < find.index("let matches = 0")
    assert "filterSettings(query)" in find[warm : find.index("let matches = 0")]
