"""WORLD_CLASS 423 (b): the Word export writes what the page shows.

A `[TOC]` is a real TOC field (Word fills and updates it), a callout is a
shaded one-cell table with its kind's edge, and `::: columns` is a Word
section with real columns, a column break between them. The builders are the
pure ones in `documents-word.js` (they take docx's namespace and blocks, no
DOM); the test runs them under node with the vendored docx, writes the file
and opens its XML. The walk from the page's DOM into them is driven in
Chromium (scratchpad/ui-sweeps/docx423.js).
"""

from __future__ import annotations

import base64
import re
import shutil
import subprocess
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from tests import _js_scope

ROOT = Path(__file__).resolve().parents[1]
WORD = ROOT / "frontend" / "js" / "documents-word.js"
DOCX = ROOT / "frontend" / "vendor" / "docx" / "docx.min.js"


def _function(text: str, name: str) -> str:
    start = text.index(f"function {name}(")
    return text[start : text.index("\n}\n", start) + 3]


def _consts(text: str) -> str:
    out = []
    for name in ("DOC_WORD_TONES", "DOC_WORD_TONE_OF"):
        start = text.index(f"const {name} =")
        out.append(text[start : text.index("\n", start) + 1])
    return "".join(out)


def _build(body: str) -> dict[str, str]:
    """Run `body` (JS that returns a docx Document built with `D`) and return the file's XML parts."""
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    word = _js_scope.unwrapped(WORD.read_text(encoding="utf-8"))
    names = ("docWordToc", "docWordCallout", "docWordFlat", "docWordSections")
    code = _consts(word) + "".join(_function(word, n) for n in names)
    script = f"""
const vm = require('vm'), fs = require('fs');
const c = {{ console, setTimeout, clearTimeout, TextEncoder, TextDecoder, URL, Blob, Uint8Array, ArrayBuffer }};
c.window = c; c.self = c; c.globalThis = c; vm.createContext(c);
vm.runInContext(fs.readFileSync({str(DOCX)!r}, 'utf8') + ';this.docx=docx', c);
const D = c.docx;
{code}
(async () => {{
  const doc = (() => {{ {body} }})();
  process.stdout.write(await D.Packer.toBase64String(doc));
}})();
"""
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 0, done.stderr[-600:]
    z = zipfile.ZipFile(BytesIO(base64.b64decode(done.stdout)))
    return {name: z.read(name).decode("utf-8") for name in ("word/document.xml", "word/settings.xml")}


def test_a_toc_is_a_field_word_can_update() -> None:
    parts = _build(
        "return new D.Document({ features: { updateFields: true }, sections: [{ children: [docWordToc(D),"
        " new D.Paragraph({ heading: D.HeadingLevel.HEADING_1, children: [new D.TextRun('Intro')] })] }] });"
    )
    xml = parts["word/document.xml"]
    assert re.search(r"<w:instrText[^>]*>TOC [^<]*\\o &quot;1-3&quot;", xml)
    assert 'w:fldCharType="begin"' in xml and 'w:fldCharType="end"' in xml
    assert "<w:updateFields/>" in parts["word/settings.xml"]


def test_a_callout_is_a_shaded_cell_with_the_kinds_edge() -> None:
    parts = _build(
        "const note = docWordCallout(D, 'note', [new D.Paragraph('Body')]);"
        " const bad = docWordCallout(D, 'danger', [new D.Paragraph('Stop')]);"
        " return new D.Document({ sections: [{ children: [note, new D.Paragraph(''), bad] }] });"
    )
    xml = parts["word/document.xml"]
    fills = re.findall(r'<w:shd [^>]*w:fill="([0-9A-F]{6})"', xml)
    assert len(fills) == 2 and fills[0] != fills[1]
    assert xml.count("<w:tc>") == 2 and "w:left" in xml


def test_a_callout_ending_in_a_table_still_ends_in_a_paragraph() -> None:
    parts = _build(
        "const inner = new D.Table({ rows: [new D.TableRow({ children: [new D.TableCell({ children: [new D.Paragraph('c')] })] })] });"
        " return new D.Document({ sections: [{ children: [docWordCallout(D, 'tip', [inner])] }] });"
    )
    cell = re.findall(r"<w:tc>.*?</w:tc>", parts["word/document.xml"], re.S)[0]
    assert cell.rstrip().endswith("<w:p/></w:tc>") or cell.rstrip().endswith("</w:p></w:tc>")


def test_columns_are_a_section_with_a_column_break_between_them() -> None:
    parts = _build(
        "const kids = [new D.Paragraph('before'), { docWordColumns: [[new D.Paragraph('left')], [new D.Paragraph('right')]] },"
        " new D.Paragraph('after')];"
        " return new D.Document({ sections: docWordSections(D, kids) });"
    )
    xml = parts["word/document.xml"]
    assert re.search(r'<w:cols [^>]*w:num="2"', xml)
    assert xml.count('<w:br w:type="column"/>') == 1
    assert xml.index(">before<") < xml.index(">left<") < xml.index('w:type="column"') < xml.index(">right<") < xml.index(">after<")
    assert xml.count("<w:sectPr") == 3 and xml.count('<w:type w:val="continuous"/>') == 2


def test_no_columns_is_one_plain_section() -> None:
    parts = _build("return new D.Document({ sections: docWordSections(D, [new D.Paragraph('only')]) });")
    xml = parts["word/document.xml"]
    assert xml.count("<w:sectPr") == 1 and "w:cols" not in xml.replace('<w:cols w:space="720"/>', "")


def test_the_walker_hands_each_block_to_its_builder() -> None:
    word = _js_scope.unwrapped(WORD.read_text(encoding="utf-8"))
    blocks = _function(word, "docWordBlocks")
    assert 'classList.contains("md-toc")' in blocks and "docWordToc(D)" in blocks
    assert 'classList.contains("callout")' in blocks and "docWordCallout(" in blocks
    assert 'classList.contains("doc-cols")' in blocks and "docWordColumns" in blocks
    blob = _function(word, "docWordBlob")
    assert "docWordSections(D, children)" in blob and "updateFields" in blob
