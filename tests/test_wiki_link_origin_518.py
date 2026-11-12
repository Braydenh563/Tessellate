"""GRAPH_PLAN 518, from the backend audit (INBOX 517).

(1) A wiki link remembers it came from a `[[name]]` (`EntryLink.origin`), so
taking the name out of the text takes the link away, and renaming a note
offers to rewrite `[[Old]]` in the notes that name it. (2) `/graph` does not
re-read every note's text on every call. (3) The cache fingerprint sees a
link removed and another added. (4) Similarity keeps each note's closest
matches without collecting every pair above the cutoff."""

from __future__ import annotations

import numpy as np
from sqlalchemy import select

from tessellate.ai.embeddings import similar_pairs
from tessellate.core.database import EntryLink


def _save(client, content):
    response = client.post("/entries", json={"content": content})
    assert response.status_code == 201, response.text
    return response.json()


def _put(client, entry, content):
    response = client.put(f"/entries/{entry['id']}", json={"content": content})
    assert response.status_code == 200, response.text
    return response.json()


def _links(session):
    session.expire_all()
    return {(row.source_entry_id, row.target_entry_id): row.origin for row in session.scalars(select(EntryLink))}


def test_a_wiki_link_is_marked_and_a_manual_one_is_not(client, session):
    target = _save(client, "# Target note\n\nbody")
    other = _save(client, "# Other note")
    holder = _save(client, "# Holder\n\nsee [[Target note]]")
    client.post(f"/entries/{holder['id']}/links", json={"target_id": other["id"]})
    assert _links(session) == {(holder["id"], target["id"]): "wiki", (holder["id"], other["id"]): None}


def test_taking_the_name_out_takes_the_wiki_link_and_keeps_a_manual_one(client, session):
    target = _save(client, "# Target note\n\nbody")
    other = _save(client, "# Other note")
    holder = _save(client, "# Holder\n\nsee [[Target note]] and [[Other note]]")
    # A link made by hand before the name was written is the person's: it stays.
    manual = _save(client, "# Manual\n\nnothing yet")
    client.post(f"/entries/{manual['id']}/links", json={"target_id": target["id"]})
    _put(client, manual, "# Manual\n\nnow [[Target note]]")
    _put(client, holder, "# Holder\n\nsee [[Other note]] only")
    _put(client, manual, "# Manual\n\nthe name is gone")
    links = _links(session)
    assert (holder["id"], target["id"]) not in links
    assert links[(holder["id"], other["id"])] == "wiki"
    assert links[(manual["id"], target["id"])] is None


def test_a_rename_offers_to_rewrite_the_names_and_does_it(client, session):
    target = _save(client, "# Old name\n\nbody")
    holder = _save(client, "# Holder\n\nsee [[Old name]], [[old name|that one]] and [[Old name#Part]]")
    untouched = _save(client, "# Elsewhere\n\nno mention")
    renamed = _put(client, target, "# New name\n\nbody")
    assert renamed["wiki_rename"] == {"old": "Old name", "new": "New name", "notes": 1}
    response = client.post(f"/entries/{target['id']}/wiki-rename", json={"old": "Old name"})
    assert response.status_code == 200, response.text
    assert response.json()["rewritten"] == 1
    text = client.get(f"/entries/{holder['id']}").json()["content"]
    assert text == "# Holder\n\nsee [[New name]], [[New name|that one]] and [[New name#Part]]"
    assert client.get(f"/entries/{untouched['id']}").json()["content"] == "# Elsewhere\n\nno mention"
    assert _links(session)[(holder["id"], target["id"])] == "wiki"


def test_an_edit_that_keeps_the_name_offers_nothing(client):
    target = _save(client, "# Same name\n\nbody")
    _save(client, "# Holder\n\nsee [[Same name]]")
    assert _put(client, target, "# Same name\n\nnew body").get("wiki_rename") is None


def test_the_fingerprint_sees_a_link_swapped_for_another(client, session):
    from tessellate.api.routes_graph import _graph_fingerprint

    a, b, c = (_save(client, f"note {i}") for i in range(3))
    first = client.post(f"/entries/{a['id']}/links", json={"target_id": b["id"]}).json()
    before = _graph_fingerprint(session)
    client.delete(f"/entries/{a['id']}/links/{first['links'][0]['link_id']}")
    client.post(f"/entries/{a['id']}/links", json={"target_id": c["id"]})
    session.expire_all()
    assert _graph_fingerprint(session) != before


def test_graph_reads_each_notes_text_once_per_version(client, monkeypatch):
    from tessellate.api import routes_graph
    from tessellate.entry import manager_text

    notes = [_save(client, f"# Note {i}\n\nwords here") for i in range(5)]
    reads = []
    original = manager_text.readable_content
    monkeypatch.setattr(routes_graph.manager_text, "readable_content", lambda e: reads.append(e.id) or original(e))
    client.get("/graph")
    assert len(reads) == 5
    client.get("/graph")
    assert len(reads) == 5, "the second call re-read every note"
    _put(client, notes[0], "# Note 0 changed\n\nnew words")
    reads.clear()
    body = client.get("/graph").json()
    assert reads == [notes[0]["id"]]
    assert next(n for n in body["nodes"] if n["id"] == notes[0]["id"])["preview"] == "Note 0 changed"


def test_similarity_per_node_keeps_each_notes_closest_matches():
    rng = np.random.default_rng(7)
    vectors = {i: rng.normal(size=16).astype("float32") for i in range(60)}
    pairs = similar_pairs(vectors, 0.0, per_node=2)
    unit = {i: v / np.linalg.norm(v) for i, v in vectors.items()}
    wanted = set()
    for i in unit:
        ranked = sorted((j for j in unit if j != i), key=lambda j: -float(unit[i] @ unit[j]))
        for j in ranked[:2]:
            if float(unit[i] @ unit[j]) >= 0.0:
                wanted.add(frozenset((i, j)))
    assert {frozenset((a, b)) for a, b, _ in pairs} == wanted
    assert all(a < b for a, b, _ in pairs)
    assert [s for _, _, s in pairs] == sorted((s for _, _, s in pairs), reverse=True)
    # Without per_node, every pair above the cutoff, as before.
    assert len(similar_pairs(vectors, -1.0)) == 60 * 59 // 2


def test_a_rename_of_the_names_is_undone_through_the_versions_it_names(client):
    """INBOX 898: the answer lists each note changed with the version it held
    before, and restoring that version is Undo; the same POST again is Redo."""
    target = _save(client, "# Old name\n\nbody")
    holder = _save(client, "# Holder\n\nsee [[Old name]]")
    original = client.get(f"/entries/{holder['id']}").json()["content"]
    _put(client, target, "# New name\n\nbody")
    done = client.post(f"/entries/{target['id']}/wiki-rename", json={"old": "Old name"}).json()
    (note,) = done["notes"]
    assert note["id"] == holder["id"]

    back = client.post(f"/entries/{note['id']}/history/{note['revision_id']}/restore")
    assert back.status_code == 200, back.text
    assert client.get(f"/entries/{holder['id']}").json()["content"] == original

    again = client.post(f"/entries/{target['id']}/wiki-rename", json={"old": "Old name"}).json()
    assert again["rewritten"] == 1
    assert "[[New name]]" in client.get(f"/entries/{holder['id']}").json()["content"]
