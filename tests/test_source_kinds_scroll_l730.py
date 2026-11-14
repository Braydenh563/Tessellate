"""L730 (owner, 2026-11-12) and CHAT_PLAN decision 37: sources of every kind, web pages first, the list scrolls in the bubble.
L-chat-20: accessed web links lead the sources, and a reply bubble fades in (reduced motion drops the duration)."""

import re

from tests._app_js import frontend_text
from pathlib import Path

KIT = frontend_text("answer-kit.js")
CSS = Path("frontend/css/02-chat-graph.css").read_text(encoding="utf-8")


def test_every_source_kind_has_a_group():
    groups = frontend_text("chat-agent.js")
    for kind in ("web", "note", "document", "file", "map", "board"):
        assert f'key: "{kind}"' in groups


def test_web_pages_lead_the_sources():
    assert 'sources.filter((s) => s.kind === "web"), ...sources.filter((s) => s.kind !== "web")' in KIT


def test_the_source_list_scrolls_and_is_reachable_by_keyboard():
    grid = re.search(r"\.chat-sources-grid \{(.*?)\}", CSS, re.S).group(1)
    assert "overflow-y: auto" in grid and "max-height" in grid
    assert "grid.tabIndex = 0;" in KIT


def test_a_bubble_fades_in():
    css = Path("frontend/css/03-dashboard-widgets.css").read_text(encoding="utf-8")
    assert re.search(r"\.msg \{[^}]*animation: msg-in var\(--ui-slow\)", css, re.S)
