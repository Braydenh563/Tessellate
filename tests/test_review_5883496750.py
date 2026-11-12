"""The five findings of the automated review 5883496750: chat document delete, anchored reminders,
the capability pre-check, the on-disk undo log and the reading pick. Clock: Tuesday 10 November 2026, 09:00."""

from __future__ import annotations

import os
import stat
from datetime import datetime

import pytest
from sqlalchemy import select

from tessellate.ai import anchor_acts, commands, tools
from tessellate.api import chat_pick
from tessellate.core.database import Document
from tessellate.entry import manager
from tessellate.core import vault

from tests.test_chat_acts_2_1112_c import _fixed_now  # noqa: F401  (autouse clock)
from tests.test_parity_acts_1110 import card_of, confirm, stream, undo

NOW = datetime(2026, 11, 10, 9, 0)


@pytest.fixture
def unlocked_vault(session):
    vault.close()
    vault.create(session, "test-passphrase")
    session.commit()
    yield
    vault.close()


def _binned(session, doc_id):
    from tessellate.entry.bin import including_binned

    session.expire_all()
    with including_binned(session):
        return session.get(Document, doc_id)


# --- 1. a document delete goes to the bin, never touches a private one -------------------------


def test_chat_delete_bins_the_document_and_undo_restores_the_same_row(client, session):
    doc = Document(title="Harbor report", content="Findings.")
    session.add(doc)
    session.commit()
    doc_id = doc.id
    done = confirm(client, card_of(stream(client, "delete the document Harbor report")))
    assert _binned(session, doc_id).deleted_at is not None
    assert [s["name"] for s in done["undo"]] == ["restore_document"]
    undo(client, done)
    row = _binned(session, doc_id)
    assert row.deleted_at is None and row.content == "Findings."
    assert session.scalars(select(Document)).all() == [row]


def test_the_tool_bins_and_its_undo_restores(session):
    doc = Document(title="Plan", content="Steps.")
    session.add(doc)
    session.commit()
    gone = tools.execute_tool(session, "delete_document", {"document_id": doc.id})
    assert gone["undo"] == {"tool": "restore_document", "arguments": {"document_id": doc.id}}
    assert _binned(session, doc.id).deleted_at is not None
    commands.run(session, [{"name": gone["undo"]["tool"], "arguments": gone["undo"]["arguments"]}])
    assert _binned(session, doc.id).deleted_at is None


def test_a_private_document_is_not_matched_by_a_sentence(client, session, unlocked_vault):
    session.add(Document(title="Secret plan", content="hidden", is_private=True))
    session.commit()
    out = stream(client, "delete the document Secret plan")
    assert not [e for e in out.get("act", []) if e.get("steps")]
    assert "no document" in out["text"]


def test_the_tool_refuses_a_private_document(session, unlocked_vault):
    doc = Document(title="Secret plan", content="hidden", is_private=True)
    session.add(doc)
    session.commit()
    assert "error" in tools.execute_tool(session, "delete_document", {"document_id": doc.id})
    assert _binned(session, doc.id).deleted_at is None


# --- 2. the anchored reminder lookup ------------------------------------------------------------


def _settle(session, sentence):
    return anchor_acts.settle(session, anchor_acts.read(sentence), NOW)


def test_a_private_note_never_anchors(session, unlocked_vault):
    entry = manager.create_entry(session, "# Dentist\n\nCheck-up tomorrow at 3pm.", category_name="Life")
    entry.is_private = True
    session.commit()
    assert "ask" in _settle(session, "remind me an hour before the dentist")


def test_words_match_on_boundaries(session):
    manager.create_entry(session, "# Gymnastics\n\nClass tomorrow at 3pm.", category_name="Life")
    manager.create_entry(session, "# Recall\n\nTo recall the form tomorrow at 4pm.", category_name="Life")
    session.commit()
    assert "ask" in _settle(session, "remind me an hour before the gym")
    assert "ask" in _settle(session, "remind me an hour before the call")


def test_the_whole_word_still_anchors(session):
    manager.create_entry(session, "# Gym\n\nSession tomorrow at 3pm.", category_name="Life")
    session.commit()
    assert _settle(session, "remind me an hour before the gym")["due_at"] == datetime(2026, 11, 11, 14, 0)


# --- 3. an attached picture is captioned once ---------------------------------------------------


@pytest.mark.parametrize("question", ["what is in this photo?", "can you search the web?"])
def test_an_attached_image_is_captioned_once(ai_client, fake_ollama, monkeypatch, question):
    from tessellate.ai import captioning

    calls = []
    monkeypatch.setattr(captioning, "caption_and_store", lambda *a, **k: calls.append(a) or "a photo of a pond")
    sent = ai_client.post("/media/upload", files={"file": ("photo.png", b"\x89PNG\r\n\x1a\n", "image/png")})
    assert ai_client.post("/chat", json={"question": question, "image_media_ids": [sent.json()["id"]]}).status_code == 200
    assert len(calls) == 1


# --- 4. the undo log is written 0600 and atomically --------------------------------------------

STEP = [{"name": "edit_note", "arguments": {"note_id": 7, "content": "# New name\n\nbody", "category": "Life"}}]


def test_the_undo_log_is_never_wider_than_0600(app_state, monkeypatch):
    from tessellate.ai import consent_store

    monkeypatch.setattr(os, "chmod", lambda *a, **k: None)  # the mode must come from the open, not a later chmod
    old = os.umask(0)
    try:
        consent_store.log_undo(STEP, "Rename")
    finally:
        os.umask(old)
    assert stat.S_IMODE(consent_store._log_path().stat().st_mode) == 0o600


def test_a_failed_write_keeps_the_old_log(app_state, monkeypatch):
    from tessellate.ai import consent_store

    consent_store.log_undo(STEP, "First")
    before = consent_store._log_path().read_text("utf-8")

    def broken(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", broken)
    consent_store.log_undo(STEP, "Second")
    assert consent_store._log_path().read_text("utf-8") == before
    assert [p.name for p in consent_store._log_path().parent.glob("chat_undo*")] == ["chat_undo.json"]


def test_the_log_lock_may_be_re_entered():
    from tessellate.ai import consent_store

    with consent_store._lock, consent_store._lock:
        pass


# --- 5. the reading pick takes only a bare number or none --------------------------------------

READINGS = [{"n": 1, "note_id": 11, "label": "a"}, {"n": 2, "note_id": 22, "label": "b"}]


@pytest.mark.parametrize(("reply", "note"), [("2", 22), (" 1. ", 11), ("2.", 22), ("none", None), ("None", None), (" NONE ", None)])
def test_a_bare_number_or_none_is_a_pick(reply, note):
    assert chat_pick.choice(reply, READINGS) == note


@pytest.mark.parametrize("reply", ["In 2024 notes, 1 fits", "Reading 2, not 1", "I think 2", "1 or 2", "none of 1", "3", ""])
def test_anything_else_is_no_pick(reply):
    assert chat_pick.choice(reply, READINGS) is None
