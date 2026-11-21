"""L603: the Notes strip's height token is written into a rule on the bars
that read it, never onto `#tab-notes`. The token is inherited, so a write on
the page restyled every row of the list on the first Notes press (3,467
elements, 83 to 117ms at 1x on a loaded host, 5,000 notes)."""

from pathlib import Path

from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parents[1]


def _body(js: str, head: str) -> str:
    start = js.index(head)
    return js[start : js.index("\n}\n", start)]


def test_the_token_is_not_written_on_the_page():
    body = _body(frontend_text("phone-shell.js"), "function initNotesSubtabHeightToken(")
    assert "page.style.setProperty" not in body
    assert "#tab-notes :is(.dock, .doc-toolbar, .question-group, .selectbar) { --notes-sticky-top:" in body


def test_every_reader_of_the_token_is_in_the_rule():
    """A rule that reads the token outside the four bars would keep the 0px default."""
    readers = []
    for css in sorted((ROOT / "frontend" / "css").glob("*.css")):
        text = css.read_text(encoding="utf-8")
        for block in text.split("}"):
            if "var(--notes-sticky-top)" in block:
                readers.append(block.rsplit("{", 1)[0].strip().splitlines()[-1])
    assert readers, "the token has readers"
    for selector in readers:
        assert any(name in selector for name in (".dock", ".doc-toolbar", ".question-group", ".selectbar")), selector


def test_the_selectbar_reads_it_on_itself():
    css = (ROOT / "frontend" / "css" / "00-tokens-shell.css").read_text(encoding="utf-8")
    assert "#tab-notes .selectbar {\n  --selectbar-top: var(--notes-sticky-top);" in css
    assert "#tab-notes {\n  --selectbar-top" not in css
