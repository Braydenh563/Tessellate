"""INBOX 1695 a: a Private toggle on the quick note and the capture card makes
that one note private; it starts as Settings' "New notes start private" says,
and a save sends `private` only when the toggle differs from the setting."""

from __future__ import annotations

from pathlib import Path

import pytest

from tessellate.core import vault
from tessellate.core.database import Entry
from tests._app_js import app_js_text

INDEX = Path(__file__).resolve().parent.parent / "frontend" / "index.html"


def test_both_forms_carry_the_toggle_and_send_its_ask():
    js = app_js_text()
    assert 'id="quick-note-private"' in INDEX.read_text(encoding="utf-8")
    assert 'createNoteSafely({ content, tags: slots?.tags || [], ...notePrivateAsk($("quick-note-private")) })' in js
    assert 'Object.assign(body, captureCard.lockAsk())' in js
    # the card's toggle is put back to the setting after a save
    assert 'captureCard.lockSync()' in js


def test_the_ask_is_null_unless_it_differs_from_the_setting():
    ask = app_js_text().split("function notePrivateAsk", 1)[1][:260]
    assert "if (!button) return {}" in ask
    assert "prefsCache?.new_notes_private" in ask and "{ private: on }" in ask


@pytest.fixture
def open_vault(session):
    vault.close()
    vault.create(session, "test-passphrase")
    session.commit()
    yield
    vault.close()


def test_a_note_can_be_private_against_either_setting(client, session, open_vault):
    mine = client.post("/entries", json={"content": "lock one", "private": True}).json()["id"]
    client.put("/preferences", json={"new_notes_private": True})
    follows = client.post("/entries", json={"content": "lock two"}).json()["id"]
    readable = client.post("/entries", json={"content": "lock three", "private": False}).json()["id"]
    session.expire_all()
    assert [session.get(Entry, i).is_private for i in (mine, follows, readable)] == [True, True, False]
