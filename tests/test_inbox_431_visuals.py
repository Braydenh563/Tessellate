"""The two small visual reports in INBOX 431, measured in Chromium.

* The Web and Plan pills in Chat, when on: the label took the on-accent
  colour and the icon kept the accent, 1.00:1 against the fill; 7.69:1 light
  and 8.01:1 dark after.
* The "Switch to nomic-embed-text" fix row sat flush on the Model backend
  box (0px); 16px after.
"""

from pathlib import Path
from tests._app_js import with_pieces

CSS = (Path(__file__).resolve().parent.parent / "frontend" / "css" / "01-forms-settings.css").read_text(encoding="utf-8")


def test_an_active_pill_draws_its_icon_in_the_label_colour():
    assert "#web-search-toggle.active i,\n#chat-plan.active i {\n  color: inherit;" in CSS


def test_the_embedding_fix_row_has_room_below():
    assert "#embedding-error-fix-row {\n  margin-block-end: var(--space-6);" in CSS


def test_the_search_engine_says_how_well_it_is_working(client):
    """INBOX 431 (3): coverage and the last search's mode, in words."""
    client.post("/entries", json={"content": "a note to count", "category": "Misc"})
    body = client.get("/models/status").json()
    assert body["embedding_coverage"]["total"] >= 1
    assert "indexed" in body["embedding_coverage"]
    client.get("/search", params={"q": "count"})
    assert isinstance(body.get("last_search"), dict)
    status_js = with_pieces("status.js")
    assert "notes searchable by meaning" in status_js and "last search used keywords only" in status_js
