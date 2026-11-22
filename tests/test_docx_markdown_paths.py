"""The shapes of Word file `docview.docx_to_markdown` reads that nothing else pinned.

Characterisation tests written before the reader was split into runs, inline
content, paragraphs, tables and assembly (cc-1101); the expected text is what
the reader produced then. Covers an oversize or broken body, the inline
wrappers (smart tags, content controls, fields), titles, quotes, lists named
by style, blank paragraphs, an empty table, a block that is neither paragraph
nor table, and a code block that ends the file.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from tessellate.core import docview

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
MONO = '<w:rFonts w:ascii="Consolas"/>'


def _file(path: Path, body: str) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", f'<w:document xmlns:w="{W_NS}"><w:body>{body}</w:body></w:document>')
    return path


def _r(text: str, props: str = "") -> str:
    rpr = f"<w:rPr>{props}</w:rPr>" if props else ""
    return f'<w:r>{rpr}<w:t xml:space="preserve">{text}</w:t></w:r>'


def _p(inner: str = "", style: str = "") -> str:
    props = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f"<w:p>{props}{inner}</w:p>"


def _read(tmp_path: Path, *blocks: str) -> str:
    return docview.docx_to_markdown(_file(tmp_path / "x.docx", "".join(blocks)))


def test_an_oversize_body_reads_as_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(docview, "_DOCX_PART_CAP", 10)
    assert _read(tmp_path, _p(_r("hello"))) == ""


def test_a_body_that_is_not_xml_reads_as_nothing(tmp_path):
    path = tmp_path / "broken.docx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", f'<w:document xmlns:w="{W_NS}"><w:body><w:p>')
    assert docview.docx_to_markdown(path) == ""


def test_inline_wrappers_read_through_to_their_runs(tmp_path):
    wrapped = (
        _r("a ")
        + f"<w:smartTag>{_r('b ')}</w:smartTag>"
        + f"<w:customXml>{_r('c ')}</w:customXml>"
        + f"<w:fldSimple>{_r('d ')}</w:fldSimple>"
        + f"<w:sdt><w:sdtContent>{_r('e ')}</w:sdtContent></w:sdt>"
        + "<w:sdt></w:sdt>"
        + f"<w:sdtContent>{_r('f')}</w:sdtContent>"
    )
    assert _read(tmp_path, _p(wrapped)) == "a b c d e f\n"


def test_a_whole_document_of_block_kinds(tmp_path):
    text = _read(
        tmp_path,
        _p(_r("Plain."), "Title"),
        _p(_r("Opening words.")),
        _p(),
        _p(_r("A quotation."), "Quote"),
        _p(_r("first"), "ListBullet"),
        _p(_r("deeper"), "ListBullet2"),
        _p(_r("one"), "ListNumber"),
        _p(_r("Back to prose.")),
        "<w:sectPr/>",
        "<w:tbl></w:tbl>",
        _p(_r("before code")),
        _p(_r("x = 1", MONO)),
        _p(_r("")),
        _p(_r("y = 2", MONO)),
        _p(_r("after code")),
        "<w:tbl><w:tr><w:tc>" + _p(_r("k")) + "</w:tc></w:tr></w:tbl>",
        _p(_r("tail code", MONO)),
    )
    # An empty table leaves its blank line behind, and an empty paragraph
    # inside a code run ends the block (so there are two): both as read today.
    assert text == (
        "# Plain.\n\nOpening words.\n\n> A quotation.\n\n- first\n  - deeper\n1. one\n\nBack to prose.\n\n\n"
        "before code\n\n```\nx = 1\n```\n\n```\ny = 2\n```\n\nafter code\n\n| k |\n| --- |\n\n```\ntail code\n```\n"
    )


def test_a_list_item_is_followed_by_a_blank_line_before_a_table_code_or_a_blank_paragraph(tmp_path):
    cell = "<w:tbl><w:tr><w:tc>" + _p(_r("k")) + "</w:tc></w:tr></w:tbl>"
    item = _p(_r("item"), "ListBullet")
    assert _read(tmp_path, item, cell) == "- item\n\n| k |\n| --- |\n"
    assert _read(tmp_path, item, _p(_r("c = 1", MONO))) == "- item\n\n```\nc = 1\n```\n"
    assert _read(tmp_path, item, _p(), _p(_r("next"))) == "- item\n\nnext\n"


def test_a_tracked_change_arrives_with_its_author_and_date_as_the_stamp(tmp_path):
    """L-documents-34: a reviewer's w:author and w:date become the mark's `{>>name, date<<}`, so the round trip through Word keeps who
    and when; a change with no date makes no claim, and a name with markup characters is written clean."""
    ins = f'<w:ins w:id="1" w:author="Ann Lee" w:date="2026-11-14T09:30:00Z">{_r("new ")}</w:ins>'
    gone = '<w:del w:id="2" w:author="Bo&lt;x&gt;" w:date="2026-11-15T00:00:00Z"><w:r><w:delText xml:space="preserve">gone </w:delText></w:r></w:del>'
    bare = f'<w:ins w:id="3" w:author="Cy">{_r("bare ")}</w:ins>'
    text = _read(tmp_path, _p(_r("Keep ") + ins + gone + bare + _r("end")))
    assert text.strip() == "Keep {++new ++}{>>Ann Lee, 2026-11-14T09:30:00Z<<}{--gone --}{>>Box, 2026-11-15T00:00:00Z<<}{++bare ++}end"
