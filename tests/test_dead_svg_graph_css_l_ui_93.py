"""Source text: whether a stylesheet still styles a renderer that no longer
exists is a fact of the files (L-ui-modernisation-93). The graph is a canvas
(graph-canvas.js) and the only SVG it makes is the minimap's
`graph-minimap-here` ring, so a rule for `.graph-node`, `.graph-edge`,
`.graph-core` or `.graph-label` reached nothing and only cost the cascade."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEAD = re.compile(r"\.graph-(node|edge|core|label)(?![\w-])")


def _without_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def test_no_stylesheet_selects_the_svg_graphs_elements():
    found = []
    for path in sorted((ROOT / "frontend" / "css").glob("*.css")):
        for n, line in enumerate(_without_comments(path.read_text(encoding="utf-8")).splitlines(), 1):
            if DEAD.search(line):
                found.append(f"{path.name}: {line.strip()}")
    assert found == []


def test_no_script_makes_those_elements():
    for path in sorted((ROOT / "frontend" / "js").glob("*.js")):
        code = re.sub(r"//.*", "", path.read_text(encoding="utf-8"))
        assert not re.search(r"[\"'` ]graph-(node|edge|core|label)[\"'` ]", code), path.name
