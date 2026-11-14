"""A document exported as HTML is one file that needs nothing else.

DOCUMENTS_PLAN Phase 7, and the decision in that plan's section 13: there is no
server-side markdown renderer in this app and the plan forbids adding one, so
the export is built in the browser from the pane that is already rendered. That
puts the thing most worth testing in a JavaScript file rather than behind an
endpoint, so this runs the document shell in node (the model lives between
`DOC-EXPORT-HTML-BEGIN` and `DOC-EXPORT-HTML-END` in documents.js, with no DOM
and no app globals in it) and reads the rest out of the source.

"Self-contained" is the whole promise: the file has to open on a machine with
no network, no Tessellate and no account. Every assertion here is one way that
promise could quietly stop being true, and the one that matters most is the
cheapest to break: a stylesheet that grows a webfont `@import` is still a file
that looks right on the machine that made it.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS_JS = ROOT / "frontend" / "js" / "documents.js"
INDEX_HTML = ROOT / "frontend" / "index.html"

BEGIN = "// DOC-EXPORT-HTML-BEGIN"
END = "// DOC-EXPORT-HTML-END"


EXPORT_JS = ROOT / "frontend" / "js" / "documents-export.js"


def export_source() -> str:
    text = EXPORT_JS.read_text(encoding="utf-8")
    start = text.find(BEGIN)
    stop = text.find(END)
    assert start != -1, f"{BEGIN} marker is missing from documents-export.js"
    assert stop > start, f"{END} marker is missing or before {BEGIN}"
    return text[start + len(BEGIN) : stop]


DRIVER = r"""
const results = [];
function check(name, ok, detail) {
  results.push({ name, ok: !!ok, detail: detail === undefined ? null : detail });
}

const page = docExportHtmlDocument('Design notes', '<h1>Design notes</h1>\n<p>Hello.</p>', 'exported today');

check('shell/is a whole html document', /^<!doctype html>/i.test(page) && page.trim().endsWith('</html>'), page.slice(0, 40));
check('shell/declares its charset', page.includes('<meta charset="utf-8">'), '');
check('shell/carries the title', page.includes('<title>Design notes</title>'), '');
check('shell/carries the body', page.includes('<p>Hello.</p>'), '');
check('shell/carries its own stylesheet', page.includes('<style>') && page.includes('max-width'), '');
check('shell/no script of any kind', !/<script/i.test(page), '');

// The promise, stated as a test: nothing in the file may name a host.
const external = page.match(/(?:https?:)?\/\/[a-z0-9.-]+/gi) || [];
check('self-contained/nothing names a host', external.length === 0, JSON.stringify(external.slice(0, 5)));
check('self-contained/no stylesheet link', !/<link/i.test(page), '');
check('self-contained/no css import', !/@import/i.test(page), '');
check('self-contained/no url() in the stylesheet', !/url\(/i.test(page), '');

// A title is text somebody typed, and it lands inside <title>.
const nasty = docExportHtmlDocument('</title><script>alert(1)</script>', '<p>x</p>', '');
check('escape/a title cannot close its own tag', !/<script/i.test(nasty), nasty.slice(0, 120));
check('escape/the characters come back as entities', nasty.includes('&lt;script&gt;'), '');
check('escape/an ampersand is escaped once', docExportEscape('a & b') === 'a &amp; b', docExportEscape('a & b'));
check('escape/nothing is not the string null', docExportEscape(null) === '', JSON.stringify(docExportEscape(null)));

// No meta line, no empty paragraph where it would have been.
const bare = docExportHtmlDocument('T', '<p>b</p>', '');
check('meta/absent rather than empty', !bare.includes('<p class="doc-export-meta">'), '');
check('meta/present when there is one', page.includes('<p class="doc-export-meta">exported today</p>'), '');
check('title/falls back rather than printing undefined', docExportHtmlDocument('', '<p>x</p>', '').includes('<title>Untitled document</title>'), '');

process.stdout.write(JSON.stringify(results));
"""


@pytest.fixture(scope="module")
def export_checks(tmp_path_factory) -> list[dict]:
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    script = tmp_path_factory.mktemp("docexporthtml") / "run.js"
    script.write_text(export_source() + DRIVER, encoding="utf-8")
    out = subprocess.run(
        [node, str(script)], capture_output=True, text=True, timeout=60, check=False
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_the_shell_runs_without_a_browser(export_checks: list[dict]) -> None:
    assert len(export_checks) > 12, "the driver did not reach the end"


def test_the_exported_file_needs_nothing_else(export_checks: list[dict]) -> None:
    failed = [c for c in export_checks if not c["ok"]]
    assert not failed, "\n".join(f"{c['name']}: {c['detail']}" for c in failed[:20])


def test_the_export_strips_what_only_works_inside_the_app() -> None:
    """The cleaner is the other half of the promise, and it has no DOM here.

    What is asserted is that it still names each class of thing it was written
    for. A removal from this list is a deliberate decision (an icon font gets
    inlined, say) and should fail here until the plan says so.
    """
    text = DOCUMENTS_JS.read_text(encoding="utf-8")
    strip = re.search(r'const DOC_EXPORT_STRIP = "([^"]+)"', text)
    assert strip, "DOC_EXPORT_STRIP is gone; the export ships the app's controls"
    selectors = strip.group(1)
    for wanted in (".code-actions", "script", "i.ph"):
        assert wanted in selectors, f"{wanted} is no longer stripped from an export"
    body = text[text.index("function docExportClean") :][:3000]
    assert "docExportUnwrapControls" in body, (
        "a [[wikilink]] renders as a button here; removed with the other "
        "controls it takes its own words out of the sentence"
    )
    assert 'removeAttribute("style")' in body, "inline styles survive into the export"
    assert "data-" in body, "the app's own data- handles travel into the export"
    assert 'a[href]' in body, "a link back into this app keeps its href"
    assert "docExportPromoteHeadings" in body, (
        "the pane's h3-and-down headings are no longer lifted, so an exported "
        "file's first heading is three levels down in a page with no h1 in it"
    )
    levels = re.search(r"const DOC_EXPORT_HEADINGS = \{([^}]+)\}", text)
    assert levels and '"h1"' in levels.group(1), levels


def test_the_menu_offers_it_where_the_other_exports_are() -> None:
    markup = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="doc-export-html"' in markup
    where = markup.index('id="doc-export-html"')
    near = markup[where - 2000 : where + 2000]
    assert 'id="doc-export-md"' in near and 'id="doc-export-pdf"' in near, (
        "the HTML export is not beside the other two, so the ⋯ menu has an "
        "export in one place and two in another"
    )


def test_a_graph_and_a_table_of_notes_export_as_figures_not_as_screen_controls() -> None:
    """Found driving the export (F1 run 2): the plot had no lines styled, the key's swatch was a style the clean-up drops, a base
    block was saved as its "Reading the notes" line, and its row names (buttons) were removed with the other controls."""
    docs = DOCUMENTS_JS.read_text(encoding="utf-8")
    export = EXPORT_JS.read_text(encoding="utf-8")
    figures = docs[docs.index("docExportClean.figures = ") :][:1400]
    assert all(name in figures for name in (".dg-tools", ".dg-params", ".dg-edit", ".db-edit", ".db-bar button", ".dg-swatch")), figures
    assert "docExportClean.figures(root)" in docs[docs.index("function docExportClean") :][:400]
    assert 'node.matches(".wiki-link, .db-open")' in docs, "a note's name in a base table must survive as text"
    css = export[export.index("const DOC_EXPORT_CSS") :][:4500]
    for rule in (".dg-svg", ".dg-line", ".dg-axis", ".dg-curve", ".dg-key", ".db-scroll"):
        assert rule in css, rule
    run = export[export.index("async function docExportHtmlRun") :][:1500]
    assert run.index("docExportHtmlRun.settled(") < run.index("cloneNode(true)"), "the rows are waited for before the preview is copied"


def test_a_board_and_a_calendar_export_with_their_own_layout_on_screen_and_on_paper() -> None:
    """L-documents-84: the file styled only the table's box, so a board was three stacked blocks and the calendar 42 full-width
    lines (measured at 794px: calendar 1293px tall, columns 672px each). The layout rules are in the file, and a print rule keeps
    a card, a column and a day from splitting across two sheets."""
    export = EXPORT_JS.read_text(encoding="utf-8")
    css = export[export.index("const DOC_EXPORT_CSS") : export.index("docExportHtmlDocument.deckCss") if "docExportHtmlDocument.deckCss" in export else None]
    for rule in (".db-board {", ".db-col {", ".db-card {", ".db-cal {", ".db-day {", ".db-dow {", ".db-day-out"):
        assert rule in css, rule
    assert "grid-template-columns: repeat(7" in css and "flex-wrap: wrap" in css
    printed = css[css.index("@media print") :]
    assert ".db-card" in printed and "break-inside: avoid" in printed


def test_a_saved_board_and_calendar_carry_no_dead_controls() -> None:
    """L-documents-98, found in a real exported file opened in Chromium (no script in it): the six board cards kept
    draggable="true" and picked up a ghost that dropped nowhere, the view switch and the Group by and Date in pickers were
    empty shells (a bare "Group by" label, empty .menu-wrap spans), and the month arrows were already gone with the other
    buttons, so the calendar's title stays as plain text for the month it was exported in."""
    docs = DOCUMENTS_JS.read_text(encoding="utf-8")
    rest = docs[docs.index("docExportClean.rest = ") :][:3500]
    for gone in (".db-choose", ".db-views", ".db-body .menu-wrap", 'removeAttribute("draggable")'):
        assert gone in rest, gone
