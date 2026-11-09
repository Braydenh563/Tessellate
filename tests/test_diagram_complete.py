"""The Mermaid completion list in the Source pane (DD-5, owner 2026-11-09).

The pure half (`DGC-BEGIN` to `-END` of diagram-complete.js) runs in node: what the caret is on and the rows it earns. The
keys, the position under the caret and Escape closing the list before the move to the views are driven in a browser
(sweep numbers in the remaining file); here they are read for what they must hold.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"
COMPLETE = (JS / "diagram-complete.js").read_text(encoding="utf-8")
EMBED = (JS / "diagram-embed.js").read_text(encoding="utf-8")
MODEL = (JS / "documents-mermaid.js").read_text(encoding="utf-8")


def _rows(source: str, row: int, col: int, force: bool = False):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    region = COMPLETE[COMPLETE.index("// DGC-BEGIN") : COMPLETE.index("// DGC-END")]
    assert "document." not in region and "window." not in region
    model = (
        "const m = (() => { const ids = [...src.matchAll(/^\\s*([A-Za-z]\\w*)\\[(?:\"?)([^\\]\"]*)/gm)];"
        "return { nodes: ids.map((x) => ({ id: x[1], text: x[2] })), subgraphs: [] }; })();"
    )
    body = f"const src = {json.dumps(source)};\n{model}\nconsole.log(JSON.stringify(dgcRows(src, {row}, {col}, m, {str(force).lower()})));"
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(region + "\n" + body)
    try:
        out = subprocess.run([node, handle.name], capture_output=True, text=True, timeout=30, check=True)
    finally:
        Path(handle.name).unlink(missing_ok=True)
    got = json.loads(out.stdout)
    return got and [r["word"] for r in got["rows"]]


def test_the_first_word_of_a_blank_diagram_offers_the_headers():
    assert _rows("flo", 0, 3) == ["flowchart"]
    assert _rows("se", 0, 2) == ["sequenceDiagram"]
    assert _rows("g", 0, 1) is None  # one letter is a guess, not a question


def test_a_direction_follows_graph_and_flowchart():
    assert _rows("flowchart ", 0, 10, True) == ["TD", "TB", "LR", "RL", "BT"]
    assert _rows("graph L", 0, 7) == ["LR"]


def test_a_flowchart_line_start_offers_its_keywords_and_the_ids_it_has():
    src = 'flowchart TD\n  Start["Begin"]\n  Stop["End"]\n  su\n  St\n'
    assert _rows(src, 3, 4) == ["subgraph"]
    assert _rows(src, 4, 4) == ["style", "Start", "Stop"]
    assert _rows(src, 4, 4)[0] not in ("participant", "sequenceDiagram")


def test_after_a_block_an_arrow_is_offered_and_a_whole_arrow_closes_the_list():
    src = 'flowchart TD\n  Start["Begin"]\n  Start --\n'
    assert _rows(src, 2, 10) == ["-->", "---", "--x", "--o"]
    assert _rows('flowchart TD\n  A --> B\n  A -->', 2, 7) is None
    assert _rows("flowchart TD\n  my-id", 1, 7) is None  # a hyphen inside an id is not an arrow


def test_a_sequence_diagram_has_its_own_words_and_arrows_and_its_names():
    src = "sequenceDiagram\n  participant Alice\n  participant Bob\n  Alice->>Bob: hi\n  p\n  Al\n  Alice -\n"
    assert _rows(src, 4, 3) is None
    assert _rows(src, 4, 4, True) == ["participant"]
    assert "Alice" in _rows(src, 5, 4)
    assert _rows(src, 6, 9) == ["->>", "-->>", "->", "-->", "-x", "--)", "-)"]


def test_front_matter_and_comments_are_left_alone():
    assert _rows("---\ntitle: Plan\n---\nflowchart TD\n  st\n", 1, 6) is None
    assert _rows("flowchart TD\n  %% sub", 1, 8) is None


def test_the_list_is_the_documents_recipe_and_escape_closes_it_before_the_move_to_views():
    assert 'className = "rich-picker-list dgm-complete hidden"' in COMPLETE and "richPickerRow(" in COMPLETE
    for part in ('"role", "listbox"', '"role", "combobox"', "aria-activedescendant", "stopImmediatePropagation", '"mousedown"'):
        assert part in COMPLETE
    assert 'diagramComplete: ["/js/diagram-complete.js"]' in MODEL
    # Wired before Tab's indent, and the embed's own Escape (which moves to the views) steps aside while the list is open.
    assert EMBED.index("diagramModel.complete.wire(") < EMBED.index('field.addEventListener("keydown", (event) => {\n      if (!(event.key === "Tab"')
    assert "if (complete?.open()) return;" in EMBED
