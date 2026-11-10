"""W18 Q26, "Export in the head" (s9b-1110): a diagram's page head carries its own Export button.

The head row (Picture, List, Source) gets a labelled `kebabMenu` opener built by the lazy diagram-embed.js, so the
boot scripts gain only an id in the type toggle. The rows press the same `embed.out` the toolbar's ... menu uses.
The browser measure (rects at 1440 and 390) is in docs/roadmap/HISTORY.md.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
EMBED = (JS / "diagram-embed.js").read_text(encoding="utf-8")
BUILDER = (JS / "diagram-builder.js").read_text(encoding="utf-8")
DOCUMENTS = (JS / "documents.js").read_text(encoding="utf-8")


def test_the_head_export_is_made_by_the_lazy_embed_file() -> None:
    assert "function headExport" in EMBED
    assert 'id = "doc-diagram-export"' in EMBED
    assert "headExport }" in EMBED or "headExport," in EMBED
    # A labelled opener, not a bare dots glyph: the word is the point of the button.
    assert "ph:export Export" in EMBED


def test_the_head_export_rows_are_the_toolbars_exports() -> None:
    body = EMBED[EMBED.index("function headExport") :]
    body = body[: body.index("\n  }\n")]
    for how in ("png", "svg", "picture", "mermaid", "svgtext"):
        assert f'"{how}"' in body, how
    assert "embed.out" in body or "out(" in body


def test_a_document_diagram_asks_for_it_and_a_dialog_does_not() -> None:
    show = BUILDER[BUILDER.index("async function show") :]
    assert "headExport" in show
    assert "io.key" in show[show.index("headExport") - 200 : show.index("headExport") + 60]


def test_the_head_export_hides_with_the_other_diagram_only_controls() -> None:
    assert 'document.querySelector(".doc-diagram-export")?.classList.toggle("hidden", type.ext !== "mmd")' in DOCUMENTS
    assert 'classList.add("doc-diagram-export")' in EMBED
