"""L-chat-227 (VC1): Harper underlines on the chat composer and the Ask box.

The lint, the findings filter and the fix popover are the documents' own (documents-prose.js);
composer-lint.js adds only a mirror that paints the underlines over the field, with the text
transparent, and the click that opens the popover."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"
SRC = (JS / "composer-lint.js").read_text(encoding="utf-8")
PROSE = (JS / "documents-prose.js").read_text(encoding="utf-8")


def _segments(text, findings):
    script = (
        "const w={__composerLintTest:{}};global.window=w;global.document={addEventListener(){},activeElement:null};"
        + SRC
        + f";console.log(JSON.stringify(w.__composerLintTest.segments({json.dumps(text)},{json.dumps(findings)})))"
    )
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


def _f(start, end, text):
    return {"start": start, "end": end, "text": text}


def test_the_mirror_splits_the_text_around_each_finding_in_order():
    text = "this are a test and and more"
    segs = _segments(text, [_f(5, 8, "are"), _f(20, 23, "and")])
    assert "".join(s["text"] for s in segs) == text
    assert [s["text"] for s in segs if s["index"] is not None] == ["are", "and"]
    assert [s["index"] for s in segs if s["index"] is not None] == [0, 1]


def test_a_finding_that_no_longer_matches_the_text_or_overlaps_is_dropped():
    text = "this are fine"
    segs = _segments(text, [_f(5, 8, "xyz"), _f(5, 8, "are"), _f(6, 9, "re ")])
    assert [s["text"] for s in segs if s["index"] is not None] == ["are"]
    assert "".join(s["text"] for s in segs) == text


def test_a_trailing_newline_keeps_its_line_in_the_mirror():
    segs = _segments("one\n", [])
    assert "".join(s["text"] for s in segs).endswith("\n ")


def test_it_reuses_the_documents_lint_and_popover_and_adds_no_global():
    assert "docGrammarAsk(" in SRC and "docGrammarFindings(" in SRC and "docProseRemap(" in SRC
    assert "noteGrammarMenu(" in SRC
    assert "docGrammarEnabled()" in SRC
    #: The library bundle (documents-prose.js) is fetched on the first check, not at boot.
    assert 'ensureModule("library")' in SRC
    assert SRC.lstrip().startswith("//") and "(() => {" in SRC and SRC.rstrip().endswith("})();")
    assert "#chat-input" in SRC and "#question" in SRC
    assert ".style.cssText" not in SRC and "setAttribute(\"style\"" not in SRC


def test_the_popover_takes_a_host_so_a_textarea_can_use_it():
    """noteGrammarMenu no longer reaches into the CodeMirror view directly: the editor and
    the composer each hand it three things (read the text, replace a span, redraw)."""
    body = PROSE.split("function noteGrammarMenu(", 1)[1].split("\n}\n", 1)[0]
    assert "view.noteHost ||" in body
    assert "host.replace(" in body and "host.text()" in body and "host.refresh()" in body
    assert "view.dispatch" not in body.split("const host", 1)[1].split("const items", 1)[1]


def test_it_rides_the_quick_note_bundle():
    app = (JS / "app.js").read_text(encoding="utf-8")
    assert '"/js/composer-lint.js"' in app
    from tests._app_js import LAZY_PIECES
    assert "composer-lint.js" in LAZY_PIECES


def test_the_lint_waits_for_a_pause_and_only_runs_on_prose():
    assert "COMPOSER_LINT_DEBOUNCE_MS" in SRC
    #: Under three words there is nothing to check, and a slash command or a code fence is not prose.
    assert "words" in SRC and '"/"' in SRC and "```" in SRC
