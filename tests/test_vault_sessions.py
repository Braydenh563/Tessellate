"""The vault key belongs to the sessions that gave the password, not the process.

OPEN.md (auth-optional): "The vault key is process-wide (`core/vault.py`):
after a LAN device unlocks, a loopback session without a password reads
private notes too until a lock or restart." The data key is still held once,
in memory (one notebook, one key); what changed is *who may use it*. Every
session that proved the password is granted it (`vault.grant`); a request
from any other session sees the vault as locked, whatever another session
did. The key is forgotten when the last granted session ends.

These tests use two kinds of caller, the way the app meets them: a device on
the network, which always gives the password, and this computer with sign-in
off, which is handed a session without one.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from tessellate.api import routes_auth
from tessellate.core import deps, vault

PASSWORD = "the owner's password"
SECRET = "the spare key is under the mat"


@pytest.fixture()
def app(client):
    return client.app


@pytest.fixture(autouse=True)
def _clean():
    routes_auth._active_tokens.clear()
    routes_auth._media_tickets.clear()
    routes_auth._clear_unlock_failures()
    vault.close()
    yield
    routes_auth._active_tokens.clear()
    routes_auth._media_tickets.clear()
    routes_auth._clear_unlock_failures()
    vault.close()


@pytest.fixture(autouse=True)
def _devices_already_allowed(client):
    """These tests are about sessions and the vault, so the phone here is one
    this computer already allowed; holding a new device is test_lan.py's."""
    from tessellate.core import lantrust

    lantrust.set_flag(deps.get_config().data_dir, "ask_new_devices", False)
    yield
    lantrust.reset_for_tests()


def _local(app) -> TestClient:
    return TestClient(app, base_url="http://127.0.0.1:8795", client=("127.0.0.1", 50000))


def _lan(app) -> TestClient:
    return TestClient(app, base_url="http://192.168.1.10:8795", client=("192.168.1.20", 50000))


def _auth(token: str) -> dict:
    return {"X-Auth-Token": token}


def _restart() -> None:
    """What a relaunch leaves: no sessions, no key in memory."""
    routes_auth._active_tokens.clear()
    routes_auth._media_tickets.clear()
    vault.close()


def _notebook_with_a_secret(app, sign_in_off: bool) -> int:
    local = _local(app)
    token = local.post("/auth/setup", json={"password": PASSWORD}).json()["token"]
    entry = local.post("/entries", json={"content": SECRET}, headers=_auth(token)).json()
    made = local.post(f"/entries/{entry['id']}/privacy", json={"private": True}, headers=_auth(token))
    assert made.status_code == 200, made.text
    if sign_in_off:
        off = local.post(
            "/auth/password-on-open",
            json={"enabled": False, "current_password": PASSWORD},
            headers=_auth(token),
        )
        assert off.status_code == 200, off.text
    _restart()
    return entry["id"]


def _reads_secret(client: TestClient, note: int, token: str) -> bool:
    response = client.get(f"/entries/{note}", headers=_auth(token))
    assert response.status_code == 200, response.text
    return response.json()["content"].startswith("the spare key")


def test_a_network_unlock_does_not_open_private_notes_for_a_session_without_a_password(app):
    """The finding itself, reproduced: failed before this change."""
    note = _notebook_with_a_secret(app, sign_in_off=True)
    lan, local = _lan(app), _local(app)
    phone = lan.post("/auth/unlock", json={"password": PASSWORD}).json()
    assert phone["vault_open"] is True
    here = local.post("/auth/auto-session").json()
    assert here["vault_open"] is False
    assert _reads_secret(lan, note, phone["token"]) is True
    assert _reads_secret(local, note, here["token"]) is False
    assert local.get("/auth/account", headers=_auth(here["token"])).json()["vault_open"] is False
    assert lan.get("/auth/account", headers=_auth(phone["token"])).json()["vault_open"] is True
    # Anything that needs the key is refused for the session without it,
    # rather than done with a key it was never given.
    toggled = local.post(f"/entries/{note}/privacy", json={"private": False}, headers=_auth(here["token"]))
    assert toggled.status_code == 409


def test_unlock_vault_grants_the_caller_only(app):
    note = _notebook_with_a_secret(app, sign_in_off=True)
    local = _local(app)
    first = local.post("/auth/auto-session").json()["token"]
    opened = local.post("/auth/unlock-vault", json={"password": PASSWORD}, headers=_auth(first))
    assert opened.json()["vault_open"] is True
    second = local.post("/auth/auto-session").json()["token"]  # another tab, no token yet
    assert second != first
    assert _reads_secret(local, note, first) is True
    assert _reads_secret(local, note, second) is False


def test_two_sessions_that_gave_the_password_both_read(app):
    note = _notebook_with_a_secret(app, sign_in_off=False)
    lan, local = _lan(app), _local(app)
    a = local.post("/auth/unlock", json={"password": PASSWORD}).json()["token"]
    b = lan.post("/auth/unlock", json={"password": PASSWORD}).json()["token"]
    assert _reads_secret(local, note, a) and _reads_secret(lan, note, b)


def test_locking_one_granted_session_keeps_the_other(app):
    note = _notebook_with_a_secret(app, sign_in_off=False)
    lan, local = _lan(app), _local(app)
    a = local.post("/auth/unlock", json={"password": PASSWORD}).json()["token"]
    b = lan.post("/auth/unlock", json={"password": PASSWORD}).json()["token"]
    local.post("/auth/lock", headers=_auth(a))
    assert _reads_secret(lan, note, b) is True
    lan.post("/auth/lock", headers=_auth(b))
    assert vault.is_open() is False


def test_the_key_goes_when_the_last_granted_session_expires(app):
    """Even while a session without the password is still live: before this
    change the key stayed until *every* session had gone."""
    note = _notebook_with_a_secret(app, sign_in_off=True)
    lan, local = _lan(app), _local(app)
    phone = lan.post("/auth/unlock", json={"password": PASSWORD}).json()["token"]
    here = local.post("/auth/auto-session").json()["token"]
    long_ago = time.time() - routes_auth._SESSION_MAX_AGE - 10
    routes_auth._active_tokens[phone] = [long_ago, long_ago]
    #: The per-request sweep runs at most every _SWEEP_EVERY seconds (audit
    #: 1028 K33); this puts the last one beyond that, which is what the wait
    #: for the phone's session to expire amounts to. Who holds the key is the
    #: stated intent and it has not moved.
    routes_auth._sweep_state["last"] = 0.0
    assert _reads_secret(local, note, here) is False  # the request sweeps
    assert vault.is_open() is False


def test_a_changed_password_keeps_the_caller_reading(app):
    note = _notebook_with_a_secret(app, sign_in_off=False)
    lan, local = _lan(app), _local(app)
    a = local.post("/auth/unlock", json={"password": PASSWORD}).json()["token"]
    b = lan.post("/auth/unlock", json={"password": PASSWORD}).json()["token"]
    changed = local.post(
        "/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "a new password"},
        headers=_auth(a),
    ).json()
    assert _reads_secret(local, note, changed["token"]) is True
    # The other session is ended, and its token opens nothing.
    assert lan.get(f"/entries/{note}", headers=_auth(b)).status_code == 401


def test_a_session_without_the_password_that_changes_it_is_granted(app):
    """Change-password asks for the current password, which proves it."""
    note = _notebook_with_a_secret(app, sign_in_off=True)
    local = _local(app)
    here = local.post("/auth/auto-session").json()["token"]
    changed = local.post(
        "/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "a new password"},
        headers=_auth(here),
    )
    assert changed.status_code == 200, changed.text
    assert _reads_secret(local, note, changed.json()["token"]) is True


def test_rotating_the_key_from_a_session_without_the_password(app):
    """`rotate-vault-key` takes the current password too; before this change a
    session without it, next to one with it, rotated with the other's key."""
    note = _notebook_with_a_secret(app, sign_in_off=True)
    local = _local(app)
    here = local.post("/auth/auto-session").json()["token"]
    rotated = local.post(
        "/auth/rotate-vault-key", json={"current_password": PASSWORD}, headers=_auth(here)
    )
    assert rotated.status_code == 200, rotated.text
    assert rotated.json()["notes_reencrypted"] == 1
    assert _reads_secret(local, note, rotated.json()["token"]) is True


def test_setup_grants_the_first_session(app):
    local = _local(app)
    token = local.post("/auth/setup", json={"password": PASSWORD}).json()["token"]
    entry = local.post("/entries", json={"content": SECRET}, headers=_auth(token)).json()
    made = local.post(f"/entries/{entry['id']}/privacy", json={"private": True}, headers=_auth(token))
    assert made.status_code == 200
    assert _reads_secret(local, entry["id"], token) is True


def test_a_request_with_no_token_never_borrows_a_granted_key(app):
    """Only the gate's own "no password yet" case passes without a token, and
    once one exists nothing tokenless can read; asserted at the module so a
    future ungated route cannot become the way round."""
    _notebook_with_a_secret(app, sign_in_off=False)
    token = _local(app).post("/auth/unlock", json={"password": PASSWORD}).json()["token"]
    with vault.request_scope(None):
        assert vault.key() is None
    with vault.request_scope("not a session"):
        assert vault.key() is None
    with vault.request_scope(token):
        assert vault.key() is not None


def test_a_request_never_reads_a_key_nobody_was_granted(app_state):
    """The window the rule above missed (review, 2026-09-26). "The rule
    starts with the first grant" made a loaded key with an empty grant set
    everyone's: `unlock` loads the key and grants its caller a few lines
    later, `change-password` and `rotate-vault-key` clear every grant and
    grant the new session after issuing it, and a sync route runs in a
    threadpool beside them, so a request from a session that never gave the
    password, timed into either gap, read private notes. Inside a request
    the key is a granted session's or nobody's, whatever the grant set
    holds; outside one (a script, a test's direct call) it is still the
    process key, which is all the previous test needs."""
    session = deps.get_db().session()
    try:
        # As `unlock` does: loaded while serving a request, for a session
        # not yet issued.
        with vault.request_scope(None):
            vault.create(session, "a passphrase")
        session.commit()
    finally:
        session.close()
    assert vault.key() is not None
    with vault.request_scope(None):
        assert vault.key() is None
    with vault.request_scope("not a session"):
        assert vault.key() is None
    vault.grant("a session that gave the password")
    with vault.request_scope("a session that gave the password"):
        assert vault.key() is not None
    with vault.request_scope("not a session"):
        assert vault.key() is None


def test_with_no_session_granted_the_key_is_the_process_key(app_state):
    """A key loaded outside any session (the direct calls tests and scripts
    make) behaves exactly as before: the rule starts with the first grant."""
    session = deps.get_db().session()
    try:
        vault.create(session, "a passphrase")
        session.commit()
        assert vault.key() is not None
    finally:
        session.close()
