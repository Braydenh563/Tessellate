"""Citations: `[@key]` in the prose, `[@key]: the source` at the foot (DOCUMENTS_PLAN row 2).

Read view turns each defined citation into a footnote, so the numbers follow the
order of first use and the list renumbers itself when paragraphs move. The pure
region runs in node; the wiring is read from the source; the drive is in CHANGELOG.
"""

from __future__ import annotations
from tests._app_js import frontend_text

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _read(name: str) -> str:
    return frontend_text(name) if name == "documents.js" else (JS / name).read_text(encoding="utf-8")


def _run(expr: str) -> object:
    text = _read("documents-prose.js")
    region = text[text.index("// DOC-CITE-BEGIN") : text.index("// DOC-CITE-END")]
    script = "function docPairInput() {}\n" + region + f"\nconsole.log(JSON.stringify({expr}));\n"
    out = subprocess.run(["node", "-"], input=script, capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr[-500:]
    return json.loads(out.stdout.strip().splitlines()[-1])


@node
def test_a_key_comes_from_the_host_or_the_first_words_and_never_repeats() -> None:
    got = _run(
        "[docPairInput.citeKey('https://www.example.com/a?b=1', []),"
        " docPairInput.citeKey('Smith, J. (2020). Notes on tiling', []),"
        " docPairInput.citeKey('https://example.org/x', ['example', 'example2']),"
        " docPairInput.citeKey('!!!', [])]"
    )
    assert got == ["example", "smith-j", "example3", "source"]


@node
def test_defined_citations_become_footnotes_and_undefined_ones_stay() -> None:
    text = "A [@smith] and [@nobody].\\n```\\n[@smith]\\n```\\n\\n[@smith]: Smith, 2020"
    got = _run(f"docPairInput.citeFootnotes('{text}')")
    assert got == "A [^smith] and [@nobody].\n```\n[@smith]\n```\n\n[^smith]: Smith, 2020"
    assert _run("docPairInput.citeFootnotes('plain [@a]')") == "plain [@a]"


@node
def test_citing_writes_the_mark_at_the_caret_and_the_source_at_the_foot() -> None:
    got = _run("docPairInput.citeInsert('One two.\\n', 3, 3, 'https://example.com/p')")
    assert got == {"value": "One[@example] two.\n\n[@example]: <https://example.com/p>\n", "caret": 13}
    again = _run(
        "docPairInput.citeInsert('A.\\n\\n[@example]: <https://example.com/p>\\n', 1, 1, 'https://example.com/p')"
    )
    assert again["value"].count("[@example]:") == 1 and again["value"].startswith("A[@example].")
    second = _run("docPairInput.citeInsert('A.\\n\\n[@x]: one\\n', 1, 1, 'Two, 2021')")
    assert second["value"].endswith("[@x]: one\n[@two-2021]: Two, 2021\n")


@node
def test_a_note_cited_by_title_is_written_as_a_wikilink_and_keeps_its_key() -> None:
    assert _run("docPairInput.citeNote('Tiling notes')") == "[[Tiling notes]]"
    #: Brackets, the alias bar and line breaks cannot sit inside `[[ ]]`.
    assert _run("docPairInput.citeNote('A [b] | c\\nd')") == "[[A b c d]]"
    assert _run("docPairInput.citeNote('  ')") == ""
    got = _run("docPairInput.citeInsert('One two.\\n', 3, 3, docPairInput.citeNote('Tiling notes'))")
    assert got["value"] == "One[@tiling-notes] two.\n\n[@tiling-notes]: [[Tiling notes]]\n"
    again = _run(
        "docPairInput.citeInsert('A.\\n\\n[@tiling-notes]: [[Tiling notes]]\\n', 1, 1, '[[Tiling notes]]')"
    )
    assert again["value"].count("[@tiling-notes]:") == 1


@node
def test_the_picker_offers_notes_and_what_was_typed() -> None:
    items = _run(
        "docPairInput.citeChoices([{id: 1, title: 'Tiling notes', content: 'x'}, {id: 2, title: '', content: '# Penrose\\nbody'},"
        " {id: 3, title: 'Other', content: 'y', is_draft: true}], 'til')"
    )
    assert [i["source"] for i in items] == ["[[Tiling notes]]", "til"]
    assert [bool(i["entry"]) for i in items] == [True, False]
    assert _run("docPairInput.citeChoices([{id: 2, title: '', content: '# Penrose\\nbody'}], '')")[0]["source"] == "[[Penrose]]"
    url = _run("docPairInput.citeChoices([], 'https://example.com/p')")
    assert [i["source"] for i in url] == ["https://example.com/p"]


def test_the_cite_row_opens_the_picker_not_a_bare_prompt() -> None:
    docs = _read("documents.js")
    cite = docs[docs.index('action.custom === "cite"') :][:900]
    assert "docPairInput.citePick(" in cite and "promptDialog" not in cite


def test_the_wiring_is_in_place() -> None:
    docs = _read("documents.js")
    assert 'cite: { custom: "cite" }' in docs and "docPairInput.citeInsert(" in docs
    assert "docPairInput.citeFootnotes(String(raw" in docs
    assert "docPairInput.citeKeys(docStr(doc))" in _read("documents-cm.js")
    assert 'id: "cite"' in _read("editor.js")
    assert "`\\n[${sigil}${id}]:`" in _read("documents-callouts.js")
