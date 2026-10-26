"""The document editor's text tools (docs3-1026): change case, sort and
de-duplicate lines, heading numbers, the date, and the statistics. The pure
half runs in node; the wiring half is checked as text, because the suite
cannot see the DOM (the Playwright run is `scratchpad/ui-sweeps/doctexttools.js`)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROSE = ROOT / "frontend/js/documents-prose.js"
DOCUMENTS = ROOT / "frontend/js/documents.js"
INDEX = ROOT / "frontend/index.html"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _pure() -> str:
    src = PROSE.read_text(encoding="utf-8")
    return src[src.index("const DOC_STOP_WORDS") : src.index("function docOpenStatistics")]


def _run(expr: str):
    script = _pure() + f"\nconsole.log(JSON.stringify({expr}));"
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60, check=True)
    return json.loads(out.stdout)


def test_title_case_keeps_small_words_down_except_at_the_ends():
    assert _run("docTitleCase('the war of the worlds and a tale')") == "The War of the Worlds and a Tale"


def test_sentence_case_capitalises_after_a_full_stop_and_keeps_the_rest_down():
    assert _run("docSentenceCase('HELLO there. how ARE you? fine')") == "Hello there. How are you? Fine"


def test_sort_is_natural_and_reversible():
    assert _run("docSortLines('b\\nItem 10\\nItem 2\\na', false)") == "a\nb\nItem 2\nItem 10"
    assert _run("docSortLines('b\\na\\nc', true)") == "c\nb\na"


def test_unique_lines_keep_the_first_and_all_blank_lines():
    assert _run("docUniqueLines('a\\n\\nA\\nb\\n\\nb')") == "a\n\nb\n"


def test_headings_number_in_a_tree_skip_a_lone_title_and_fenced_code():
    text = "# T\n\n## A\n\n### A1\n\n### A2\n\n## B\n\n```\n## no\n```\n"
    got = _run(f"docNumberHeadings({json.dumps(text)}, true)")
    assert [line for line in got.split("\n") if line.startswith("#")] == ["# T", "## 1 A", "### 1.1 A1", "### 1.2 A2", "## 2 B", "## no"]


def test_numbering_twice_renumbers_and_removing_restores_the_original():
    text = "# T\n\n## A\n\n## B\n\n### B1\n"
    once = _run(f"docNumberHeadings({json.dumps(text)}, true)")
    twice = _run(f"docNumberHeadings({json.dumps(once)}, true)")
    assert once == twice
    assert _run(f"docNumberHeadings({json.dumps(once)}, false)") == text


def test_without_a_lone_title_the_top_level_is_numbered():
    got = _run("docNumberHeadings('# A\\n\\n# B\\n\\n## B1\\n', true)")
    assert got == "# 1 A\n\n# 2 B\n\n## 2.1 B1\n"


def test_dates_are_iso_and_the_time_is_24_hour():
    assert _run("docDateText('iso', new Date(2026, 9, 6, 9, 5))") == "2026-10-06"
    assert _run("docDateText('time', new Date(2026, 9, 6, 9, 5))") == "09:05"


def test_statistics_ignore_code_links_and_comments_and_name_repeats():
    text = "# Title\n\n" + "Garden garden garden. " * 10 + "See [the page](https://example.com/x).\n\n```\nlots of code words here\n```\n%%a remark%% End.\n"
    got = _run(f"docStatistics({json.dumps(text)})")
    # Title (1) + 30 garden + "See the page" (3) + "End" (1); code, URL and remark are not read.
    assert got["words"] == 35
    assert "code" not in json.dumps(got["top"])
    assert got["top"][0][0] == "garden"
    assert got["headings"] == 1
    assert 0 <= got["ease"] <= 100


def test_statistics_of_nothing_is_zero_not_nan():
    got = _run("docStatistics('')")
    assert got["words"] == 0 and got["ease"] == 0 and got["grade"] == 0 and got["top"] == []


def test_the_commands_the_dialog_and_the_count_are_wired():
    commands = DOCUMENTS.read_text(encoding="utf-8")
    for tool in ("stats", "upper", "lower", "title", "sentence", "sort-asc", "sort-desc", "unique",
                 "number-headings", "unnumber-headings", "date-iso", "date-long", "time"):
        assert f'docRunTextTool("{tool}")' in commands, tool
    markup = INDEX.read_text(encoding="utf-8")
    for ident in ("doc-stats-dialog", "doc-stats-list", "doc-stats-scope"):
        assert f'id="{ident}"' in markup
    assert re.search(r'id="doc-counts"[^>]*role="button"[^>]*tabindex="0"', markup)
    assert '$("doc-counts")?.addEventListener("click"' in commands


def test_text_size_and_line_spacing_are_menu_rows_with_prose_only_css():
    markup = INDEX.read_text(encoding="utf-8")
    documents = DOCUMENTS.read_text(encoding="utf-8")
    css = (ROOT / "frontend/css/library-lazy.css").read_text(encoding="utf-8")
    for ident in ("doc-text-size", "doc-text-size-label", "doc-line-spacing", "doc-line-spacing-label"):
        assert f'id="{ident}"' in markup
    assert 'docRunControl("doc-text-size"' in documents and 'docRunControl("doc-line-spacing"' in documents
    # A code file keeps its own metrics: every size and spacing rule excludes it.
    rules = re.findall(r"#tab-documents\.doc-(?:size|spacing)-\w+ [^{]*\{", css)
    assert len(rules) == 4 and all(":not(.doc-content-code)" in r for r in rules)
    assert "!important" not in css[css.index("Text size and line spacing for prose") :]
