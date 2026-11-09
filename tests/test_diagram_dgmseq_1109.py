"""INBOX 1702 (the owner's sequence diagram in the builder): the list reads as sentences, the shelf can fold and cannot cover
the drawing, the fold button clears the scrollbar, a pick shows in both halves, and Picture / List say what they change.
Numbers measured are in docs/roadmap/agent-remaining/dgmseq-1109.md and the CHANGELOG line."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")


def _js(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def _rule(selector: str) -> str:
    return CSS[CSS.index(selector + " {") :].split("}", 1)[0]


def test_a_sequence_row_is_one_sentence_with_who_to_whom_under_it_not_a_column_away():
    kinds = _js("diagram-kinds.js")
    assert 'card.classList.add("dgm-card-two")' in kinds
    assert "\\u2192" in kinds  # "Browser \u2192 Web service", written as an escape
    rule = _rule(".dgm-card-two")
    assert "grid-template-areas" in rule and "grid-row" not in rule.split("grid-template-areas")[0]
    assert ".dgm-card-two > .dgm-meta" in CSS and ".dgm-card-two > .dgm-label" in CSS


def test_activate_and_deactivate_are_said_in_plain_words_and_stay_kept_lines():
    kinds = _js("diagram-kinds.js")
    assert "function keptWords(" in kinds
    for words in ("is active", "is done"):
        assert words in kinds
    # still a locked row: the line is printed back as it stood
    assert 'block.classList.add("dgm-kept")' in kinds and "row.line" in kinds


def test_a_sequence_list_has_a_participants_and_a_messages_heading():
    kinds = _js("diagram-kinds.js")
    assert '"Participants"' in kinds and '"Messages"' in kinds and "dgm-sechead" in kinds
    assert ".dgm-sechead {" in CSS


def test_block_and_divider_kinds_are_words_under_the_row_not_at_its_right_edge():
    kinds = _js("diagram-kinds.js")
    for words in ("Loop, repeats", "Else, the other way"):
        assert words in kinds


def test_the_shelf_folds_to_one_button_the_choice_is_remembered_and_the_picture_makes_room():
    lib = _js("diagram-library.js")
    assert 'const SHELF = "diagram.shelf"' in lib and "prefs.set(SHELF" in lib
    assert "dgm-shelf-toggle" in lib and 'setAttribute("aria-expanded"' in lib
    assert ".dgm-stage.dgm-shelved > .dgm-picture" in CSS
    assert ".dgm-shelf.dgm-shelf-off" in CSS


def test_the_shelf_caret_closes_its_menu_on_a_second_press_like_the_add_caret():
    lib = _js("diagram-library.js")
    assert 'more.getAttribute("aria-expanded") === "true"' in lib and "closeActionMenus()" in lib
    assert 'more.setAttribute("aria-expanded", "true")' in lib


def test_the_fold_button_stays_off_the_scrollbar():
    split = _js("diagram-split.js")
    assert "S.fig.offsetWidth - S.fig.clientWidth" in split and "right.style.insetInlineEnd" in split
    assert "(S.fig.onzoom ||= []).push(clear)" in split


def test_a_pick_is_brought_into_view_in_the_other_half():
    overlay = _js("diagram-overlay.js")
    assert "const reveal = " in overlay and "scrollIntoView" in overlay.split("const reveal = ", 1)[1][:900]


def test_picture_and_list_differ_in_width_and_say_so_in_a_visible_line():
    embed = _js("diagram-embed.js")
    assert "dgm-viewnote" in embed and "Picture: the drawing gets the room" in embed
    assert "List: the blocks get the room" in embed
    assert 'dispatchEvent(new CustomEvent("dgmlayout"' in embed
    assert '[data-dgm-layout="canvas"] .dgm-body.dgm-split {\n  --dgm-list: 14rem;' in CSS
    assert '[data-dgm-layout="blocks"] .dgm-body.dgm-split {\n  --dgm-list: 50%;' in CSS
    split = _js("diagram-split.js")
    assert '"dgmlayout"' in split
