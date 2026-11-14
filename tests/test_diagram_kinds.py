"""The other kinds in the block pane (1546 P4; DOCUMENTS_PLAN "1546 design" D2, D5 to D10).

`DIAGRAM-KINDS-BEGIN` to `-END` in diagram-kinds.js is the pure half: a mind map, a
timeline and a sequence diagram each read into blocks and printed back, run here in node
beside the model's own region (documents-mermaid.js). D2's invariants hold per kind over
what the composer writes, what the board's sequence reader takes and the new templates:

- `print(parse(print(m))) === print(m)` (the printer's own output is a fixed point), and
- `parse(s)` and `parse(print(parse(s)))` hold the same blocks.

A line the reader does not understand is kept where it stood, never dropped; a source it
cannot take at all (a second mind map root, `box`, `create`) is refused as null so the pane
leaves it in Source. The rest of the file (the DOM, the pointer mode, the keys) is read for
what it must and must not contain; the browser run is scratchpad numbers in the commit.
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
from tests._app_js import lazy_modules_source

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
KINDS = JS / "diagram-kinds.js"
BUILDER = JS / "diagram-builder.js"
SUGGEST = JS / "diagram-suggest.js"
MERMAID = JS / "documents-mermaid.js"
TEMPLATES = ROOT / "frontend" / "board-library" / "diagram-templates.json"


def _region(path: Path, name: str) -> str:
    text = path.read_text(encoding="utf-8")
    return text[text.index(f"// {name}-BEGIN") : text.index(f"// {name}-END")]


def _run(body: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    kinds = _region(KINDS, "DIAGRAM-KINDS")
    assert "document." not in kinds and "window." not in kinds, "the pure region reached for the DOM"
    code = _region(MERMAID, "DIAGRAM-MODEL") + "\n" + kinds + "\n" + body
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(code)
    try:
        out = subprocess.run([node, handle.name], capture_output=True, text=True, timeout=60, check=True)
    finally:
        Path(handle.name).unlink(missing_ok=True)
    return json.loads(out.stdout)


#: Every check below reads a source the same way: the printed form is a fixed point, and the blocks
#: (type, words, nesting, kept lines) are the same before and after one trip through the printer.
CHECK = """
const rowsOf = (A, m) => JSON.stringify(diagramKindOps.rows(A, m).map(function strip(r) {
  return r.type === "k" ? { k: r.line } : { t: r.type, x: A.text(r.node), kids: (r.kids || []).map(strip) };
}));
const check = (kind, s) => {
  const A = diagramKinds[kind];
  const m = A.parse(s);
  if (!m) return { id: s.slice(0, 60), null: true };
  const p1 = A.print(m);
  const m2 = A.parse(p1);
  if (!m2) return { id: s.slice(0, 60), reparse: false };
  return { id: s.slice(0, 60), fixed: A.print(m2) === p1, same: rowsOf(A, m) === rowsOf(A, m2), blocks: diagramKindOps.count(A, m) };
};
"""


def _checks(kind: str, sources: list[str]):
    return _run(CHECK + f"console.log(JSON.stringify({json.dumps(sources)}.map((s) => check({json.dumps(kind)}, s))));")


def _all_hold(got):
    assert got, "no sources were checked"
    bad = [row for row in got if row.get("null") or row.get("reparse") is False or not (row["fixed"] and row["same"])]
    assert not bad, bad


# --- the composer's outputs --------------------------------------------------------------

AWKWARD = ['Say "hello" [loudly]', "Room #3; floor <2>", "a `code` bit (with parens) {and braces}", "Key: value: more", "C:\\path\\to", "Tom & Jerry's #1"]


def _composed(want: str, texts: list[str]) -> list[str]:
    made = [cm.diagram(text, want=want) for text in texts]
    return [d.source for d in made if d and d.shape == want]


def test_the_composers_mind_maps_open_as_blocks_and_round_trip():
    texts = [
        "# Garden\n- Tomatoes\n  - need sun\n- Beans\n- Herbs",
        "## Trip ideas\n* Lisbon\n* Porto\n    * by train\n",
        "Reasons to move. The rent is lower. The commute is shorter. The school is closer.",
        "# Project\n## Design\n## Build\n- tests first",
        "# Big\n" + "\n".join(f"- branch {i}" for i in range(60)),
        *[f"# {a}\n- {a}\n  - {a} deeper" for a in AWKWARD],
    ]
    sources = _composed("mindmap", texts)
    assert len(sources) == len(texts)
    got = _checks("mindmap", sources)
    _all_hold(got)
    assert all(row["blocks"] >= 2 for row in got)


def test_the_composers_timelines_open_as_blocks_and_round_trip():
    texts = [
        "- 2 April 2026: tomatoes in\n- 2026-03-01 seeds sown\n- May 2026 first harvest",
        "We moved in on 3 June 2024. The boiler broke on 12 January 2025. We sold the flat in March 2026.",
        "- Jan 5, 2026 kickoff\n- Feb 20, 2026 design done\n- April 1st, 2026 launch",
        "2019: started the job\n2021: promoted\n2023: moved teams",
        "\n".join(f"- {2000 + i} event number {i}" for i in range(60)),
        *[f"- 2 May 2026 {a}\n- 3 May 2026 {a}" for a in AWKWARD],
    ]
    sources = _composed("timeline", texts)
    assert len(sources) == len(texts)
    _all_hold(_checks("timeline", sources))


def test_a_mind_map_label_carries_no_entity_codes():
    """A mind map draws `#35;` and `#quot;` as written (measured in the frame), so the composer leaves them out of its mind maps."""
    for awkward in AWKWARD:
        source = cm.diagram(f"# {awkward}\n- {awkward}", want="mindmap").source
        assert not re.search(r"#\w+;", source), source
        assert source.count('"') % 2 == 0 and re.search(r'^  root\(\("[^"]*"\)\)$', source.splitlines()[1])


def test_a_composer_mind_map_reads_back_with_its_words_whole():
    got = _run(
        CHECK
        + "const A = diagramKinds.mindmap; const m = A.parse("
        + json.dumps(cm.diagram("# Garden\n- Tomatoes\n  - need sun\n- Beans", want="mindmap").source)
        + "); console.log(JSON.stringify(diagramKindOps.rows(A, m).map(function s(r) { return [A.text(r.node), (r.kids || []).map(s)]; })));"
    )
    assert got == [["Garden", [["Tomatoes", [["need sun", []]]], ["Beans", []]]]]


# --- the board's sequence corpus and the templates ------------------------------------------

SEQUENCE = [
    # tests/test_wb_mermaid_kinds.py: participants, actors, a self message, a note, a loop, autonumber
    "sequenceDiagram\nparticipant A as Alice\nactor B as Bob\nA->>B: Hello\nB-->>A: Hi back\nA->>A: think\nNote over A,B: a note\nloop Every minute\n  B-)C: ping\nend\nautonumber",
    # tests/test_boardfill2_1031.py and tests/test_mermaid_frame.py
    "sequenceDiagram\n  A->>B: hi",
    "---\ntitle: Sign in\n---\nsequenceDiagram\nA->>B: hi",
    # arrows, activation, dividers and the odd characters a message may hold
    "sequenceDiagram\n  participant A as Alice\n  actor B as Bob\n  A->>B: hi\n  B-->>A:\n  A-xB: x\n  A-)B: async\n  Note over A,B: n\n  loop Every\n    A->>+B: q\n    B-->>-A: r\n  end\n  alt ok\n    A->>B: y\n  else no\n    A->>B: n\n  end\n  opt maybe\n    A->>B: m\n  end\n",
    "sequenceDiagram\n  title: T\n  A->>B: self #35;1 #59; semi\n  Note right of A: R\n  autonumber\n  activate A\n  par one\n   A->>B: p1\n  and two\n   B->>A: p2\n  end\n  %% c\n",
    "sequenceDiagram\n  participant API-1\n  API-1->>B: hi\n  A<<->>B: both\n",
    "sequenceDiagram\n  participant A\n  A->>B: hi; there\n  Note left of A: l\n  rect rgb(0,0,255)\n   A->>B: x\n  end\n",
    'sequenceDiagram\n  A->>B: a: b: c\n  B-->>A: <b>x</b> "q"\n  critical Establish\n    A->>B: x\n  option Fail\n    B->>A: y\n  end\n  break stop\n   A->>B: z\n  end\n',
    "sequenceDiagram\n",
]


def test_the_boards_sequence_corpus_round_trips_as_blocks():
    _all_hold(_checks("sequence", SEQUENCE))


def test_the_new_templates_are_one_of_each_kind_and_print_unchanged():
    rows = [t for t in json.loads(TEMPLATES.read_text(encoding="utf-8"))["templates"] if t.get("kind") in ("mindmap", "timeline", "sequence")]
    assert [(t["id"], t["kind"]) for t in rows] == [("brainstorm", "mindmap"), ("project-plan", "timeline"), ("sign-in", "sequence"), ("request-reply", "sequence")]
    got = _run(
        f"const rows = {json.dumps(rows)};\n"
        "console.log(JSON.stringify(rows.map((t) => { const A = diagramKinds[t.kind]; const m = A.parse(t.source);"
        " return { id: t.id, read: Boolean(m), same: Boolean(m) && A.print(m) === t.source, blocks: m ? diagramKindOps.count(A, m) : 0,"
        " kept: m ? diagramKindOps.rows(A, m).filter((r) => r.type === 'k').length : -1, head: A.header === t.source.split('\\n')[0] }; })));"
    )
    assert all(row["read"] and row["same"] and row["head"] and row["kept"] == 0 and row["blocks"] >= 8 for row in got), got
    for t in rows:
        for words in (t["name"], t["hint"], *re.findall(r'"([^"]+)"', t["source"])):
            assert "\u2014" not in words and "!" not in words, words
        assert t["name"][0].isupper() and t["hint"].endswith(".")


# --- kept lines and refusals --------------------------------------------------------------


def test_lines_the_reader_does_not_know_are_kept_in_place_for_every_kind():
    sources = {
        "mindmap": "mindmap\n  %% a comment\n  root((\"Top\"))\n    A\n    ::icon(fa fa-book)\n    B:::cls\n",
        "timeline": "timeline\n  title T\n  accDescr {\n   hello\n  }\n  2002 : A\n  %% c\n",
        "sequence": "sequenceDiagram\n  autonumber\n  A->>B: hi\n  activate A\n  %% c\n  link A: Docs @ https://example.com\n",
    }
    for kind, source in sources.items():
        got = _run(
            CHECK
            + f"const A = diagramKinds.{kind}; const s = {json.dumps(source)}; const m = A.parse(s); const p = A.print(m);"
            " const lines = s.split('\\n').map((l) => l.trim()).filter(Boolean);"
            " console.log(JSON.stringify({ check: check('" + kind + "', s), missing: lines.filter((l) => !p.includes(l)) }));"
        )
        assert got["check"]["fixed"] and got["check"]["same"], (kind, got)
        assert got["missing"] == [], (kind, got)


@pytest.mark.parametrize(
    ("kind", "source"),
    [
        ("mindmap", "mindmap\n  root((One))\n    A\n  second((Two))\n"),
        ("sequence", "sequenceDiagram\n  box Aqua Group\n  participant A\n  A->>B: hi\n"),
        ("sequence", "sequenceDiagram\n  participant A\n  create participant B\n  Note over A: hi\n"),
        ("sequence", "sequenceDiagram\n  A->>B: hi\n  destroy B\n"),
        ("timeline", "flowchart TD\n  A --> B\n"),
    ],
)
def test_a_source_the_reader_cannot_take_is_null_so_it_stays_in_source(kind, source):
    got = _run(f"console.log(JSON.stringify(diagramKinds.{kind}.parse({json.dumps(source)}) === null));")
    assert got is True


# --- the engine ---------------------------------------------------------------------------


def _ops(kind: str, source: str, steps: str):
    """Parse `source`, run `steps` (JS using `A`, `m`, `o`, `key`), answer what it returns plus the printed source."""
    return _run(
        f"const A = diagramKinds.{kind}; const m = A.parse({json.dumps(source)}); const o = diagramKindOps;\n"
        "const key = (uid) => { let hit = null; o.walk(A, m, (n) => n.uid === uid && n.type !== 'k' && (hit = o.key(n))); return hit; };\n"
        f"const result = (() => {{ {steps} }})();\n"
        "console.log(JSON.stringify({ result, src: A.print(m), again: A.print(A.parse(A.print(m))) }));"
    )


MM = "mindmap\n  root((Top))\n    A\n      A1\n    B\n    C\n"


def test_mind_map_moves_nest_lift_step_and_remove_keep_the_source_stable():
    got = _ops("mindmap", MM, "return [o.step(A, m, key('u4'), 1), o.nest(A, m, key('u5')), o.lift(A, m, key('u3')), o.remove(A, m, key('u2'))];")
    assert got["result"][:3] == [True, True, True]
    assert got["result"][3]["count"] >= 1
    assert got["src"] == got["again"]
    assert got["src"].splitlines()[0] == "mindmap" and "root((" in got["src"]


def test_the_root_of_a_mind_map_cannot_move_or_go():
    got = _ops("mindmap", MM, "return [o.move(A, m, key('u1'), key('u2')), o.remove(A, m, key('u1')), o.step(A, m, key('u1'), 1), o.lift(A, m, key('u1'))];")
    assert got["result"] == [False, None, False, False]
    assert got["src"] == MM.replace("(Top)", '("Top")') or got["src"] == got["again"]


def test_a_block_cannot_move_into_what_it_holds():
    got = _ops("mindmap", MM, "return o.move(A, m, key('u2'), key('u3'));")
    assert got["result"] is False and got["src"] == got["again"]


def test_a_new_mind_map_branch_goes_under_the_selection_or_the_root():
    got = _ops(
        "mindmap",
        MM,
        "const t = A.tiles.find((x) => x.id === 'leaf');"
        "const under = o.spot(A, m, t.type, key('u2'), true); const a = o.add(A, m, t.type, { ...under, fields: { text: 'New' } });"
        "const top = o.spot(A, m, t.type, null); const b = o.add(A, m, t.type, { ...top, fields: { text: 'Loose' } });"
        "return [Boolean(a), Boolean(b), a && A.text(a), b && A.text(b)];",
    )
    assert got["result"][:2] == [True, True]
    assert got["src"] == got["again"] and "New" in got["src"] and "Loose" in got["src"]


TL = "timeline\n  title Plan\n  section One\n    2001 : a : b\n    2002 : c\n  section Two\n    2003 : d\n"


def test_a_timeline_event_lands_in_a_period_and_a_period_in_a_section():
    got = _ops(
        "timeline",
        TL,
        "const ev = A.tiles.find((x) => x.id === 'event'); const pe = A.tiles.find((x) => x.id === 'period');"
        "const p = o.spot(A, m, ev.type, null); const a = o.add(A, m, ev.type, { ...p, fields: { text: 'Late' } });"
        "const q = o.spot(A, m, pe.type, key('u2'), true); const b = o.add(A, m, pe.type, { ...q, fields: { when: '2010' } });"
        "return [Boolean(a), Boolean(b), o.count(A, m)];",
    )
    assert got["result"][:2] == [True, True]
    assert got["src"] == got["again"] and "Late" in got["src"] and "2010" in got["src"]


def test_removing_a_section_takes_its_periods_and_the_source_stays_valid():
    got = _ops("timeline", TL, "return o.remove(A, m, key('u1'));")
    assert got["result"]["count"] == 5 and "One" not in got["src"] and "Two" in got["src"]
    assert got["src"] == got["again"]


SEQ = "sequenceDiagram\n  participant A as Alice\n  participant B as Bob\n  A->>B: hi\n  B-->>A: hello\n  loop Often\n    A->>B: ping\n  end\n"


def test_a_sequence_message_needs_two_participants_and_a_block_holds_messages():
    got = _ops(
        "sequence",
        "sequenceDiagram\n",
        "const t = A.tiles.find((x) => x.id === 'message'); const sel = null;"
        "const d = A.defaults(m, t, sel);"
        "const p = o.spot(A, m, t.type, null); const a = o.add(A, m, t.type, { ...p, fields: d.fields });"
        "return [Boolean(a), m.participants.length, d.made];",
    )
    assert got["result"] == [True, 2, 2] and got["src"] == got["again"] and "->>" in got["src"]


def test_a_new_loop_or_alt_is_never_empty_because_mermaid_logs_nan_for_an_empty_one():
    """Measured in the frame: an empty `loop` or `alt` draws with NaN attributes and fills the console."""
    for tile, inside in (("loop", ["m"]), ("opt", ["m"]), ("alt", ["m", "d", "m"])):
        got = _ops(
            "sequence",
            SEQ,
            f"const t = A.tiles.find((x) => x.id === '{tile}'); const d = A.defaults(m, t, null);"
            "const a = o.add(A, m, t.type, { parent: null, before: null, fields: d.fields });"
            "return a.steps.map((s) => s.type);",
        )
        assert got["result"] == inside and got["src"] == got["again"], (tile, got)


def test_removing_a_participant_takes_its_messages_and_says_how_many():
    got = _ops("sequence", SEQ, "return o.remove(A, m, key('u1'));")
    assert got["result"]["joins"] >= 3 and "Alice" not in got["src"]
    assert got["src"] == got["again"]


def test_a_sequence_block_nests_lifts_and_steps_with_its_messages():
    got = _ops("sequence", SEQ, "return [o.step(A, m, key('u4'), -1), o.nest(A, m, key('u3')), o.lift(A, m, key('u7'))];")
    assert got["src"] == got["again"]
    assert got["result"][0] is True


def test_merging_a_suggestion_matches_participants_by_name_and_keeps_ids_unique():
    got = _ops(
        "sequence",
        SEQ,
        "const inc = A.parse('sequenceDiagram\\n  participant X as Alice\\n  participant Y as Carol\\n  X->>Y: new one\\n');"
        "const before = m.participants.length; const done = o.merge(A, m, inc, null);"
        "const ids = m.participants.map((p) => p.id);"
        "return { done, before, after: m.participants.length, unique: new Set(ids).size === ids.length, labels: m.participants.map((p) => p.label) };",
    )
    r = got["result"]
    assert r["after"] == r["before"] + 1 and r["unique"] and r["labels"].count("Alice") == 1 and "Carol" in r["labels"]
    assert "new one" in got["src"] and got["src"] == got["again"]


def test_taking_only_participants_adds_the_new_ones_and_counts_them():
    """Found in the browser: two participants taken alone were added to the source but counted as nothing, so no undo step was made."""
    got = _ops(
        "sequence",
        SEQ,
        "const inc = A.parse('sequenceDiagram\\n  participant X as Alice\\n  participant Y as Carol\\n  X->>Y: new one\\n'); const keys = [];"
        "o.walk(A, inc, (n) => n.type === 'a' && keys.push(o.key(n))); const done = o.merge(A, m, inc, new Set(keys));"
        "return { added: done.added, first: done.first, labels: m.participants.map((p) => p.label) };",
    )
    r = got["result"]
    assert r["added"] == 1 and r["first"].startswith("a:") and r["labels"] == ["Alice", "Bob", "Carol"]
    assert "new one" not in got["src"] and got["src"] == got["again"]


def test_a_message_that_brings_participants_does_not_push_past_the_limit():
    got = _run(
        "const A = diagramKinds.sequence; const o = diagramKindOps; const m = A.empty();"
        "const t = A.tiles.find((x) => x.id === 'message');"
        "for (let i = 0; i < 400; i++) { const d = A.defaults(m, t, null); const p = o.spot(A, m, t.type, null); if (!o.add(A, m, t.type, { ...p, fields: d.fields })) break; }"
        "const inc = A.parse('sequenceDiagram\\n  P->>Q: one\\n  R->>S: two\\n  T->>U: three\\n'); const done = o.merge(A, m, inc, null);"
        "console.log(JSON.stringify({ count: o.count(A, m), max: o.MAX, skipped: done.skipped }));"
    )
    assert got["count"] <= got["max"] and got["skipped"] >= 1


def test_merging_mind_map_and_timeline_blocks_brings_them_under_a_home():
    got = _ops(
        "mindmap",
        MM,
        "const inc = A.parse('mindmap\\n  root((Other))\\n    P\\n      P1\\n    Q\\n'); const done = o.merge(A, m, inc, null);"
        "return [done.added, done.skipped, o.count(A, m)];",
    )
    assert got["result"][1] == 0 and got["result"][2] >= 4 + 3 and got["src"] == got["again"]
    got = _ops(
        "timeline",
        TL,
        "const inc = A.parse('timeline\\n  section Three\\n    2020 : x\\n    2021 : y : z\\n'); const done = o.merge(A, m, inc, null);"
        "return [done.added, done.skipped];",
    )
    assert got["result"][0] >= 3 and got["result"][1] == 0 and "Three" in got["src"] and got["src"] == got["again"]


def test_a_chosen_part_of_a_suggestion_comes_with_what_it_holds_and_no_more():
    got = _ops(
        "mindmap",
        MM,
        "const inc = A.parse('mindmap\\n  root((Other))\\n    P\\n      P1\\n    Q\\n'); const keys = {};"
        "o.walk(A, inc, (n) => (keys[A.text(n)] = o.key(n)));"
        "const done = o.merge(A, m, inc, new Set([keys.P])); return [done.added, done.skipped];",
    )
    assert got["result"] == [1, 0]
    assert "P1" not in got["src"] and "Q" not in got["src"] and "Other" not in got["src"] and got["src"] == got["again"]
    assert re.search(r"^ +P$", got["src"], re.M)


#: The tile each kind fills a diagram with: a mind map's leaves under its central idea, a timeline's periods, a sequence's messages.
FILL = {"mindmap": "leaf", "timeline": "period", "sequence": "message"}


@pytest.mark.parametrize("kind", ["mindmap", "timeline", "sequence"])
def test_a_diagram_holds_at_most_the_limit_of_blocks(kind):
    got = _run(
        f"const A = diagramKinds.{kind}; const o = diagramKindOps; const m = A.empty(); if (A.start) A.start(m);"
        f"const t = A.tiles.find((x) => x.id === '{FILL[kind]}'); let made = 0;"
        "for (let i = 0; i < 400; i++) { const d = A.defaults ? A.defaults(m, t, null) : { fields: { ...t.fields } }; const p = o.spot(A, m, t.type, null);"
        " if (!p) break; if (o.add(A, m, t.type, { ...p, fields: d.fields })) made++; else break; }"
        "console.log(JSON.stringify({ made, count: o.count(A, m), max: o.MAX, again: A.print(A.parse(A.print(m))) === A.print(m) }));"
    )
    assert got["count"] <= got["max"] == 120 and got["again"] and got["made"] >= 100, got


def test_the_limit_refuses_a_suggestion_it_has_no_room_for():
    got = _run(
        "const A = diagramKinds.mindmap; const o = diagramKindOps;"
        "const big = 'mindmap\\n  root((R))\\n' + Array.from({ length: 119 }, (_, i) => '    n' + i).join('\\n') + '\\n';"
        "const m = A.parse(big); const inc = A.parse('mindmap\\n  root((S))\\n    a\\n    b\\n    c\\n');"
        "const before = o.count(A, m); const done = o.merge(A, m, inc, null);"
        "console.log(JSON.stringify({ before, added: done.added, skipped: done.skipped, after: o.count(A, m) }));"
    )
    assert got["before"] == 120 and got["added"] == 0 and got["skipped"] >= 3 and got["after"] == 120


# --- what the file must and must not contain ----------------------------------------------


def test_the_kinds_are_a_bundle_of_their_own_never_at_boot():
    rows = lazy_modules_source()
    assert 'diagramKinds: ["/js/diagram-kinds.js"]' in rows
    for boot in ("app.js", "lazy-entries.js"):
        assert "diagramKinds" not in (JS / boot).read_text(encoding="utf-8"), boot
    assert "diagram-kinds.js" not in (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    # The flowchart path asks for it only when the source is another kind.
    builder = BUILDER.read_text(encoding="utf-8")
    assert builder.count('ensureModule("diagramKinds")') == 1 and "kindOf(" in builder


def test_one_closure_one_export_and_no_markup_built_from_text():
    code = KINDS.read_text(encoding="utf-8")
    assert code.count("diagramModel.kinds =") == 1
    assert "innerHTML" not in code and "insertAdjacentHTML" not in code and "outerHTML" not in code
    assert 'setAttribute("style"' not in code and ".style." not in code and "style=" not in code
    assert 'tree.setAttribute("role", "tree")' in code and '"treeitem"' in code
    # Text nodes only: every line of copy goes through the builder's `el`.
    assert "OBJ_MODES.diagramKind" in code and code.count("OBJ_MODES.diagramKind =") == 1


def test_the_suggestions_know_the_kinds_and_refuse_a_mismatch_with_a_reason():
    code = SUGGEST.read_text(encoding="utf-8")
    assert 'ensureModule("diagramKinds")' in code and "kindOf(" in code and "ghostSpec(" in code
    assert "so blocks cannot add to it. It was left out." in code
    assert "kind || \"flowchart\"" in code, "the template list is filtered by the pane's kind"


def test_a_bar_letter_pressed_on_the_pane_does_not_reach_the_name_it_opens_for_editing():
    """Measured: `n` on a focused pane added a block, its name opened for editing, and the letter landed in it."""
    for path in (KINDS, BUILDER):
        text = path.read_text(encoding="utf-8")
        tail = text[text.index("S.pane.addEventListener(\"keydown\""):][:600]
        assert "event.preventDefault()" in tail, path.name


def test_the_flowchart_pane_file_stays_lean_and_its_joins_load_when_used():
    """diagram-builder.js carried 14.1 KB gzipped against a 12 KB target. The kinds live in their own file and the joins in
    another (fetched on the first join), so the flowchart path is smaller than it was and must not creep back up."""
    import gzip

    size = len(gzip.compress(BUILDER.read_bytes(), 9))
    assert size <= 12000, size
    rows = lazy_modules_source()
    assert 'diagramJoins: ["/js/diagram-joins.js"]' in rows
    builder = BUILDER.read_text(encoding="utf-8")
    assert builder.count('ensureModule("diagramJoins")') == 1 and "function joinItems" not in builder and "function joinPick" not in builder
    for boot in ("app.js", "lazy-entries.js"):
        assert "diagramJoins" not in (JS / boot).read_text(encoding="utf-8"), boot
    assert "diagram-joins.js" not in (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def test_the_kinds_docks_do_not_inherit_the_flowcharts_one_row_rule():
    # DD-2 (1107): `.dgm-dock { flex-wrap: nowrap }` was unscoped, so the kinds' wrapping palette (13 tiles for a sequence
    # diagram) overflowed its row and Suggest, Undo, Redo and the menu were painted over the tiles (3, 14 and 4 overlapping
    # button pairs; docks 549, 127 and 204 px). Measured after: 0 pairs and a 46 px dock for every kind at 1440, 1000 and 390.
    css = (Path(__file__).resolve().parents[1] / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")
    plain = css.split("\n.dgm-dock {", 1)[1].split("}", 1)[0]
    assert "flex-wrap" not in plain
    assert "flex-wrap: nowrap" in css.split(".dgm-dock:has(> .dgm-addsplit) {", 1)[1].split("}", 1)[0]
    # The kinds' palette is the Add sheet at every width, so no tile can sit under the dock's buttons.
    assert ".dgm-addlist :is(.dgm-palette, .dgm-lib-hint)" in css
    touch = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "diagram-touch.js").read_text(encoding="utf-8")
    builder = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "diagram-builder.js").read_text(encoding="utf-8")
    assert '"dgm-compact" : "dgm-addlist"' in touch
    assert "(S.k || matchMedia(COMPACT).matches) && (await ensureModule(\"diagramTouch\"))" in builder


def test_insert_on_a_selected_sequence_message_adds_one_in_the_gap_below_it():
    """Review finding 4: the block list's Insert key (diagram-kinds.js `keydown`) asks `ops.spot` for the row after the
    selection, which is the gap the picture's + opens, so a keyboard user can insert between two messages."""
    got = _ops(
        "sequence",
        SEQ,
        "const t = A.tiles.find((x) => x.id === 'message'); const sel = key('u3');"
        "const p = o.spot(A, m, t.type, sel); const d = A.defaults(m, t, null);"
        "o.add(A, m, t.type, { ...p, fields: { ...d.fields, text: 'between' } });",
    )
    lines = [ln.strip() for ln in got["src"].splitlines()]
    hi = next(i for i, ln in enumerate(lines) if ln.endswith(": hi"))
    assert lines[hi + 1].endswith(": between") and lines[hi + 2].endswith(": hello")


def test_a_mind_map_keeps_the_authors_quoting_when_it_round_trips():
    """dgpolish-1109: saving rewrote `root((Plan))` as `root(("Plan"))`. A shape the author wrote bare stays bare while its
    words stay plain; a quoted one stays quoted; words that a bracket or a quote would break are quoted, as a new node's are."""
    got = _run(
        CHECK
        + "const A = diagramKinds.mindmap;"
        "const src = 'mindmap\\n  root((Plan))\\n    A[Bare]\\n    B[\"Quoted\"]\\n    Plain\\n';"
        "const m = A.parse(src); const first = A.print(m);"
        "const bare = m.root.children[0]; bare.text = 'now (odd)'; const odd = A.print(m);"
        "console.log(JSON.stringify({ first, odd }));"
    )
    assert got["first"] == "mindmap\n  root((Plan))\n    A[Bare]\n    B[\"Quoted\"]\n    Plain\n"
    assert 'A["now (odd)"]' in got["odd"] and "root((Plan))" in got["odd"]
