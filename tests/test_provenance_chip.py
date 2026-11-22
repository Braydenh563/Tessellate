"""L-general-13: a note row says where the note came from, when that is known.

The server names it (`source_kind`, `source_label`: tests/test_note_provenance.py);
the card draws one chip from those, with an icon per kind, and a clipped page's
chip still opens the page. A note typed by hand has no kind and no chip.
(The card once drew two chips from `source_url` and `source_path` alone, when
extracted and transcribed notes were not recorded; the kind replaced them.)"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD = (ROOT / "frontend" / "js" / "entry-card.js").read_text(encoding="utf-8")


def _block() -> str:
    start = CARD.index("if (entry.source_kind && entry.source_label) {")
    return CARD[start : CARD.index("meta.insertBefore(provenance, date);", start)]


def test_one_chip_per_kind_and_none_for_a_typed_note() -> None:
    body = _block()
    for kind in ("url", "document", "file", "audio"):
        assert f"{kind}:" in body, kind
    assert "provenance.dataset.sourceKind = entry.source_kind;" in body
    assert "provenanceChip(" not in CARD  # the two-chip path is gone


def test_a_clipped_page_still_opens_its_source() -> None:
    body = _block()
    assert 'entry.source_kind === "url" && entry.source_url' in body
    assert 'window.open(safeHref(entry.source_url), "_blank", "noopener,noreferrer")' in body
