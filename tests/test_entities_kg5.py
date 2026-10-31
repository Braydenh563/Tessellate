"""The entity layer (GRAPH_PLAN KG5, INBOX 528): kinds, aliases, merging, an
entity page and entity-to-entity edges from co-mention.

The merge itself (and "Sam" with "Sam Lee", every mention following) is in
`test_suggestions_inbox_kg9.py`, where the inbox offers it; this file is the
rest of the layer.
"""

from __future__ import annotations

from tessellate.ai.entities import extract_entities_pass, suggest_entities, suggest_entities_with_kinds
from tessellate.core.database import Entity, EntityMention, Entry, EntryDate


class _Models:
    def utility_model(self) -> str:
        return "fake"


class _Ollama:
    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    def chat(self, model, messages, mode=None):  # noqa: ANN001, ARG002
        self.prompts.append(messages[0]["content"])
        return {"content": self.replies.pop(0) if self.replies else "NONE"}


def test_the_model_names_a_kind_and_odd_ones_are_read_or_dropped():
    ollama = _Ollama(["Sam Lee|person, Leeds | place, Acme|org, Glaze club|club, Priya"])
    found = suggest_entities_with_kinds("text", _Models(), ollama)
    assert found == [
        ("Sam Lee", "person"),
        ("Leeds", "place"),
        ("Acme", "organisation"),
        ("Glaze club", None),
        ("Priya", None),
    ]
    assert "person" in ollama.prompts[0] and "|" in ollama.prompts[0]
    assert suggest_entities("text", _Models(), _Ollama(["Sam|person"])) == ["Sam"]


def test_extraction_keeps_the_kind_and_fills_one_missing(session):
    session.add(Entity(name="Sam Lee"))
    session.add(Entry(content="Went over the kiln rota with Sam Lee in Leeds today.", ai_confidence=0))
    session.commit()
    extract_entities_pass(session, _Models(), _Ollama(["Sam Lee|person, Leeds|place"]))
    kinds = {e.name: e.kind for e in session.query(Entity)}
    assert kinds == {"Sam Lee": "person", "Leeds": "place"}


def _note(client, text):
    return client.post("/entries", json={"content": text}).json()


def _entity(session, name, *entry_ids, kind=None, aliases=None):
    entity = Entity(name=name, kind=kind, aliases=aliases)
    session.add(entity)
    session.flush()
    for entry_id in entry_ids:
        session.add(EntityMention(entity_id=entity.id, entry_id=entry_id))
    session.commit()
    return entity.id


def test_the_list_counts_visible_notes_and_leaves_out_merged_and_private(client, session):
    a = _note(client, "Sam Lee came by the studio")
    b = _note(client, "Private: Sam Lee again")
    sam = _entity(session, "Sam Lee", a["id"], b["id"], kind="person")
    gone = _entity(session, "Sam", a["id"])
    session.get(Entity, gone).merged_into = sam
    session.get(Entry, b["id"]).is_private = True
    hidden = _entity(session, "Secret", b["id"])
    session.commit()
    rows = {r["id"]: r for r in client.get("/entities").json()}
    assert rows[sam]["notes"] == 1 and rows[sam]["kind"] == "person"
    assert gone not in rows and hidden not in rows


def test_the_entity_page_has_mentions_in_context_co_mentions_and_dates(client, session):
    a = _note(client, "# Rota\n\nSam went over the kiln rota with Priya. Then lunch.")
    b = _note(client, "# Firing\n\nPriya and Sam Lee loaded kiln two on Thursday.")
    c = _note(client, "# Glaze\n\nPriya mixed the shino.")
    sam = _entity(session, "Sam Lee", a["id"], b["id"], kind="person", aliases=["Sam"])
    priya = _entity(session, "Priya", a["id"], b["id"], c["id"], kind="person")
    # Saving the note resolved "on Thursday" (EntryDate) on its own.
    assert session.query(EntryDate).filter_by(entry_id=b["id"]).count() == 1
    page = client.get(f"/entities/{sam}").json()
    assert page["name"] == "Sam Lee" and page["kind"] == "person" and page["aliases"] == ["Sam"]
    by_note = {m["id"]: m for m in page["mentions"]}
    assert set(by_note) == {a["id"], b["id"]}
    hit = by_note[a["id"]]
    assert hit["context"][hit["hit_start"]:hit["hit_end"]] == "Sam"
    assert by_note[b["id"]]["context"][by_note[b["id"]]["hit_start"]:by_note[b["id"]]["hit_end"]] == "Sam Lee"
    assert page["related"][0]["id"] == priya and page["related"][0]["notes"] == 2
    assert page["dates"][0]["phrase"].endswith("Thursday") and page["dates"][0]["entry_id"] == b["id"]
    assert page["first_seen"] <= page["last_seen"]
    assert client.get("/entities/99999").status_code == 404


def test_an_entity_can_be_renamed_kinded_and_merged_by_hand(client, session):
    a, b = _note(client, "one"), _note(client, "two")
    x = _entity(session, "Sammy", a["id"])
    y = _entity(session, "Sam Lee", b["id"])
    ok = client.patch(f"/entities/{x}", json={"kind": "person", "aliases": ["Sam L", "sam l", ""]})
    assert ok.status_code == 200 and ok.json()["aliases"] == ["Sam L"]
    assert client.patch(f"/entities/{x}", json={"kind": "planet"}).status_code == 422
    merged = client.post(f"/entities/{x}/merge", json={"into_id": y})
    assert merged.status_code == 200, merged.text
    session.expire_all()
    assert session.get(Entity, x).merged_into == y
    assert set(session.get(Entity, y).aliases) == {"Sammy", "Sam L"}
    assert session.get(Entity, y).kind == "person"
    assert client.post(f"/entities/{y}/merge", json={"into_id": y}).status_code == 400


def test_two_entities_named_together_twice_are_joined_on_the_graph(client, session):
    a, b, c = _note(client, "one"), _note(client, "two"), _note(client, "three")
    sam = _entity(session, "Sam Lee", a["id"], b["id"])
    priya = _entity(session, "Priya", a["id"], b["id"], c["id"])
    once = _entity(session, "Leeds", c["id"])
    graph = client.get("/graph", params={"include_entities": "true"}).json()
    pairs = {
        frozenset((e["source"], e["target"])): e
        for e in graph["edges"]
        if e.get("kind") == "comention"
    }
    edge = pairs.get(frozenset((f"entity:{sam}", f"entity:{priya}")))
    assert edge is not None and edge["weight"] == 2
    assert frozenset((f"entity:{priya}", f"entity:{once}")) not in pairs
    kinds = {n["id"]: n.get("entity_kind") for n in graph["nodes"] if n.get("type") == "entity"}
    assert f"entity:{sam}" in kinds


def test_the_list_counts_notes_not_mention_rows_and_leaves_out_the_bin(client, session):
    """Audit 1028 K31: the list is counted in SQL now. A note that names an
    entity twice is one note; a binned note is not counted; the limit keeps
    the most named and the header still says how many there are."""
    a = _note(client, "Ada Park, then Ada Park again")
    b = _note(client, "Ada Park in the bin")
    c = _note(client, "Lin Wu once")
    ada = _entity(session, "Ada Park", a["id"], a["id"], b["id"])
    lin = _entity(session, "Lin Wu", c["id"])
    session.get(Entry, b["id"]).is_deleted = True
    session.commit()
    got = client.get("/entities?limit=1")
    assert [(r["id"], r["notes"]) for r in got.json()] == [(ada, 1)], "a tie goes by name"
    assert got.headers["X-Total-Count"] == "2"
    every = client.get("/entities").json()
    assert {r["id"]: r["notes"] for r in every} == {ada: 1, lin: 1}
