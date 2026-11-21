"""L603: the Notes strip's height token is written into a rule on the bars
that read it, never onto `#tab-notes`. The token is inherited, so a write on
the page restyled every row of the list on the first Notes press (3,467
elements, 83 to 117ms at 1x on a loaded host, 5,000 notes)."""

from pathlib import Path

from tests._app_js import app_js_text, frontend_text

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


def _fn(js: str, name: str) -> str:
    start = js.index(f"function {name}(")
    return js[start : js.index("\n}\n", start)]


def test_the_first_notes_press_draws_the_list_once():
    """The press defers the draw past the paint with an empty `data-stale`; the reveal
    drew it again inside the press when the sidebar was owed (210 then 63ms at 5k)."""
    body = _fn(app_js_text(), "revealTab")
    assert 'name === "notes" && $("entry-list").dataset.stale) renderEntries()' in body
    assert "window.notesSidebarOwed)) renderEntries()" not in body


def test_the_dashboard_outline_is_hidden_not_taken_out_of_body():
    """Removing a child of `body` restyled all 6,267 elements (106ms) just after the press."""
    body = _fn(frontend_text("dashboard.js"), "dashFillingSkeletonDone")
    assert "outline.remove()" not in body
    assert 'outline.style.display = "none"' in body


def test_a_section_shown_measures_and_paints_only_itself():
    """Boxes and heads in hidden sections forced a layout and painted faces nobody saw:
    5 to 11 and 12ms of the first Notes press. Each section does its own when shown."""
    body = _fn(app_js_text(), "showNotesSection")
    assert "autoGrowVisible($(wanted) || document)" in body
    assert "paintAssistantHeads($(wanted) || document)" in body
    assert "function autoGrowVisible(root = document)" in app_js_text()


def test_the_notes_surface_is_parsed_first_in_idle_time():
    """The Notes press is the first interaction; parsing its surface inside the press was
    most of a 55 to 124ms click."""
    js = frontend_text("settings-body.js")
    warm = js[js.index("  warm() {") :][:900]
    assert warm.index('name === "notes"') < warm.index('name === "settings"')
