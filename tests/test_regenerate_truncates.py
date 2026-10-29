"""Regenerate from a non-last answer cuts the saved chat; a write is not re-run silently.

Audit E1: `regenerateFromBubble` dropped the later bubbles but not the saved
turns, and `replaceLast` then wrote over the last saved one. E2: an answer that
wrote something asks before Regenerate or Edit asks the question again.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from tessellate.ai import agent
from tests._app_js import JS_DIR

pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _fn(source: str, name: str, is_async: bool = True) -> str:
    prefix = "async function" if is_async else "function"
    match = re.search(rf"^{prefix} {name}\(.*?^\}}", source, re.S | re.M)
    assert match, f"{name} is gone"
    return match.group(0)


def _run(turns: int, regen_index: int, ran_write: bool, confirm: bool = True) -> dict:
    edit = (JS_DIR / "chat-edit.js").read_text(encoding="utf-8")
    code = "\n".join(
        [_fn(edit, "questionForBubble", False), _fn(edit, "regenerateFrom"), _fn(edit, "confirmRerun")]
    )
    script = f"""
const calls = []; let sent = null, confirms = 0;
function mk(role, text) {{
  const n = {{ role, text, prev: null, dataset: {{}}, removed: false,
    classList: {{ contains: (c) => c === "msg" || c === role }},
    querySelector: () => ({{ textContent: text }}),
    remove() {{ this.removed = true; host.children = host.children.filter((x) => x !== this); }} }};
  return n;
}}
const host = {{ children: [] }};
for (let t = 1; t <= {turns}; t++) {{ host.children.push(mk("user", "q" + t), mk("assistant", "a" + t)); }}
host.children.forEach((n, i) => Object.defineProperty(n, "previousElementSibling", {{ get: () => host.children[host.children.indexOf(n) - 1] || null }}));
host.querySelectorAll = (sel) => host.children.filter((n) => n.role === "assistant");
const $ = () => host;
let chatController = null;
const chatConv = {{ id: 7, turns: Array.from({{ length: {turns} }}, (_, i) => ({{ question: "q" + (i + 1), answer: "a" + (i + 1) }})) }};
const toast = () => {{}};
const apiJson = async (url, opts) => {{ calls.push([url, JSON.parse(opts.body)]); }};
const confirmDialog = async () => {{ confirms++; return {str(confirm).lower()}; }};
const sendChatMessage = (q, o) => {{ sent = [q, o]; }};
{code}
const target = host.children.filter((n) => n.role === "assistant")[{regen_index}];
if ({str(ran_write).lower()}) target.dataset.wrote = "1";
regenerateFrom(target).then(() => process.stdout.write(JSON.stringify({{
  calls, sent, confirms, turns: chatConv.turns.map((t) => t.question), dom: host.children.map((n) => n.text) }})));
"""
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def test_regenerate_of_turn_one_of_three_cuts_the_saved_turns_after_it():
    got = _run(3, 0, False)
    assert got["calls"] == [["/conversations/7/truncate", {"from_turn": 1}]]
    assert got["turns"] == ["q1"]
    assert got["dom"] == ["q1"]
    assert got["sent"][1]["replaceLast"] is True


def test_regenerate_of_the_last_answer_needs_no_cut():
    got = _run(3, 2, False)
    assert got["calls"] == []
    assert got["turns"] == ["q1", "q2", "q3"]


def test_an_answer_that_wrote_asks_before_it_is_run_again():
    refused = _run(2, 1, True, confirm=False)
    assert refused["confirms"] == 1 and refused["sent"] is None and refused["calls"] == []
    allowed = _run(2, 1, True, confirm=True)
    assert allowed["confirms"] == 1 and allowed["sent"] is not None


def test_an_answer_that_only_read_does_not_ask():
    assert _run(2, 1, False)["confirms"] == 0


def test_the_tool_event_says_whether_it_wrote():
    assert agent._tool_event("create_note", {}, {"ok": True})["wrote"] is True
    assert agent._tool_event("create_note", {}, {"error": "no"})["wrote"] is False
    assert agent._tool_event("search_notes", {}, {"results": []})["wrote"] is False
