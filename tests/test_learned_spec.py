"""What the notebook learned (WORLD_CLASS_PLAN 15, I7 and I9): the spec.

Strict-xfail until an Opus session builds it (see tests/test_events.py for
why the specs are written this way). Specified together because I9 is the
contract I7 ships under: no learned boost exists without a place to see,
edit, delete and switch it off.

I7, the corrections loop: a re-file, a dismissed link, a result opened
after a question, a "never again" on a resurfacing card are recorded as
`corrections` rows; `learned_boosts` is derived from them and is what
filing, search and link suggestions read. I9, the Settings section: every
derived row is listed with its source span, model and time; each can be
edited (and is then never overwritten), deleted (and then never
re-derived), reset; every runner obeys its switch and the master switch;
"forget everything" leaves notes and revisions byte-identical.

Module and function names below are the contract; a session that needs a
different shape changes the test in the same commit, with the reason.
"""

from __future__ import annotations

import hashlib

import pytest

def _note(session, text, category=None):
    from tessellate.entry import manager

    entry = manager.create_entry(session, text, tags=[])
    if category is not None:
        manager.set_category(session, entry, category)
    session.commit()
    return entry


def _table_hash(session, table: str) -> str:
    from sqlalchemy import text

    rows = session.execute(text(f"SELECT * FROM {table} ORDER BY 1")).all()  # noqa: S608  # table name is a literal
    return hashlib.sha256(repr(rows).encode()).hexdigest()


# --- I7: corrections are recorded and change behaviour ------------------------


def test_a_refile_is_recorded_and_reaches_the_next_filing_prompt(session):
    from tessellate.ai import learning

    entry = _note(session, "fixed the flaky retry in the payments worker", category="Work")
    learning.record(session, kind="refile", subject={"entry_id": entry.id}, from_value="Work", to_value="Projects")
    session.commit()
    rows = learning.corrections(session, kind="refile")
    assert [(r.from_value, r.to_value) for r in rows] == [("Work", "Projects")]
    evidence = learning.filing_evidence(session, "another fix in the payments worker retry path")
    # The prompt gets the nearest already-filed notes and the matching corrections.
    assert any(item["kind"] == "correction" and item["to"] == "Projects" for item in evidence)
    assert any(item["kind"] == "neighbour" and item["entry_id"] == entry.id for item in evidence)


def test_two_refiles_away_from_a_category_stop_the_centroid_choosing_it(session):
    from tessellate.ai import learning

    for text in ("payments worker retry", "payments worker timeout", "payments worker queue"):
        _note(session, text, category="Work")
    for i in range(2):
        learning.record(session, kind="refile", subject={"entry_id": i + 1}, from_value="Work", to_value="Projects")
    session.commit()
    boosts = learning.boosts(session, kind="filing")
    assert boosts.get(("Work", "Projects")) is not None
    assert learning.centroid_excluded(session, "Work", "payments worker crash") is True


def test_an_open_after_ask_reorders_the_next_similar_question(session):
    from tessellate.ai import learning
    from tessellate.search import search_manager

    # The spec was written calling `retrieve(session, query, limit=...)` and
    # iterating the result. The real signature takes the embedding service and
    # returns `(entries, mode)`, and that shape is load-bearing: the mode is
    # how the UI says whether an answer came from a keyword match or a concept
    # one ("so the UI can be honest", `retrieve`'s own docstring). Changing the
    # code to match the spec would ripple through every caller to make the
    # search *less* able to explain itself, so the test is changed here
    # instead, per this file's header.
    from tessellate.core import deps

    def ids(question):
        entries, _mode = search_manager.retrieve(
            session, question, deps.get_embeddings(), limit=5
        )
        return [entry.id for entry in entries]

    a = _note(session, "sourdough starter feeding schedule, morning and night")
    b = _note(session, "sourdough loaf shaping and scoring notes")
    before = ids("sourdough notes")
    assert before[0] in (a.id, b.id)
    chosen = b.id if before[0] == a.id else a.id
    learning.record(session, kind="open_after_ask", subject={"question": "sourdough notes", "entry_id": chosen})
    session.commit()
    assert ids("my sourdough notes")[0] == chosen


def test_a_dismissed_link_pair_never_returns(ai_client, fake_embeddings):
    a = ai_client.post("/entries", json={"content": "bubble tea order for the office"}).json()
    b = ai_client.post("/entries", json={"content": "bubble tea shop opening hours"}).json()
    ai_client.post("/learned/corrections", json={"kind": "dismiss_link", "subject": {"a": a["id"], "b": b["id"]}})
    pairs = {(s["a"], s["b"]) for s in ai_client.get("/entries/link-suggestions").json()}
    assert (a["id"], b["id"]) not in pairs and (b["id"], a["id"]) not in pairs


def test_boosts_are_bounded_and_decay(session):
    from tessellate.ai import learning

    for _ in range(50):
        learning.record(session, kind="open_after_ask", subject={"question": "q", "entry_id": 1})
    session.commit()
    weight = learning.boosts(session, kind="search").get(("q", 1))
    assert 0 < weight <= learning.MAX_BOOST
    assert learning.decayed(weight, days=30) == pytest.approx(weight / 2, rel=0.05)


# --- I9: see, edit, delete, reset, switch off ---------------------------------


def test_the_section_lists_every_kind_with_its_source_span(ai_client, fake_ollama):
    entry = ai_client.post("/entries", json={"content": "The batch size should stay at 32. Should we move to 64?"}).json()
    ai_client.post("/night/run", json={"budget": 1000})
    rows = ai_client.get("/learned?kind=question").json()["items"]
    assert rows, "the night shift derived no question from a sentence ending in ?"
    row = rows[0]
    assert row["entry_id"] == entry["id"]
    assert entry["content"][row["span"][0] : row["span"][1]].endswith("?")
    assert row["model"] and row["computed_at"] and 0 <= row["confidence"] <= 1


def test_an_edited_fact_survives_a_rerun(ai_client, fake_ollama):
    ai_client.post("/entries", json={"content": "The batch size should stay at 32."})
    ai_client.post("/night/run", json={"budget": 1000})
    fact = ai_client.get("/learned?kind=claim").json()["items"][0]
    ai_client.patch(f"/learned/{fact['id']}", json={"text": "Batch size: 32, until the memory fix lands."})
    ai_client.post("/night/run", json={"budget": 1000, "force": True})
    again = ai_client.get(f"/learned/{fact['id']}").json()
    assert again["text"] == "Batch size: 32, until the memory fix lands."
    assert again["edited_by_user"] is True
    assert again["original_text"] == fact["text"]


def test_a_deleted_fact_is_not_rederived(ai_client, fake_ollama):
    ai_client.post("/entries", json={"content": "The batch size should stay at 32."})
    ai_client.post("/night/run", json={"budget": 1000})
    fact = ai_client.get("/learned?kind=claim").json()["items"][0]
    deleted = ai_client.delete(f"/learned/{fact['id']}")
    assert deleted.status_code == 204
    ai_client.post("/night/run", json={"budget": 1000, "force": True})
    texts = [r["text"] for r in ai_client.get("/learned?kind=claim").json()["items"]]
    assert fact["text"] not in texts
    kinds = [c["kind"] for c in ai_client.get("/learned/corrections").json()]
    assert "delete_fact" in kinds


def test_reset_restores_what_the_model_said(ai_client, fake_ollama):
    ai_client.post("/entries", json={"content": "The batch size should stay at 32."})
    ai_client.post("/night/run", json={"budget": 1000})
    fact = ai_client.get("/learned?kind=claim").json()["items"][0]
    ai_client.patch(f"/learned/{fact['id']}", json={"text": "changed"})
    ai_client.post(f"/learned/{fact['id']}/reset")
    again = ai_client.get(f"/learned/{fact['id']}").json()
    assert again["text"] == fact["text"] and again["edited_by_user"] is False


def _two_claims(ai_client):
    ai_client.post("/entries", json={"content": "The batch size should stay at 32."})
    ai_client.post("/entries", json={"content": "The learning rate should stay at 0.001 for now."})
    ai_client.post("/night/run", json={"budget": 1000})
    return ai_client.get("/learned?kind=claim").json()["items"]


def test_bulk_delete_removes_each_and_remembers_each(ai_client, fake_ollama):
    """`POST /learned/bulk` (the plan's `{ids, action}`), so the table's
    selection is one request that lands whole, not N that can half fail."""
    claims = _two_claims(ai_client)
    assert len(claims) >= 2
    ids = [row["id"] for row in claims[:2]]
    reply = ai_client.post("/learned/bulk", json={"ids": ids, "action": "delete"})
    assert reply.status_code == 200
    assert reply.json() == {"action": "delete", "done": 2, "missing": []}
    left = {row["id"] for row in ai_client.get("/learned").json()["items"]}
    assert not left & set(ids)
    kinds = [c["kind"] for c in ai_client.get("/learned/corrections").json()]
    assert kinds.count("delete_fact") >= 2


def test_bulk_reset_puts_back_only_what_was_edited(ai_client, fake_ollama):
    claims = _two_claims(ai_client)
    edited, untouched = claims[0], claims[1]
    ai_client.patch(f"/learned/{edited['id']}", json={"text": "changed by hand"})
    reply = ai_client.post(
        "/learned/bulk", json={"ids": [edited["id"], untouched["id"]], "action": "reset"}
    ).json()
    assert reply["done"] == 1
    again = ai_client.get(f"/learned/{edited['id']}").json()
    assert again["text"] == edited["text"] and again["edited_by_user"] is False


def test_bulk_names_what_it_could_not_find_and_refuses_nonsense(ai_client, fake_ollama):
    claims = _two_claims(ai_client)
    reply = ai_client.post("/learned/bulk", json={"ids": [claims[0]["id"], 999999], "action": "delete"})
    assert reply.json()["missing"] == [999999]
    assert ai_client.post("/learned/bulk", json={"ids": [1], "action": "explode"}).status_code == 422
    assert ai_client.post("/learned/bulk", json={"ids": [], "action": "delete"}).status_code == 422


def test_each_switch_off_yields_no_rows_and_a_paused_reply(ai_client, fake_ollama):
    ai_client.put("/learned/switches", json={"night_shift": False})
    ai_client.post("/entries", json={"content": "The batch size should stay at 32."})
    reply = ai_client.post("/night/run", json={"budget": 1000})
    assert reply.status_code == 204 or reply.json() == {"paused": True}
    assert ai_client.get("/learned").json()["items"] == []


def test_the_master_switch_pauses_every_runner(ai_client, fake_ollama):
    ai_client.put("/learned/switches", json={"paused": True})
    switches = ai_client.get("/learned/switches").json()
    assert switches["paused"] is True
    assert all(v is False for k, v in switches.items() if k != "paused")


def test_forget_everything_leaves_notes_and_revisions_byte_identical(ai_client, fake_ollama, session):
    ai_client.post("/entries", json={"content": "The batch size should stay at 32. Should we move to 64?"})
    ai_client.post("/night/run", json={"budget": 1000})
    before = (_table_hash(session, "entries"), _table_hash(session, "entry_revisions"))
    assert ai_client.get("/learned").json()["items"]
    # `TestClient.delete` takes no body (httpx does not give DELETE one), so
    # the spec's own call raises TypeError before it reaches the app. Changed
    # here per this file's header: the route is the thing under test and it
    # does require the body, which is why this goes through `request`.
    forgotten = ai_client.request("DELETE", "/learned", json={"confirm": True})
    assert forgotten.status_code == 200
    assert ai_client.get("/learned").json()["items"] == []
    assert ai_client.get("/learned/corrections").json() == []
    session.expire_all()
    assert (_table_hash(session, "entries"), _table_hash(session, "entry_revisions")) == before


def test_a_private_notes_facts_are_never_listed(ai_client, fake_ollama, session, monkeypatch):
    from tessellate.core.database import Entry
    from tessellate.entry import manager_private

    saved = ai_client.post("/entries", json={"content": "The batch size should stay at 32."}).json()
    ai_client.post("/night/run", json={"budget": 1000})
    # `set_private` encrypts the note and returns False when the vault has no
    # key, so the spec as written never made the note private and the
    # assertion below passed on a note that was never hidden. The key is
    # stubbed the same way `test_search_engine.py` does it, and the return
    # value is asserted, which is what makes this test able to fail.
    monkeypatch.setattr("tessellate.core.vault.key", lambda: b"k" * 32)
    assert manager_private.set_private(session, session.get(Entry, saved["id"]), True)
    session.commit()
    assert all(r["entry_id"] != saved["id"] for r in ai_client.get("/learned").json()["items"])


def test_the_export_is_readable_json_of_everything(ai_client, fake_ollama):
    ai_client.post("/entries", json={"content": "The batch size should stay at 32."})
    ai_client.post("/night/run", json={"budget": 1000})
    export = ai_client.get("/learned/export").json()
    assert set(export) >= {"facts", "corrections", "boosts", "switches", "exported_at"}
    assert export["facts"] and all("entry_id" in f and "text" in f for f in export["facts"])
