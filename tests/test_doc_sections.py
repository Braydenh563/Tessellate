"""A library of text sections for ordinary documents (INBOX 904 B18).

The owner: "On the document editor, I want a library of prefilled templates and
curated text sections and stuff like the code snippets but for general
documents as well". The whole-page templates already exist (`DOC_TEMPLATES`);
this is the other half: the Snippets panel, open for a markdown document too,
listing curated sections (a meeting block, a risk table, a callout) that go in
at the caret or where a row is dropped, with the same stops Tab walks.

The data and the spacing rule run here in node; the panel itself, in Chromium,
is `scratchpad/ui-sweeps/docsections1018.js`.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
KIT = (ROOT / "frontend" / "js" / "documents-codekit.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _block(start: str, end: str) -> str:
    i = KIT.index(start)
    return KIT[i : KIT.index(end, i) + len(end)]


def _node(script: str):
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=60, check=False)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def _sections() -> list:
    source = _block("const DOC_SECTIONS = [", "\n];")
    return _node(f"{source}\nprocess.stdout.write(JSON.stringify(DOC_SECTIONS));")


def test_the_library_is_a_real_set_of_sections() -> None:
    rows = _sections()
    assert len(rows) >= 20
    words = [row[0] for row in rows]
    names = [row[1] for row in rows]
    assert len(set(words)) == len(words) and len(set(names)) == len(names)
    tags = {tag for row in rows for tag in row[2]}
    assert {"meetings", "planning", "writing", "reference", "reviews", "study", "callouts", "tasks"} <= tags
    for word, name, row_tags, template in rows:
        assert word == word.lower() and " " not in word, word
        assert name[:1].isupper() and name == name.strip(), name
        assert chr(0x2014) not in template and chr(0x2014) not in name
        assert row_tags and all(tag == tag.lower() for tag in row_tags), word
        assert template.strip() and "\t" not in template, word


def test_every_template_is_valid_in_the_snippet_engine() -> None:
    """Stops are `${name}`; a stray `$` or `#{` would be read as one, a name
    used twice would mirror itself, and only one final `${}` is allowed. Each
    section has at least one stop, so Tab has somewhere to go."""
    for word, _name, _tags, template in _sections():
        assert "#{" not in template, word
        assert not re.search(r"\$(?!\{)", template), word
        stops = re.findall(r"\$\{([^}]*)\}", template)
        assert stops, word
        named = [stop for stop in stops if stop]
        assert len(named) == len(set(named)), (word, "a name twice would mirror")
        assert stops.count("") <= 1, word
        assert template.count("${") == len(stops), word


def test_the_panel_lists_them_for_a_markdown_document() -> None:
    builtins = _block("function docKitBuiltins(", "\n}\n")
    assert "DOC_SECTIONS" in builtins and 'language: "md"' in builtins
    assert "previewable" in _block("function docKitCurrent(", "\n}\n")
    render = _block("function docSnippetsRender(", "\n}\n")
    assert "docKitCurrent()" in render
    assert "docFileType().ext" not in render.split("const current")[1].split("\n")[0]


def test_the_panel_is_open_to_prose_and_the_assistant_is_not() -> None:
    selector = re.search(r"(#tab-documents:not\(\.doc-is-code\)[^{]*)\{", CSS)
    assert selector and selector.group(1).strip() == "#tab-documents:not(.doc-is-code) .doc-code-only"
    assert "#tab-documents.doc-is-code .doc-prose-only" in CSS
    opener = re.search(r'<button id="doc-code-snippets-open"[^>]*>', HTML)
    assert opener and "doc-code-only" not in opener.group(0)
    tab = re.search(r'<button role="tab" data-side="assist"[^>]*>', HTML)
    assert tab and "doc-code-only" in tab.group(0)
    assert re.search(r'<section id="doc-code-assist" class="[^"]*doc-code-only', HTML)


def _pad(cases: list) -> list:
    source = _block("function docSectionPad(", "\n}\n")
    return _node(f"{source}\nprocess.stdout.write(JSON.stringify({json.dumps(cases)}.map((c) => docSectionPad(...c))));")


def test_a_section_goes_in_as_a_block() -> None:
    got = _pad(
        [
            ["", "", None, None],  # an empty document: nothing around it
            ["Some text", "", None, None],  # the end of a line of text: a blank line first
            ["", "", "Text above", "Text below"],  # an empty line wedged between text
            ["", "", "", ""],  # an empty line between blank lines
            ["half a ", "sentence", "x", "y"],  # mid-line: blank lines both sides
            ["   ", "", "", None],  # only indent before the caret
        ]
    )
    assert got == [
        {"lead": "", "trail": ""},
        {"lead": "\n\n", "trail": ""},
        {"lead": "\n", "trail": "\n"},
        {"lead": "", "trail": ""},
        {"lead": "\n\n", "trail": "\n\n"},
        {"lead": "", "trail": ""},
    ]


def test_insert_uses_the_spacing_and_a_dropped_section_lands_at_the_drop() -> None:
    insert = _block("function docSnippetInsert(", "\n}\n")
    assert "docSectionPad(" in insert and "at == null" in insert
    assert "docSectionFill(" in insert
    fill = _block("function docSectionFill(", "\n}\n")
    assert "docTemplateFill(" in fill


def test_a_saved_section_is_kept_for_markdown_and_the_words_follow_the_type() -> None:
    save = _block("async function docSnippetSave(", "\n}\n")
    assert "docKitCurrent()" in save
    assert "Select some text first" in save
    labels = _block("function docKitSyncLabels(", "\n}\n")
    for word in ("Search sections", "Save the selected text as a section", "Sections"):
        assert word in labels, word
