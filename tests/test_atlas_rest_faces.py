"""D9: only the newest reply keeps the drawn Atlas head; older ones point at a shared copy.

A chat reply's corner mark is Atlas's tiny head, 161 nodes of a reply's 167
(measured in the running app, four replies). Older replies now hold an
`<svg><use></svg>` (2 nodes) of one hidden copy per look, mood and size.
The block between the `rest-begin` and `rest-end` markers in atlas.js runs
here under node against a small fake document.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ATLAS = (ROOT / "frontend" / "js" / "atlas.js").read_text(encoding="utf-8")
LAZY_CSS = (ROOT / "frontend" / "css" / "atlas-lazy.css").read_text(encoding="utf-8")


def _block() -> str:
    return ATLAS[ATLAS.index("//: rest-begin") : ATLAS.index("//: rest-end")]


HARNESS = """
class Node {
  constructor(tag) { this.tag = tag; this.attrs = {}; this.dataset = {}; this.children = []; this.parent = null; this.id = ""; this.className = ""; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return this.attrs[k] ?? null; }
  appendChild(c) { c.parent = this; this.children.push(c); return c; }
  replaceChildren() { this.children = []; }
  cloneNode() { const n = new Node(this.tag); n.attrs = { ...this.attrs }; n.dataset = { ...this.dataset }; n.children = this.children.map((c) => c.cloneNode()); n.className = this.className; return n; }
  contains(o) { for (let n = o; n; n = n.parent) if (n === this) return true; return false; }
  replaceWith(n) { const i = this.parent.children.indexOf(this); n.parent = this.parent; this.parent.children[i] = n; this.parent = null; }
  count() { return 1 + this.children.reduce((a, c) => a + c.count(), 0); }
}
const bodyEl = new Node("body");
const listeners = {};
const bubbles = [];
const document = {
  body: bodyEl,
  getElementById: (id) => (id === "chat-messages" ? { id } : bodyEl.children.find((c) => c.id === id) || null),
  createElement: (t) => new Node(t),
  addEventListener: (name, fn) => { listeners[name] = fn; },
  querySelectorAll(sel) {
    if (sel === "#chat-messages .msg.assistant") return bubbles.map((b) => b.bubble);
    return bubbles.map((b) => b.avatar.children[0]).filter((f) => f && f.className.includes("atl-tiny"));
  },
};
let painted = 0;
globalThis.paintAssistantAvatar = () => { painted++; };
const atlasMake = (tag, attrs, parent) => { const n = new Node(tag); n.className = (attrs && attrs.class) || ""; for (const [k, v] of Object.entries(attrs || {})) n.setAttribute(k, v); if (parent) parent.appendChild(n); return n; };
function reply(mood = "calm") {
  const bubble = new Node("div");
  const avatar = new Node("span");
  bubble.appendChild(avatar);
  const face = new Node("svg");
  face.className = "name-mark nm-atlas atl atl-tiny";
  face.attrs = { width: "20", height: "20" };
  face.dataset = { atlasLook: "masculine", atlasMood: mood };
  for (let i = 0; i < 160; i++) face.appendChild(new Node("path"));
  avatar.appendChild(face);
  bubbles.push({ bubble, avatar });
  return face;
}
"""


def _run(body: str) -> object:
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    script = f"{HARNESS}\n{_block()}\n(async () => {{ {body} }})();"
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_older_replies_become_two_nodes_and_the_newest_keeps_its_head() -> None:
    result = _run(
        """
        const heads = [reply(), reply(), reply()];
        listeners["atlas-repainted"]();
        const nodes = bubbles.map((b) => b.avatar.children[0].count());
        console.log(JSON.stringify({ nodes, newestIsLive: bubbles[2].avatar.children[0] === heads[2],
          classes: bubbles.map((b) => b.avatar.children[0].className) }));
        """
    )
    assert result["nodes"] == [2, 2, 161]
    assert result["newestIsLive"] is True
    assert result["classes"][:2] == ["atl-rest", "atl-rest"]


def test_the_older_replies_share_one_copy_per_look_mood_and_size() -> None:
    result = _run(
        """
        reply(); reply(); reply("happy"); reply();
        listeners["atlas-repainted"]();
        const hosts = bodyEl.children.filter((c) => c.id === "atl-rest-host");
        const copies = hosts[0].children;
        const uses = bubbles.slice(0, 3).map((b) => b.avatar.children[0].children[0].attrs.href);
        console.log(JSON.stringify({ hosts: hosts.length, copies: copies.length, uses, ids: copies.map((c) => c.id),
          frozen: copies.every((c) => "atlRest" in c.dataset) }));
        """
    )
    assert result["hosts"] == 1
    assert result["copies"] == 2, "calm and happy: one copy each"
    assert result["uses"][0] == result["uses"][1] != result["uses"][2]
    assert result["frozen"] is True, "mood changes and plays skip a copy"


def test_a_change_of_look_drops_the_old_copies_and_redraws_from_the_new_heads() -> None:
    result = _run(
        """
        reply(); reply(); reply();
        listeners["atlas-repainted"]();
        const before = bodyEl.children[0].children.map((c) => c.id);
        // atlasRepaint put live heads back where the rest faces were.
        for (const b of bubbles) { const f = reply.call(null); bubbles.pop(); f.dataset.atlasLook = "feminine"; b.avatar.children[0] = f; f.parent = b.avatar; }
        listeners["atlas-repainted"]();
        const after = bodyEl.children[0].children.map((c) => c.id);
        console.log(JSON.stringify({ before, after }));
        """
    )
    assert result["before"] != result["after"]
    assert len(result["after"]) == 1


def test_a_painted_head_retires_the_older_ones_in_one_pass_and_wakes_nothing() -> None:
    result = _run(
        """
        reply(); reply();
        const mine = globalThis.paintAssistantAvatar;
        reply();
        mine(null, 20); mine(null, 20); mine(null, 20);
        await Promise.resolve();
        console.log(JSON.stringify({ painted, nodes: bubbles.map((b) => b.avatar.children[0].count()) }));
        """
    )
    assert result["painted"] == 3, "the wrapped original still paints every head"
    assert result["nodes"] == [2, 2, 161]
    block = _block()
    assert "MutationObserver" not in block and "setInterval" not in block and "requestAnimationFrame" not in block
    assert "Object.assign(window" not in block and "window." not in block
    assert block.count("\n(() => {") == 1, "wrapped whole: no new name in the shared scope"


def test_the_shared_scope_is_told_about_the_copies() -> None:
    """Mood changes and plays skip a copy, a repaint skips the host and
    redraws a rest face, and the host is hidden by the lazy sheet."""
    assert 'querySelectorAll(".nm-atlas:not([data-atl-rest])")' in ATLAS
    assert ATLAS.count('.nm-atlas:not([data-atl-rest])') == 2
    assert "#nm-buddy, #atl-rest-host" in ATLAS
    assert 'svg.nm-atlas, svg.atl-rest' in ATLAS
    assert 'new Event("atlas-repainted")' in ATLAS
    assert ".atl-rest-host { position: absolute; width: 0; height: 0; overflow: hidden; }" in LAZY_CSS
