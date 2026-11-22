"""L628 (Brief 94 decision (a): one meaning layer for every search box, the
Library boxes named): the Library and graph filter boxes matched the words as
typed only, so "my notes about harbours" or "harbuor" found nothing while
"harbour" found the note. The boxes' test (`meaningAlts` once per search, then
`meaningHolds` per row, inlined in each box: the shared scope only shrinks): the plain words
anywhere in the text, or every thing the query names held by it (an ending, a
synonym, a slip of a word the notes themselves use, the request's own words
dropped). Run on the real meaning.js with the real tables (`GET /read/words`).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tessellate.ai import meaning

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"

HARNESS = """
const vm = require("vm"), fs = require("fs");
const table = JSON.parse(process.argv[2]);
const ctx = vm.createContext({ document: { addEventListener() {}, dispatchEvent() {} }, Event: function () {}, apiJson: () => Promise.resolve(table), setTimeout, clearTimeout });
ctx.window = ctx;
vm.runInContext(fs.readFileSync(process.argv[1], "utf8"), ctx);
ctx.meaningAsk();
setTimeout(() => {
  const texts = ["Harbour walk: the tide tables", "Dark theme notes", "Shopping list"];
  const vocab = new Set(texts.join(" ").toLowerCase().match(/[a-z0-9]+/g));
  const out = {};
  for (const q of JSON.parse(process.argv[3])) {
    const things = ctx.meaningAlts(q, vocab);
    const test = (text) => text.includes(q) || ctx.meaningHolds(things, text);
    out[q] = texts.filter((t) => test(t.toLowerCase()));
  }
  console.log(JSON.stringify(out));
}, 0);
"""


def _matches(queries: list[str]) -> dict[str, list[str]]:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    out = subprocess.run(
        [node, "-e", HARNESS, str(JS / "meaning.js"), json.dumps(meaning.table()), json.dumps(queries)],
        capture_output=True, text=True,
    )
    assert out.returncode == 0, out.stderr[-600:]
    return json.loads(out.stdout)


def test_the_plain_words_still_match_anywhere() -> None:
    got = _matches(["harbour", "tide tab", "list"])
    assert got["harbour"] == ["Harbour walk: the tide tables"]
    assert got["tide tab"] == ["Harbour walk: the tide tables"]
    assert got["list"] == ["Shopping list"]


def test_an_ending_a_slip_and_the_request_words_are_read() -> None:
    got = _matches(["harbours", "harbuor", "find my harbour notes", "night"])
    assert got["harbours"] == ["Harbour walk: the tide tables"]
    assert got["harbuor"] == ["Harbour walk: the tide tables"]
    assert got["find my harbour notes"] == ["Harbour walk: the tide tables"]
    assert got["night"] == ["Dark theme notes"]


def test_a_word_no_note_holds_matches_nothing() -> None:
    assert _matches(["zebra"])["zebra"] == []


def test_both_boxes_use_it_and_load_the_layer() -> None:
    app = (JS / "app.js").read_text(encoding="utf-8")
    for bundle in ("library", "graph"):
        start = app.index(f"  {bundle}: [")
        assert '"/js/meaning.js"' in app[start : app.index("]", start)], bundle
    for name in ("library.js", "graph.js"):
        text = (JS / name).read_text(encoding="utf-8")
        assert "meaningAlts(query" in text and "meaningHolds(things, " in text, name
