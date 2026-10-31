"""Live view reveals a formatted span's marks per span, not per line (INBOX 1473 b).

The owner: "rn the codemirror shows md formatting for the line im on but i
want it to be like obsidian where it does it per phrase, word, or whatever
text string is formatted when clicked inside or next to". The rule is two
pure functions in documents.js, run here under node, and the plugin's use of
them is held by the static checks below. The browser half (a click inside
`**bold**` mid-line shows that span's marks and no other) is
`scratchpad/ui-sweeps/cm-reveal.js`.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from tests._app_js import JS_DIR

DOCUMENTS_JS = (JS_DIR / "documents.js").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _function(name: str) -> str:
    match = re.search(rf"^function {name}\(.*?^\}}", DOCUMENTS_JS, re.S | re.M)
    assert match, f"{name} is gone from documents.js"
    return match.group(0)


def _run(expression: str):
    script = (
        _function("docLiveSpanTouched")
        + "\n"
        + _function("docLiveRevealSame")
        + f"\nprocess.stdout.write(JSON.stringify({expression}));"
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def _touched(selections, span):
    sel = json.dumps([{"from": a, "to": b} for a, b in selections])
    return _run(f"docLiveSpanTouched({sel}, {span[0]}, {span[1]})")


# "Alpha **one** beta": the span `**one**` is 6..13.
BOLD = (6, 13)


@needs_node
@pytest.mark.parametrize("caret", [6, 7, 9, 12, 13])
def test_a_caret_inside_or_touching_either_end_reveals(caret):
    assert _touched([(caret, caret)], BOLD) is True


@needs_node
@pytest.mark.parametrize("caret", [0, 5, 14, 18])
def test_a_caret_elsewhere_on_the_same_line_does_not(caret):
    assert _touched([(caret, caret)], BOLD) is False


@needs_node
def test_every_cursor_counts_not_only_the_main_one():
    assert _touched([(0, 0), (9, 9)], BOLD) is True
    assert _touched([(0, 0), (16, 16)], BOLD) is False


@needs_node
def test_a_selection_reveals_every_span_it_touches():
    assert _touched([(2, 6)], BOLD) is True
    assert _touched([(13, 17)], BOLD) is True
    assert _touched([(0, 18)], BOLD) is True
    assert _touched([(14, 18)], BOLD) is False


@needs_node
def test_nested_spans_reveal_the_innermost_and_its_ancestors_only():
    # "**a *b* c** and *d*": outer 0..11, inner 4..7, sibling 16..19.
    caret = [(5, 5)]
    assert _touched(caret, (0, 11)) is True
    assert _touched(caret, (4, 7)) is True
    assert _touched(caret, (16, 19)) is False


@needs_node
def test_a_selection_move_that_flips_no_span_needs_no_rebuild():
    # Probes are [from, to, revealed] triples, flat.
    probes = "[6, 13, 1, 20, 30, 0]"
    assert _run(f"docLiveRevealSame({probes}, [{{from: 9, to: 9}}])") is True
    assert _run(f"docLiveRevealSame({probes}, [{{from: 10, to: 10}}])") is True
    assert _run(f"docLiveRevealSame({probes}, [{{from: 15, to: 15}}])") is False
    assert _run(f"docLiveRevealSame({probes}, [{{from: 9, to: 9}}, {{from: 25, to: 25}}])") is False


def _build() -> str:
    start = DOCUMENTS_JS.index("function docLivePlugin(CM)")
    body = DOCUMENTS_JS[start: DOCUMENTS_JS.index("docLivePluginCache = ViewPlugin.fromClass(", start)]
    return body[body.index("  function build(view, record"):]


def test_inline_spans_reveal_through_the_span_rule():
    build = _build()
    assert re.search(r"const rangeRevealed = \(from, to\) =>\s*probe\(from, to\)", build), (
        "rangeRevealed is no longer the per-span rule"
    )
    assert "docLiveSpanTouched(" in build, "the plugin no longer asks docLiveSpanTouched"
    assert "state.selection.ranges" in build, "only the main cursor reveals; every cursor must"
    emphasis = build[build.index('name === "EmphasisMark"'):]
    emphasis = emphasis[: emphasis.index('if (name === "Link")')]
    assert "revealedBy(parent.from, parent.to)" in emphasis
    assert ": rangeRevealed;" in emphasis, "an inline span's marks no longer use the span rule"
    escape = build[build.index('name === "Escape"'):]
    assert "rangeRevealed(node.from, node.to)" in escape[: escape.index("return false;")]


def test_code_fences_keep_their_block_rule():
    build = _build()
    assert "const blockRevealed" in build
    fenced = build[build.index('if (name === "FencedCode")'):]
    assert "blockRevealed(node.from, node.to)" in fenced[: fenced.index("return undefined;")]
    mark = build[build.index('name === "EmphasisMark"'):]
    assert 'parent.name === "FencedCode" ? blockRevealed' in mark[: mark.index('if (name === "Link")')]


def test_a_selection_move_rebuilds_only_when_a_span_flips():
    start = DOCUMENTS_JS.index("docLivePluginCache = ViewPlugin.fromClass(")
    update = DOCUMENTS_JS[start: DOCUMENTS_JS.index("decorations: (plugin)", start)]
    assert "docLiveRevealSame(" in update, "every caret move rebuilds the visible ranges again"
