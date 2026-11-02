"""Documents audit 1102 quick wins (DX3, DX4, DX7, DX10, DX11, DX14, DX15, DX27, DX32).

Each class is fixed once, in the one function every caller asks. The pure
functions run in node here; the browser numbers (before and after) are in the
commit messages.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
DOCS = (JS / "documents.js").read_text(encoding="utf-8")

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not available")


def _slice(source: str, head: str, tail: str) -> str:
    start = source.index(head)
    return source[start : source.index(tail, start) + len(tail)]


def _node(script: str, *sources: str) -> dict:
    done = subprocess.run(
        ["node", "-e", "const vm=require('node:vm');const ctx={};vm.createContext(ctx);"
         "for (const s of JSON.parse(process.argv[1])) vm.runInContext(s, ctx);"
         "console.log(JSON.stringify(vm.runInContext(process.argv[2], ctx)));",
         json.dumps(list(sources)), script],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(done.stdout)


# DX3 -----------------------------------------------------------------------


@node
def test_dx3_a_pasted_block_starts_its_own_line():
    fit = _slice(DOCS, "docRichPasteEvent.fit = ", "\n};\n")
    out = _node(
        """({
          heading: docRichPasteEvent.fit("## Two\\n\\n- a", "Pick here please", ""),
          fence: docRichPasteEvent.fit("```\\ncode\\n```", "Pick ", ""),
          quote: docRichPasteEvent.fit("> quoted", "x", ""),
          table: docRichPasteEvent.fit("| a |\\n| - |", "x", ""),
          paras: docRichPasteEvent.fit("one\\n\\ntwo", "x", ""),
          before_and_after: docRichPasteEvent.fit("- a", "x", " tail"),
          at_line_start: docRichPasteEvent.fit("## Two", "", ""),
          indent_only: docRichPasteEvent.fit("## Two", "   ", ""),
          inline: docRichPasteEvent.fit("**bold**", "x", "y"),
          link: docRichPasteEvent.fit("[a](http://x)", "x", ""),
        })""",
        "function docRichPasteEvent() {}\n" + fit,
    )
    assert out["heading"] == "\n\n## Two\n\n- a"
    assert out["fence"].startswith("\n\n```")
    assert out["quote"] == "\n\n> quoted"
    assert out["table"].startswith("\n\n| a |")
    assert out["paras"] == "\n\none\n\ntwo"
    assert out["before_and_after"] == "\n\n- a\n\n"
    assert out["at_line_start"] == "## Two"
    assert out["indent_only"] == "## Two"
    assert out["inline"] == "**bold**"
    assert out["link"] == "[a](http://x)"


def test_dx3_the_paste_writes_the_fitted_text_and_offers_it():
    body = _slice(DOCS, "function docRichPasteEvent(event, view) {", "\n}\n")
    assert "docRichPasteEvent.fit(markdown," in body
    assert "insert: markdown" not in body
    assert "docPasteOfferRich(view, sel.from, insert," in body
