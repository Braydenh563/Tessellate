"""Documents and entities join graph similarity, as derived vectors (L-graph-15, owner 2026-11-12)."""

from __future__ import annotations

import numpy as np

from tessellate.ai.embeddings import derived_pairs, vector_to_bytes
from tessellate.core import deps
from tessellate.core.database import DocumentLink, EmbeddingRecord, Entity, EntityMention, Entry


def _note(client, text):
    response = client.post("/entries", json={"content": text})
    assert response.status_code == 201
    return response.json()


def _vector(session, note, values):
    session.add(
        EmbeddingRecord(
            entry_id=note["id"],
            embedding=vector_to_bytes(np.array(values, dtype="float32")),
            dim=len(values),
            model_version=deps.get_embeddings().backend_id(),
        )
    )
    session.commit()


def _document(client, title, *notes):
    doc = client.post("/documents", json={"title": title, "content": ""}).json()
    for note in notes:
        client.post(f"/documents/{doc['id']}/notes", json={"entry_id": note["id"]})
    return doc


def _lines(client, **flags):
    params = {"similarity": "true", **{f"include_{k}": "true" for k in flags}}
    edges = client.get("/graph", params=params).json()["edges"]
    return [e for e in edges if e["kind"] == "similar" and e.get("derived")]


def _world(client, session):
    a, b = _note(client, "alpha one"), _note(client, "alpha two")
    near, far = _note(client, "alpha three"), _note(client, "gamma")
    _vector(session, a, [1.0, 0.1, 0.0])
    _vector(session, b, [1.0, -0.1, 0.0])
    _vector(session, near, [0.9, 0.0, 0.1])
    _vector(session, far, [0.0, 0.0, 1.0])
    return a, b, near, far


def test_a_document_reads_like_the_notes_its_own_notes_resemble(client, session):
    a, b, near, far = _world(client, session)
    doc = _document(client, "Plan", a, b)
    lines = _lines(client, documents=True)
    key = f"document:{doc['id']}"
    assert [(e["source"], e["target"]) for e in lines] == [(key, near["id"])]
    assert lines[0]["derived"] is True and lines[0]["score"] >= 0.55
    assert far["id"] not in {e["target"] for e in lines}


def test_the_layer_is_opt_in_and_a_member_is_never_lined_to_its_own_node(client, session):
    a, b, near, _far = _world(client, session)
    _document(client, "Plan", a, b)
    assert _lines(client) == []
    assert all(e["target"] not in (a["id"], b["id"]) for e in _lines(client, documents=True))


def test_an_entity_is_the_mean_of_the_notes_that_name_it(client, session):
    a, b, near, _far = _world(client, session)
    entity = Entity(name="Priya", kind="person")
    session.add(entity)
    session.flush()
    session.add_all([EntityMention(entity_id=entity.id, entry_id=a["id"]), EntityMention(entity_id=entity.id, entry_id=b["id"])])
    session.commit()
    lines = _lines(client, entities=True)
    assert [(e["source"], e["target"]) for e in lines] == [(f"entity:{entity.id}", near["id"])]


def test_a_private_note_never_lends_a_document_its_meaning(client, session):
    a, b, near, far = _world(client, session)
    secret = _note(client, "secret")
    _vector(session, secret, [1.0, 0.0, 0.0])
    session.get(Entry, secret["id"]).is_private = True
    doc = _document(client, "Only secret", far)
    session.add(DocumentLink(document_id=doc["id"], entry_id=secret["id"]))
    session.commit()
    targets = {e["target"] for e in _lines(client, documents=True) if e["source"] == f"document:{doc['id']}"}
    # The vector of "far" alone decides: nothing near the secret's direction is lined.
    assert near["id"] not in targets and a["id"] not in targets and b["id"] not in targets


def test_a_trace_can_hop_from_a_document_to_a_similar_note(client, session):
    a, b, near, _far = _world(client, session)
    doc = _document(client, "Plan", a, b)
    key = f"document:{doc['id']}"
    got = client.get("/graph/path", params={"source": key, "target": near["id"], "documents": "true", "similarity": "true"}).json()
    assert got["found"] is True
    assert got["nodes"][0]["id"] == key and got["nodes"][-1]["id"] == near["id"]


def test_derived_pairs_keeps_each_nodes_best_partners_and_skips_joined_notes():
    notes = {1: np.array([1.0, 0.0]), 2: np.array([0.9, 0.1]), 3: np.array([0.0, 1.0])}
    found = derived_pairs({"document:1": np.array([1.0, 0.05])}, notes, 0.55, 4, {("document:1", 1)})
    assert [(a, b) for a, b, _ in found] == [("document:1", 2)]
    assert derived_pairs({}, notes, 0.55, 4) == []
