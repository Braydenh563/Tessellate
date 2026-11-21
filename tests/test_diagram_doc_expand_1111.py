"""The diagram in a document, 2026-11-11 (the owner): the blocks pane's foot never lies over its text, the sideways offer
is one row, and a toolbar Expand opens the full screen builder (the embed dialog) and Collapse puts the document back.

The measured side (foot against every text line at every scroll, the offer's height, the scroll put back) is
`scratchpad/ui-sweeps` territory; this file holds what a diff can break.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")


def _js(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def _rule(selector: str) -> str:
    start = CSS.index(selector + " {")
    return CSS[start : CSS.index("}", start)]


def test_the_foot_is_outside_the_scroller_so_it_cannot_cover_a_line():
    steps = _js("diagram-steps.js")
    assert 'S.scroll.className = "dgm-scroll"' in steps and "S.pane.append(S.scroll, foot)" in steps
    pane, scroll, foot = _rule(".dgm-pane.dgm-framed"), _rule(".dgm-scroll"), _rule(".dgm-foot")
    assert "overflow: hidden" in pane and "flex-direction: column" in pane
    assert "overflow: auto" in scroll and "min-block-size: 0" in scroll
    assert "position: sticky" not in foot and "position: sticky" not in _rule(".dgm-next")


def test_the_pane_hugs_its_content_so_there_is_no_dead_gap_under_the_foot():
    assert "max-block-size: 100%" in _rule(".dgm-pane.dgm-framed")
    # The list column is the frame from 600 up: it sits at the top of its cell, not stretched to the picture's height.
    column = CSS[CSS.index("@media (min-width: 600px) {\n  .dgm-listcol {") :][:400]
    assert "align-self: start" in column and "max-block-size: 100%" in column
    assert "flex: 0 1 auto" in CSS[CSS.index(".dgm-listcol > .dgm-pane {") :][:80]


def test_the_drop_line_reads_the_scroller_that_holds_the_blocks():
    pointer = _js("diagram-pointer.js")
    assert "S.scroll || S.pane" in pointer and "g.S.scroll || g.S.pane" in pointer


def test_the_sideways_offer_is_one_notice_row_whose_words_wrap_before_its_buttons_do():
    outline = _js("diagram-outline.js")
    assert 'line.className = "notice dgm-sideways"' in outline and "line.append(mark, words, acts)" in outline
    # The pair is one group: the row drops it under the words as a pair (never one button alone) and only below the width of a narrow column of words.
    assert "acts.append(turn, keep)" in outline
    row, words, acts = _rule(".dgm-sideways"), _rule(".dgm-sideways-words"), _rule(".dgm-sideways-acts")
    assert "flex-wrap: wrap" in row
    assert "min-width: 6rem" in words and "flex: 1 1 6rem" in words
    assert "flex: none" in acts
    assert "white-space: nowrap" in _rule(".dgm-sideways-acts > button")


def test_the_expanded_builder_does_not_make_the_offer_it_is_already_the_whole_screen():
    assert "!S.io?.collapse" in _js("diagram-outline.js")


def test_both_toolbars_carry_the_expand_button_made_in_the_kind_bar():
    kindbar = _js("diagram-kindbar.js")
    #: The export also carries fold (e768ad94); what is pinned is that expand is exported.
    assert "expand," in kindbar.split("diagramModel.kindbar = {")[1].split("}", 1)[0]
    assert '"ph:arrows-out"' in kindbar and '"ph:arrows-in"' in kindbar
    assert 'out ? "Expand" : "Collapse"' in kindbar and "dgm-expand" in kindbar
    # A builder that is a dialog of its own (a board's, the door's) has no Expand, and only a live one a Collapse.
    assert "!S.io.dialog" in kindbar and "S.io.collapse" in kindbar
    assert "diagramModel.kindbar?.expand(S)" in _js("diagram-bar.js")
    assert "diagramModel.kindbar?.expand(S)" in _js("diagram-kinds.js")


def test_expand_reuses_the_embed_dialog_with_the_documents_own_io():
    embed = _js("diagram-embed.js")
    assert "async function expand(S)" in embed and "live: S.io" in embed
    assert "expand }" in embed.split("diagramModel.embed = {")[1]
    # Every change in the dialog reaches the document by its own saving, and leaving asks nothing of a live one.
    assert "live?.set(next)" in embed and "live?.set(history[at])" in embed
    assert "collapse: live ? () => finish(true) : null" in embed and "onClose?.()" in embed
    assert 'overlay.classList.add("dgm-expanded")' in embed


def test_collapse_puts_the_document_back_where_it_was():
    embed = _js("diagram-embed.js")
    body = embed[embed.index("async function expand(S)") :]
    for kept in ("S.scroll", "S.fig", "parentElement", "scrollTop", "scrollLeft", "onpaint", "button.focus("):
        assert kept in body, kept


def test_the_expanded_dialog_fills_the_window_and_the_phone_has_no_expand_button():
    overlay, card = _rule(".modal-overlay.dgm-expanded"), _rule(".modal-overlay.dgm-expanded .dgm-dialog")
    assert "padding: var(--space-3)" in overlay
    assert "width: 100%" in card and "height: 100%" in card and "max-width: none" in card
    phone = CSS[CSS.index(".dgm-dock .dgm-expand") :][:120]
    assert "display: none" in phone


def test_the_new_copy_has_no_em_dash_and_no_exclamation():
    for name in ("diagram-kindbar.js", "diagram-embed.js", "diagram-outline.js", "diagram-steps.js"):
        text = _js(name)
        assert chr(0x2014) not in text, name
        assert not re.search(r'"[^"\n]*[A-Za-z]!"', text), name
