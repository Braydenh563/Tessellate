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
