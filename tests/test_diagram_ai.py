"""The AI in the diagram builder, the browser half (dgai-1110; docs/roadmap/agent-remaining/dgai-1110.md F2, F6 to F8).

`DIAGRAM-AI-BEGIN` to `-END` in diagram-ai.js is pure: the ops the Ask box and Suggestions get are played through
`diagramOps` (the pane's one writer), diffed and drawn as one marked picture, and the lint finds what F6 lists. It runs
here in node beside the model's and the ops' regions. The rest of the file is read for what it must and must not hold.
"""

from __future__ import annotations

import gzip
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
AI = JS / "diagram-ai.js"


def _region(path: Path, name: str) -> str:
    text = path.read_text(encoding="utf-8")
    return text[text.index(f"// {name}-BEGIN") : text.index(f"// {name}-END")]


def _run(source: str, steps: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    pure = _region(AI, "DIAGRAM-AI")
    assert "document." not in pure and "window." not in pure and "eval(" not in pure and "Function(" not in pure
    code = "\n".join([
        _region(JS / "documents-mermaid.js", "DIAGRAM-MODEL"),
        _region(JS / "diagram-ops.js", "DIAGRAM-OPS"),
        pure,
        f"const m = diagramModel.parse({json.dumps(source)}); const o = diagramOps; const ai = diagramAiPure;",
        f"const result = (() => {{ {steps} }})();",
        "console.log(JSON.stringify({ result, src: diagramModel.print(m) }));",
    ])
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(code)
    try:
        out = subprocess.run([node, handle.name], capture_output=True, text=True, timeout=60, check=True)
    finally:
        Path(handle.name).unlink(missing_ok=True)
    return json.loads(out.stdout)


SHOP = """flowchart TD
  subgraph G1 ["Warehouse"]
    B{"In stock?"}
    C["Ship it"]
  end
  A(["Order placed"])
  A --> B
  B -->|Yes| C
"""


def test_the_asks_ops_apply_through_the_panes_own_functions():
    out = _run(SHOP, """
      const ops = [
        { op: "add", text: "Refund", shape: "rect", after: "B", label: "No", group: "G1" },
        { op: "rename", target: "G1", text: "Fulfilment" },
      ];
      const before = JSON.parse(JSON.stringify(m));
      const run = ai.apply(m, ops, o);
      return { run, diff: ai.diff(before, m), name: ai.name(before, ops), said: ops.map((op) => ai.say(before, op)) };
    """)
    r = out["result"]
    assert r["run"] == {"done": 2, "refused": 0}
    assert 'subgraph G1 ["Fulfilment"]' in out["src"] and 'D["Refund"]' in out["src"] and 'B -->|"No"| D' in out["src"]
    assert r["diff"]["added"] == ["n:D"] and r["diff"]["changed"] == ["g:G1"]
    assert r["name"] == "AI: added Refund after In stock? (No) and 1 more change"
    assert r["said"] == ["Add Refund after In stock? (No)", "Rename Warehouse to Fulfilment"]


def test_ops_from_outside_are_refused_unless_they_apply():
    out = _run(SHOP, """
      return ai.apply(m, [
        { op: "eval", code: "1" }, null, "x", { op: "rename", target: "Nobody", text: "a" },
        { op: "join", from: "A", to: "A" }, { op: "nest", target: "G1", group: "G1" },
        { op: "delete", from: "A", to: "C" }, { op: "add", text: "<img src=x onerror=1>", shape: "script" },
      ], o);
    """)
    #: The last is a plain box whose words are text; the printer quotes them (D2).
    assert out["result"] == {"done": 1, "refused": 7}
    assert "#lt;img" in out["src"] or "&lt;img" in out["src"] or '"<img' in out["src"]
    many = _run(SHOP, 'return ai.apply(m, Array.from({ length: 30 }, (_, i) => ({ op: "add", text: `S${i}` })), o);')
    assert many["result"] == {"done": 12, "refused": 18}


def test_the_marked_picture_puts_back_what_went_and_colours_each_kind():
    out = _run(SHOP, """
      const before = JSON.parse(JSON.stringify(m));
      ai.apply(m, [{ op: "delete", target: "C" }, { op: "add", text: "Refund", after: "B", label: "No" }, { op: "rename", target: "A", text: "Ordered" }], o);
      return ai.marked(before, m, diagramModel.print, { add: "#00aa00", del: "#aa0000", chg: "#aaaa00" });
    """)
    src = out["result"]["source"]
    assert "style D fill:" in src and "stroke:#00aa00" in src
    assert 'C["Ship it"]' in src and "stroke:#aa0000" in src and 'B -.->|"Yes"| C' in src
    assert "style A fill:" in src and "stroke:#aaaa00" in src
    #: The model itself keeps no mark: the preview is a copy.
    assert "#00aa00" not in out["src"]


def test_the_lint_finds_what_f6_lists_and_each_apply_fixes_it():
    source = """flowchart TD
  subgraph G1 ["Lonely"]
    E["Pack"]
  end
  A{"Paid?"}
  B["Pack"]
  C["Wait"]
  D["Stray"]
  A --> B
  B --> C
"""
    out = _run(source, """
      const found = ai.lint(m, o);
      const texts = found.map((f) => f.text);
      for (const f of found) ai.apply(m, f.ops, o);
      return { texts, acts: found.map((f) => f.act), after: ai.lint(m, o).map((f) => f.text) };
    """)
    r = out["result"]
    assert "An arrow out of Paid? has no words." in r["texts"]
    assert "Paid? has one way out; its no branch leads off the diagram." in r["texts"]
    assert "Wait has no way out." in r["texts"]
    assert "Stray is not joined to anything." in r["texts"]
    assert "Two blocks say Pack." in r["texts"]
    assert "The group Lonely holds one block." in r["texts"]
    assert 'A -->|"yes"| B' in out["src"] and "subgraph" not in out["src"]
    #: What is left is the new Ends' own: none of the six come back.
    assert not [t for t in r["after"] if "Paid?" in t or "Lonely" in t or "Two blocks" in t or "not joined" in t]


def test_the_file_is_lazy_and_the_builder_stays_in_budget():
    text = AI.read_text(encoding="utf-8")
    assert 'diagramAi: ["/js/diagram-ai.js"]' in (JS / "documents-mermaid.js").read_text(encoding="utf-8")
    builder = (JS / "diagram-builder.js").read_text(encoding="utf-8")
    wire = builder.index('ensureModule("diagramAi"))) diagramModel.ai.wire(S, helpers)')
    #: Before the menu is rebuilt, so the Versions row shows on the first open.
    assert wire < builder.index("if (S) refreshMore(S);")
    assert len(gzip.compress((JS / "diagram-builder.js").read_bytes(), 9)) <= 12000
    #: One closure, one export, and nothing the model wrote becomes markup.
    assert text.count("diagramModel.ai = ") == 1 and "innerHTML" not in text and "insertAdjacentHTML" not in text
    #: Versions are the document's (F7, F8): the revisions route, no store of its own.
    assert "/revisions" in text and "localStorage" not in text and "indexedDB" not in text
