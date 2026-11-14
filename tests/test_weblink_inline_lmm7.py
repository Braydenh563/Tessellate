"""L-mindmap-7 (the owner 2026-11-12: inline syntax): the slash menu's Web link on
a line of its own writes `[text](<url>)`, which the lone-link card rule skips and
the inline grammar draws as a plain link; inside a sentence it stays `[text](url)`."""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from pathlib import Path

from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]


def _fn(text: str, name: str) -> str:
    start = text.index(f"function {name}(")
    depth, i = 0, text.index("{", start)
    while True:
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        i += 1
        if depth == 0:
            return text[start:i]


def _node(script: str):
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


JS = app_js_text() + (ROOT / "frontend" / "js" / "editor.js").read_text(encoding="utf-8")


def _weblink(value: str, s: int, e: int):
    script = f"""
let sel = null;
function editorSplice(t, s, e, text, select) {{ t.value = t.value.slice(0, s) + text + t.value.slice(e); sel = [s + select.from, s + select.to]; }}
{_fn(JS, "editorWebLink")}
const t = {{ value: {json.dumps(value)}, selectionStart: {s}, selectionEnd: {e} }};
editorWebLink(t);
console.log(JSON.stringify([t.value, t.value.slice(sel[0], sel[1])]));
"""
    return _node(script)


def test_web_link_on_an_empty_line_writes_the_angle_destination():
    value, picked = _weblink("one\n\nthree", 4, 4)
    assert value == "one\n[link text](<https://>)\nthree"
    assert picked == "https://"


def test_web_link_inside_a_sentence_stays_plain():
    value, picked = _weblink("see  here", 4, 4)
    assert value == "see [link text](https://) here"
    assert picked == "https://"


def test_the_card_rule_skips_the_angle_destination():
    m = re.search(r"const LONE_LINK =\s*(/.+/);", JS)
    script = f"""
const LONE_LINK = {m.group(1)};
console.log(JSON.stringify([LONE_LINK.test("[a](<https://x.org>)"), LONE_LINK.test("[a](https://x.org)")]));
"""
    assert _node(script) == [False, True]


def test_angle_autolinks_leave_a_destination_alone():
    script = f"""
{_fn(JS, "expandAngleAutolinks")}
console.log(JSON.stringify([expandAngleAutolinks("[a](<https://x.org>)"), expandAngleAutolinks("go <https://x.org> now")]));
"""
    assert _node(script) == ["[a](<https://x.org>)", "go [https://x.org](https://x.org) now"]


def test_the_inline_grammar_unwraps_the_angle_destination():
    assert "if (linkUrl && /^<[^<>]+>$/.test(linkUrl)) linkUrl = linkUrl.slice(1, -1);" in JS
