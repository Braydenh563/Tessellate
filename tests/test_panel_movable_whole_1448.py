"""INBOX 1448: "dragging the ocr workspace only dragges the header and not the rest of the window".

`panelOf` took the head's own parent as the panel. The OCR workspace wraps its
head and tool row in `.ocr-head`, so the drag translated that wrapper alone.
The panel is now the dialog itself or the card that is its direct child, for
every head in `index.html`. The test runs the real `panelOf` over a small DOM
built from the page's own markup. Browser half, measured on 1440x900 with a
(+100,+66) drag: head (50,71) to (150,137) and card (29,54) to (129,120), body
(50,167) to (150,233): the same +100,+66 for all three (before: the card and
body did not move).
"""

import json
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "frontend" / "js" / "panel-movable.js").read_text(encoding="utf-8")
VOID = {"meta", "link", "input", "img", "br", "hr", "source", "path", "use"}


class _Tree(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.nodes: list[dict] = []
        self.stack: list[int] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.nodes.append(
            {"tag": tag, "id": a.get("id", ""), "cls": (a.get("class") or "").split(), "role": a.get("role", ""),
             "fixed": "data-panel-fixed" in a, "parent": self.stack[-1] if self.stack else -1}
        )
        if tag not in VOID:
            self.stack.append(len(self.nodes) - 1)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID and self.stack:
            self.stack.pop()

    def handle_endtag(self, tag):
        while self.stack and self.nodes[self.stack[-1]]["tag"] != tag:
            self.stack.pop()
        if self.stack:
            self.stack.pop()


def _function(name: str) -> str:
    start = JS.index(f"function {name}(")
    return JS[start : JS.index("\n}\n", start) + 3]


def test_every_head_in_the_page_moves_its_whole_panel() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    tree = _Tree()
    tree.feed((ROOT / "frontend" / "index.html").read_text(encoding="utf-8"))
    script = (
        f"const T = {json.dumps(tree.nodes)};\n"
        "class Element { constructor(i) { this.i = i; this.n = T[i]; }\n"
        "  get parentElement() { return this.n.parent < 0 ? null : els[this.n.parent]; }\n"
        "  isHost() { return this.n.tag === 'dialog' || this.n.role === 'dialog'; }\n"
        "  closest(sel) { for (let e = this; e; e = e.parentElement) {\n"
        "    if (sel === '[data-panel-fixed]' ? e.n.fixed : e.isHost()) return e; } return null; }\n"
        "  querySelector() { return els.find((e) => e.n.parent === this.i && e.n.cls.includes('dialog-head')) || null; } }\n"
        "const els = T.map((_, i) => new Element(i));\n"
        + _function("panelOf")
        + "\nconst bad = [];\n"
        "for (const head of els.filter((e) => e.n.cls.includes('dialog-head'))) {\n"
        "  const host = head.closest('dialog');\n"
        "  if (!host) continue;\n"
        "  const p = panelOf(head);\n"
        "  if (p === null) continue;\n"
        "  if (!(p === host || p.parentElement === host)) bad.push(host.n.id || head.n.cls.join('.'));\n"
        "}\n"
        "console.log(JSON.stringify({ heads: els.filter((e) => e.n.cls.includes('dialog-head')).length, bad }));\n"
    )
    out = subprocess.run([node, "-"], input=script, capture_output=True, text=True, check=True)
    result = json.loads(out.stdout.strip())
    assert result["heads"] > 20
    assert result["bad"] == [], f"a drag would move only part of: {result['bad']}"
