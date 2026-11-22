"""The graph Trace panel: a route reads as chip, arrow, chip, and its
"Generate from path" opener is an enabled secondary button with a split-menu
chevron (owner's bugs, three of them)."""

from __future__ import annotations

import re

from tests._css_paths import FRONTEND_DIR

CSS = FRONTEND_DIR / "css"


def _rule(text: str, selector: str) -> str:
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", text)
    assert m, selector
    return m.group(1)


def test_the_route_arrow_is_visible_and_the_reason_is_not_a_line_of_text():
    css = (CSS / "graph-lazy.css").read_text(encoding="utf-8")
    arrow = _rule(css, ".graph-trace-arrow-icon")
    # --border is a 10% hairline (1.2:1); an arrow needs the muted ink (3:1+).
    assert "var(--border)" not in arrow
    assert "var(--muted)" in arrow
    js = (FRONTEND_DIR / "js" / "graph.js").read_text(encoding="utf-8")
    # The reason rides on the tooltip and for screen readers, not as a visible run.
    assert 'how.className = "graph-trace-connector-label visually-hidden"' in js


def test_the_story_opener_rests_as_the_secondary_button_with_token_gaps():
    css = (CSS / "04-chat-dock-appearance.css").read_text(encoding="utf-8")
    opener = _rule(css, ".story-mode-btn")
    assert "var(--on-accent)" not in opener  # white on a pale glass read as disabled
    assert "var(--btn-quiet-bg)" in opener
    assert "var(--ghost-btn-border)" in opener
    assert "display: inline-flex" in opener
    assert "gap: var(--space-2)" in opener


def test_the_story_chevron_is_standard_size_and_turns_open_but_not_when_reduced():
    css = (CSS / "graph-lazy.css").read_text(encoding="utf-8")
    assert "[open] > summary > .doc-toolbar-menu-caret" in css
    caret = _rule(css, ".graph-trace-story > summary > .doc-toolbar-menu-caret")
    assert "font-size: 1em" in caret
    assert "opacity: 1" in caret
    reduced = css.split("@media (prefers-reduced-motion: reduce)")[1]
    assert ".graph-trace-story[open] > summary > .doc-toolbar-menu-caret" in reduced
    assert "transform: none" in reduced
