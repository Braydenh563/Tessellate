"""The ```graph block (DOCUMENTS_PLAN gap row 16, the graph step).

A fence of `y = ...` lines is a plot with sliders. The reader is a small parser
(no `eval`, so a document from anywhere runs no code); this runs its region in
node, then checks the wiring that cannot run without a browser: Read swaps the
fence, Live draws it through a state field, the "/" menu offers it, and the
module is lazy and registered where the other lazy documents bundles are.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._app_js import documents_text

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _run(body: str) -> object:
    text = (JS / "documents-graph.js").read_text(encoding="utf-8")
    region = text[text.index("// DOC-GRAPH-BEGIN") : text.index("// DOC-GRAPH-END")]
    script = "var window = {};\n(() => {\n" + region + "\nwindow.g = { parse, compile, ticks, runs, tickText, autoY };\n})();\nconst g = window.g;\n" + body
    out = subprocess.run(["node", "-"], input=script, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-600:]
    return json.loads(out.stdout.strip().splitlines()[-1])


@node
def test_expressions_read_as_a_person_writes_them() -> None:
    got = _run(
        "const names = new Set(['x', 'a']);"
        "const f = (t, v = {}) => g.compile(t, names)({ x: 2, a: 3, ...v });"
        "console.log(JSON.stringify([f('2x+1'), f('x^2'), f('-x^2'), f('2^3^2'), f('sin(pi/2)'), f('sqrt(16)'), f('a x'), f('ax'), f('2(x+1)'),"
        " f('x²'), f('2x', { x: 5 }), +f('sin 2x', { x: 0.5 }).toFixed(6), +f('sin x cos x', { x: 1 }).toFixed(6), f('max(1, x, a)'), f('1/2x'), f('x^-1'), f('abs(-x)')]));"
    )
    assert got[:6] == [5, 4, -4, 512, 1, 4]
    assert got[6:9] == [6, 6, 6]
    assert got[9] == 4 and got[10] == 10
    assert got[11] == pytest.approx(0.841471) and got[12] == pytest.approx(0.454649)
    assert got[13:] == [3, 1, 0.5, 2]


@node
def test_a_bad_line_says_why_and_a_name_off_the_list_runs_nothing() -> None:
    got = _run(
        "const names = new Set(['x']);"
        "const bad = (t) => { try { g.compile(t, names); return ''; } catch (e) { return e.message; } };"
        "console.log(JSON.stringify([bad('foo(x)'), bad('2 +'), bad('(x'), bad('x )'), bad('constructor'), bad('__proto__ x'), bad('x $ 2')]));"
    )
    assert "not a function or a slider" in got[0] and got[1] and "Missing" in got[2] and "Unexpected" in got[3]
    assert "not a function or a slider" in got[4] and got[5] and got[6]


@node
def test_a_fence_becomes_curves_sliders_and_a_window() -> None:
    got = _run(
        "const m = g.parse('title: Waves\\ny = a sin(b x)\\nf(x) = x^2 # a parabola\\ncos(x)\\na = 2 [0, 5]\\nb = 1\\nc = -4\\nx: -6..6\\ny: -3 to 3\\nnonsense line');"
        "console.log(JSON.stringify({ title: m.title, curves: m.curves.map((c) => [c.label, !!c.fn]), params: m.params, x: m.x, y: m.y, errors: m.errors }));"
    )
    assert got["title"] == "Waves"
    assert got["curves"] == [["y = a sin(b x)", True], ["f(x) = x^2", True], ["y = cos(x)", True]]
    a, b, c = got["params"]
    assert (a["min"], a["max"], a["value"]) == (0, 5, 2) and a["step"] == pytest.approx(0.05)
    assert (b["min"], b["max"]) == (0, 3) and (c["min"], c["max"]) == (-12, 0)
    assert got["x"] == [-6, 6] and got["y"] == [-3, 3]
    assert got["errors"] == ["Not understood: nonsense line"]


@node
def test_limits_a_constant_curve_and_a_curve_that_names_an_unknown_slider() -> None:
    got = _run(
        "const many = g.parse(Array.from({ length: 9 }, (_, i) => `y = x + ${i}`).join('\\n') + '\\n' + 'abcdefghij'.split('').map((c) => c + ' = 1').join('\\n'));"
        "const k = g.parse('y = 3\\ny = q x');"
        "console.log(JSON.stringify({ curves: many.curves.length, params: many.params.length, errors: many.errors, constant: k.curves[0].fn({ x: 9 }), unknown: k.curves[1].error }));"
    )
    assert got["curves"] == 6 and got["params"] == 8
    assert "At most 6 curves." in got["errors"] and "At most 8 sliders." in got["errors"]
    assert got["constant"] == 3 and "not a function or a slider" in got["unknown"]


@node
def test_an_asymptote_breaks_the_line_and_ticks_land_on_round_numbers() -> None:
    got = _run(
        "const tan = g.compile('tan(x)', new Set(['x']));"
        "const pieces = g.runs(tan, { x: 0 }, -4, 4, -5, 5);"
        "const t = g.ticks(-10, 10, 8);"
        "const small = g.ticks(0, 0.5, 5);"
        "const [lo, hi] = g.autoY([{ fn: tan }], { x: 0 }, -10, 10);"
        "console.log(JSON.stringify({ pieces: pieces.length, step: t.step, first: t.values[0], last: t.values.at(-1), small: small.values, text: [g.tickText(0.30000000000000004, 0.1), g.tickText(-0, 1), g.tickText(5, 5)], band: [lo < 0 && hi > 0 && hi - lo < 100] }));"
    )
    assert got["pieces"] >= 3
    assert got["step"] == 2 and got["first"] == -10 and got["last"] == 10
    assert got["small"] == [0, 0.1, 0.2, 0.3, 0.4, 0.5]
    assert got["text"] == ["0.3", "0", "5"] and got["band"] == [True]


def test_read_swaps_the_fence_and_live_draws_it() -> None:
    math = (JS / "documents-math.js").read_text(encoding="utf-8")
    docs = documents_text()
    editor = (JS / "editor.js").read_text(encoding="utf-8")
    # Read: after the mermaid swap, on the rendered preview; Live: the field joins the editor's extensions.
    assert "docRenderMermaidIn(preview);\n  docMathRender.graphIn(preview);" in docs
    assert "docMathRender.graphField(CM)" in docs
    # Lazy, and registered from a lazy file so it costs the boot scripts nothing.
    assert 'docGraph: ["/css/doc-graph-lazy.css", "/js/documents-graph.js"]' in (JS / "lazy-entries.js").read_text(encoding="utf-8")
    assert 'module: "docGraph"' in math and "ensureModule(spec.module)" in math
    assert '{ id: "graph"' in editor and "```graph" in editor
    graph = (JS / "documents-graph.js").read_text(encoding="utf-8")
    # No eval, no Function constructor, no innerHTML: the text of a document is data.
    for banned in ("eval(", "new Function", "innerHTML", "insertAdjacentHTML"):
        assert banned not in graph, banned


def test_the_graph_stylesheet_is_balanced_and_has_no_inline_or_important() -> None:
    css = (ROOT / "frontend" / "css" / "doc-graph-lazy.css").read_text(encoding="utf-8")
    assert css.count("{") == css.count("}")
    assert "!important" not in css and "style=" not in css


def test_the_guide_has_a_topic_and_a_lead_for_the_graph_block() -> None:
    from tessellate.ai import help_chat, help_leads

    topics = {t["id"]: t for t in help_chat.HELP_TOPICS}
    assert "document-graph" in topics and len(topics["document-graph"]["body"]) < 1900
    assert "document-graph" in help_leads.TOPIC_LEADS


@node
def test_a_long_run_of_digits_or_spaces_is_refused_quickly() -> None:
    """CodeQL js/polynomial-redos: each number had two ways to split a run of digits (`\\d*\\.?\\d+`) and the comment
    strip was `\\s+#.*$`, so a 40,000-character line froze the tab for seconds. Each must read in well under one."""
    got = _run(
        "const long = (s) => { const t = Date.now(); g.parse(s); return Date.now() - t; };"
        "console.log(JSON.stringify([long('a = ' + '1'.repeat(40000) + 'x'), long('x: ' + '1'.repeat(40000) + 'x'),"
        " long('a = 1 [1, ' + '1'.repeat(40000) + 'x'), long('a' + ' '.repeat(40000) + 'x'),"
        " g.parse('x: -5..5\\ny: -2 to 2\\na = .5 [0, 2.5, 0.5]\\ny = a x  # a comment')]));"
    )
    assert all(took < 1000 for took in got[:4]), got[:4]
    fence = got[4]
    assert fence["x"] == [-5, 5] and fence["y"] == [-2, 2] and not fence["errors"]
    assert fence["params"][0]["value"] == 0.5 and fence["curves"][0]["text"] == "a x"
