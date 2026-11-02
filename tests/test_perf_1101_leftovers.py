"""The motion agent's leftovers (docs/roadmap/agent-remaining/motion-1101.md)."""

from __future__ import annotations

from tests._css_paths import FRONTEND_DIR


def test_the_graph_menus_chevron_turns_open_without_the_librarys_sheet():
    css = (FRONTEND_DIR / "css" / "graph-lazy.css").read_text(encoding="utf-8")
    assert ".graph-trace-story[open] > summary > .doc-toolbar-menu-caret" in css
    assert "rotate(180deg)" in css.split(".graph-trace-story[open] > summary > .doc-toolbar-menu-caret")[1]
