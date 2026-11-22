"""Highlights as a queryable collection (BACKLOG 109.4): `has:highlight` in the
search operators and a Highlights kind in the Library. The marks are
`==words==` in the text, so there is no table to read."""

from __future__ import annotations

import re

from tests._app_js import documents_text

from tessellate.entry import highlights, manager
from tessellate.search import engine


def _note(session, content, **flags):
    entry = manager.create_entry(session, content)
    for key, value in flags.items():
        setattr(entry, key, value)
    session.commit()
    return entry


def _hit_ids(session, q):
    return {(hit.kind, hit.ref_id) for hit in engine.search(session, q, ctx=None, hybrid=False)}


def test_passages_reads_both_spellings_and_ignores_lookalikes():
    text = "a ==yellow one== and ==red|with a colour== then a == b == c and ===== and ==a|b=="
    assert highlights.passages(text) == ["yellow one", "with a colour", "a|b"]
    assert highlights.has_highlight("x ==y== z")
    assert not highlights.has_highlight("if a == b then c == d")
    assert not highlights.has_highlight("")
    assert not highlights.has_highlight(None)


def test_has_highlight_filters_a_search(session):
    marked = _note(session, "harbour walk, ==the pier was lovely==")
    coloured = _note(session, "harbour notes ==green|low tide at six==")
    plain = _note(session, "harbour walk, nothing marked, if a == b")
    found = _hit_ids(session, "has:highlight harbour")
    assert ("note", marked.id) in found
    assert ("note", coloured.id) in found
    assert ("note", plain.id) not in found


def test_has_highlight_alone_lists_the_notes_that_have_one(session):
    marked = _note(session, "something ==worth keeping== here")
    plain = _note(session, "something plain here")
    found = _hit_ids(session, "has:highlight")
    assert ("note", marked.id) in found
    assert ("note", plain.id) not in found


def test_the_library_lists_each_passage_with_its_note(client):
    one = client.post("/entries", json={"content": "# Harbour\nthe ==pier was lovely== and ==red|tide at six=="}).json()
    client.post("/entries", json={"content": "no marks here, a == b"})
    items = [i for i in client.get("/library").json()["items"] if i["kind"] == "highlight"]
    assert [i["title"] for i in items] == ["pier was lovely", "tide at six"]
    assert {i["entry_id"] for i in items} == {one["id"]}
    assert all(i["detail"] == "in Harbour" for i in items)
    counts = client.get("/library").json()["counts"]
    assert counts["highlight"] == 2


def test_the_library_search_narrows_passages(client):
    client.post("/entries", json={"content": "==alpha passage== and ==beta passage=="})
    items = [i for i in client.get("/library", params={"q": "beta"}).json()["items"] if i["kind"] == "highlight"]
    assert [i["title"] for i in items] == ["beta passage"]


def test_private_binned_and_draft_notes_give_no_passages(client, session):
    _note(session, "a ==private mark==", is_private=True)
    _note(session, "a ==binned mark==", is_deleted=True)
    _note(session, "a ==draft mark==", is_draft=True)
    items = [i for i in client.get("/library").json()["items"] if i["kind"] == "highlight"]
    assert items == []


def test_the_colour_words_are_the_toolbars():
    """The same list the editors write: a colour the toolbar adds must be one
    this reader strips, or a passage would start with its own colour name."""
    source = documents_text()
    match = re.search(r"const MD_COLOURS = \[(.*?)\];", source, re.S)
    assert match, "MD_COLOURS not found: has the toolbar moved?"
    assert tuple(re.findall(r'"([a-z]+)"', match.group(1))) == highlights.COLOURS
