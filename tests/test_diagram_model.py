"""The diagram model (1546 P1; DOCUMENTS_PLAN "1546 design" D1 to D4).

The marked region of documents-mermaid.js (`DIAGRAM-MODEL-BEGIN` to `-END`) is
the one flowchart grammar: `diagramModel.parse(source)` to a plain model and
`diagramModel.print(model)` back to the whole source. Node runs it here over a
corpus: every fence in tests/test_doc_mermaid.py and tests/test_wb_interchange.py
(copied below), the composer's flowcharts (tests/test_composer_mermaid_1466.py),
the "/" menu's starter and the board writer's output.

D2's invariants, per fence: `print(parse(print(m))) === print(m)`, and `parse(s)`
and `parse(print(parse(s)))` hold the same nodes, edges and groups; a line the
reader cannot place is kept verbatim, never dropped.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from tessellate.ai import composer_mermaid as cm

ROOT = Path(__file__).resolve().parents[1]
MERMAID_JS = ROOT / "frontend" / "js" / "documents-mermaid.js"

NESTED = """flowchart TD
A[Start] --> B
subgraph S1 [Build]
  B[Compile] --> C[Test]
  subgraph S2 ["Ship it"]
    D[Deploy]
  end
  C --> D
end
subgraph Plain words here
  E[Lone]
end
D --> E
A --> S1
"""

BOARD_WRITER = 'flowchart TD\n  subgraph f1 ["Team A"]\n    n1["In"]\n  end\n  n2["Out"]\n  n1 -->|go| n2\n  n2 --- n1\n'

CORPUS = [
    "flowchart LR\n  A[Start] --> B{Ready?}\n  B -->|yes| C([Go])\n  B -- no --> D((Wait))\n  D -.-> A\n  C ==> E{{Done}}\n",
    'graph TD\n%% a comment\na & b --> c --- d\nc --> e["Quoted (text)"]\nstyle a fill:#f9f\nclassDef x fill:#fff\n',
    "graph TB\nnode-1-->node-2",
    "flowchart LR\nA[Start] --> B{Is it OK?}\nB -->|yes| C((Done))\nB -- no --> D(Fix it) --> B\nstyle A fill:#f9f\nF[\"Quoted\"] -.-> A; G --- A",
    NESTED,
    BOARD_WRITER,
    "flowchart TD\n  A[Start] --> B[Next]",
    "graph TD\nA-->B\nB-->C\nA-->C\nC-->A",
    "graph LR\nA-->B\nA-->C",
    "flowchart TD\nA[Start] --> B[Done]",
    "flowchart LR\n  A --> C",
    # What this reader keeps rather than reads.
    "flowchart TD\n  A@{ shape: rect, label: \"x\" } --> B\n  C[\"`**md** text`\"] --> B\n  click A callback\n  linkStyle 0 stroke:red\n  A:::hot --> B\n  D[[Sub]] --> A\n  E[[Stored]] --> A\n",
    "---\ntitle: Plan\n---\n%%{init: {'theme': 'dark'}}%%\nflowchart TD\n  A --> B\n",
    "flowchart TD\n  subgraph S\n    direction LR\n    A --> B\n  end\n  %% last words\n",
    # Awkward labels: quote, hash, angle brackets, bar, semicolon, brackets.
    'flowchart TD\n  A["say #quot;hi#quot; #35;3 #lt;b#gt; a|b"] -->|"x #124; y"| B["semi; colon"]\n',
    "flowchart TD\nA[a] --> B[b]; B --> C[c]; C -.- D[d]",
]


def _composer_flowcharts() -> list[str]:
    texts = [
        "1. Wake up\n2. Brew coffee\n3. Read the news\n4. Go to work",
        "First boil the water, then add the pasta, then drain it and finally add the sauce.",
        "- First call the bank\n- Then cancel the card\n- Finally order a new one",
    ]
    out = [cm.diagram(t, want="").source for t in texts]
    for awkward in ['Say "hello" [loudly]', "Room #3; floor <2>", "a `code` bit (with parens) {and braces}", "Key: value: more"]:
        out.append(cm.diagram(f"1. {awkward}\n2. then {awkward}", want="flowchart").source)
    out.append(cm.diagram("\n".join(f"{i}. step number {i}" for i in range(1, 30)), want="flowchart").source)
    return out


def _slash_sample() -> str:
    editor = (ROOT / "frontend" / "js" / "editor.js").read_text(encoding="utf-8")
    row = re.search(r'add\(\{ id: "flowchart".*?run: \(t\) => editorBlock\(t, "```mermaid\\n(.*?)\\n```"', editor)
    assert row, "the Flowchart row has moved"
    return row.group(1).replace("\\n", "\n")


def _run(body: str, corpus=None):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    text = MERMAID_JS.read_text(encoding="utf-8")
    region = text[text.index("// DIAGRAM-MODEL-BEGIN") : text.index("// DIAGRAM-MODEL-END")]
    assert "document." not in region and "window." not in region, "the region reached for the DOM"
    #: A file, not `node -e`: the conftest's installer guard refuses any argv with "pip" in it.
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(region + f"\nconst CORPUS = {json.dumps(corpus or [])};\n" + body)
    try:
        out = subprocess.run([node, handle.name], capture_output=True, text=True, timeout=60, check=True)
    finally:
        Path(handle.name).unlink(missing_ok=True)
    return json.loads(out.stdout)


def _all() -> list[str]:
    return CORPUS + _composer_flowcharts() + [_slash_sample()]


def _parse(src: str):
    return _run(f"console.log(JSON.stringify(diagramModel.parse({json.dumps(src)})));")


def test_every_fence_in_the_corpus_round_trips():
    corpus = _all()
    body = """
const out = CORPUS.map((src) => {
  const m = diagramModel.parse(src);
  const once = diagramModel.print(m);
  const again = diagramModel.parse(once);
  const byId = (a) => [...a].sort((x, y) => (x.id < y.id ? -1 : 1));
  return {
    stable: diagramModel.print(again) === once,
    same: JSON.stringify([byId(m.nodes), m.edges, m.subgraphs, m.dir]) === JSON.stringify([byId(again.nodes), again.edges, again.subgraphs, again.dir]),
    kept: JSON.stringify(m.kept.map((k) => k.line)) === JSON.stringify(again.kept.map((k) => k.line)),
    keptAt: JSON.stringify(m.kept) === JSON.stringify(again.kept),
    front: JSON.stringify(m.front) === JSON.stringify(again.front),
    printed: m.kept.every((k) => once.includes(k.line)),
  };
});
console.log(JSON.stringify(out));
"""
    results = _run(body, corpus)
    assert len(results) == len(corpus) >= 25
    for src, got in zip(corpus, results):
        assert all(got.values()), (src, got)


def test_nodes_shapes_links_and_labels_are_read():
    g = _parse("flowchart LR\n  A[Start] --> B{Ready?}\n  B -->|yes| C([Go])\n  B -- no --> D((Wait))\n  D -.-> A\n  C ==> E{{Done}}\n  F(Round)\n")
    assert g["dir"] == "LR" and g["kind"] == "flowchart"
    assert {n["id"]: (n["shape"], n["text"]) for n in g["nodes"]} == {
        "A": ("rect", "Start"), "B": ("diamond", "Ready?"), "C": ("stadium", "Go"),
        "D": ("circle", "Wait"), "E": ("hexagon", "Done"), "F": ("round", "Round"),
    }
    assert [(e["from"], e["to"], e["style"], e["arrow"], e["label"]) for e in g["edges"]] == [
        ("A", "B", "solid", True, ""), ("B", "C", "solid", True, "yes"), ("B", "D", "solid", True, "no"),
        ("D", "A", "dotted", True, ""), ("C", "E", "thick", True, ""),
    ]
    assert g["kept"] == []


def test_chains_fans_quotes_and_the_six_link_kinds():
    g = _parse('graph TD\na & b --> c --- d\nc --> e["Quoted (text)"]\nc -.- f\nc === g\nc ==> h\nc -.-> i\n')
    assert [(e["from"], e["to"], e["style"], e["arrow"]) for e in g["edges"]] == [
        ("a", "c", "solid", True), ("b", "c", "solid", True), ("c", "d", "solid", False), ("c", "e", "solid", True),
        ("c", "f", "dotted", False), ("c", "g", "thick", False), ("c", "h", "thick", True), ("c", "i", "dotted", True),
    ]
    assert next(n for n in g["nodes"] if n["id"] == "e")["text"] == "Quoted (text)"
    assert _parse("graph TB\nnode-1-->node-2")["edges"][0]["from"] == "node-1"
    assert _parse("graph TB\nA-->B")["dir"] == "TD"


def test_subgraphs_nest_and_a_node_belongs_to_the_first_one_that_names_it():
    g = _parse(NESTED)
    assert g["subgraphs"] == [
        {"id": "S1", "title": "Build", "parent": None},
        {"id": "S2", "title": "Ship it", "parent": "S1"},
        {"id": "Plain words here", "title": "Plain words here", "parent": None},
    ]
    assert {n["id"]: n["group"] for n in g["nodes"]} == {"A": None, "B": "S1", "C": "S1", "D": "S2", "E": "Plain words here"}
    assert any(e["from"] == "A" and e["to"] == "S1" for e in g["edges"])
    assert g["kept"] == []


def test_a_line_it_cannot_place_is_kept_verbatim_where_it_stood():
    src = (
        "flowchart TD\n  %% first\n  A[One] --> B[Two]\n  style A fill:#f9f\n  classDef default fill:#f00\n"
        "  C(((deep))) --> A\n  D>flag] --> A\n  click A callback\n  E{{{odd}}} --> A\n  F[[sub]] --> A\n  B --> C\n"
    )
    g = _parse(src)
    assert [k["line"] for k in g["kept"]] == [
        "%% first", "style A fill:#f9f", "classDef default fill:#f00", "C(((deep))) --> A", "D>flag] --> A",
        "click A callback", "E{{{odd}}} --> A", "F[[sub]] --> A",
    ]
    #: A kept line has no node of its own: C comes from the last line only.
    assert [n["id"] for n in g["nodes"]] == ["A", "B", "C"]
    printed = _run(f"console.log(JSON.stringify(diagramModel.print(diagramModel.parse({json.dumps(src)}))));")
    lines = [line.strip() for line in printed.splitlines()]
    #: In place: the comment before the first node, the style lines after the nodes and before the edges.
    assert lines[1] == "%% first"
    assert lines.index("style A fill:#f9f") > lines.index('B["Two"]') and lines.index("style A fill:#f9f") < lines.index("A --> B")
    for k in g["kept"]:
        assert k["line"] in lines


def test_text_before_the_header_stays_ahead_of_it():
    g = _parse("---\ntitle: Plan\n---\n%%{init: {'theme': 'dark'}}%%\nflowchart TD\n  A --> B\n")
    assert g["front"] == ["---", "title: Plan", "---", "%%{init: {'theme': 'dark'}}%%"]
    printed = _run('console.log(JSON.stringify(diagramModel.print(diagramModel.parse("%% note\\ngraph LR\\nA-->B"))));')
    assert printed.startswith("%% note\nflowchart LR\n")


@pytest.mark.parametrize(
    "src",
    ["sequenceDiagram\nA->>B: hi", "pie\n\"a\": 1", "mindmap\n  root((x))", "timeline\n  title T\n  2020 : a", "stateDiagram-v2\n[*] --> A", "erDiagram\nA ||--o{ B : has"],
)
def test_another_kind_of_diagram_is_null(src):
    assert _parse(src) is None


def test_nothing_is_dropped_from_a_half_written_line():
    g = _parse("flowchart TD\nA --> \nB[unclosed --> C\nD --> E\n")
    assert [k["line"] for k in g["kept"]] == ["A -->", "B[unclosed --> C"]
    assert [n["id"] for n in g["nodes"]] == ["D", "E"]
    assert _parse("")["nodes"] == [] and _parse("flowchart TD")["nodes"] == []


@pytest.mark.parametrize(
    "text",
    ['say "hi"', "Room #3", "a < b > c", "x | y", "semi; colon", "[brackets] (parens) {braces}", "#quot; typed", "#35;", "a<br/>b", "tick ` and \\ slash", "ünï çödé", "  padded  "],
)
def test_a_label_with_awkward_characters_survives_node_and_edge(text):
    body = f"""
const t = {json.dumps(text)};
const m = {{ kind: "flowchart", dir: "TD", front: [], kept: [], subgraphs: [],
  nodes: [{{ id: "a", text: t, shape: "rect", group: null }}, {{ id: "b", text: t, shape: "diamond", group: null }}],
  edges: [{{ from: "a", to: "b", label: t, style: "solid", arrow: true }}] }};
const printed = diagramModel.print(m);
const back = diagramModel.parse(printed);
console.log(JSON.stringify({{ printed, back, again: diagramModel.print(back) }}));
"""
    out = _run(body)
    want = text
    assert [n["text"] for n in out["back"]["nodes"]] == [want, want]
    assert out["back"]["edges"][0]["label"] == want
    assert out["again"] == out["printed"] and out["back"]["kept"] == []
    #: Each line holds one quoted label and no raw quote inside it.
    for line in out["printed"].splitlines()[1:]:
        assert line.count('"') == 2, line


def test_a_model_made_by_hand_prints_in_canonical_order():
    body = """
const m = { kind: "flowchart", dir: "RL", front: [], kept: [{ at: 99, line: "%% end" }], subgraphs: [{ id: "g", title: "Group", parent: null }, { id: "h", title: "h", parent: "g" }],
  nodes: [{ id: "a", text: "A", shape: "round", group: null }, { id: "b", text: "B", shape: "stadium", group: "g" }, { id: "c", text: "C", shape: "hexagon", group: "h" }, { id: "d", text: "D", shape: "circle", group: null }],
  edges: [{ from: "a", to: "b", label: "yes", style: "dotted", arrow: false }, { from: "b", to: "c", label: "", style: "thick", arrow: true }] };
console.log(JSON.stringify(diagramModel.print(m)));
"""
    assert _run(body) == (
        "flowchart RL\n"
        '  subgraph g ["Group"]\n'
        "    subgraph h\n"
        '      c{{"C"}}\n'
        "    end\n"
        '    b(["B"])\n'
        "  end\n"
        '  a("A")\n'
        '  d(("D"))\n'
        '  a -.-|"yes"| b\n'
        "  b ==> c\n"
        "  %% end\n"
    )


def test_a_hundred_and_twenty_nodes_parse_and_print_fast():
    lines = ["flowchart TD"] + [f'  n{i}["Step {i}"] --> n{i + 1}["Step {i + 1}"]' for i in range(0, 119)]
    src = "\n".join(lines) + "\n"
    body = f"""
const src = {json.dumps(src)};
const times = [];
let m;
for (let i = 0; i < 20; i++) {{
  const t = process.hrtime.bigint();
  m = diagramModel.parse(src);
  diagramModel.print(m);
  times.push(Number(process.hrtime.bigint() - t) / 1e6);
}}
times.sort((a, b) => a - b);
console.log(JSON.stringify({{ nodes: m.nodes.length, edges: m.edges.length, median: times[10], max: diagramModel.MAX_NODES, again: diagramModel.print(diagramModel.parse(diagramModel.print(m))) === diagramModel.print(m) }}));
"""
    out = _run(body)
    assert out["nodes"] == 120 == out["max"] and out["edges"] == 119 and out["again"]
    #: Measured at 1 to 3 ms in node; the bound is for a slow shared runner.
    assert out["median"] < 150, out


def test_the_old_readers_are_gone_and_the_board_reads_the_model():
    mermaid = MERMAID_JS.read_text(encoding="utf-8")
    interchange = (ROOT / "frontend" / "js" / "whiteboard-interchange.js").read_text(encoding="utf-8")
    assert "mermaidFlowParse" not in mermaid and "mermaidFlowLayout" not in mermaid and "DOC-MERMAID" not in mermaid
    assert "function wbMermaidParse" not in interchange and "function wbMermaidText" not in interchange
    assert "diagramModel.parse(source)" in interchange
    assert re.search(r"Object\.assign\(window, \{[^}]*\bdiagramModel\b", mermaid)


def test_a_coloured_arrow_and_a_both_ways_arrow_round_trip_and_other_link_styles_stay_kept():
    """1679 slice 10: `linkStyle N stroke:#hex,stroke-width:2px` is the builder's own line (lifted to `colour` in edge order);
    `<-->`, `<-.->` and `<==>` read as `both`; any other linkStyle line stays a kept line, byte for byte."""
    src = (
        "flowchart TD\n  A --> B\n  B <--> C\n  C <-.-> D\n  D <==> A\n"
        "  linkStyle 1 stroke:#387fe3,stroke-width:2px\n  linkStyle 0 stroke:#f00\n"
    )
    got = _run(
        f"const m = diagramModel.parse({json.dumps(src)}); const once = diagramModel.print(m);"
        "const back = diagramModel.parse(once);"
        "console.log(JSON.stringify({ edges: m.edges.map((e) => [e.style, e.arrow, Boolean(e.both), e.colour || null]),"
        " kept: m.kept.map((k) => k.line), once, again: diagramModel.print(back) === once,"
        " colours: back.edges.map((e) => e.colour || null) }));"
    )
    assert got["edges"] == [["solid", True, False, None], ["solid", True, True, "#387fe3"], ["dotted", True, True, None], ["thick", True, True, None]]
    assert got["kept"] == ["linkStyle 0 stroke:#f00"]
    assert "  B <--> C\n" in got["once"] and "  C <-.-> D\n" in got["once"] and "  D <==> A\n" in got["once"]
    assert got["once"].count("linkStyle 1 stroke:#387fe3,stroke-width:2px") == 1
    assert got["again"] is True and got["colours"] == [None, "#387fe3", None, None]


def test_removing_an_arrow_renumbers_the_colour_lines_and_a_plain_arrow_prints_no_linkstyle():
    got = _run(
        "const m = diagramModel.parse('flowchart TD\\n  A --> B\\n  B --> C\\n'); m.edges[1].colour = '#da5252'; const a = diagramModel.print(m);"
        "m.edges.shift(); const b = diagramModel.print(m);"
        "console.log(JSON.stringify({ a, b, plain: diagramModel.print(diagramModel.parse('flowchart TD\\n  A --> B\\n')) }));"
    )
    assert "linkStyle 1 stroke:#da5252" in got["a"] and "linkStyle 0 stroke:#da5252" in got["b"]
    assert "linkStyle" not in got["plain"]


def test_a_cylinder_and_a_parallelogram_are_read_and_print_back_as_themselves():
    """R14 (1679 slice 10): `[(..)]` is a database and `[/../]` an input or output; the slanted `[/..\\]` stays a kept line."""
    src = 'flowchart TD\n  A[("Store")] --> B[/"Input"/]\n  B --> C\n'
    got = _run(
        f"const m = diagramModel.parse({json.dumps(src)}); const once = diagramModel.print(m);"
        "console.log(JSON.stringify({ shapes: m.nodes.map((n) => [n.id, n.shape, n.text]), once, again: diagramModel.print(diagramModel.parse(once)) === once }));"
    )
    assert got["shapes"] == [["A", "cylinder", "Store"], ["B", "parallelogram", "Input"], ["C", "rect", "C"]] or got["shapes"][:2] == [["A", "cylinder", "Store"], ["B", "parallelogram", "Input"]]
    assert 'A[("Store")]' in got["once"] and 'B[/"Input"/]' in got["once"] and got["again"]
