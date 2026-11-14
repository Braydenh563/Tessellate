"""Gantt, pie, state, class and ER as block kinds (L-documents-57, INBOX 1679 gap 3).

`DIAGRAM-KINDS-MORE-BEGIN` to `-END` in diagram-kinds-more.js is the pure half, run in node beside
the model's region and the engine's (diagram-kinds.js). For each kind: a source in the docs' own
form prints back byte for byte; the printer's output is a fixed point; a structured edit (add a
row, rename it, set its value) prints Mermaid the reader takes back as the same blocks; a line the
reader does not place is kept where it stood. The DOM half is the browser run's numbers (CHANGELOG).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"


def _region(path: Path, name: str) -> str:
    text = path.read_text(encoding="utf-8")
    return text[text.index(f"// {name}-BEGIN") : text.index(f"// {name}-END")]


def _run(body: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    more = _region(JS / "diagram-kinds-more.js", "DIAGRAM-KINDS-MORE")
    assert "document." not in more and "window." not in more, "the pure region reached for the DOM"
    code = (
        _region(JS / "documents-mermaid.js", "DIAGRAM-MODEL")
        + "\n"
        + _region(JS / "diagram-kinds.js", "DIAGRAM-KINDS")
        + "\n"
        + more
        + "\nObject.assign(diagramKinds, diagramKindsMore);\n"
        + "const K = diagramKinds, O = diagramKindOps;\n"
        + body
    )
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(code)
    try:
        out = subprocess.run([node, handle.name], capture_output=True, text=True, timeout=60, check=True)
    finally:
        Path(handle.name).unlink(missing_ok=True)
    return json.loads(out.stdout)


GANTT = """gantt
    title A Gantt Diagram
    dateFormat YYYY-MM-DD
    axisFormat %H:%M
    section Section
    A task           :a1, 2014-01-01, 30d
    Another task     :after a1, 20d
    section Another
    Task in sec      :2014-01-12, 12d
    another task     :24d
"""
PIE = 'pie showData title Pets adopted\n    "Dogs" : 386\n    "Cats" : 85.5\n    %% a comment\n    "Rats" : 15\n'
STATE = """stateDiagram-v2
    direction LR
    [*] --> Still
    Still --> [*]
    Still --> Moving : push
    Moving --> Still
    state "Long name" as long
    state Active {
        [*] --> NumLockOff
        NumLockOff --> NumLockOn : EvNumLockPressed
    }
    note right of Still
    A note
    end note
    Moving --> Crash
"""
CLASS = """classDiagram
    class Animal {
        <<abstract>>
        +String name
        +eat() void
    }
    class Duck
    Animal <|-- Duck
    Animal "1" --> "*" Zebra : feeds
    Animal : +int age
"""
ER = """erDiagram
    CUSTOMER ||--o{ ORDER : places
    ORDER ||--|{ LINE-ITEM : contains
    CUSTOMER }|..|{ DELIVERY-ADDRESS : uses
    CUSTOMER {
        string name
        string custNumber PK
        string sector
    }
    PRODUCT
"""
SOURCES = {"gantt": GANTT, "pie": PIE, "state": STATE, "class": CLASS, "er": ER}


def test_a_source_in_the_docs_form_prints_back_unchanged():
    got = _run(f"""
const src = {json.dumps(SOURCES)};
console.log(JSON.stringify(Object.entries(src).map(([k, s]) => {{
  const m = K[k].parse(s);
  return [k, Boolean(m), m && K[k].print(m) === s, m && O.count(K[k], m)];
}})));""")
    assert [(k, ok, same) for k, ok, same, _ in got] == [(k, True, True) for k in SOURCES], got
    assert all(n > 0 for *_, n in got)


def test_the_printed_form_is_a_fixed_point_and_reads_as_the_same_blocks():
    got = _run(f"""
const src = {json.dumps(SOURCES)};
const rows = (A, m) => JSON.stringify(O.rows(A, m).map(function s(r) {{ return r.type === "k" ? {{ k: r.line }} : {{ t: r.type, x: A.text(r.node), kids: (r.kids || []).map(s) }}; }}));
console.log(JSON.stringify(Object.entries(src).map(([k, s]) => {{
  const A = K[k];
  const m = A.parse(s);
  //: Every row edited (its raw form dropped) prints the canonical form, which must itself be a fixed point.
  O.walk(A, m, (n) => {{ delete n.raw; }});
  const p1 = A.print(m);
  const m2 = A.parse(p1);
  return [k, A.print(m2) === p1, rows(A, m) === rows(A, m2)];
}})));""")
    assert all(fixed and same for _, fixed, same in got), got


def test_odd_indent_and_unknown_lines_are_kept_not_dropped():
    got = _run(r"""
const out = {};
out.gantt = K.gantt.print(K.gantt.parse("gantt\n  title X\n  foo bar baz\n  section S\n  T :1d\n"));
out.pie = K.pie.print(K.pie.parse('pie\n\t"a" : 1\n\tnonsense\n'));
out.state = K.state.print(K.state.parse("stateDiagram\n  A --> B\n  A:::cls --> B\n  state fork <<fork>>\n"));
out.class = K.class.print(K.class.parse("classDiagram\n  class A{\n  +x\n  }\n  A..>B\n"));
out.er = K.er.print(K.er.parse('erDiagram\n  "My Table" {\n    int id\n  }\n  nonsense here\n'));
console.log(JSON.stringify(out));""")
    assert "  foo bar baz" in got["gantt"] and got["gantt"].startswith("gantt\n  title X")
    assert '\t"a" : 1\n\tnonsense\n' in got["pie"]
    assert "  A:::cls --> B" in got["state"] and "  state fork <<fork>>" in got["state"] and got["state"].startswith("stateDiagram\n")
    assert "  class A {\n    +x\n  }" in got["class"] and "  A..>B" in got["class"]
    assert '  "My Table" {\n    int id\n  }' in got["er"] and "  nonsense here" in got["er"]


def test_a_source_the_reader_cannot_take_is_refused_not_guessed():
    got = _run(r"""
console.log(JSON.stringify([K.state.parse("stateDiagram-v2\n  state A {\n  B --> C\n"), K.class.parse("classDiagram\n  class A {\n  +x\n"), K.er.parse("erDiagram\n  A {\n  int x\n"), K.pie.parse("flowchart TD\n  A-->B\n"), K.gantt.parse("pie\n")]));""")
    assert got == [None] * 5


def test_each_kind_adds_renames_and_removes_a_block():
    got = _run(r"""
const out = {};
const add = (k, m, type, opts = {}) => { const A = K[k]; const tile = A.tiles.find((t) => t.type === type); const d = A.defaults ? A.defaults(m, tile, opts.sel) : { fields: tile.fields }; const place = O.spot(A, m, type, opts.selKey || null, Boolean(tile.into)); return O.add(A, m, type, { parent: place && place.parent, before: place && place.before, fields: d.fields }); };
let A, m, n;
// pie
A = K.pie; m = A.empty(); n = add("pie", m, "s"); O.relabel(A, m, O.key(n), 'Big "one"'); n.value = "42"; delete n.raw;
out.pie = A.print(m);
// gantt: the first task starts on a date, a section holds a task
A = K.gantt; m = A.empty(); n = add("gantt", m, "s"); O.relabel(A, m, O.key(n), "Build");
const t2 = add("gantt", m, "t", { selKey: O.key(n) }); O.relabel(A, m, O.key(t2), "Second");
out.gantt = A.print(m);
// state: a transition needs two states; renaming a group renames it in the transitions
A = K.state; m = A.empty(); const x = add("state", m, "x"); out.stateX = A.print(m);
const g = add("state", m, "c"); out.stateG = A.print(m);
O.relabel(A, m, O.key(g), "Work mode");
const tr = add("state", m, "x"); tr.to = g.id; delete tr.raw; out.stateRename = A.print(m); out.stateRemoved = (O.remove(A, m, O.key(g)), A.print(m));
// class: a relation needs two classes; renaming a class renames it in the relations
A = K.class; m = A.empty(); const r = add("class", m, "r"); out.classR = A.print(m);
const cl = m.items.find((i) => i.type === "c"); O.relabel(A, m, O.key(cl), "Vehicle"); out.classRename = A.print(m);
const mem = add("class", m, "m", { selKey: O.key(cl) }); O.relabel(A, m, O.key(mem), "+wheels: int"); out.classMember = A.print(m);
// er
A = K.er; m = A.empty(); const rel = add("er", m, "r"); out.erR = A.print(m);
const en = m.items.find((i) => i.type === "e"); O.relabel(A, m, O.key(en), "Big customer"); out.erRename = A.print(m);
console.log(JSON.stringify(out));""")
    assert got["pie"] == "pie\n    \"Big 'one'\" : 42\n"
    assert got["gantt"].startswith("gantt\n    section Build\n    Task :") and re.search(r"\n    Task :\d{4}-\d\d-\d\d, 3d\n    Second :3d\n$", got["gantt"])
    assert got["stateX"] == "stateDiagram-v2\n    state \"State\" as S1\n    S1 --> [*]\n"
    assert "state Group1 {\n        state \"State\" as S2\n    }" in got["stateG"]
    assert "state Work_mode {" in got["stateRename"] and "Work_mode" in got["stateRename"].split("}")[1]
    assert "Work_mode" not in got["stateRemoved"]
    assert got["classR"] == "classDiagram\n    class Class1\n    class Class2\n    Class1 <|-- Class2\n"
    assert "class Vehicle\n    class Class2\n    Vehicle <|-- Class2" in got["classRename"]
    assert "class Vehicle {\n        +wheels: int\n    }" in got["classMember"]
    assert got["erR"] == "erDiagram\n    ENTITY1\n    ENTITY2\n    ENTITY1 ||--o{ ENTITY2 : has\n"
    assert '"Big customer"\n' in got["erRename"] and '"Big customer" ||--o{ ENTITY2 : has' in got["erRename"]


def test_gantt_status_words_lead_the_timing_and_toggle_off():
    got = _run(r"""
const m = K.gantt.parse("gantt\n    section S\n    T :a1, 2026-01-01, 3d\n");
const t = m.sections[0].tasks[0];
const seen = [];
for (const flag of ["crit", "done", "crit"]) { const on = kmFlag(t, flag); seen.push([on, K.gantt.print(m).split("\n")[2]]); }
console.log(JSON.stringify(seen));""")
    assert got == [
        [True, "    T :crit, a1, 2026-01-01, 3d"],
        [True, "    T :done, crit, a1, 2026-01-01, 3d"],
        [False, "    T :done, a1, 2026-01-01, 3d"],
    ]


def test_the_blocks_state_their_words_for_the_list():
    got = _run(f"""
const out = {{}};
for (const [k, s] of Object.entries({json.dumps(SOURCES)})) {{
  const A = K[k], m = A.parse(s);
  out[k] = [];
  O.walk(A, m, (n) => {{ if (n.type !== "k") out[k].push([A.text(n), A.words(m, n).kind, A.glyph(n)]); }});
}}
console.log(JSON.stringify(out));""")
    assert ["Dogs", "slice", "chart-pie-slice"] in got["pie"]
    assert ["First", "task", "calendar-check"] not in got["gantt"] and any(g == "calendar-check" for _, _, g in got["gantt"])
    assert any(kind == "inheritance" for _, kind, _ in got["class"])
    assert any(kind == "exactly one to zero or more" for _, kind, _ in got["er"])
    assert any(g == "key" for _, _, g in got["er"])
    assert ["push", "transition", "arrow-right"] in got["state"]


def test_gantt_and_pie_title_and_date_format_are_blocks_that_round_trip_and_edit():
    """L-documents-87: `title` and `dateFormat` are editable blocks, byte-identical until touched."""
    got = _run(r"""
const out = {};
const g = "gantt\n  title  Odd   spacing\n  dateFormat  DD-MM-YYYY\n  axisFormat %H\n  section S\n  title inside\n  T :1d\n";
const gm = K.gantt.parse(g);
out.gSame = K.gantt.print(gm) === g;
out.gBlocks = []; O.walk(K.gantt, gm, (n) => { if (n.type === "p") out.gBlocks.push([n.key, K.gantt.text(n), K.gantt.words(gm, n).kind]); });
const t = gm.free.find((n) => n.type === "p" && n.key === "title");
O.relabel(K.gantt, gm, O.key(t), "Release plan");
out.gEdit = K.gantt.print(gm);
const pies = ['pie\n  "a" : 1\n', 'pie showData title Pets  adopted\n    "Dogs" : 386\n', 'pie title X\n    title Body\n    "a" : 1\n'];
out.pSame = pies.map((s) => K.pie.print(K.pie.parse(s)) === s);
const pm = K.pie.parse(pies[1]);
const pt = pm.items.find((n) => n.type === "p");
out.pBlock = [pt.key, pt.head, K.pie.text(pt)];
O.relabel(K.pie, pm, O.key(pt), "Strays");
out.pEdit = K.pie.print(pm);
O.remove(K.pie, pm, O.key(pt));
out.pGone = K.pie.print(pm);
const em = K.pie.empty();
const tile = K.pie.tiles.find((x) => x.type === "p");
const place = O.spot(K.pie, em, "p", null, false);
O.add(K.pie, em, "p", { parent: place.parent, before: place.before, fields: tile.fields });
out.pAdd = K.pie.print(em);
const gem = K.gantt.empty();
const dt = K.gantt.tiles.find((x) => x.fields.key === "dateFormat");
O.add(K.gantt, gem, "p", { parent: null, fields: dt.fields });
out.gAdd = K.gantt.print(gem);
console.log(JSON.stringify(out));""")
    assert got["gSame"] and all(got["pSame"]), got
    assert got["gBlocks"] == [["title", "Odd   spacing", "title"], ["dateFormat", "DD-MM-YYYY", "date format"]]
    assert "  title Release plan\n  dateFormat  DD-MM-YYYY\n  axisFormat %H" in got["gEdit"] and "  title inside" in got["gEdit"]
    assert got["pBlock"] == ["title", True, "Pets  adopted"]
    assert got["pEdit"] == 'pie showData title Strays\n    "Dogs" : 386\n'
    assert got["pGone"] == 'pie showData\n    "Dogs" : 386\n'
    assert got["pAdd"].startswith("pie") and "title" in got["pAdd"].lower()
    assert re.search(r"dateFormat \S+", got["gAdd"])


# --- the wiring ---------------------------------------------------------------------------


def test_the_kind_bar_offers_all_nine_kinds_and_each_starter_reads_as_its_kind():
    bar = (JS / "diagram-kindbar.js").read_text(encoding="utf-8")
    keys = re.findall(r'^\s+\["(\w+)", "[^"]+", "[^"]+", "[^"]+"\],$', bar, re.M)
    assert keys == ["flowchart", "sequence", "mindmap", "timeline", "gantt", "pie", "state", "class", "er"]
    sample = bar[bar.index("const SAMPLE") : bar.index("function sample")]
    block = bar[bar.index("const STARTERS") : bar.index("  };", bar.index("const STARTERS"))]
    for key in ("gantt", "pie", "state", "class", "er"):
        assert f"    {key}: " in sample, f"{key} has no drawn sample"
    starters = dict(re.findall(r'^    (\w+): ("(?:[^"\\]|\\.)*"|\'.*\'),$', block, re.M))
    assert set(starters) == {"gantt", "pie", "state", "class", "er"}
    src = {k: json.loads(v) if v.startswith('"') else v[1:-1].replace("\\n", "\n") for k, v in starters.items()}
    got = _run(f"""
const src = {json.dumps(src)};
console.log(JSON.stringify(Object.entries(src).map(([k, s]) => {{ const m = K[k].parse(s); return [k, Boolean(m), m && K[k].print(m) === s, m && O.count(K[k], m)]; }})));""")
    assert all(ok and same and n >= 2 for _, ok, same, n in got), got


def test_the_builder_routes_the_five_kinds_and_the_plain_list_no_longer_names_them():
    builder = (JS / "diagram-builder.js").read_text(encoding="utf-8")
    assert "gantt|pie|stateDiagram|classDiagram|erDiagram" in builder
    assert "diagramModel.kinds.load(kind)" in builder
    ops = (JS / "diagram-ops.js").read_text(encoding="utf-8")
    plain = re.search(r"const DGB_PLAIN = (.*);", ops).group(1)
    for gone in ("state diagrams", "class diagrams", "pie charts", "Gantt charts", "ER diagrams"):
        assert gone not in plain, gone
    kinds = (JS / "diagram-kinds.js").read_text(encoding="utf-8")
    assert "diagram-kinds-more.js" in kinds
    lib = (JS / "diagram-library.js").read_text(encoding="utf-8")
    for tile in ("slice", "transition", "relationship"):
        assert f'"{tile}"' in lib
