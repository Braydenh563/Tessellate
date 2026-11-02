"""One diff model, shared by the history dialog and the AI edit panel.

DOCUMENTS_PLAN Phase 5 items 2 and 3. The model lives between `DOC-DIFF-BEGIN`
and `DOC-DIFF-END` in documents-history.js and is pure string work with no DOM and no
app globals in it, so python can run it in node, the same way the block
reference, table, frontmatter and columns models are tested.

What matters here is not that a diff of two different strings is non-empty. It
is the three properties the two surfaces depend on: a diff of a text with
itself is empty (so "no change" is a state the panel can draw rather than a
list of every line), a rejected hunk leaves the *old* lines in place rather
than dropping them (accept-or-reject per hunk is meaningless otherwise), and
applying every hunk of a diff reproduces the newer text exactly, which is what
makes the AI panel's textarea and its diff two views of one value.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS_JS = ROOT / "frontend" / "js" / "documents-history.js"  # the model moved out of documents.js (docs-1101, DC13)
EDITOR_CSS = ROOT / "frontend" / "css" / "09-editor.css"

BEGIN = "// DOC-DIFF-BEGIN"
END = "// DOC-DIFF-END"


def diff_source() -> str:
    text = DOCUMENTS_JS.read_text(encoding="utf-8")
    start = text.find(BEGIN)
    stop = text.find(END)
    assert start != -1, f"{BEGIN} marker is missing from documents-history.js"
    assert stop > start, f"{END} marker is missing or before {BEGIN}"
    return text[start + len(BEGIN) : stop]


DRIVER = r"""
const results = [];
function check(name, ok, detail) {
  results.push({ name, ok: !!ok, detail: detail === undefined ? null : detail });
}
const shape = (ops) => ops.map((o) => o.op).join('');

// --- the empty and identical cases ----------------------------------------
{
  const same = 'one\ntwo\nthree';
  const ops = docDiffLines(same, same);
  check('same/every line is unchanged', shape(ops) === '   ', shape(ops));
  const stat = docDiffStat(ops);
  check('same/nothing added or removed', stat.added === 0 && stat.removed === 0, JSON.stringify(stat));
  check('same/no hunks', docDiffHunks(ops).length === 0, '');
  check('same/no rows to draw', docDiffRows(ops).length === 0, JSON.stringify(docDiffRows(ops)));
  check('null/an absent side is the empty text', docDiffLines(null, null).length === 0, '');
}

// --- a change in the middle, with the ends trimmed -------------------------
{
  const before = ['a', 'b', 'c', 'd', 'e'].join('\n');
  const after = ['a', 'b', 'CHANGED', 'd', 'e'].join('\n');
  const ops = docDiffLines(before, after);
  check('middle/one line out, one line in', shape(ops) === '  -+  ', shape(ops));
  const stat = docDiffStat(ops);
  check('middle/stat says +1 -1', stat.added === 1 && stat.removed === 1, JSON.stringify(stat));
  const hunks = docDiffHunks(ops);
  check('middle/one hunk', hunks.length === 1, JSON.stringify(hunks));
  check('middle/the hunk counts both sides', hunks[0].added === 1 && hunks[0].removed === 1, JSON.stringify(hunks[0]));
  check('middle/removal is drawn before the addition', ops[2].op === '-' && ops[3].op === '+', shape(ops));
}

// --- applying and rejecting hunks -----------------------------------------
{
  const before = ['keep', 'one', 'keep2', 'two', 'keep3'].join('\n');
  const after = ['keep', 'ONE', 'keep2', 'TWO', 'keep3'].join('\n');
  const ops = docDiffLines(before, after);
  const hunks = docDiffHunks(ops);
  check('hunks/two separate changes', hunks.length === 2, JSON.stringify(hunks));
  check('apply/all hunks reproduces the newer text', docDiffApply(ops, hunks, []) === after, JSON.stringify(docDiffApply(ops, hunks, [])));
  check('apply/no hunks reproduces the older text', docDiffApply(ops, hunks, [0, 1]) === before, JSON.stringify(docDiffApply(ops, hunks, [0, 1])));
  const half = docDiffApply(ops, hunks, [1]);
  check('apply/a rejected hunk keeps its old lines', half === ['keep', 'ONE', 'keep2', 'two', 'keep3'].join('\n'), JSON.stringify(half));
  check('apply/a Set is accepted too', docDiffApply(ops, hunks, new Set([0])) === ['keep', 'one', 'keep2', 'TWO', 'keep3'].join('\n'), '');
}

// --- insertion and deletion only ------------------------------------------
{
  const ops = docDiffLines('a\nb', 'a\nnew\nb');
  check('insert/one addition', shape(ops) === ' + ', shape(ops));
  const hunks = docDiffHunks(ops);
  check('insert/apply all reproduces the newer text', docDiffApply(ops, hunks, []) === 'a\nnew\nb', '');
  const gone = docDiffLines('a\nb\nc', 'a\nc');
  check('delete/one removal', shape(gone) === ' - ', shape(gone));
  const fresh = docDiffLines('', 'a\nb');
  check('empty-before/everything is an addition', shape(fresh) === '++', shape(fresh));
}

// --- the context window ----------------------------------------------------
{
  const lines = [];
  for (let i = 0; i < 40; i++) lines.push('line ' + i);
  const after = lines.slice();
  after[20] = 'CHANGED';
  const ops = docDiffLines(lines.join('\n'), after.join('\n'));
  const rows = docDiffRows(ops, 2);
  const gaps = rows.filter((r) => r.op === 'gap');
  check('context/the untouched run is counted, not printed', gaps.length === 2, JSON.stringify(rows.length));
  const drawn = rows.filter((r) => r.op !== 'gap').length;
  check('context/every op is either drawn or counted', gaps.reduce((n, g) => n + g.skipped, 0) + drawn === ops.length, JSON.stringify([gaps, drawn, ops.length]));
  check('context/two lines either side are kept', rows.filter((r) => r.op === ' ').length === 4, JSON.stringify(rows.filter((r) => r.op === ' ').length));
}

// --- the cap ---------------------------------------------------------------
{
  check('cap/the cap is a number the fallback can reach', DOC_DIFF_MAX_CELLS > 0, String(DOC_DIFF_MAX_CELLS));
  const a = [];
  const b = [];
  for (let i = 0; i < 60; i++) { a.push('a' + i); b.push('b' + i); }
  const ops = docDiffLines(a.join('\n'), b.join('\n'));
  const stat = docDiffStat(ops);
  check('cap/a rewrite that shares nothing is all out then all in', stat.added === 60 && stat.removed === 60, JSON.stringify(stat));
  check('cap/applying it reproduces the newer text', docDiffApply(ops, docDiffHunks(ops), []) === b.join('\n'), '');
}

process.stdout.write(JSON.stringify(results));
"""


@pytest.fixture(scope="module")
def diff_checks(tmp_path_factory) -> list[dict]:
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    script = tmp_path_factory.mktemp("docdiff") / "run.js"
    script.write_text(diff_source() + DRIVER, encoding="utf-8")
    out = subprocess.run(
        [node, str(script)], capture_output=True, text=True, timeout=60, check=False
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_the_model_runs_without_a_browser(diff_checks: list[dict]) -> None:
    assert len(diff_checks) > 20, "the driver did not reach the end"


def test_the_diff_model_holds_its_properties(diff_checks: list[dict]) -> None:
    failed = [c for c in diff_checks if not c["ok"]]
    assert not failed, "\n".join(f"{c['name']}: {c['detail']}" for c in failed[:20])


def test_one_diff_builder_and_no_second_one() -> None:
    """The recipe row in DESIGN.md says a diff is `docRenderDiff`'s `.doc-diff`.

    Standing order 11: new UI comes from the recipe index, and a recipe with no
    lint is a recipe that lasts one session. This is that lint. It fails when a
    second function starts building diff rows by hand, which is the way the
    history dialog and the AI panel would come to draw the same object
    differently.
    """
    text = DOCUMENTS_JS.read_text(encoding="utf-8")
    builders = re.findall(r"\n *function (docRenderDiff\w*)\(", text)  # indented: the file is one closure now (docs-1101)
    assert builders == ["docRenderDiff"], builders
    rows = re.findall(r'"doc-diff-line[^"]*"', text)
    assert rows, "docRenderDiff no longer draws .doc-diff-line rows"
    # Every class the builder draws is laid out in the file that owns the
    # editor's space, not left to inherit whatever a dialog happens to set.
    css = EDITOR_CSS.read_text(encoding="utf-8")
    for name in ("doc-diff", "doc-diff-line", "doc-diff-gap"):
        assert f".{name}" in css, f".{name} has no rule in 09-editor.css"
