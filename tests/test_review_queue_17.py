"""WORLD_CLASS_PLAN row 11, section 17's first row: the review queue.

The original vision: "confidence on every filing, low ones flagged for
review". The card already flags a filing under `REVIEW_THRESHOLD` ("check
this"); the queue is those notes and every note the janitor left in
Uncategorised, until a person decides: Accept keeps the filing and takes the
note out, Refile moves it (a move is a decision already), Split extracts it
into notes. The dashboard's Categories widget says how many wait."""

from __future__ import annotations

from pathlib import Path

from tessellate.core.database import Entry

ROOT = Path(__file__).resolve().parents[1]


def _note(client, session, text: str, *, category: str = "Work", confidence: int = 0, user_filed: bool = False) -> int:
    made = client.post("/entries", json={"content": text, "category": category}).json()
    entry = session.get(Entry, made["id"])
    entry.ai_confidence = confidence
    entry.user_filed = user_filed
    session.commit()
    return made["id"]


def _count(client) -> int:
    return client.get("/insights/stats").json()["to_review"]


def test_low_confidence_and_uncategorised_wait_for_review(client, session):
    before = _count(client)
    _note(client, session, "unsure filing", confidence=31)
    _note(client, session, "sure filing", confidence=92)
    _note(client, session, "left in the tray", category="Uncategorised")
    _note(client, session, "the person filed this", confidence=20, user_filed=True)
    assert _count(client) - before == 2


def test_accept_takes_a_note_out_of_the_queue_and_undo_puts_it_back(client, session):
    note = _note(client, session, "a guess worth checking", confidence=40)
    before = _count(client)
    accepted = client.post(f"/entries/{note}/filing", json={"accepted": True})
    assert accepted.status_code == 200
    assert accepted.json()["user_filed"] is True
    assert _count(client) == before - 1
    undone = client.post(f"/entries/{note}/filing", json={"accepted": False})
    assert undone.json()["user_filed"] is False
    assert _count(client) == before


def test_accept_on_a_missing_note_is_a_404(client):
    assert client.post("/entries/999999/filing", json={"accepted": True}).status_code == 404


def test_the_notes_filter_has_is_review():
    notes = (ROOT / "frontend" / "js" / "notes-list.js").read_text(encoding="utf-8")
    assert 'flag === "review"' in notes
    app = notes
    # One rule for "needs a look", read by the card's chip and the filter.
    assert "function entryNeedsReview(" in app
    cards = ((ROOT / "frontend" / "js" / "note-cards.js").read_text(encoding="utf-8") + (ROOT / "frontend" / "js" / "entry-card.js").read_text(encoding="utf-8"))
    assert "entryNeedsReview(entry)" in cards


def test_a_card_in_the_queue_offers_accept_refile_and_split():
    cards = ((ROOT / "frontend" / "js" / "note-cards.js").read_text(encoding="utf-8") + (ROOT / "frontend" / "js" / "entry-card.js").read_text(encoding="utf-8"))
    block = cards.split("function noteReviewActions", 1)[1].split("\n}\n", 1)[0]
    for label in ("ph:check Accept", "ph:folder-open Refile", "ph:scissors Split"):
        assert label in block
    assert "/filing" in block and "toastAction(" in block


def test_the_dashboard_says_how_many_wait():
    dash = (ROOT / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")
    widget = dash.split("async function renderCategoriesWidget", 1)[1].split("\n}\n", 1)[0]
    assert "to_review" in widget and 'showNotesFilter("is:review")' in widget
