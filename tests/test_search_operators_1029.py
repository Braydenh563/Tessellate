"""Search operators answer in SQL, before the limit, and say what they did not
understand (audit 1029 N2, N3, N4, N5, N16).

Every case is a row in a table, so a new operator or alias is one more row and
the class (an operator is a filter on the index, never a trim of its top rows)
is held rather than one query.
"""

from __future__ import annotations

import pytest

from tessellate.entry import manager
from tessellate.search import engine
from tessellate.search import query as query_understanding


def _search(client, q: str, **params) -> dict:
    reply = client.get("/search", params={"q": q, "limit": 50, **params})
    assert reply.status_code == 200, reply.text
    return reply.json()


def _note_ids(body: dict) -> set[int]:
    return {hit["id"] for hit in body["hits"] if hit["kind"] == "note"}


def _make(client, content: str, **patch) -> int:
    made = client.post("/entries", json={"content": content})
    assert made.status_code == 201, made.text
    entry_id = made.json()["id"]
    if patch:
        updated = client.put(f"/entries/{entry_id}", json={"content": content, **patch})
        assert updated.status_code == 200
    return entry_id


@pytest.mark.parametrize("filter_word", ["is:pinned", "is:favourite", "is:favorite", "is:starred"])
def test_a_flag_filter_is_applied_before_the_depth_limit(session, filter_word):
    """The pinned note is the oldest of five; the engine reads three rows."""
    old = manager.create_entry(session, "Oldest pinned note")
    old.pinned = True
    session.commit()
    for n in range(4):
        manager.create_entry(session, f"Newer plain note {n}")
    hits = engine.search(session, filter_word, kinds=["note"], depth=3, hybrid=False)
    assert [hit.ref_id for hit in hits] == [old.id]


def test_a_flag_filter_with_words_is_applied_before_the_depth_limit(session):
    pinned = manager.create_entry(session, "garden pinned once")
    pinned.pinned = True
    session.commit()
    for n in range(6):
        manager.create_entry(session, f"garden garden garden note {n}")
    hits = engine.search(session, "garden is:pinned", kinds=["note"], depth=2, hybrid=False)
    assert [hit.ref_id for hit in hits] == [pinned.id]


def test_a_binned_note_is_left_out_unless_asked_and_marked_when_shown(client):
    kept = _make(client, "Zorbleflux kept note")
    binned = _make(client, "Zorbleflux binned note")
    binned_reply = client.delete(f"/entries/{binned}")
    assert binned_reply.status_code in (200, 204)
    assert _note_ids(_search(client, "Zorbleflux")) == {kept}
    asked = _search(client, "Zorbleflux is:deleted")
    assert _note_ids(asked) == {binned}
    assert asked["hits"][0]["explain"][0] == "in the bin"
    assert _note_ids(_search(client, "is:bin")) == {binned}


def test_a_binned_note_is_not_listed_by_a_filter_alone(client):
    binned = _make(client, "Gone for good", pinned=True)
    binned_reply = client.delete(f"/entries/{binned}")
    assert binned_reply.status_code in (200, 204)
    assert binned not in _note_ids(_search(client, "is:pinned"))


@pytest.mark.parametrize(
    ("query", "expected_titles"),
    [
        ("title:Friday", {"Friday plans"}),
        ("title:friday", {"Friday plans"}),
        ("title:Lisbon", {"Lisbon trip"}),
        ("title:Lisbon trip", {"Lisbon trip"}),
        ("title:Nonesuch", set()),
    ],
)
def test_title_searches_the_title_only(client, query, expected_titles):
    """The decoy says the word in its body and in no title."""
    _make(client, "# Friday plans\n\nPack the car")
    _make(client, "# Lisbon trip\n\nFlights booked")
    _make(client, "# Weekly notes\n\nOn Friday we flew to Lisbon and wrote about the title")
    found = {hit["title"].lstrip("# ").strip() for hit in _search(client, query)["hits"] if hit["kind"] == "note"}
    assert found == expected_titles


def test_a_title_with_no_match_says_so(client):
    _make(client, "# Weekly notes\n\nFriday")
    body = _search(client, "title:Friday")
    assert body["hits"] == []
    assert any("No title says" in notice for notice in body["notices"])


@pytest.mark.parametrize("query", ["4471", "9999", "20260", "3.14"])
def test_a_number_is_matched_as_typed(client, query):
    """Neither a longer number it begins nor a nearby word is the number."""
    _make(client, "Invoice 44710 and 447 and 99990 and 202601 were filed")
    _make(client, "Receipt for a plain purchase")
    assert _note_ids(_search(client, query, hybrid="false")) == set()


def test_a_number_still_finds_the_note_that_holds_it(client):
    holder = _make(client, "Invoice 4471 was filed")
    _make(client, "Invoice 44710 was filed")
    assert _note_ids(_search(client, "4471", hybrid="false")) == {holder}


@pytest.mark.parametrize(
    ("query", "words"),
    [
        ("has:attachments", {"file"}),
        ("has:attachment", {"file"}),
        ("has:picture", {"image"}),
        ("is:favourite", {"pinned"}),
        ("is:binned", {"deleted"}),
    ],
)
def test_the_names_the_app_uses_are_aliases(query, words):
    asked = query_understanding.understand(query)
    assert set(asked.filters["is"] + asked.filters["has"]) == words
    assert asked.notices == []


@pytest.mark.parametrize(
    ("query", "fragment"),
    [
        ("has:nothing", "No filter called has:nothing"),
        ("is:private", "No filter called is:private"),
        ("is:pinnd", "Did you mean is:pinned?"),
        ("has:imag", "Did you mean has:image?"),
        ("colour:red", "No filter called colour:"),
        ("garden rating:5", "No filter called rating:"),
    ],
)
def test_an_unknown_filter_is_reported(query, fragment):
    asked = query_understanding.understand(query)
    assert any(fragment in notice for notice in asked.notices), asked.notices


@pytest.mark.parametrize(
    "query",
    ["meet at 10:30", "see https://example.com/a", "mailto:me@example.com", "tag:work", "is:pinned", "Re: plan", "note: later"],
)
def test_ordinary_text_and_real_filters_raise_no_notice(query):
    assert query_understanding.understand(query).notices == []


def test_the_route_carries_the_notices(client):
    _make(client, "Something about a file")
    unknown = _search(client, "has:zzz")
    plain = _search(client, "file")
    assert unknown["notices"][0].startswith("No filter called has:zzz")
    assert plain["notices"] == []
