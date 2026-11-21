"""L342: per-key main-thread time in a 20k-word document at 4x CPU.

The gate (scratchpad/ui-sweeps/typegate.js) asks for a per-key ThreadTime
p95 under 50 ms in both views. Each cut here keeps what the person sees
equal and moves work off the keys that do not need it.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
PROSE = (JS / "documents-prose.js").read_text(encoding="utf-8")
LT = (JS / "documents-languagetool.js").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _function(source: str, head: str) -> str:
    start = source.index(head)
    end = source.index("\n}\n", start) + 3
    return source[start:end]


def _node(script: str, *args: str) -> dict:
    out = subprocess.run(["node", "-e", script, *args], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


@needs_node
def test_a_grammar_answer_landing_mid_typing_works_out_its_findings_only_when_read():
    script = (
        """
let docGrammarCache = { text: null, findings: [] };
const docGrammarWire = { asking: null };
const docProse = { typedAt: 0 };
let worked = 0, drawn = 0, answer;
const docGrammarEnabled = () => true, docCheckLinkText = () => "";
const docGrammarFindings = (lints, text) => { worked += 1; return lints.map((l) => ({ start: l.start, text })); };
const renderDocProse = () => { drawn += 1; void docGrammarCache.findings; };
const docGrammarAsk = (text, early) => new Promise((r) => { answer = r; });
"""
        + _function(PROSE, "function docGrammarRequest(")
        + """
(async () => {
  const out = {};
  docGrammarRequest("one two");
  docProse.typedAt = performance.now() + 1;
  answer([{ start: 0 }]);
  await new Promise((r) => setTimeout(r, 0));
  out.typed = { worked, drawn };
  out.first = docGrammarCache.findings.length;
  void docGrammarCache.findings;
  out.read = worked;
  docProse.typedAt = 0;
  docGrammarRequest("three");
  answer([{ start: 1 }, { start: 2 }]);
  await new Promise((r) => setTimeout(r, 0));
  out.paused = { worked, drawn, n: docGrammarCache.findings.length, text: docGrammarCache.text };
  console.log(JSON.stringify(out));
})();
"""
    )
    got = _node(script)
    assert got["typed"] == {"worked": 0, "drawn": 0}
    assert got["first"] == 1 and got["read"] == 1
    assert got["paused"] == {"worked": 2, "drawn": 1, "n": 2, "text": "three"}


@needs_node
def test_a_first_languagetool_check_maps_every_paragraph_once_without_a_quadratic_search():
    assert "paras.findIndex" not in LT and "touched.find(" not in LT
    script = r"""
    global.window = {docSpell: {}}; global.$ = () => null; global.docSpellingVariant = () => "us";
    const sent = [];
    global.apiJson = async (u, o) => { const b = JSON.parse(o.body); sent.push(b.text);
      return {available: true, matches: [...b.text.matchAll(/bad/g)].map((m) => ({start: m.index, end: m.index + 3, message: "m", suggestions: []}))}; };
    eval(require("fs").readFileSync(process.argv[1], "utf8"));
    const paras = [];
    for (let i = 0; i < 3000; i += 1) paras.push(i % 7 === 0 ? "bad same" : `line ${i} bad`);
    const text = paras.join("\n\n");
    const lt = window.docSpell.languageTool;
    (async () => {
      const a = await lt([], text);
      const edited = text.replace("line 1 bad", "line 1 bad bad");
      const b = await lt([], edited);
      const want = (t) => [...t.matchAll(/bad/g)].map((m) => m.index);
      console.log(JSON.stringify({ n: sent.length, second: sent[1], a: a.map((l) => l.start).join() === want(text).join(), b: b.map((l) => l.start).join() === want(edited).join() }));
    })();
    """
    got = _node(script, str(JS / "documents-languagetool.js"))
    assert got == {"n": 2, "second": "line 1 bad bad", "a": True, "b": True}
