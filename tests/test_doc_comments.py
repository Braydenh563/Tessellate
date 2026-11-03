"""Comments parse, resolve and export the way the plan's decision says.

DOCUMENTS_PLAN Phase 5 item 1. The model lives between `DOC-COMMENT-BEGIN` and
`DOC-COMMENT-END` in documents-comments.js and is pure string work with no DOM and no
app globals in it, so python can run it in node. That is a property this test
enforces by existing, the same way the table, frontmatter, columns and
block-reference models are tested.

What matters here is the shapes *around* a comment: a `%%` pair inside a fence
is an example of the syntax rather than a remark, a resolve may not leave a
stray space in the middle of a finished sentence, and the footnote conversion
exists twice (here and in `core/docexport.py`, because the browser renders Read
view and the server writes the downloads) so the last test runs both over one
fixture and fails if they differ by a byte.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tessellate.core import docexport

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS_JS = ROOT / "frontend" / "js" / "documents-comments.js"  # the model moved out of documents.js (DC13 remainder, doc23-1102)

BEGIN = "// DOC-COMMENT-BEGIN"
END = "// DOC-COMMENT-END"


def comment_source() -> str:
    text = DOCUMENTS_JS.read_text(encoding="utf-8")
    start = text.find(BEGIN)
    stop = text.find(END)
    assert start != -1, f"{BEGIN} marker is missing from documents-comments.js"
    assert stop > start, f"{END} marker is missing or before {BEGIN}"
    return text[start + len(BEGIN) : stop]


#: One fixture, used by the node driver and by the python parity test below, so
#: "the two agree" is about the same text in both.
FIXTURE = "\n".join(
    [
        "---",
        "status: draft %%not a comment, a property%%",
        "---",
        "",
        "# The river",
        "",
        "The ==quick brown fox== %%too many adjectives%% jumped.",
        "",
        "A standing remark on its own line.",
        "%%ask about the numbers%%",
        "",
        "Inline `%%not a comment%%` and a fence:",
        "",
        "```",
        "%%also not a comment%%",
        "```",
        "",
        "Two ==marks== and ==one remark== %%about the second%% only.",
    ]
)


DRIVER = r"""
const results = [];
function check(name, ok, detail) {
  results.push({ name, ok: !!ok, detail: detail === undefined ? null : detail });
}

const FIXTURE = __FIXTURE__;

// --- what is and is not a comment -----------------------------------------
{
  const found = docCommentsParse(FIXTURE);
  check('parse/three comments in the fixture', found.length === 3, JSON.stringify(found.map((c) => c.body)));
  check('parse/frontmatter is not prose', !found.some((c) => c.body.includes('a property')), '');
  check('parse/inline code is not a comment', !found.some((c) => c.body.includes('not a comment')), '');
  check('parse/a fence is not a comment', !found.some((c) => c.body.includes('also not')), '');
  const first = found[0];
  check('parse/the first is anchored to its highlight', first.target === 'quick brown fox', JSON.stringify(first.target));
  check('parse/the anchor starts at the highlight', FIXTURE.slice(first.anchorFrom, first.anchorFrom + 2) === '==', JSON.stringify(FIXTURE.slice(first.anchorFrom, first.anchorFrom + 4)));
  check('parse/the span is the remark itself', FIXTURE.slice(first.from, first.to) === '%%too many adjectives%%', JSON.stringify(FIXTURE.slice(first.from, first.to)));
  const standing = found[1];
  check('parse/a bare remark has no target', standing.target === '', JSON.stringify(standing.target));
  check('parse/a bare remark anchors to itself', standing.anchorFrom === standing.from, '');
  const last = found[2];
  check('parse/the nearest highlight wins', last.target === 'one remark', JSON.stringify(last.target));
  check('parse/lines are counted', found.map((c) => c.line).join(',') === '7,10,18', found.map((c) => c.line).join(','));
  check('parse/ids are unique', new Set(found.map((c) => c.id)).size === 3, '');
}

// --- the shapes that must NOT become comments ------------------------------
{
  check('parse/an empty pair is not a remark', docCommentsParse('a %%%% b').length === 0, '');
  check('parse/one pair on a line is not a remark', docCommentsParse('100%% of it').length === 0, '');
  check('parse/a remark may not span lines', docCommentsParse('%%one\ntwo%%').length === 0, '');
  check('parse/null is empty', docCommentsParse(null).length === 0, '');
  const twoSpaces = docCommentsParse('==words==  %%remark%%');
  check('parse/two spaces is not an anchor', twoSpaces.length === 1 && twoSpaces[0].target === '', JSON.stringify(twoSpaces[0] && twoSpaces[0].target));
}

// --- resolving -------------------------------------------------------------
{
  const text = 'The ==quick fox== %%too many adjectives%% jumped.';
  const comment = docCommentsParse(text)[0];
  const edit = docCommentResolveEdit(text, comment);
  const after = text.slice(0, edit.from) + edit.insert + text.slice(edit.to);
  check('resolve/the words stay, unwrapped', after === 'The quick fox jumped.', JSON.stringify(after));
}
{
  const text = 'A sentence %%a remark%% and more.';
  const comment = docCommentsParse(text)[0];
  const edit = docCommentResolveEdit(text, comment);
  const after = text.slice(0, edit.from) + edit.insert + text.slice(edit.to);
  check('resolve/no double space is left', after === 'A sentence and more.', JSON.stringify(after));
}
{
  const text = 'One.\n%%a remark%%\nTwo.';
  const comment = docCommentsParse(text)[0];
  const edit = docCommentResolveEdit(text, comment);
  const after = text.slice(0, edit.from) + edit.insert + text.slice(edit.to);
  check('resolve/a line that was only a remark goes whole', after === 'One.\nTwo.', JSON.stringify(after));
}
{
  check('resolve/nothing to resolve is null', docCommentResolveEdit('x', null) === null, '');
}

// --- stripping -------------------------------------------------------------
{
  const stripped = docCommentStrip(FIXTURE);
  check('strip/no remark survives', !stripped.includes('%%too many'), '');
  check('strip/the highlight survives', stripped.includes('==quick brown fox=='), '');
  check('strip/a fence is left alone', stripped.includes('%%also not a comment%%'), '');
  check('strip/inline code is left alone', stripped.includes('`%%not a comment%%`'), '');
  check('strip/frontmatter is left alone', stripped.includes('status: draft %%not a comment, a property%%'), '');
  check('strip/the standing remark took its line with it', !stripped.includes('\n\n\nInline'), JSON.stringify(stripped.slice(stripped.indexOf('A standing'), stripped.indexOf('Inline'))));
  check('strip/empty text is empty', docCommentStrip(null) === '', '');
}

// --- footnotes -------------------------------------------------------------
{
  const out = docCommentFootnotes(FIXTURE);
  check('footnotes/the reference sits where the remark was', out.includes('==quick brown fox== [^c1]'), JSON.stringify(out.slice(out.indexOf('==quick'), out.indexOf('jumped'))));
  check('footnotes/every remark has a definition', out.includes('[^c1]: too many adjectives') && out.includes('[^c2]: ask about the numbers') && out.includes('[^c3]: about the second'), '');
  check('footnotes/nothing without a comment is touched', docCommentFootnotes('plain text') === 'plain text', '');
  check('footnotes/the prefix is a parameter', docCommentFootnotes('a %%b%%', 'note').includes('[^note1]'), '');
  process.stdout.write('');
}

process.stdout.write(JSON.stringify(results));
"""


@pytest.fixture(scope="module")
def comment_checks(tmp_path_factory) -> list[dict]:
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    script = tmp_path_factory.mktemp("doccomments") / "run.js"
    driver = DRIVER.replace("__FIXTURE__", json.dumps(FIXTURE))
    script.write_text(comment_source() + driver, encoding="utf-8")
    out = subprocess.run(
        [node, str(script)], capture_output=True, text=True, timeout=60, check=False
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_the_model_runs_without_a_browser(comment_checks: list[dict]) -> None:
    assert len(comment_checks) > 25, "the driver did not reach the end"


def test_comments_parse_and_resolve_as_decided(comment_checks: list[dict]) -> None:
    failed = [c for c in comment_checks if not c["ok"]]
    assert not failed, "\n".join(f"{c['name']}: {c['detail']}" for c in failed[:20])


def test_python_finds_the_same_comments() -> None:
    found = docexport.parse_comments(FIXTURE)
    assert [c.body for c in found] == [
        "too many adjectives",
        "ask about the numbers",
        "about the second",
    ]
    assert [c.target for c in found] == ["quick brown fox", "", "one remark"]


@pytest.mark.parametrize(
    "text",
    [
        FIXTURE,
        "",
        "plain prose with no remarks in it",
        "A ==word== %%remark%% and a bare %%one%% too.",
        "One.\n%%only a remark%%\nTwo.",
        "Trailing newline kept %%remark%%\n",
    ],
)
def test_footnote_export_agrees_with_the_editor(text: str) -> None:
    """The one thing that keeps two implementations of one rule honest."""
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    driver = (
        "const text = "
        + json.dumps(text)
        + ";\nprocess.stdout.write(JSON.stringify({"
        + "footnotes: docCommentFootnotes(text), stripped: docCommentStrip(text)}));"
    )
    out = subprocess.run(
        [node, "-e", comment_source() + driver],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert out.returncode == 0, out.stderr
    theirs = json.loads(out.stdout)
    assert theirs["footnotes"] == docexport.comments_to_footnotes(text)
    assert theirs["stripped"] == docexport.strip_comments(text)
