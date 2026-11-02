"""The guided equation editor (DOCUMENTS_PLAN row 16, math-editor.js).

The owner, 2026-10-26: "an easier and guided way to write out mathematical
equations and symbols like with word or desmos". Two halves are tested here.

The pure core (`MATH-EDITOR-CORE-BEGIN` to `-END`) runs in node beside the
renderer's own region of documents.js: the guided typing (Word's linear
format), the slots Tab walks, the palette's inserts, the markdown written and
the equation found under the caret. Every palette symbol is drawn by the
renderer as the glyph its tile shows, and every template parses into
structure rather than the words of its commands.

The wiring is read from the files: one lazy module behind one stand-in, every
surface a caller of `openMathEditor`, nothing at boot, and its help on the
`data-help-for` recipe and in the Guide.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
EDITOR = (JS / "math-editor.js").read_text(encoding="utf-8")


def _region(text: str, begin: str, end: str) -> str:
    start, stop = text.find(begin), text.find(end)
    assert start != -1 and stop > start, f"{begin} / {end} markers are missing"
    return text[start + len(begin) : stop]


DRIVER = r"""
const results = [];
const check = (name, ok, detail) => results.push({ name, ok: !!ok, detail: detail == null ? null : String(detail) });
function sketch(node) {
  if (node.text != null && !(node.kids || []).length) return `${node.tag}(${node.text})`;
  return `${node.tag}[${(node.kids || []).map(sketch).join(" ")}]`;
}

// The markdown written.
check("inline", mathEditorOutput(" x^2 ", false) === "$x^2$", mathEditorOutput(" x^2 ", false));
check("display", mathEditorOutput("x", true) === "$$x$$", mathEditorOutput("x", true));
//: One line always: the Live view draws no formula that spans lines.
check("display in one line", mathEditorOutput("a\n b", true) === "$$a b$$", mathEditorOutput("a\n b", true));
check("nothing for nothing", mathEditorOutput("  ", true) === "", "");
check("written inline is read as maths", docMathLooksLikeMath(mathEditorOutput("x^2", false).slice(1, -1)), "");

// The equation under the caret, to edit it.
const span = (v, s, e) => JSON.stringify(mathEditorSpan(v, s, e));
check("caret in inline", span("a $x^2$ b", 4, 4) === JSON.stringify({ from: 2, to: 7, tex: "x^2", display: false }), span("a $x^2$ b", 4, 4));
check("caret in display", span("p\n$$\nx\n$$\nq", 5, 5) === JSON.stringify({ from: 2, to: 9, tex: "x", display: true }), span("p\n$$\nx\n$$\nq", 5, 5));
check("caret after an equation is beside it", mathEditorSpan("a $x$", 5, 5) === null, span("a $x$", 5, 5));
check("caret before one is beside it", mathEditorSpan("$x$ a", 0, 0) === null, span("$x$ a", 0, 0));
check("caret before a display is beside it", mathEditorSpan("$$x$$", 0, 0) === null, span("$$x$$", 0, 0));
check("selected equation", span("$$y$$", 0, 5) === JSON.stringify({ from: 0, to: 5, tex: "y", display: true }), span("$$y$$", 0, 5));
check("prices are not an equation", mathEditorSpan("from $5 and $10 up", 9, 9) === null, span("from $5 and $10 up", 9, 9));
check("plain text is not", mathEditorSpan("hello", 2, 2) === null, span("hello", 2, 2));

// Every symbol draws as its glyph; every template and sample is structure.
const groups = mathEditorGroups();
check("seventeen groups", groups.length === 17, groups.map((g) => g.key).join());
check("Word's eleven structure groups, in Word's order", groups.slice(0, 11).map((g) => g.label).join() === "Fraction,Script,Radical,Integral,Large operator,Bracket,Function,Accent,Limit and log,Operator,Matrix", groups.slice(0, 11).map((g) => g.label).join());
const COMMAND_WORDS = /m[io]\((frac|tfrac|sqrt|begin|end|binom|vec|hat|overline|left|right|partial|to|square|lfloor|rfloor|lceil|rceil|langle|rangle|iiint|coprod|tilde)\)/;
//: A template's boxes, as the stored text has them.
const boxed = (tex) => tex.replace(/#[@?]/g, "{}");
for (const group of groups) {
  for (const item of group.items) {
    if (item.glyph) {
      const tree = docMathTree(item.tex);
      const leaf = tree.kids[0];
      check(`glyph/${item.name}`, leaf.text === item.glyph, `${sketch(tree)} for ${item.glyph}`);
    }
    if (group.structures) {
      check(`template/${item.name}/has a box`, /#[@?]/.test(item.tex), item.tex);
      check(`template/${item.name}/first box takes the selection`, item.tex.includes("#@") || item.tex.startsWith("#@"), item.tex);
    }
    for (const tex of [boxed(item.tex), item.sample].filter(Boolean)) {
      let out;
      try {
        out = sketch(docMathTree(tex, true));
      } catch (error) {
        out = `threw ${error.message}`;
      }
      check(`structure/${item.name}/${tex}`, !COMMAND_WORDS.test(out) && !out.startsWith("threw"), out);
    }
  }
}
process.stdout.write(JSON.stringify(results));
"""


@pytest.fixture(scope="module")
def core_checks(tmp_path_factory) -> list[dict]:
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    docs = (JS / "documents.js").read_text(encoding="utf-8")
    source = _region(docs, "// DOC-MATH-BEGIN", "// DOC-MATH-END")
    source += _region(EDITOR, "// MATH-EDITOR-CORE-BEGIN", "// MATH-EDITOR-CORE-END")
    script = tmp_path_factory.mktemp("matheditor") / "run.js"
    script.write_text(source + DRIVER, encoding="utf-8")
    out = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60, check=False)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_the_core_runs_without_a_browser(core_checks: list[dict]) -> None:
    assert len(core_checks) > 150


def test_the_templates_output_and_span(core_checks: list[dict]) -> None:
    failed = [c for c in core_checks if not c["ok"]]
    assert not failed, "\n".join(f"{c['name']}: {c['detail']}" for c in failed[:20])


def test_one_lazy_module_behind_one_stand_in() -> None:
    entries = (JS / "lazy-entries.js").read_text(encoding="utf-8")
    assert (
        'mathEditor: ["/css/math-field-lazy.css", "/vendor/mathlive/mathlive.min.js", "/js/math-field.js", '
        '"/css/math-editor-lazy.css", "/js/math-editor.js"]'
    ) in entries
    assert 'mathEditor: ["openMathEditor"]' in entries
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "math-editor.js" not in index and "math-editor-lazy.css" not in index
    assert (ROOT / "frontend" / "css" / "math-editor-lazy.css").is_file()


def test_every_surface_is_a_thin_caller() -> None:
    editor = (JS / "editor.js").read_text(encoding="utf-8")
    assert re.search(r'id: "equation".*run: \(t\) => openMathEditor\(\{ target: t \}\)', editor)
    assert re.search(r'id: "chat-equation".*openMathEditor\(\{ target: document\.getElementById\("chat-input"\) \}\)', editor)
    board = (JS / "whiteboard.js").read_text(encoding="utf-8")
    assert re.search(r'board: \[[^\]]*"equation"', board)
    docs = (JS / "documents.js").read_text(encoding="utf-8")
    assert 'equation: { custom: "equation" }' in docs and "openMathEditor({ target: box })" in docs
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'data-md="equation"' in index
    entries = (JS / "lazy-entries.js").read_text(encoding="utf-8")
    assert 'event.code !== "Equal"' in entries and 'box?.id !== "question"' in entries


def test_its_help_is_the_popover_recipe_and_a_guide_topic() -> None:
    assert 'setAttribute("data-help-for", "math-editor-help")' in EDITOR
    assert 'body.id = "math-editor-help"' in EDITOR
    from tessellate.ai import help_topics_more

    topic = next(t for t in help_topics_more.MORE_TOPICS if t["id"] == "equation-editor")
    assert "Alt+=" in topic["body"] and "/equation" in topic["body"]
    assert "LaTeX" in topic["body"] and "dotted box" in topic["body"]
    assert help_topics_more.TOPIC_META["equation-editor"]["title"] == "Equation editor"
