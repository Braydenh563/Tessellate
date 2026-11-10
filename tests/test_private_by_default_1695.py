"""INBOX 1695 (Q30): a note can be sealed from its first write.

A create may carry `private`, and a Settings switch ("New notes start
private", off by default) presets it. Either way the note is encrypted before
the first commit, is never filed by a model, and has no embedding.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from tessellate.core import vault
from tessellate.core.database import EmbeddingRecord, Entry

SECRET = "the boathouse code is 4715"


@pytest.fixture(autouse=True)
def open_vault(session):
    vault.close()
    vault.create(session, "test-passphrase")
    session.commit()
    yield
    vault.close()


def _row(session, entry_id):
    session.expire_all()
    return session.get(Entry, entry_id)


def test_the_switch_is_off_by_default(client):
    prefs = client.get("/preferences").json()
    plain = client.post("/entries", json={"content": "plain note"}).json()
    assert prefs["new_notes_private"] is False
    assert plain["is_private"] is False


def test_a_create_can_ask_for_private(client, session):
    made = client.post("/entries", json={"content": SECRET, "private": True})
    assert made.status_code == 201, made.text
    body = made.json()
    assert body["is_private"] is True
    assert body["content"] == SECRET
    row = _row(session, body["id"])
    assert row.is_private and SECRET not in row.content
    assert row.filing_state != "pending"
    assert session.scalars(select(EmbeddingRecord).where(EmbeddingRecord.entry_id == row.id)).first() is None


def test_the_switch_presets_new_notes_and_a_create_can_opt_out(client):
    saved = client.put("/preferences", json={"new_notes_private": True})
    assert saved.status_code == 200
    preset = client.post("/entries", json={"content": SECRET}).json()
    assert preset["is_private"] is True
    opted_out = client.post("/entries", json={"content": "shopping list", "private": False}).json()
    assert opted_out["is_private"] is False


def test_a_note_the_agent_makes_follows_the_switch(session):
    from tessellate.ai.tools.tool_write import _create_note
    from tessellate.core import deps

    deps.get_config().merge_preferences({"new_notes_private": True})
    made = _create_note(session, {"content": SECRET})
    row = _row(session, made["id"] if "id" in made else made["note_id"])
    assert row.is_private and SECRET not in row.content


def test_private_create_needs_an_open_vault(client, session):
    vault.close()
    refused = client.post("/entries", json={"content": SECRET, "private": True})
    assert refused.status_code == 409
    assert "Unlock" in refused.json()["detail"]
    assert session.scalars(select(Entry)).first() is None
