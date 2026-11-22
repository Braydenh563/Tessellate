"""The graph repaints on a theme change.

Toggling light and dark left node outlines and label chips in the old theme: `gcReadTokens` ran only when a map was rendered, and every
cache (the scene, the label copy, each node's sprite) is keyed on the
*identity* of `gcTokens`, which never changed. The fix re-reads on the
app's own theme announcement (`refreshArtForTheme`, which the toggle, the OS
scheme and a palette all reach) and hands out a new tokens object, so each cache
misses once, then redraws once. No polling, no per-frame style read.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAPH = (ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8")


def test_tokens_are_replaced_not_mutated_on_a_theme_change() -> None:
 assert re.search(r"\blet gcTokens\b", GRAPH), "identity must be able to change"
 fn = GRAPH[GRAPH.index("function gcThemeChanged") :][:1500]
 assert "gcTokens = {}" in fn and "gcReadTokens(" in fn
 assert "gcSpriteCache.clear()" in fn
 assert "gcRequestDraw(" in fn


def test_the_app_announcement_of_a_theme_change_reaches_the_graph() -> None:
    dashboard = (ROOT / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")
    assert re.search(r"function refreshArtForTheme\(\) \{[^}]*window\.gcThemeChanged\?\.\(\)", dashboard, re.S)
    assert "gcThemeChanged" in GRAPH and "MutationObserver" not in GRAPH
    settings = (ROOT / "frontend" / "js" / "settings.js").read_text(encoding="utf-8")
    assert "refreshArtForTheme();" in settings[settings.index("function scheduleThemeArt") :][:700]


def test_theme_redraw_does_not_poll_or_read_styles_per_frame() -> None:
 fn = GRAPH[GRAPH.index("function gcThemeChanged") :][:1500]
 assert "setInterval" not in fn
 start = GRAPH.index("function gcDraw(")
 draw = GRAPH[start : GRAPH.index("\n  function ", start + 10)]
 assert "gcReadTokens(" not in draw
