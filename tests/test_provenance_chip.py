"""L-general-13: a note row says where the note came from, when that is known.

Recorded today: `Entry.source_url` (a clipped page) and `Entry.source_path`
(an imported file). Not recorded on the note: "extracted from a document" (the
document link is a general attachment, not a provenance) and "transcribed from
audio" (the transcript is composed into the note text by the page), so there is
no chip for those two and none is guessed."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARD = (ROOT / "frontend" / "js" / "entry-card.js").read_text(encoding="utf-8")


def _chip_body() -> str:
    start = CARD.index("function provenanceChip(")
    return CARD[start : CARD.index("const clipChip", start)]


def test_a_clipped_and_an_imported_note_wear_a_provenance_chip_with_the_kind_in_words():
    body = _chip_body()
    assert "Clipped from URL" in body and "Imported from file" in body
    assert "found.dataset.provenance = kind;" in body
    assert 'found.setAttribute("aria-label", said);' in body


def test_the_card_draws_it_only_from_a_recorded_source():
    assert 'provenanceChip(entry, "url")' in CARD and 'provenanceChip(entry, "file")' in CARD
    assert 'if (kind === "url" ? !entry.source_url : !entry.source_path) return null;' in _chip_body()
    # The two unrecorded kinds are not drawn from a guess.
    assert "transcribed" not in _chip_body().lower() and "extracted" not in _chip_body().replace("Extracted from a document", "").lower()


def test_the_api_sends_both_recorded_sources(client):
    made = client.post(
        "/entries", json={"content": "A page", "source_url": "https://example.com/a", "source_title": "Example"}
    ).json()
    got = client.get(f"/entries/{made['id']}").json()
    assert got["source_url"] == "https://example.com/a" and got["source_path"] == ""


def test_help_says_where_the_chip_is():
    text = (ROOT / "src" / "tessellate" / "ai" / "help_topics_more.py").read_text(encoding="utf-8")
    assert "Clipped from URL or Imported from file" in text
