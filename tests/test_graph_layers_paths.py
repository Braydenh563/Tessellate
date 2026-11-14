"""Document and entity nodes in centrality and the trace path (owner, 2026-11-12)."""

from __future__ import annotations

from tessellate.api import routes_graph
from tessellate.core.database import Entity, EntityMention, Entry


def _note(client, text):
    response = client.post("/entries", json={"content": text})
    assert response.status_code == 201
    return response.json()


def _document(client, title, *notes):
    doc = client.post("/documents", json={"title": title, "content": ""}).json()
    for note in notes:
        attached = client.post(f"/documents/{doc['id']}/notes", json={"entry_id": note["id"]})
        assert attached.status_code < 300
    return doc


def _centrality(client, flags=""):
    nodes = client.get(f"/graph?{flags}").json()["nodes"]
    return {n["id"]: n["centrality"] for n in nodes}


def test_a_trace_runs_through_a_document_both_notes_are_attached_to(client):
    a, b = _note(client, "alpha note"), _note(client, "beta note")
    doc = _document(client, "Shared plan", a, b)
    key = f"document:{doc['id']}"

    off = client.get("/graph/path", params={"source": a["id"], "target": b["id"]}).json()
    assert off["found"] is False

    body = client.get("/graph/path", params={"source": a["id"], "target": b["id"], "documents": "true"}).json()
    assert body["found"] is True and body["hops"] == 2
    assert [n["id"] for n in body["nodes"]] == [a["id"], key, b["id"]]
    assert body["nodes"][1]["preview"] == "Shared plan" and body["nodes"][1]["type"] == "document"
    assert [s["kind"] for s in body["steps"]] == ["document", "document"]


def test_a_path_can_start_at_a_document_and_a_bad_id_is_refused(client):
    a = _note(client, "alpha note")
    doc = _document(client, "Plan", a)
    got = client.get("/graph/path", params={"source": f"document:{doc['id']}", "target": a["id"], "documents": "true"}).json()
    assert got["found"] is True and got["hops"] == 1
    refused = client.get("/graph/path", params={"source": "x:1", "target": a["id"]})
    assert refused.status_code == 422
    # Layer off: the prefixed id is simply not in the map.
    missing = client.get("/graph/path", params={"source": f"document:{doc['id']}", "target": a["id"]}).json()
    assert missing["found"] is False


def test_a_trace_runs_through_an_entity_both_notes_name(client, session):
    a, b = _note(client, "alpha note"), _note(client, "beta note")
    entity = Entity(name="Priya", kind="person")
    session.add(entity)
    session.flush()
    session.add_all([EntityMention(entity_id=entity.id, entry_id=a["id"]), EntityMention(entity_id=entity.id, entry_id=b["id"])])
    session.commit()
    params = {"source": a["id"], "target": b["id"]}
    assert client.get("/graph/path", params=params).json()["found"] is False
    body = client.get("/graph/path", params={**params, "entities": "true"}).json()
    assert [n["id"] for n in body["nodes"]] == [a["id"], f"entity:{entity.id}", b["id"]]
    assert body["nodes"][1]["preview"] == "Priya"


def test_a_linked_document_has_centrality_and_lends_it_to_its_notes(client):
    a, b = _note(client, "alpha note"), _note(client, "beta note")
    doc = _document(client, "Shared plan", a, b)
    key = f"document:{doc['id']}"
    before = _centrality(client, "include_documents=true")
    assert before[key] > 0
    # The notes' own rank is the notes-only graph's unless the layer is asked for.
    plain = _centrality(client)
    assert plain[a["id"]] == plain[b["id"]]
    assert before[a["id"]] != plain[a["id"]]


def test_a_lone_document_has_zero_centrality_and_the_cache_follows_attachments(client):
    a = _note(client, "alpha note")
    doc = _document(client, "Plan")
    key = f"document:{doc['id']}"
    assert _centrality(client, "include_documents=true")[key] == 0
    client.post(f"/documents/{doc['id']}/notes", json={"entry_id": a["id"]})
    assert _centrality(client, "include_documents=true")[key] > 0


def test_similarity_still_works_with_documents_present(client):
    a, b = _note(client, "alpha note"), _note(client, "beta note")
    _document(client, "Plan", a, b)
    body = client.get("/graph?similarity=true&include_documents=true")
    assert body.status_code == 200
    assert all(isinstance(e["source"], int) for e in body.json()["edges"] if e["kind"] == "similar")


def test_entity_centrality_joins_when_asked(client, session):
    a, b = _note(client, "alpha note"), _note(client, "beta note")
    entity = Entity(name="Priya", kind="person")
    session.add(entity)
    session.flush()
    session.add_all([EntityMention(entity_id=entity.id, entry_id=a["id"]), EntityMention(entity_id=entity.id, entry_id=b["id"])])
    session.commit()
    assert _centrality(client, "include_entities=true")[f"entity:{entity.id}"] > 0


def test_a_document_never_routes_to_a_private_note_for_the_ai(client, session):
    """The AI's index (include_private=False) drops the edge to a private note,
    so a document cannot be the way round that rule."""
    from tessellate.entry import paths

    a, secret = _note(client, "open note"), _note(client, "my private thought")
    doc = _document(client, "Plan", a, secret)
    session.get(Entry, secret["id"]).is_private = True
    session.commit()
    routes_graph.reset_graph_cache()
    index = paths.build(session, include_private=False, documents=True, entities=True)
    key = f"document:{doc['id']}"
    assert secret["id"] not in index.entries
    assert set(index.neighbours(key)) <= {a["id"]}
    assert paths.find(index, a["id"], secret["id"]) is None
    assert all(not isinstance(n, int) or n != secret["id"] for n in index.nodes())


def test_a_locked_private_note_on_a_route_through_a_document_shows_no_text(client, session):
    from tessellate.core import vault

    vault.close()
    vault.create(session, "test-passphrase")
    session.commit()
    try:
        a = _note(client, "open note")
        secret = _note(client, "the spare key is under the mat")
        doc = _document(client, "Plan", a, secret)
        made = client.post(f"/entries/{secret['id']}/privacy", json={"private": True})
        assert made.status_code == 200
        vault.close()
        body = client.get("/graph/path", params={"source": a["id"], "target": secret["id"], "documents": "true"}).json()
        assert body["found"] is True
        assert "spare key" not in str(body)
        assert body["nodes"][1]["id"] == f"document:{doc['id']}"
    finally:
        vault.close()


def test_a_private_note_lends_no_entity_to_a_route_with_the_vault_locked(client, session):
    """Review 5883476033 (1): an entity is a name read out of a note's text,
    so a private note's mentions stay off the route, and an entity only a
    private note names is no node at all."""
    from tessellate.core import vault

    vault.close()
    vault.create(session, "test-passphrase")
    session.commit()
    try:
        a = _note(client, "open note")
        secret = _note(client, "meeting Marguerite about the loan")
        made = client.post(f"/entries/{secret['id']}/privacy", json={"private": True})
        assert made.status_code == 200
        shared = Entity(name="Priya", kind="person")
        hidden = Entity(name="Marguerite", kind="person")
        session.add_all([shared, hidden])
        session.flush()
        session.add_all([
            EntityMention(entity_id=shared.id, entry_id=a["id"]),
            EntityMention(entity_id=shared.id, entry_id=secret["id"]),
            EntityMention(entity_id=hidden.id, entry_id=secret["id"]),
        ])
        session.commit()
        vault.close()
        routes_graph.reset_graph_cache()
        body = client.get("/graph/path", params={"source": a["id"], "target": secret["id"], "entities": "true"}).json()
        assert body["found"] is False
        assert "Marguerite" not in str(body)

        from tessellate.entry import paths

        index = paths.build(session, entities=True)
        assert f"entity:{hidden.id}" not in index.nodes()
        assert set(index.neighbours(f"entity:{shared.id}")) == {a["id"]}
    finally:
        vault.close()


def test_a_private_document_is_never_a_stop_on_a_route(client, session):
    """Review 5883476033 (2): the same rule as `_layer_members`, for every caller."""
    from tessellate.core.database import Document
    from tessellate.entry import paths

    a, b = _note(client, "alpha note"), _note(client, "beta note")
    doc = _document(client, "Secret plan", a, b)
    session.get(Document, doc["id"]).is_private = True
    session.commit()
    routes_graph.reset_graph_cache()
    index = paths.build(session, documents=True)
    assert f"document:{doc['id']}" not in index.nodes()
    body = client.get("/graph/path", params={"source": a["id"], "target": b["id"], "documents": "true"}).json()
    assert body["found"] is False and "Secret plan" not in str(body)
