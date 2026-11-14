"""BS1 follow-up: a focused `.card-open` is ringed by its card, and the sweep knows.

focusring.js reported `strong.library-card-title.card-open` as a stop with no
ring because it read the title, whose own outline is none by design
(00-tokens-shell.css): the ring is the card's, drawn through `:has()`. Measured
1111 on the Library: the focused note card has `solid 2px rgb(47, 91, 211)`.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_the_card_carries_the_ring_a_focused_title_does_not():
    css = (ROOT / "frontend/css/00-tokens-shell.css").read_text(encoding="utf-8")
    at = css.index(".library-card:has(.card-open:focus-visible)")
    body = css[at : at + 300]
    assert "outline: 2px solid var(--accent)" in body


def test_the_sweep_reads_the_card_for_a_card_open_stop():
    sweep = (ROOT / "scratchpad/ui-sweeps/focusring.js").read_text(encoding="utf-8")
    assert "card-open" in sweep and ".library-card, .doc-list-item" in sweep
