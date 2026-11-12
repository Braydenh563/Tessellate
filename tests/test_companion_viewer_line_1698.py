"""INBOX 1698: in the large view a floating companion's line went under the card's sticky head and was cut off."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_a_floating_companions_line_in_the_large_view_clears_the_card_head() -> None:
    css = (ROOT / "frontend" / "css" / "characters-lazy.css").read_text(encoding="utf-8")
    assert '.nm-viewer-figure > #nm-buddy[data-pose="float"] > .nm-say { top: calc(var(--nmb-edge) * -1); }' in css
