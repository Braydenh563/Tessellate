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
    warm = find.index("(!topics.firstElementChild || topics.dataset.dropping)")
    # Before the matching, and only until they are drawn: an empty box is the mark (the drawing
    # fills it on success and writes a line on failure, so a failed fetch cannot loop). Leaving
    # Help empties it again (L676) instead of setting aria-busy by hand (test_spinner_recipe).
    assert warm < find.index("let matches = 0")
    assert "filterSettings(query)" in find[warm : find.index("let matches = 0")]


def test_leaving_help_and_closing_the_sheet_release_their_nodes() -> None:
    """L676: after Help was visited and the ? sheet opened and closed the page kept
    1,770 Help nodes and 240 shortcut rows. Both are drawn again on the next open:
    leaving the Help pane empties its topics (not while a search is typed, whose
    results point at them) and `closeShortcuts` dispatches `sheet-closed`, which
    the lazy reveal file answers by emptying the sheet's lists."""
    root = Path(__file__).resolve().parents[1] / "frontend" / "js"
    find = (root / "settings-find.js").read_text(encoding="utf-8")
    watch = find[find.index("function settingsIndexWatchSection(name)") :]
    watch = watch[: watch.index("lazyScript(")]
    for needle in (
        'name !== "help" && helpTopicsLoad',
        '!$("settings-search").value',
        "helpTopicsLoad = null;",
        "helpTopicsDrop(help);",
    ):
        assert needle in watch
    # Marked by emptiness (or `data-dropping` while the slices run), not a hand-set aria-busy.
    assert 'setAttribute("aria-busy"' not in watch
    wiring = (root / "settings-wiring.js").read_text(encoding="utf-8")
    close = wiring[wiring.index("function closeShortcuts()") :]
    assert 'document.dispatchEvent(new Event("sheet-closed"));' in close[: close.index("\n}\n")]
    reveal = (root / "reveal-targets.js").read_text(encoding="utf-8")
    assert 'document.addEventListener("sheet-closed"' in reveal
    assert 'overlay.querySelectorAll(".shortcut-list")' in reveal and "list.replaceChildren()" in reveal
    html = (root.parent / "index.html").read_text(encoding="utf-8")
    sheet = html[html.index('id="shortcuts-overlay"') :]
    assert sheet.count('class="shortcut-list"') >= 4, "every list the sheet draws is inside the overlay"
