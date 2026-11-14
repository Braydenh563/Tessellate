"""Source text: the behaviour is front-end script that pytest cannot run without a browser, so these pin the code's text.

Suggestions for a mind map, a timeline and a sequence diagram (L-documents-21).

The pure lint in diagram-ai.js reads each kind's own model (diagram-kinds.js) and offers the removals a person would
make by hand: an empty period, a section with no periods, a participant nobody writes to, a block that holds no steps,
a branch said twice. Each row carries the uid it drops; `kindDrop` returns the model without it, printed by the kind.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _region(path: Path, name: str) -> str:
    text = path.read_text(encoding="utf-8")
    return text[text.index(f"// {name}-BEGIN") : text.index(f"// {name}-END")]


def _run(kind: str, source: str, steps: str = "return rows;"):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    code = "\n".join([
        _region(JS / "documents-mermaid.js", "DIAGRAM-MODEL"),
        _region(JS / "diagram-ops.js", "DIAGRAM-OPS"),
        _region(JS / "diagram-kinds.js", "DIAGRAM-KINDS"),
        _region(JS / "diagram-ai.js", "DIAGRAM-AI"),
        f"const k = diagramKinds.{kind}; const m = k.parse({json.dumps(source)}); const rows = diagramAiPure.kindLint({json.dumps(kind)}, m);",
        f"const result = (() => {{ {steps} }})();",
        "console.log(JSON.stringify({ result }));",
    ])
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(code)
    try:
        out = subprocess.run([node, handle.name], capture_output=True, text=True, timeout=60, check=True)
    finally:
        Path(handle.name).unlink(missing_ok=True)
    return json.loads(out.stdout)["result"]


def test_a_timeline_period_with_no_events_and_an_empty_section_are_found_and_dropped():
    source = "timeline\n  title History\n  2002\n  section Empty\n  section Early\n    2004 : Facebook\n"
    texts = _run("timeline", source, "return rows.map((r) => r.text);")
    assert "2002 has no events." in texts and "The section Empty has no periods." in texts
    out = _run("timeline", source, "const r = rows.find((x) => x.act === 'Remove the section'); return k.print(diagramAiPure.kindDrop(m, r.drop));")
    assert "section Empty" not in out and "section Early" in out and "Facebook" in out


def test_a_sequence_participant_nobody_writes_to_and_an_empty_block_are_found():
    source = "sequenceDiagram\n  participant A\n  participant B\n  participant C\n  A->>B: hi\n  loop never\n  end\n"
    texts = _run("sequence", source, "return rows.map((r) => r.text);")
    assert "C never sends or receives a message." in texts and "The loop block holds no steps." in texts
    out = _run("sequence", source, "const r = rows.find((x) => /participant/.test(x.act)); return k.print(diagramAiPure.kindDrop(m, r.drop));")
    assert "participant C" not in out and "A->>B: hi" in out


def test_a_mind_map_branch_said_twice_drops_the_second_and_a_clean_map_has_no_rows():
    source = "mindmap\n  root((Plan))\n    Budget\n    Budget\n    Risks\n"
    texts = _run("mindmap", source, "return rows.map((r) => r.text);")
    assert texts == ["Plan has Budget twice."]
    out = _run("mindmap", source, "return k.print(diagramAiPure.kindDrop(m, rows[0].drop));")
    assert out.count("Budget") == 1 and "Risks" in out
    assert _run("mindmap", "mindmap\n  root((Plan))\n    Budget\n    Risks\n", "return rows.length;") == 0


def test_a_message_keeps_its_participants_even_when_a_note_names_them():
    source = "sequenceDiagram\n  participant A\n  participant B\n  Note over A,B: shared\n"
    assert _run("sequence", source, "return rows.length;") == 0
