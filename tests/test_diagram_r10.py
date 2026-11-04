"""DOCUMENTS_PLAN 22.4 R10 (INBOX 1621): export and Copy as picture, from the builder, the page head and the shelf menu.

The PNG is twice the SVG viewBox, the .mmd download is the stored text byte for byte, and Copy as picture puts a PNG on the
clipboard (a download with a toast where the browser will not). The drawing itself needs a browser: HISTORY names the run.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
EMBED = (JS / "diagram-embed.js").read_text(encoding="utf-8")
BUILDER = (JS / "diagram-builder.js").read_text(encoding="utf-8")
LIBRARY = (JS / "library.js").read_text(encoding="utf-8")
DOCS = (JS / "documents.js").read_text(encoding="utf-8")
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def test_copy_as_picture_writes_a_png_and_falls_back_to_a_download():
    body = EMBED[EMBED.index("async function copyPicture") : EMBED.index("//: `how`")]
    assert 'new ClipboardItem({ "image/png"' in body and "navigator.clipboard.write" in body
    assert "saveFile(" in body and ".png" in body
    assert 'how === "picture"' in EMBED and "pngOf(svg)" in EMBED


def test_the_builders_menu_offers_it_and_a_shelf_row_exports_by_id():
    assert "Copy as picture" in BUILDER and '"picture"' in BUILDER
    assert "async function outDoc" in EMBED and "apiJson(`/documents/${id}`)" in EMBED
    assert "diagramModel.embed = { open, out, outDoc }" in EMBED
    assert "diagramModel.embed.outDoc(item.id, how)" in LIBRARY and 'item.kind === "diagram" ? [["ph:file-svg Save as SVG"' in LIBRARY
    for row in ("Save as PNG", "Copy as picture"):
        assert row in LIBRARY, row


def test_the_page_head_menu_has_png_and_copy_rows_for_a_diagram_only():
    for ident in ("doc-export-picture", "doc-copy-picture"):
        assert f'id="{ident}"' in INDEX and f'"{ident}"' in DOCS, ident
    assert "diagramModel.embed.out(how, docText()" in DOCS and 'type.ext !== "mmd"' in DOCS


def test_the_mmd_export_round_trips_byte_for_byte(ai_client):
    src = "flowchart TD\n  A[Start] --> B{Ok?}\n  B -->|yes| C((Done))\n  %% a comment, tabs\t and unicode é\n"
    made = ai_client.post("/documents", json={"title": "Flow", "content": src, "file_type": "mmd"}).json()
    got = ai_client.get(f"/documents/{made['id']}/export.md")
    assert got.status_code == 200 and got.content == src.encode("utf-8")
    assert ".mmd" in got.headers["content-disposition"]


def test_the_mmd_download_is_the_stored_text():
    # The shelf's Download .mmd goes through the export route, which returns the row's content unchanged.
    assert "downloadFromApi(`/documents/${item.id}/export.md`" in LIBRARY


def test_the_library_rows_load_the_bundle_that_defines_diagram_model_first():
    # diagram-embed.js assigns diagramModel.embed; on a fresh boot only the library bundle defines diagramModel.
    row = LIBRARY[LIBRARY.index("Save as SVG") : LIBRARY.index("Show in graph")]
    assert row.index('ensureModule("library")') < row.index('ensureModule("diagramEmbed")')
    assert "diagramModel" in (JS / "documents-mermaid.js").read_text(encoding="utf-8")
