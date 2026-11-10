"""F6 (INBOX 1695 c, d): a Private row in the sidebar over `is:private`, and
"Make all notes private" behind a confirm."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from tests._app_js import app_js_text
from tessellate.core import vault
from tessellate.core.database import Entry


def test_sidebar_has_private_row_over_is_private():
    js = app_js_text()
    assert 'queryRow("ph:lock Private", (e) => e.is_private, "is:private"' in js
    helper = js.split("const queryRow = ", 1)[1][:400]
    assert "noteSearch === query" in helper and "filterNotesBy(query)" in helper


@pytest.fixture
def open_vault(session):
    vault.close()
    vault.create(session, "test-passphrase")
    session.commit()
    yield
    vault.close()


def test_make_all_private_seals_every_ordinary_note(client, session, open_vault):
    a = client.post("/entries", json={"content": "alpha secret"}).json()["id"]
    b = client.post("/entries", json={"content": "beta secret"}).json()["id"]
    done = client.post("/entries/make-all-private", json={"confirm": True})
    assert done.status_code == 200
    assert done.json()["sealed"] == 2
    session.expire_all()
    for entry_id in (a, b):
        row = session.get(Entry, entry_id)
        assert row.is_private and "secret" not in row.content
    # idempotent: nothing left to seal
    again = client.post("/entries/make-all-private", json={"confirm": True})
    assert again.json()["sealed"] == 0


def test_make_all_private_needs_the_confirm(client, session, open_vault):
    note = client.post("/entries", json={"content": "keep me"}).json()["id"]
    missing = client.post("/entries/make-all-private", json={})
    declined = client.post("/entries/make-all-private", json={"confirm": False})
    assert (missing.status_code, declined.status_code) == (422, 400)
    session.expire_all()
    assert not session.get(Entry, note).is_private


def test_make_all_private_needs_an_open_vault(client, session):
    vault.close()
    client.post("/entries", json={"content": "x"})
    refused = client.post("/entries/make-all-private", json={"confirm": True})
    assert refused.status_code == 409
    assert not session.scalars(select(Entry).where(Entry.is_private.is_(True))).all()
