"""W17 diagram builder fixes (agent w17-1110). Source reads; the browser numbers are in the CHANGELOG line and w17-1110.md."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(*parts: str) -> str:
    return ROOT.joinpath(*parts).read_text(encoding="utf-8")


def test_keys_typed_before_the_name_box_opens_are_kept_for_it_not_run_as_shortcuts():
    edges = _read("frontend", "js", "diagram-edges.js")
    # C1: letters, Enter and Escape wait for the box the picture draws a moment later.
    assert "Keys typed between Add and the name box opening" in edges
    assert "held += key" in edges and "if (entered) (entered = false), end(true)" in edges
    assert "if (held) (input.value = held), (held = \"\")" in edges


def test_the_help_line_pins_above_the_sticky_foot_not_under_it():
    css = _read("frontend", "css", "diagram-lazy.css")
    rule = css[css.index(".dgm-next {") :].split("}", 1)[0]
    # C2: both stuck to the same edge and the foot covered the hint in a scrolling pane (600 to 820 px wide).
    assert "position: sticky" in rule and "inset-block-end: 0" in rule
    assert "S.next.style.marginBlockEnd" in _read("frontend", "js", "diagram-steps.js")


def test_a_drop_on_an_earlier_block_says_it_connects_back():
    pointer = _read("frontend", "js", "diagram-pointer.js")
    assert "`Connect back to ${said}`" in pointer and "`Connect to ${said}`" in pointer


def test_a_new_diagram_opens_with_the_list_folded_and_an_existing_one_as_it_was_left():
    split = _read("frontend", "js", "diagram-split.js")
    # C8, INBOX 1720: not stored, only while no fold was ever chosen and the source is the starter or blank.
    assert '!prefs.has(FOLD) && ["", diagramModel.starter' in split
    assert 'paint(fresh ? "left" : fold.get())' in split


def test_versions_list_puts_named_versions_first_and_the_plain_saves_under_their_own_line():
    ai = _read("frontend", "js", "diagram-ai.js")
    assert "const ordered = [...rows.filter((r) => r.name), ...rows.filter((r) => !r.name)]" in ai
    assert '"dgm-versions-head muted text-sm", "Saves"' in ai


def test_a_phone_has_an_ask_button_that_opens_the_sheet_with_the_question_box_in_hand():
    touch = _read("frontend", "js", "diagram-touch.js")
    assert 'smallButton("ph:sparkle", "Ask for a change"' in touch
    assert 'S.pane.querySelector(".dgm-ai-form input")?.focus()' in touch
