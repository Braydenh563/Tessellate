"""Download a document as a slide deck (DOCUMENTS_PLAN gap row 15).

A level-1 or level-2 heading starts a slide, a horizontal rule starts one too,
and the rest of that section is the slide. The file is one self-contained
page (the HTML export's own shell, images as data URIs) with arrow-key,
space and click navigation, a counter, and every slide on its own sheet when
printed. The grouping is pure and runs in node here; the rest is read from the
source and driven in the app (numbers in CHANGELOG).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._app_js import documents_text

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "frontend" / "js" / "documents-export.js"
INDEX = ROOT / "frontend" / "index.html"

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _region() -> str:
    text = EXPORT.read_text(encoding="utf-8")
    start, stop = text.index("// DOC-SLIDES-BEGIN"), text.index("// DOC-SLIDES-END")
    return text[start:stop]


def _run(expr: str) -> object:
    script = "function docExportHtmlDocument() {}\n" + _region() + f"\nconsole.log(JSON.stringify({expr}));\n"
    out = subprocess.run(["node", "-"], input=script, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-500:]
    return json.loads(out.stdout.strip().splitlines()[-1])


def _blocks(*items: str) -> str:
    return json.dumps([{"tag": tag, "html": f"<{tag.lower()}>{tag}</{tag.lower()}>"} for tag in items])


@node
def test_headings_one_and_two_start_a_slide() -> None:
    got = _run(f"docExportHtmlDocument.slides({_blocks('H1', 'P', 'H2', 'P', 'UL', 'H3', 'P', 'H2', 'P')}).length")
    assert got == 3


@node
def test_text_before_the_first_heading_is_an_opening_slide_and_empty_ones_go() -> None:
    assert _run(f"docExportHtmlDocument.slides({_blocks('P', 'H2', 'P')}).length") == 2
    assert _run("docExportHtmlDocument.slides([]).length") == 0


@node
def test_a_rule_splits_and_is_not_drawn() -> None:
    got = _run(f"docExportHtmlDocument.slides({_blocks('H2', 'P', 'HR', 'P', 'P')})")
    assert len(got) == 2
    assert all("hr" not in slide for slide in got)
    assert got[1].count("<p>") == 2


@node
def test_a_lower_heading_stays_inside_its_slide() -> None:
    got = _run(f"docExportHtmlDocument.slides({_blocks('H2', 'H3', 'P', 'H4', 'P')})")
    assert len(got) == 1 and "<h3>" in got[0] and "<h4>" in got[0]


def test_the_title_line_is_not_said_twice() -> None:
    region = _region()
    assert "doc-preview-title" in region and 'tagName === "H1"' in region


def test_the_deck_navigates_and_prints_a_slide_to_a_sheet() -> None:
    region = _region()
    for key in ("ArrowRight", "ArrowLeft", "PageDown", "PageUp", '" "', "Home", "End"):
        assert key in region
    assert "page-break-after: always" in region or "break-after: page" in region
    assert "@media print" in region
    assert "aria-live" in region or "aria-label" in region


def test_the_download_row_is_in_the_menu_the_palette_and_the_code_file_hide() -> None:
    markup = INDEX.read_text(encoding="utf-8")
    assert 'id="doc-export-slides"' in markup
    near = markup[markup.index('id="doc-export-slides"') - 1500 :][:3500]
    assert 'id="doc-export-html"' in near
    docs = documents_text()
    assert re.search(r'"doc-export-html", "doc-export-slides", "doc-export-zip"', docs)
    assert 'id: "export-slides"' in docs
    # a property of the HTML stand-in, not a new name in the shared scope (the ratchet)
    assert '$("doc-export-slides").addEventListener("click", exportDocumentHtml.slides);' in docs
    assert "docExportHtmlRun(true)" in docs
    # a code file has no headings to cut into slides: the row hides with the prose-only ones
    sync = docs[docs.index("function syncDocFileType(") :].split("\n}\n")[0]
    assert '$("doc-export-slides")?.classList.toggle("hidden", docIsCodeFile());' in sync
