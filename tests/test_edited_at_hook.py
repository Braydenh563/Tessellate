"""`Entry.edited_at` is stamped in one `before_flush` hook (L570): any write to
a saved note's text moves it (an AI-tool edit, a merge), and nothing else
does (an import of a new note, an open's access_count bump, a pin, a privacy
toggle). `lexical_filing` keys its changed-since read on it."""

from __future__ import annotations

from tessellate.ai import lexical_filing
from tessellate.core.database import Entry
from tessellate.entry import app_import


def _made(client, text="a note about gardens"):
    return client.post("/entries", json={"content": text, "category": "General"}).json()["id"]


def test_a_text_write_outside_the_edit_routes_stamps_it(client, session):
    entry_id = _made(client)
    entry = session.get(Entry, entry_id)
    assert entry.edited_at is None
    entry.content = "an AI tool rewrote this note"
    session.commit()
    session.refresh(entry)
    assert entry.edited_at is not None


def test_a_merge_stamps_the_kept_note(client, session):
    keeper, other = _made(client, "tomato plants need sun"), _made(client, "tomato plants need sun and water")
    reply = client.post("/duplicates/merge", json={"ids": [keeper, other], "use_ai": False})
    assert reply.status_code == 200, reply.text
    session.expire_all()
    assert session.get(Entry, keeper).edited_at is not None


def test_an_import_of_new_notes_leaves_them_never_edited(client, session):
    note = app_import.Imported(key="a.md", title="Imported", body="from a vault")
    out = app_import.write(session, "obsidian", [note])
    session.commit()
    assert out["imported"] == 1
    assert [e.edited_at for e in session.query(Entry).all()] == [None]


def test_an_open_a_pin_and_a_privacy_toggle_do_not_stamp_it(client, session):
    entry_id = _made(client)
    entry = session.get(Entry, entry_id)
    entry.access_count = (entry.access_count or 0) + 1
    session.commit()
    assert session.get(Entry, entry_id).edited_at is None
    client.get(f"/entries/{entry_id}")
    client.put(f"/entries/{entry_id}", json={"pinned": True})
    session.expire_all()
    assert session.get(Entry, entry_id).edited_at is None


def test_the_lexical_corpus_follows_the_stamp(client, session):
    entry_id = _made(client, "zebra crossing")
    corpus = lexical_filing._corpus_for(session)
    assert entry_id in corpus.docs
    entry = session.get(Entry, entry_id)
    entry.content = "quokka habitat"
    session.commit()
    lexical_filing._corpus.full_at = lexical_filing.time.monotonic()  # no full refresh: the stamp alone must show it
    corpus = lexical_filing._corpus_for(session)
    assert "quokka" in " ".join(corpus.docs[entry_id].words)
