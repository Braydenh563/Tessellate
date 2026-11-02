"""A private note's kept tag suggestions travel exactly like its tags.

Decision (2026-10-04): `Entry.suggested_tags` and `Entry.discarded_tags` are
handled the way `tags` are for a private note. Tags stay readable while the
vault is open, and hidden everywhere while it is locked (INBOX 1437, which
replaced the 2026-10-04 "tags stay readable" line), so a suggestion may be
shown wherever the tags are, and must be shown nowhere the tags are not. The check is a comparison, not a list of places: a surface that
hides the tags (search, the graph, the model's context, a locked export) hides
the suggestions, and a surface that never carried a suggestion at all (every
one but the note itself) stays that way.
"""

from __future__ import annotations

import json

import pytest

from tessellate.core import vault
from tessellate.core.database import Entry

TAG, SUGGESTED, DISCARDED = "zq-tagword", "zq-suggestedword", "zq-discardedword"


@pytest.fixture(autouse=True)
def open_vault(session):
    vault.close()
    vault.create(session, "test-passphrase")
    session.commit()
    yield
    vault.close()


def _private_note(client, session, content="a private thought"):
    note = client.post("/entries", json={"content": content, "tags": [TAG]}).json()
    assert client.post(f"/entries/{note['id']}/privacy", json={"private": True}).status_code == 200
    row = session.get(Entry, note["id"])
    row.suggested_tags = json.dumps([SUGGESTED])
    row.discarded_tags = json.dumps([DISCARDED])
    session.commit()
    return note["id"]


SURFACES = [
    "/entries", "/search?q={tag}", "/search?q={sug}", "/graph", "/timeline", "/insights",
    "/duplicates", "/tags", "/entries/link-suggestions", "/resurface", "/entries/most-accessed",
    "/ask-history", "/library/all", "/export/json", "/export/csv", "/export/markdown",
    "/entries/{id}", "/entries/{id}/references", "/entries/{id}/connections",
]


def _where(client, entry_id, *words):
    """For each word, the surfaces whose response holds it. One pass for all
    the words: opening the note bumps its access count, so a second pass
    would see surfaces (most-accessed) the first one did not."""
    found = {word: set() for word in words}
    for template in SURFACES:
        path = template.format(id=entry_id, tag=TAG, sug=SUGGESTED)
        reply = client.get(path)
        if reply.status_code != 200:
            continue
        #: A search echoes its query back; subtract what the caller put in.
        body = reply.text.replace(f'"query":"{TAG}"', "").replace(f'"query":"{SUGGESTED}"', "")
        for word in words:
            if word in body:
                found[word].add(template)
    return found


@pytest.mark.parametrize("locked", [False, True])
def test_suggestions_appear_only_where_the_tags_do(client, session, locked):
    entry_id = _private_note(client, session)
    if locked:
        vault.close()
    seen = _where(client, entry_id, TAG, SUGGESTED)
    tags_at, suggested_at = seen[TAG], seen[SUGGESTED]
    if locked:  # INBOX 1437: a locked private note's tags show nowhere
        assert tags_at == set() and suggested_at == set(), (tags_at, suggested_at)
        return
    assert tags_at, "the tag shows up nowhere: the comparison would pass for nothing"
    assert suggested_at <= tags_at, f"suggested tags leak at {sorted(suggested_at - tags_at)}"


@pytest.mark.parametrize("locked", [False, True])
def test_discarded_tags_are_never_handed_out(client, session, locked):
    entry_id = _private_note(client, session)
    if locked:
        vault.close()
    assert _where(client, entry_id, DISCARDED)[DISCARDED] == set()


def test_the_note_itself_carries_them_like_its_tags(client, session):
    entry_id = _private_note(client, session)
    body = client.get(f"/entries/{entry_id}").json()
    assert body["tags"] == [TAG] and body["suggested_tags"] == [SUGGESTED]
    vault.close()  # INBOX 1437: locked, neither shows
    body = client.get(f"/entries/{entry_id}").json()
    assert not body["tags"] and not body["suggested_tags"]


def test_answering_a_suggestion_on_a_private_note_works_like_tagging_it(client, session):
    entry_id = _private_note(client, session)
    body = client.post(
        f"/entries/{entry_id}/suggested-tags", json={"take": [SUGGESTED], "discard": []}
    ).json()
    assert SUGGESTED in body["tags"] and body["suggested_tags"] == []
    stored = session.get(Entry, entry_id)
    assert stored.is_private is True
    assert "private thought" not in stored.content


def test_the_model_and_search_never_see_them(client, session):
    from tessellate.core import deps
    from tessellate.search import search_manager

    entry_id = _private_note(client, session, "zarquon private words")
    for word in (TAG, SUGGESTED, DISCARDED, "zarquon"):
        entries, _mode = search_manager.retrieve(session, word, deps.get_embeddings(), limit=10)
        assert entry_id not in [e.id for e in entries], word


def test_filing_makes_no_suggestions_for_a_private_note(client, session):
    from tessellate.api import routes_entries

    #: A vocabulary tag the private note names, so a public note would be offered it.
    client.post("/entries", json={"content": "starter notes", "tags": ["sourdough"]})
    entry_id = _private_note(client, session, "a thought about sourdough and rye bread")
    row = session.get(Entry, entry_id)
    row.suggested_tags = "[]"
    session.commit()
    public = client.post("/entries", json={"content": "more sourdough and rye bread"}).json()
    public_row = session.get(Entry, public["id"])
    routes_entries._keep_suggestions(session, public_row, None)
    assert "sourdough" in json.loads(public_row.suggested_tags), "the probe offers nothing even to a public note"
    for locked in (False, True):
        if locked:
            vault.close()
        routes_entries._keep_suggestions(session, row, None)
        assert json.loads(row.suggested_tags) == []
