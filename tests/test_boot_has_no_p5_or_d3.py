"""The boot loads neither p5 nor d3 (audit 2026-10-05, FE-07).

p5 (1 MB raw, 239 KB gzipped) was fetched after every load for the emblem,
a still drawing turned by CSS; d3 (280 KB raw, 90 KB gzipped) was a blocking
script in the head for two lazy surfaces. The emblem became a 2D canvas
(pixel-matched against the p5 sketch by
`scratchpad/ui-sweeps/perf2-1005-emblem.js`), and since the tessellation mark
(2026-10-11) it is a few SVG layers; d3 is the first file of the two bundles
that use it.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"


def _function(text: str, name: str) -> str:
    start = text.index(f"function {name}(")
    # A wrapped file (row 37a) indents its functions, so the closing brace
    # sits at the function's own indent.
    indent = text[text.rindex("\n", 0, start) + 1 : start].replace("async ", "")
    return text[start : text.index(f"\n{indent}}}\n", start)]


def test_the_page_has_no_d3_script():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert not re.search(r'<script src="/vendor/d3', html)


def test_d3_leads_both_bundles_that_use_it():
    """D22 (2026-11-11): the `library` bundle no longer uses d3; the board code is the `boards`
    bundle (lazy-entries.js), the library files first and then d3 ahead of the first whiteboard file."""
    app = (JS / "app.js").read_text(encoding="utf-8")
    table = app[app.index("const LAZY_MODULES = {") :]
    graph = re.search(r"graph: \[([^\]]*)\]", table).group(1)
    assert re.findall(r'"(/[^"]+)"', graph)[0] == "/vendor/d3.v7.min.js", graph
    library = re.search(r"\n  library: \[(.*?)\]", table, re.S).group(1)
    assert "d3" not in library, "a first document open must not fetch d3"
    entries = (JS / "lazy-entries.js").read_text(encoding="utf-8")
    boards = re.findall(r'"(/[^"]+)"', re.search(r"\n  boards: \[(.*?)\n  \],", entries, re.S).group(1))
    assert boards.index("/vendor/d3.v7.min.js") < min(i for i, n in enumerate(boards) if n.startswith("/js/whiteboard")), boards


def test_a_file_two_bundles_share_is_fetched_once():
    app = (JS / "app.js").read_text(encoding="utf-8")
    assert "lazyFileLoads" in _function(app, "lazyScript")
    assert "files.map(lazyScript)" in _function(app, "ensureModule")


def test_the_emblem_needs_no_p5():
    shell = (JS / "phone-shell.js").read_text(encoding="utf-8")
    body = _function(shell, "renderEmblem")
    code = "\n".join(line for line in body.splitlines() if not line.lstrip().startswith("//"))
    assert "p5" not in code and "ensureP5" not in code
    assert "emblemArt(" in code
    avatar = (JS / "assistant-avatar.js").read_text(encoding="utf-8")
    assert "ensureP5" not in _function(avatar, "assistantEmblemInto")
