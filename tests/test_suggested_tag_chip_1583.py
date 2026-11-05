"""A suggested tag is one split chip: take, and a dismiss half of its own
(INBOX 1583, the owner: "those x button on the suggested tags are badly
designed and need a redesign fix").

The chip is built by the real loop in entry-card.js, run in node against a
small stand-in DOM, so the test reads what the card draws: two buttons in one
chip, their names, and what each press sends. The sizes are measured in the
app (`getBoundingClientRect`, port 8791): before, the take was 89.5x24 and the
x a 28x28 box hung 2px over the 24px chip, 4px after the words; after, the
take is 89.5x24 and the dismiss half 24x24 inside the chip (44x44 under a
finger, the chip still 24px).
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tests._app_js import frontend_text

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not available")


def _loop() -> str:
    js = frontend_text("entry-card.js")
    start = js.index("  for (const tag of suggestions) {")
    end = js.index("    meta.appendChild(group);\n  }\n", start) + len("    meta.appendChild(group);\n  }\n")
    return js[start:end]


HARNESS = r"""
const vm = require("node:vm");
class El {
  constructor(tag) { this.tag = tag; this.children = []; this.dataset = {}; this.attrs = {}; this.on = {}; this.className = ""; this.title = ""; }
  appendChild(c) { this.children.push(c); return c; }
  replaceChildren() { this.children = []; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return this.attrs[k] ?? null; }
  addEventListener(type, fn) { this.on[type] = fn; }
}
const sent = [];
const ctx = {
  document: { createElement: (t) => new El(t) },
  chip: (text, cls) => { const c = new El("span"); c.className = `chip ${cls}`; c.children.push({ label: text }); return c; },
  setLabel: (el, label) => { el.label = label; },
  answerTags: (entry, answer) => sent.push(answer),
  entry: { id: 7, suggested_tags: ["study", "university"], suggested_tag_reasons: { study: "It mentions “assignment”." } },
  meta: new El("div"),
};
vm.createContext(ctx);
vm.runInContext("const suggestions = entry.suggested_tags;\n" + process.argv[1], ctx);
const stop = { stopPropagation() {} };
const chips = ctx.meta.children.map((g) => ({
  cls: g.className, tag: g.dataset.tag,
  buttons: g.children.map((b) => ({ tag: b.tag, type: b.type, cls: b.className, label: b.label, name: b.getAttribute("aria-label"), title: b.title })),
}));
for (const g of ctx.meta.children) for (const b of g.children) b.on.click(stop);
console.log(JSON.stringify({ chips, sent }));
"""


def _run() -> dict:
    done = subprocess.run(["node", "-e", HARNESS, _loop()], capture_output=True, text=True, check=True)
    return json.loads(done.stdout)


@node
def test_each_suggestion_is_one_chip_of_two_buttons() -> None:
    out = _run()
    assert [c["tag"] for c in out["chips"]] == ["study", "university"]
    for chip in out["chips"]:
        assert chip["cls"] == "chip tag suggested-tag"
        assert [b["tag"] for b in chip["buttons"]] == ["button", "button"]
        assert [b["type"] for b in chip["buttons"]] == ["button", "button"]
        assert [b["cls"] for b in chip["buttons"]] == ["suggested-tag-take", "suggested-tag-dismiss"]


@node
def test_each_half_is_named_and_says_what_it_does() -> None:
    study = _run()["chips"][0]["buttons"]
    take, dismiss = study
    assert take["label"] == "ph:plus study" and take["name"] == "Add tag study"
    assert take["title"] == "Add tag study. It mentions “assignment”."
    assert dismiss["label"] == "ph:x" and dismiss["name"] == "Dismiss tag study"
    assert dismiss["title"] == "Dismiss: stop suggesting #study for this note"
    for text in (take["name"], dismiss["name"], dismiss["title"]):
        assert chr(0x2014) not in text and "!" not in text and text[0].isupper()


@node
def test_take_adds_and_dismiss_turns_down_only_its_own_tag() -> None:
    assert _run()["sent"] == [
        {"take": ["study"]},
        {"discard": ["study"]},
        {"take": ["university"]},
        {"discard": ["university"]},
    ]
