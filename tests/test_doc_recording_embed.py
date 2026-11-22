"""`![[Recording name]]` plays a recording in a document (DOCUMENTS_PLAN gap row 1).

Audio is a recording and never a file (WORLD_CLASS_PLAN "Audio in the notebook", decision 2), so the only
thing an embed can play is a take, found by the name the Library shows. This runs documents-embeds.js in node
against a tiny stand-in for the page; the Live and Read drawing was driven in Chromium on :8796.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

#: Only what the embed code touches: elements that remember their children, the two lookups it makes, a window.
HARNESS = """
const calls = [];
class El {
  constructor(tag) { this.tagName = tag.toUpperCase(); this.children = []; this.attrs = {}; this.isConnected = true; this.className = ""; }
  append(...kids) { this.children.push(...kids); }
  replaceChildren(...kids) { this.children = kids; }
  setAttribute(k, v) { this.attrs[k] = v; }
  addEventListener() {}
}
const document = { createElement: (t) => new El(t), addEventListener() {} };
const window = {};
const docs = [];
const wikiLinkTarget = (n) => n;
const docBlockRefSplit = (n) => ({ name: n, blockId: null });
const resolveWikiTarget = () => null;
const apiJson = async (url) => { calls.push(url); return { recordings: [{ id: 7, title: "Standup 10 Nov" }] }; };
"""


def _run(body: str) -> object:
    text = (JS / "documents-embeds.js").read_text(encoding="utf-8")
    script = HARNESS + text + "\n;(async () => {\n" + body + "\n})();\n"
    out = subprocess.run(["node", "-"], input=script, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-800:]
    return json.loads(out.stdout.strip().splitlines()[-1])


@node
def test_a_recordings_name_swaps_the_nothing_called_box_for_a_player() -> None:
    got = _run(
        "const body = new El('div');"
        "window.docEmbedFill(body, 'standup 10 nov', { keep: true });"
        "await new Promise((r) => setTimeout(r, 20));"
        "const fig = body.children[0];"
        "const audio = fig.children[1];"
        "console.log(JSON.stringify({ calls, tag: fig.tagName, cap: fig.children[0].textContent, src: audio.src, controls: audio.controls, preload: audio.preload }));"
    )
    assert got == {
        "calls": ["/recordings?limit=500"],
        "tag": "FIGURE",
        "cap": "Standup 10 Nov",
        "src": "/media/recordings/7",
        "controls": True,
        "preload": "none",
    }


@node
def test_a_name_that_is_no_recording_leaves_the_box_and_asks_once_per_half_minute() -> None:
    got = _run(
        "const body = new El('div'); body.children = ['Nothing called it yet.'];"
        "window.docEmbedFill(body, 'no such take', { keep: true });"
        "window.docEmbedFill(body, 'another', { keep: true });"
        "await new Promise((r) => setTimeout(r, 20));"
        "window.docEmbedFill(body, 'again', { keep: true });"
        "await new Promise((r) => setTimeout(r, 20));"
        "console.log(JSON.stringify({ calls, kept: body.children }));"
    )
    assert got == {"calls": ["/recordings?limit=500"], "kept": ["Nothing called it yet."]}


def test_read_and_live_both_reach_the_player_and_the_css_and_guide_say_so() -> None:
    markdown = (JS / "markdown.js").read_text(encoding="utf-8")
    assert "window.docEmbedFill?.(body, name, { keep: true })" in markdown
    embeds = (JS / "documents-embeds.js").read_text(encoding="utf-8")
    assert "kind: \"recording\"" in embeds and "!options?.keep" in embeds
    css = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    assert ".doc-embed-recording audio" in css

    from tessellate.ai import help_chat

    body = {t["id"]: t for t in help_chat.HELP_TOPICS}["voice"]["body"]
    assert "![[a recording's name]]" in body
