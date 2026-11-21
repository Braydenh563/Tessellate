"""The Library's and the graph's search boxes on the meaning layer (L628).

Both boxes asked `GET /read/filter` for phrases that are filters and matched
every other query as one literal substring, so "notes about the harbor" found
nothing and a slip ("harbr") found nothing. The route now also says which
notes hold every word the leftover words name, with the request's own words
dropped and a slip read as a word the notebook holds (ai/meaning.py's rules).
The Settings synonym groups stay out: "dark" is a theme in Settings and only a
word in a note.
"""

from __future__ import annotations

from pathlib import Path

from tessellate.ai import filters
from tessellate.core.database import Entry

ROOT = Path(__file__).resolve().parents[1]


def _notes(session):
    harbor = Entry(content="Harbor shed\nThe boat shed plan for spring.")
    crane = Entry(content="Crane hire quote\nTwo days at the harbor wall.")
    dark = Entry(content="Night walk\nA dark evening by the river.")
    hidden = Entry(content="Harbor salary talk", is_private=True)
    board = Entry(content="Harbor board", is_board=True)
    session.add_all([harbor, crane, dark, hidden, board])
    session.commit()
    return harbor, crane, dark


def test_the_request_words_are_dropped(session):
    harbor, crane, _ = _notes(session)
    assert set(filters.by_words(session, "notes about the harbor")) == {harbor.id, crane.id}


def test_a_slip_is_read_as_a_word_the_notebook_holds(session):
    harbor, crane, _ = _notes(session)
    assert set(filters.by_words(session, "harbr")) == {harbor.id, crane.id}
    assert set(filters.by_words(session, "boat shde")) == {harbor.id}


def test_every_word_named_must_be_held_at_a_word_start(session):
    harbor, crane, _ = _notes(session)
    assert set(filters.by_words(session, "harbor crane")) == {crane.id}
    #: "plans" holds "plan" by its ending; "pla" is not a word of it.
    assert set(filters.by_words(session, "plans")) == {harbor.id}
    assert filters.by_words(session, "pla") == []


def test_settings_synonyms_do_not_reach_notes(session):
    _, _, dark = _notes(session)
    #: "theme" is in "dark"'s Settings group; a note that says "dark" is not about a theme.
    assert filters.by_words(session, "theme") == []
    assert filters.by_words(session, "dark") == [dark.id]


def test_private_notes_and_boards_stay_out_and_the_filter_narrows(session):
    harbor, crane, _ = _notes(session)
    assert set(filters.by_words(session, "harbor")) == {harbor.id, crane.id}
    assert filters.by_words(session, "harbor", among=[crane.id]) == [crane.id]
    assert filters.by_words(session, "the") == []


def test_the_route_returns_the_words_ids_beside_the_filter(client):
    token = client.post("/auth/setup", json={"password": "first-pass"}).json()["token"]
    auth = {"X-Auth-Token": token}
    made = client.post("/entries", json={"content": "Harbor shed\nThe boat shed plan."}, headers=auth)
    assert made.status_code in (200, 201), made.text
    got = client.get("/read/filter", params={"q": "notes about the harbr"}, headers=auth).json()
    assert got["ids"] is None and got["word_ids"] == [made.json()["id"]]
    assert client.get("/read/filter", params={"q": ""}, headers=auth).json()["word_ids"] is None


def test_both_boxes_match_on_the_words_ids_too():
    js = ROOT / "frontend/js"
    library = (js / "library.js").read_text(encoding="utf-8")
    graph = (js / "graph.js").read_text(encoding="utf-8")
    assert "libraryPhrase.words" in library and "got.word_ids" in library
    assert "graphPhrase.words" in graph and "got.word_ids" in graph
