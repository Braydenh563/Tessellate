"""Words on a board beyond plain text (WHITEBOARD_PLAN section 5): subscript and superscript (`H~2~O`, `x^2^`) and `$...$`
maths. `whiteboard-text-more.js` is run in node for its pure parts; the browser half is `scratchpad/ui-sweeps/wbtext3.js`."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tests._app_js import frontend_text


def _node(body: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = "const wbFmtState = {};\n" + frontend_text("whiteboard-text-more.js") + "\n" + body
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)


def _split(text):
    return _node(f"console.log(JSON.stringify(wbFmtState.textMore.splitScripts({json.dumps(text)})));")


def test_water_and_a_square_split_into_plain_lowered_and_raised():
    assert _split("H~2~O") == [{"text": "H", "kind": ""}, {"text": "2", "kind": "sub"}, {"text": "O", "kind": ""}]
    assert _split("x^2^ + 1") == [{"text": "x", "kind": ""}, {"text": "2", "kind": "sup"}, {"text": " + 1", "kind": ""}]


def test_strikethrough_spaces_and_lone_marks_are_left_alone():
    for text in ("~~gone~~", "a ~ b ~ c", "2^ and ^3", "~two words~", "plain"):
        assert _split(text) == [{"text": text, "kind": ""}]


def test_the_export_drops_the_marks_and_tags_the_characters():
    out = _node(
        "const chars = [...'H~2~O'].map((ch, at) => ({ ch, attrs: {}, at }));"
        "console.log(JSON.stringify(wbFmtState.textMore.markScripts(chars).map((c) => [c.ch, c.attrs.script || ''])));"
    )
    assert out == [["H", ""], ["2", "sub"], ["O", ""]]


def test_nothing_is_built_from_html():
    src = frontend_text("whiteboard-text-more.js")
    assert "innerHTML" not in src and "insertAdjacentHTML" not in src


def test_the_board_calls_it_at_the_three_places_words_are_drawn():
    wb = frontend_text("whiteboard.js")
    assert "wbFmtState.textMore?.paintScripts(contentEl)" in wb
    assert "wbFmtState.textMore?.scriptSpans(span, fontSize)" in wb
    assert "wbFmtState.textMore?.markScripts(" in wb
    assert "/js/whiteboard-text-more.js" in frontend_text("lazy-entries.js")


def test_dollar_spans_split_into_text_and_maths_and_prose_dollars_stay_text():
    looks = "(body) => !/^\\s|\\s$/.test(body)"
    out = _node(f"console.log(JSON.stringify(wbFmtState.textMore.mathPieces('Area $x^2$ and $5 or $10', {looks})));")
    assert out == [{"text": "Area "}, {"math": "x^2"}, {"text": " and $5 or $10"}]
    out = _node(f"console.log(JSON.stringify(wbFmtState.textMore.mathPieces('costs $5 or $10', {looks})));")
    assert out == [{"text": "costs $5 or $10"}]


def test_has_maths_is_false_without_a_span_or_a_renderer():
    assert _node("console.log(JSON.stringify(wbFmtState.textMore.hasMath('no dollars here', () => true)));") is False
    assert _node("console.log(JSON.stringify(wbFmtState.textMore.hasMath('$a$', () => true)));") is True


def test_the_label_math_overlay_is_called_laid_out_and_dropped_from_the_export():
    wb = frontend_text("whiteboard.js")
    assert "wbFmtState.textMore?.mathLabel(groupEl, label, area, fontSize)" in wb
    assert '":scope > .sketch-label-math"' in wb
    assert "innerHTML" not in frontend_text("whiteboard-text-more.js")


def _wrap(text, start, end, mark):
    return _node(f"console.log(JSON.stringify(wbFmtState.textMore.wrapScript({json.dumps(text)}, {start}, {end}, {json.dumps(mark)})));")


def test_the_selection_is_wrapped_in_tildes_or_carets_l_whiteboard_27():
    assert _wrap("H2O", 1, 2, "~") == {"text": "H~2~O", "from": 2, "to": 3}
    assert _wrap("x2", 1, 2, "^") == {"text": "x^2^", "from": 2, "to": 3}


def test_a_wrapped_selection_unwraps_and_a_choice_that_would_not_draw_is_refused():
    assert _wrap("H~2~O", 2, 3, "~") == {"text": "H2O", "from": 1, "to": 2}
    # spaces, a line break, a mark inside, nothing selected, more than 20 characters and a doubled mark all draw as plain text
    for text, a, b in (("two words", 0, 9), ("a\nb", 0, 3), ("a~b", 0, 3), ("abc", 1, 1), ("x" * 21, 0, 21), ("~~gone~~", 2, 6)):
        assert _wrap(text, a, b, "~") is None, text


def test_the_text_style_menu_has_the_script_row():
    js = frontend_text("whiteboard.js")
    menu = js[js.index("async function wbOpenRunMenu") : js.index("function wbBulletTextLines")]
    assert 'wbColourHeading("Script")' in menu and "wrapScript(" in menu
