"""The document editor's prose tools (INBOX 401 and 404, the prose side).

Grammar through Harper, vendored and run in a worker. What a Python test can
hold of it is the contract around the browser: the binary and its licence are
in the tree, the policy lets WebAssembly compile without letting `eval` in,
the binary is not gzipped on every cold fetch, the switch is a preference that
round-trips, and the checker is reached lazily rather than at boot. What it
does in the page is `scratchpad/ui-sweeps/p2-harper.js`.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tessellate.core import security

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
HARPER = FRONTEND / "vendor" / "harper"
#: documents.js and documents-prose.js joined: the prose tools moved into
#: documents-prose.js verbatim on 2026-09-24, and the panel and dock wiring
#: that reaches them stayed in documents.js.
DOCUMENTS = "\n".join(
    (FRONTEND / "js" / name).read_text(encoding="utf-8") for name in ("documents.js", "documents-prose.js")
)
WORKER = (FRONTEND / "js" / "harper-worker.js").read_text(encoding="utf-8")


def _body(name: str) -> str:
    start = DOCUMENTS.index(f"function {name}(")
    end = DOCUMENTS.find("\n}\n", start)
    return DOCUMENTS[start:end]


# --- grammar -------------------------------------------------------------------


def test_harper_is_vendored_with_its_licence() -> None:
    assert (HARPER / "LICENSE").read_text(encoding="utf-8").lstrip().startswith("Apache License")
    for name in ("slimBinary.js", "harper_wasm_slim_bg.wasm"):
        assert (HARPER / name).is_file(), name
    #: The worker imports the loader by its hashed name; a re-vendor that
    #: changes the hash has to change the import with it.
    for spec in re.findall(r'from "\./vendor/harper/([^"]+)"', WORKER):
        assert (HARPER / spec).is_file(), f"harper-worker.js imports {spec}, which is not vendored"
    assert (HARPER / "harper_wasm_slim_bg.wasm").read_bytes()[:4] == b"\0asm"


def test_the_policy_compiles_wasm_and_still_refuses_eval() -> None:
    policy = security.build_csp([])
    script = next(part for part in policy.split("; ") if part.startswith("script-src "))
    assert "'wasm-unsafe-eval'" in script.split()
    assert "'unsafe-eval'" not in script.split()
    assert "worker-src 'self'" in policy


def test_the_binary_is_served_as_wasm_and_gzipped_once(client) -> None:
    """Was left uncompressed: the middleware took 755 ms to gzip it on every
    cold fetch. The precompressed cache (`RevalidatedStatic`) pays that once
    per version and keeps the bytes, so it now goes as 8 MB rather than 15.9
    (audit 2026-10-05, FE-03); the bytes are the file's own."""
    import gzip

    from tessellate.api.app import FRONTEND_DIR

    with client.stream(
        "GET", "/vendor/harper/harper_wasm_slim_bg.wasm", headers={"Accept-Encoding": "gzip"}
    ) as response:
        raw = b"".join(response.iter_raw())
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/wasm"
    assert response.headers["content-encoding"] == "gzip"
    wasm = FRONTEND_DIR / "vendor" / "harper" / "harper_wasm_slim_bg.wasm"
    assert len(raw) < wasm.stat().st_size * 0.6
    assert gzip.decompress(raw) == wasm.read_bytes()


def test_the_grammar_switch_is_a_preference_on_by_default(client) -> None:
    assert client.get("/preferences").json()["grammar_check"] is True
    assert client.put("/preferences", json={"grammar_check": False}).json()["grammar_check"] is False
    assert client.get("/preferences").json()["grammar_check"] is False


def test_the_worker_is_same_origin_and_started_only_on_demand() -> None:
    """`harper.js`'s own WorkerLinter builds a `blob:` worker, which
    `worker-src 'self'` refuses without a sound; and a worker started at load
    would fetch 15.9 MB on every launch whether or not anything is written."""
    code = "\n".join(line for line in WORKER.splitlines() if not line.lstrip().startswith("//"))
    assert "createObjectURL" not in code and "WorkerLinter" not in code
    assert 'import { slimBinary } from "../vendor/harper/slimBinary.js"' in WORKER
    starts = [m.start() for m in re.finditer(r"new Worker\(`\$\{DOC_GRAMMAR_WORKER_URL\}", DOCUMENTS)]
    assert len(starts) == 1
    assert starts[0] > DOCUMENTS.index("function docGrammarAsk(")
    assert starts[0] < DOCUMENTS.index("function docGrammarMessage(")


def test_harper_spelling_is_left_to_the_dictionary_and_never_fixed_in_bulk() -> None:
    assert 'DOC_GRAMMAR_SKIP_KINDS = new Set(["Spelling"])' in DOCUMENTS
    #: "Fix all" applies every non-null replacement without asking.
    assert "replacement: null," in _body("docGrammarFindings")


def test_a_grammar_finding_is_drawn_filed_and_answered() -> None:
    assert 'return "grammar";' in _body("docFindingKind")
    assert '["grammar", "Grammar"]' in DOCUMENTS
    assert "finding.alternatives" in _body("docSuggestAlternatives")
    assert "docProseExtras(text, docProseFindings(text))" in _body("renderDocProse")


def test_the_note_boxes_get_the_grammar_plugin() -> None:
    assert "noteGrammarPlugin(CM)" in _body("noteSurfaceExtensions")


#: The real worker, run in node on the vendored binary: a stand-in `self` for
#: the worker's message port, and `fetch` answering the `file:` URL the binary
#: is loaded from (node's own fetch refuses that scheme).
HARPER_DRIVER = r"""
import { readFile } from "node:fs/promises";
const realFetch = globalThis.fetch;
globalThis.fetch = async (url, init) => {
  const href = String(url && url.href ? url.href : url);
  if (href.startsWith("file:")) {
    return new Response(await readFile(new URL(href)), { headers: { "Content-Type": "application/wasm" } });
  }
  return realFetch(url, init);
};
let handler = null;
const replies = [];
globalThis.self = {
  addEventListener: (type, fn) => { if (type === "message") handler = fn; },
  postMessage: (message) => replies.push(message),
};
await import(process.argv[2]);
const text = process.argv[3];
for (const dialect of ["uk", "us"]) {
  await handler({ data: { id: dialect, dialect, text } });
}
process.stdout.write(JSON.stringify(replies));
"""


def test_a_sentence_case_heading_is_not_a_finding(tmp_path) -> None:
    """The app writes headings in sentence case (CLAUDE.md standing order 6),
    and Harper's `UseTitleCase` asked for title case on every one of them:
    four of the six suggestions on the README's focus-mode shot, 2026-09-26.
    Run through the worker itself, so the rule is off where the page gets its
    findings, not only in a list; the repeated word proves the checker ran."""
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    script = tmp_path / "harper.mjs"
    script.write_text(HARPER_DRIVER, encoding="utf-8")
    text = "# Why we moved the notebook offline\n\n## What changed\n\nThe the search index moved.\n"
    out = subprocess.run(
        [node, str(script), (FRONTEND / "js" / "harper-worker.js").as_uri(), text],
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert out.returncode == 0, out.stderr
    replies = json.loads(out.stdout)
    assert [r["id"] for r in replies] == ["uk", "us"]
    for reply in replies:
        assert reply["ok"], reply
        messages = [lint["message"] for lint in reply["lints"]]
        assert not [m for m in messages if "title case" in m.lower()], messages
        assert any(lint["problem"] == "The the" for lint in reply["lints"]), messages


# --- suggestion mode -----------------------------------------------------------
#
# The model between DOC-SUGGEST-BEGIN and DOC-SUGGEST-END is pure string work,
# run here in node: what one keystroke does to the text and where it leaves
# the caret, which is the whole of the feature's correctness.

SUGGEST_DRIVER = r"""
const results = [];
const eq = (name, got, want) => results.push({ name, ok: JSON.stringify(got) === JSON.stringify(want), detail: JSON.stringify(got) });
const run = (text, from, to, insert, back) => docSuggestEdit(text, from, to, insert, back);

eq('type/opens an insertion', run('hello world', 5, 5, 'X', false), { text: 'hello{++X++} world', caret: 9 });
eq('type/extends it', run('hello{++X++} world', 9, 9, 'Y', false), { text: 'hello{++XY++} world', caret: 10 });
eq('type/next to an insertion joins it', run('a{++X++}b', 8, 8, 'Z', false), { text: 'a{++XZ++}b', caret: 6 });
eq('backspace/wraps a letter', run('abc', 2, 3, '', true), { text: 'ab{--c--}', caret: 2 });
eq('backspace/a run is one deletion', run('ab{--c--}', 1, 2, '', true), { text: 'a{--bc--}', caret: 1 });
eq('backspace/over your own insertion deletes it', run('a{++XY++}b', 5, 6, '', true), { text: 'a{++X++}b', caret: 5 });
eq('backspace/the last inserted letter leaves nothing', run('a{++X++}b', 4, 5, '', true), { text: 'ab', caret: 1 });
eq('backspace/over a marker reaches the letter', run('a{++X++}b', 5, 8, '', true), { text: 'ab', caret: 1 });
eq('backspace/after a deletion reaches the letter before it', run('x{--abc--}', 7, 10, '', true), { text: '{--xabc--}', caret: 0 });
eq('delete/forward wraps and steps past', run('abc', 0, 1, '', false), { text: '{--a--}bc', caret: 7 });
eq('replace/a selection becomes both', run('the cat', 4, 7, 'dog', false), { text: 'the {--cat--}{++dog++}', caret: 19 });
eq('type/inside a deletion goes after it', run('a{--bc--}d', 5, 5, 'Q', false), { text: 'a{--bc--}{++Q++}d', caret: 13 });
eq('normalise/only near the edit', run('a --}{-- b and more', 18, 18, 'X', false), { text: 'a --}{-- b and mor{++X++}e', caret: 22 });
eq('resolve/accept all', docSuggestResolveAll('a{++X++}b{--c--}d', true), 'aXbd');
eq('resolve/reject all', docSuggestResolveAll('a{++X++}b{--c--}d', false), 'abcd');
eq('resolve/one edit', docSuggestResolve(docSuggestParse('a{--bc--}d')[0], false), { from: 1, to: 9, insert: 'bc' });
eq('parse/code is not a suggestion', docSuggestParse('```\n{++x++}\n```\nand `{--y--}`').length, 0);
eq('parse/kinds and spans', docSuggestParse('a{++X++}b{--c--}').map((m) => [m.kind, m.start, m.end, m.body]), [['ins', 1, 8, 'X'], ['del', 9, 16, 'c']]);
eq('read/struck and highlighted', docSuggestForRead('a{++X++}b{--c--}'), 'a==X==b~~c~~');
process.stdout.write(JSON.stringify(results));
"""


def _suggest_source() -> str:
    start = DOCUMENTS.index("// DOC-SUGGEST-BEGIN")
    stop = DOCUMENTS.index("// DOC-SUGGEST-END")
    return DOCUMENTS[start:stop]


def test_suggestion_mode_edits_as_decided(tmp_path) -> None:
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    script = tmp_path / "suggest.js"
    script.write_text(_suggest_source() + SUGGEST_DRIVER, encoding="utf-8")
    out = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60, check=False)
    assert out.returncode == 0, out.stderr
    failed = [f"{r['name']}: {r['detail']}" for r in json.loads(out.stdout) if not r["ok"]]
    assert not failed, "\n".join(failed)


def test_suggestion_mode_is_wired_and_reachable() -> None:
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    for element in ("doc-suggest-mode", "doc-suggest-next", "doc-suggest-accept-all", "doc-suggest-reject-all", "doc-suggest-status"):
        assert f'id="{element}"' in html, element
        assert f'$("{element}")' in DOCUMENTS, element
    assert "docProseToolExtensions(CM)" in _body("docCmExtensions")
    assert "docSuggestForRead(" in _body("renderDocPreview")


#: INBOX 689: a press on a suggested change whose text is also a spelling
#: finding opens one menu, the change's answers first and the finding's after.
MENU_DRIVER = r"""
const results = [];
const eq = (name, got, want) => results.push({ name, ok: JSON.stringify(got) === JSON.stringify(want), detail: JSON.stringify(got) });
const text = 'Say {++faque++} and {--old--}.';
const [ins, del] = docSuggestParse(text);
const finding = { start: text.indexOf('faque'), end: text.indexOf('faque') + 5, text: 'faque', rule: 'spelling' };
const elsewhere = { start: 0, end: 3, text: 'Say', rule: 'spelling' };
const straddle = { start: ins.start - 2, end: ins.bodyStart + 2, text: 'x', rule: 'spelling' };
eq('finding/inside the body', docSuggestFindingFor(ins, [elsewhere, finding]), finding);
eq('finding/outside the body is none', docSuggestFindingFor(ins, [elsewhere]), null);
eq('finding/the marker alone is not the body', docSuggestFindingFor(ins, [{ start: ins.start, end: ins.bodyStart }]), null);
eq('finding/overlapping the body edge counts', docSuggestFindingFor(ins, [straddle]), straddle);
eq('finding/none for a deletion without one', docSuggestFindingFor(del, [finding]), null);
eq('finding/no list is none', docSuggestFindingFor(ins, undefined), null);
const second = { start: finding.start + 2, end: finding.end, text: 'que', rule: 'spelling' };
eq('finding/the one under the offset wins', docSuggestFindingFor(ins, [finding, second], finding.end - 1), finding);
const calls = [];
const run = {
  one: (accept) => () => calls.push(['one', accept]),
  all: (accept) => () => calls.push(['all', accept]),
  next: () => () => calls.push(['next']),
};
const answers = [
  { label: 'fake', title: 'Replace with fake', run: () => calls.push(['fix']) },
  { label: 'ph:book-open-text Add to dictionary', title: 't', run: () => calls.push(['dict']) },
  { label: 'ph:eye-slash Ignore in this document', title: 't', run: () => calls.push(['ignore']) },
];
const alone = docSuggestMenuItems(ins, 1, [], run);
eq('menu/no finding keeps the old two rows', alone.map((i) => [i.group, i.label]), [['one', 'ph:check Accept this insertion'], ['one', 'ph:x Reject this insertion']]);
const many = docSuggestMenuItems(del, 2, [], run);
eq('menu/two changes add the all rows', many.map((i) => i.group), ['one', 'one', 'all', 'all', 'all']);
const one = docSuggestMenuItems(ins, 2, answers, run);
eq('menu/the change first, the finding after', one.map((i) => i.label), [
  'ph:check Accept this insertion', 'ph:x Reject this insertion', 'ph:checks Accept all 2', 'ph:x-circle Reject all 2',
  'ph:arrow-down Next change', 'fake', 'ph:book-open-text Add to dictionary', 'ph:eye-slash Ignore in this document',
]);
eq('menu/the finding is its own group', [...new Set(one.slice(5).map((i) => i.group))], ['finding']);
eq('menu/groups in order', [...new Set(one.map((i) => i.group))], ['one', 'all', 'finding']);
one.forEach((item) => item.run());
eq('menu/every row runs its own action', calls.map((c) => c.join(':')), ['one:true', 'one:false', 'all:true', 'all:false', 'next', 'fix', 'dict', 'ignore']);
process.stdout.write(JSON.stringify(results));
"""


def test_a_suggested_change_with_a_finding_is_one_menu(tmp_path) -> None:
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    script = tmp_path / "menu.js"
    script.write_text(_suggest_source() + MENU_DRIVER, encoding="utf-8")
    out = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60, check=False)
    assert out.returncode == 0, out.stderr
    failed = [f"{r['name']}: {r['detail']}" for r in json.loads(out.stdout) if not r["ok"]]
    assert not failed, "\n".join(failed)


def test_the_change_menu_and_the_popover_take_their_answers_from_one_builder() -> None:
    """The finding's answers are `docFindingAnswerRows`, drawn by the popover
    (`docSuggestAnswers`) and listed by the change's menu (`docSuggestMenu`),
    and no pointer menu is open when the popover is asked for."""
    assert "docFindingAnswerRows(" in _body("docSuggestAnswers")
    menu = _body("docSuggestMenu")
    assert "docFindingAnswerRows(" in menu
    assert "closeDocSuggest()" in menu
    assert "docSuggestMenuItems(" in menu
    assert "docPointerMenuOpen()" in _body("docOpenSuggestFor")
    # The labels live in the builder alone: a second literal is a second copy.
    # (Ignore's words come from `docIgnoreLabel`, which says which of the two
    # an Ignore is: this document for now, or a link offer's name for good.)
    assert DOCUMENTS.count(': "Ignore in this document";') == 1
    assert "docIgnoreLabel(finding)" in _body("docFindingAnswerRows")
    assert DOCUMENTS.count('"ph:book-open-text Add to dictionary"') == 1


# --- read aloud ----------------------------------------------------------------

READ_DRIVER = r"""
const results = [];
const eq = (name, got, want) => results.push({ name, ok: JSON.stringify(got) === JSON.stringify(want), detail: JSON.stringify(got) });
eq('speak/syntax is not said', docSpeakable('## A **bold** [link](http://x) and `code`'), 'A bold link and code');
eq('speak/a suggested deletion is not said', docSpeakable('Keep {--this --}{++that++} word'), 'Keep that word');
eq('speak/a task box is not said', docSpeakable('- [x] Done it'), 'Done it');
eq('speak/a comment is not said', docSpeakable('Words %%note to self%% here.'), 'Words here.');
const text = '# Title\n\nOne. Two!\n\n```\nnot read.\n```\n';
const spans = docReadAloudSentences(text, 0, text.length).map((s) => text.slice(s.from, s.to));
eq('sentences/per line, fences skipped', spans, ['# Title', 'One.', 'Two!']);
const part = docReadAloudSentences(text, text.indexOf('Two'), text.indexOf('Two') + 4).map((s) => text.slice(s.from, s.to));
eq('sentences/clipped to the range', part, ['Two!']);
process.stdout.write(JSON.stringify(results));
"""


def test_read_aloud_says_words_not_markdown(tmp_path) -> None:
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    start = DOCUMENTS.index("function docSpeakable(")
    stop = DOCUMENTS.index("let docReadAloud = null;")
    script = tmp_path / "read.js"
    script.write_text(DOCUMENTS[start:stop] + READ_DRIVER, encoding="utf-8")
    out = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60, check=False)
    assert out.returncode == 0, out.stderr
    failed = [f"{r['name']}: {r['detail']}" for r in json.loads(out.stdout) if not r["ok"]]
    assert not failed, "\n".join(failed)


def test_read_aloud_is_reachable_and_stoppable() -> None:
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    for element in ("doc-read-aloud", "doc-read-stop"):
        assert f'id="{element}"' in html and f'$("{element}")' in DOCUMENTS, element
    #: Local voices first: a network voice is the one thing this app avoids.
    assert "localService !== false" in _body("docReadAloudVoice")
    assert "docReadAloudExtension(CM)" in _body("docProseToolExtensions")


# --- accessibility -------------------------------------------------------------

A11Y_DRIVER = r"""
const results = [];
const eq = (name, got, want) => results.push({ name, ok: JSON.stringify(got) === JSON.stringify(want), detail: JSON.stringify(got) });
const rules = (text) => docAccessFindings(text).map((f) => [f.rule, f.text]);
eq('heading/a skipped level', rules('# A\n\n### C\n'), [['heading-order', '### C']]);
eq('heading/the fix is one level down', docAccessFindings('## A\n#### B\n')[0].alternatives, ['### B']);
eq('heading/going back up is fine', rules('# A\n## B\n### C\n# D\n## E\n'), []);
eq('heading/the first heading sets no rule', rules('### Start deep\n'), []);
eq('heading/fences and frontmatter are not headings', rules('---\ntitle: x\n---\n# A\n```\n### not a heading\n```\n'), []);
eq('image/no alt', rules('See ![](pic.png) and ![a cat](cat.png)'), [['image-alt', '![](pic.png)']]);
eq('image/html without alt', rules('<img src="a.png"> <img src="b.png" alt="A chart">'), [['image-alt', '<img src="a.png">']]);
eq('link/vague text', rules('[Click here](http://x). [the report](http://y) and [more](z)'), [['link-text', '[Click here](http://x)'], ['link-text', '[more](z)']]);
eq('link/an address as its text', rules('[https://example.com](https://example.com)'), [['link-text', '[https://example.com](https://example.com)']]);
eq('link/code is not checked', rules('`[here](x)` and\n```\n![](y)\n```\n'), []);
process.stdout.write(JSON.stringify(results));
"""


def test_accessibility_findings_as_decided(tmp_path) -> None:
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    a11y = DOCUMENTS[DOCUMENTS.index("// DOC-A11Y-BEGIN") : DOCUMENTS.index("// DOC-A11Y-END")]
    script = tmp_path / "a11y.js"
    script.write_text(_suggest_source() + a11y + A11Y_DRIVER, encoding="utf-8")
    out = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60, check=False)
    assert out.returncode == 0, out.stderr
    failed = [f"{r['name']}: {r['detail']}" for r in json.loads(out.stdout) if not r["ok"]]
    assert not failed, "\n".join(failed)


def test_accessibility_is_its_own_group_in_the_panel() -> None:
    assert 'return "access";' in _body("docFindingKind")
    assert '["access", "Accessibility"]' in DOCUMENTS
    assert "docAccessFindings(text)" in _body("docProseExtras")


# --- .docx round trip ----------------------------------------------------------
#
# The importer is tested on a Word file written here by hand. The exporter is
# in the browser now (documents-word.js); the python-docx one is retired.

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _word_file(path: Path, body: str, numbering: str = "", rels: str = "") -> Path:
    import zipfile

    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "word/document.xml",
            f'<w:document xmlns:w="{W_NS}" xmlns:r="{R_NS}"><w:body>{body}</w:body></w:document>',
        )
        if numbering:
            archive.writestr("word/numbering.xml", f'<w:numbering xmlns:w="{W_NS}">{numbering}</w:numbering>')
        if rels:
            archive.writestr(
                "word/_rels/document.xml.rels",
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                f"{rels}</Relationships>",
            )
    return path


def _p(inner: str, props: str = "") -> str:
    return f"<w:p>{f'<w:pPr>{props}</w:pPr>' if props else ''}{inner}</w:p>"


def _r(text: str, props: str = "", deleted: bool = False) -> str:
    tag = "w:delText" if deleted else "w:t"
    rpr = f"<w:rPr>{props}</w:rPr>" if props else ""
    return f'<w:r>{rpr}<{tag} xml:space="preserve">{text}</{tag}></w:r>'


def test_a_word_file_with_tables_links_lists_and_revisions_reads_as_markdown(tmp_path) -> None:
    from tessellate.core import docview

    numbering = (
        '<w:abstractNum w:abstractNumId="0"><w:lvl w:ilvl="0"><w:numFmt w:val="decimal"/></w:lvl></w:abstractNum>'
        '<w:abstractNum w:abstractNumId="1"><w:lvl w:ilvl="0"><w:numFmt w:val="bullet"/></w:lvl>'
        '<w:lvl w:ilvl="1"><w:numFmt w:val="bullet"/></w:lvl></w:abstractNum>'
        '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>'
        '<w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num>'
    )
    rels = (
        '<Relationship Id="rId9" Type="hyperlink" Target="https://example.com/a" TargetMode="External"/>'
        '<Relationship Id="rId10" Type="hyperlink" Target="javascript:alert(1)" TargetMode="External"/>'
    )
    num = lambda n, level=0: f'<w:numPr><w:ilvl w:val="{level}"/><w:numId w:val="{n}"/></w:numPr>'  # noqa: E731
    body = "".join(
        [
            _p(_r("Plan"), '<w:pStyle w:val="Heading1"/>'),
            _p(_r("First"), num(1)),
            _p(_r("Second"), num(1)),
            _p(_r("Point"), num(2)),
            _p(_r("Sub point"), num(2, 1)),
            _p(
                _r("See ")
                + f'<w:hyperlink r:id="rId9">{_r("the page")}</w:hyperlink>'
                + _r(" and ")
                + f'<w:hyperlink r:id="rId10">{_r("this")}</w:hyperlink>'
                + _r(" with ")
                + _r("old", "<w:strike/>")
                + _r(" and ")
                + _r("x = 1", '<w:rFonts w:ascii="Consolas"/>')
            ),
            _p(
                _r("Keep ")
                + f'<w:ins w:id="1" w:author="A">{_r("new ")}</w:ins>'
                + f'<w:del w:id="2" w:author="A">{_r("gone ", deleted=True)}</w:del>'
                + _r("words.")
            ),
            "<w:tbl><w:tr><w:tc>" + _p(_r("Name", "<w:b/>")) + "</w:tc><w:tc>" + _p(_r("Score", "<w:b/>"))
            + "</w:tc></w:tr><w:tr><w:tc>" + _p(_r("Ann")) + "</w:tc><w:tc>" + _p(_r("9")) + "</w:tc></w:tr></w:tbl>",
            _p(_r("def f():", '<w:rFonts w:ascii="Consolas"/>')),
            _p(_r("    return 1", '<w:rFonts w:ascii="Consolas"/>')),
            _p(_r("Done.")),
        ]
    )
    path = _word_file(tmp_path / "review.docx", body, numbering, rels)
    text = docview.docx_to_markdown(path)
    assert "# Plan" in text
    assert "1. First\n1. Second\n- Point\n  - Sub point" in text
    assert "See [the page](https://example.com/a) and this with ~~old~~ and `x = 1`" in text
    assert "javascript" not in text
    assert "Keep {++new ++}{--gone --}words." in text
    assert "| Name | Score |\n| --- | --- |\n| Ann | 9 |" in text
    assert "```\ndef f():\n    return 1\n```" in text
    assert docview.docx_has_revisions(path)
    assert not docview.docx_has_revisions(_word_file(tmp_path / "plain.docx", _p(_r("x"))))


def test_a_grammar_lint_on_a_wiki_link_is_dropped(tmp_path) -> None:
    """Harper reads markdown and skips code, but `[[Another doc]]` is this
    app's syntax, not markdown: "a [[Another doc]] chip" came back as a
    redundancy ("Use another on its own") whose only fix was "aNother",
    measured in the live view on 2026-10-04 (`cm-live.js`'s fixture). A lint
    that touches a link or an embed is dropped; one beside it is kept. Run in
    node on the page's own `docGrammarFindings`, through the real worker so
    the lint is the one Harper really returns."""
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    text = "A link to a [[Another doc]] chip and ![[Some picture.png]] here.\n\nThe the search index moved.\n"
    script = tmp_path / "harper.mjs"
    script.write_text(HARPER_DRIVER, encoding="utf-8")
    out = subprocess.run(
        [node, str(script), (FRONTEND / "js" / "harper-worker.js").as_uri(), text],
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert out.returncode == 0, out.stderr
    lints = json.loads(out.stdout)[0]["lints"]
    #: The premise: Harper itself does flag the link, so the filter is what
    #: removes it (were Harper ever to stop, this test says so rather than
    #: passing on nothing).
    assert any("[[" in text[lint["start"] : lint["end"]] for lint in lints), lints
    src = "\n".join(
        DOCUMENTS[DOCUMENTS.index(start) : DOCUMENTS.index(end, DOCUMENTS.index(start)) + len(end)]
        for start, end in (
            ("const DOC_GRAMMAR_SKIP_KINDS", ";\n"),
            ("const DOC_GRAMMAR_DASH", ";\n"),
            ("function docGrammarMessage(", "\n}\n"),
            ("const DOC_GRAMMAR_WIKI", ";\n"),
            ("function docGrammarOutside(", "\n}\n"),
            ("function docGrammarFindings(", "\n}\n"),
        )
    )
    runner = tmp_path / "findings.js"
    runner.write_text(
        src + "\nconst lints = JSON.parse(process.argv[2]);\n"
        "process.stdout.write(JSON.stringify(docGrammarFindings(lints, process.argv[3])));\n",
        encoding="utf-8",
    )
    found = subprocess.run(
        [node, str(runner), json.dumps(lints), text], capture_output=True, text=True, timeout=60, check=False
    )
    assert found.returncode == 0, found.stderr
    findings = json.loads(found.stdout)
    assert not [f for f in findings if "[[" in f["text"] or "]]" in f["text"]], findings
    assert any(f["text"] == "The the" for f in findings), findings


def test_a_worker_that_does_not_start_says_which_file_and_why():
    """INBOX 804: the owner's Windows log said only "the grammar worker did not
    start", the bare event a module worker fires when a file it loads is
    refused. The page then fetches each file the worker loads and names the
    one that failed and how; the list is the worker's own imports, in order."""
    prose = (FRONTEND / "js" / "documents-prose.js").read_text(encoding="utf-8")
    worker = (FRONTEND / "js" / "harper-worker.js").read_text(encoding="utf-8")
    imports = ["/vendor/harper/" + name for name in re.findall(r'from "\.\./vendor/harper/([\w.-]+\.js)"', worker)]
    listed = re.search(r"const DOC_GRAMMAR_FILES = \[\s*DOC_GRAMMAR_WORKER_URL,\s*((?:\"[^\"]+\",\s*)+)\]", prose)
    assert listed and re.findall(r'"([^"]+)"', listed.group(1)) == imports
    assert "docGrammarWhy().then((why) => docGrammarFail(" in prose
