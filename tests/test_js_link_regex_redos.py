"""The browser's link and picture scanners cannot be frozen by a long unclosed run (L568).

`[^\\]\\n]*` followed by a literal `]` is quadratic on a long run of `[` or `![`
(each start scans to the end), and `[^)\\s]+` beside `[^)\\n]*` split a run two
ways. Python's scanners have such tests (`test_doc_graph.py`, `test_file_editing.py`);
these are the JS side, run in node on the regex literals as they are written in
the source, plus an oracle: a hand-written scanner that strips pictures the way
the stated grammar says, which the regex must agree with on a seeded corpus.
"""

from __future__ import annotations

import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

#: (file, text the literal starts at, text it ends at, flags the source uses)
SCANNERS = {
    "status picture strip": ("status.js", ".replace(/!\\[", "/g, \"\")", "g"),
    "document link check": ("documents-prose.js", "const links = /", "/g;", "g"),
    "document wiki grammar": ("documents-prose.js", "const DOC_GRAMMAR_WIKI = /", "/g;", "g"),
    "note pick picture": ("note-pick-preview.js", "const NOTE_PICK_IMAGE = /", "/;", ""),
}


def _literal(name: str) -> str:
    file, start, end, _flags = SCANNERS[name]
    text = (JS / file).read_text(encoding="utf-8")
    at = text.index(start) + (len(start) if start.endswith("/") else len(".replace(/"))
    if start.startswith(".replace"):
        at = text.index(start) + len(".replace(/")
    return text[at : text.index(end, at)]


def _node(body: str) -> object:
    out = subprocess.run(["node", "-"], input=body, capture_output=True, text=True, timeout=90)
    assert out.returncode == 0, out.stderr[-600:]
    return json.loads(out.stdout.strip().splitlines()[-1])


def _timed(name: str) -> dict:
    _file, _start, _end, flags = SCANNERS[name]
    source = _literal(name)
    return _node(
        f"const rx = new RegExp({json.dumps(source)}, {json.dumps(flags)});"
        "const N = 40000; const shapes = {"
        "'[': '['.repeat(N), '![': '!['.repeat(N / 2), '[[': '[['.repeat(N / 2),"
        "'[a](': '[a]('.repeat(N / 4), '![a](': '![a]('.repeat(N / 5), '[a](b': '[a](b'.repeat(N / 5)};"
        "const took = {}; for (const [k, s] of Object.entries(shapes)) {"
        "const t = Date.now(); s.replace(rx, ''); took[k] = Date.now() - t; }"
        "console.log(JSON.stringify(took));"
    )


@node
@pytest.mark.parametrize("name", sorted(SCANNERS))
def test_a_long_unclosed_run_is_read_in_well_under_a_second(name):
    took = _timed(name)
    assert max(took.values()) < 800, (name, took)


def _oracle_strip(text: str) -> str:
    """`![alt](address)` removed: alt up to 99 characters with no `]` or newline,
    the address up to 999 with no `)` or newline. A scanner, not a regex."""
    out: list[str] = []
    i = 0
    while i < len(text):
        if text.startswith("![", i):
            close = text.find("]", i + 2)
            alt = text[i + 2 : close] if close != -1 else None
            if alt is not None and len(alt) <= 99 and "\n" not in alt and text.startswith("(", close + 1):
                end = text.find(")", close + 2)
                inner = text[close + 2 : end] if end != -1 else None
                if inner is not None and len(inner) <= 999 and "\n" not in inner:
                    i = end + 1
                    continue
        out.append(text[i])
        i += 1
    return "".join(out)


def _corpus() -> list[str]:
    rng = random.Random(568)
    bits = ["![", "[", "]", "(", ")", "a", "b c", "\n", " ", "http://x/y.png", "!", "# ", "**"]
    return ["".join(rng.choice(bits) for _ in range(rng.randint(0, 24))) for _ in range(600)]


@node
def test_the_picture_strip_agrees_with_a_hand_written_scanner():
    source = _literal("status picture strip")
    corpus = _corpus()
    got = _node(
        f"const rx = new RegExp({json.dumps(source)}, 'g');"
        f"const corpus = {json.dumps(corpus)};"
        "console.log(JSON.stringify(corpus.map((s) => s.replace(rx, ''))));"
    )
    wrong = [(s, g, _oracle_strip(s)) for s, g in zip(corpus, got) if g != _oracle_strip(s)]
    assert not wrong, wrong[:3]


@node
def test_the_bounded_literals_keep_the_shapes_the_features_read():
    source = _literal("document link check")
    got = _node(
        f"const rx = new RegExp({json.dumps(source)}, 'g');"
        "const s = 'see [docs](https://a.b/c \"title\") and ![alt text](pic.png) and [](x)';"
        "console.log(JSON.stringify([...s.matchAll(rx)].map((m) => [m[1], m[2], m[3]])));"
    )
    assert got == [["", "docs", "https://a.b/c"], ["!", "alt text", "pic.png"], ["", "", "x"]]
