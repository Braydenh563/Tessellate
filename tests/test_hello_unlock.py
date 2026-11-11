"""Windows Hello unlock (INBOX 1727): a third wrap of the vault key, opened
by the WebAuthn PRF output, this computer only, the password always the way
back, and dropped by a password change, a re-key or a restore.

The authenticator is tests/_fake_authenticator.py: real keys, real CBOR and
real signatures. Real Windows Hello is unverified here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests._fake_authenticator import FakeAuthenticator, b64url, unb64url
from tests.test_pin_unlock import FakeStore
from tessellate.api import routes_auth
from tessellate.core import deps, hellostore, pinstore, spacelock, vault, webauthn

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "the owner's password"
NEW_PASSWORD = "a brand new passphrase"
SECRET = "the spare key is under the mat"
ORIGIN = "http://localhost:8795"


@pytest.fixture()
def fake():
    store = FakeStore()
    pinstore.set_store(store)
    yield store
    pinstore.set_store(None)


@pytest.fixture(autouse=True)
def _clean(client):
    from tessellate.core import lantrust

    routes_auth._active_tokens.clear()
    routes_auth._clear_unlock_failures()
    hellostore.reset_for_tests()
    spacelock.close_all()
    vault.close()
    lantrust.set_flag(deps.get_config().data_dir, "ask_new_devices", False)
    yield
    lantrust.reset_for_tests()
    routes_auth._active_tokens.clear()
    routes_auth._clear_unlock_failures()
    hellostore.reset_for_tests()
    spacelock.close_all()
    vault.close()


def _local(client) -> TestClient:
    return TestClient(client.app, base_url=ORIGIN, client=("127.0.0.1", 50000))


def _auth(token: str) -> dict:
    return {"X-Auth-Token": token}


def _restart() -> None:
    routes_auth._active_tokens.clear()
    vault.close()


def _notebook(client):
    local = _local(client)
    token = local.post("/auth/setup", json={"password": PASSWORD}).json()["token"]
    entry = local.post("/entries", json={"content": SECRET}, headers=_auth(token)).json()
    made = local.post(f"/entries/{entry['id']}/privacy", json={"private": True}, headers=_auth(token))
    assert made.status_code == 200, made.text
    return local, token, entry["id"]


def _enrol(local, token, device, *, password=PASSWORD, with_assertion=True):
    begin = local.post("/auth/hello/enrol/begin", json={"current_password": password}, headers=_auth(token))
    if begin.status_code != 200:
        return begin
    b = begin.json()
    body = {"ticket": b["ticket"], **device.create(b, ORIGIN), "prf": b64url(device.prf(unb64url(b["prf_salt"])))}
    if with_assertion:
        body["assertion"] = {
            "ticket": b["get_ticket"], **device.get(b["get_challenge"], b["rp_id"], ORIGIN), "prf": body["prf"],
        }
    return local.post("/auth/hello/enrol/finish", json=body, headers=_auth(token))


def _assertion(local, device, **change):
    begin = local.post("/auth/hello/begin")
    assert begin.status_code == 200, begin.text
    b = begin.json()
    body = {"ticket": b["ticket"], **device.get(b["challenge"], b["rp_id"], ORIGIN), "prf": b64url(device.prf(unb64url(b["prf_salt"])))}
    body.update(change)
    return body


def _with_hello(client, device=None):
    device = device or FakeAuthenticator()
    local, token, note = _notebook(client)
    answer = _enrol(local, token, device)
    assert answer.status_code == 200, answer.text
    _restart()
    return local, device, note


# --- enrolment -------------------------------------------------------------------


def test_status_says_whether_hello_unlocks_here(client, fake):
    local, token, _ = _notebook(client)
    assert local.get("/auth/status").json()["hello_here"] is False
    assert _enrol(local, token, FakeAuthenticator()).status_code == 200
    assert local.get("/auth/status").json()["hello_here"] is True
    lan = TestClient(client.app, base_url="http://192.168.1.10:8795", client=("192.168.1.20", 50000))
    assert lan.get("/auth/status").json()["hello_here"] is False


def test_enrolment_needs_the_password(client, fake):
    local, token, _ = _notebook(client)
    assert _enrol(local, token, FakeAuthenticator(), password="not it").status_code == 401
    assert fake.items == {}


def test_enrolment_is_refused_from_another_device_and_a_tunnel(client, fake):
    local, token, _ = _notebook(client)
    lan = TestClient(client.app, base_url="http://192.168.1.10:8795", client=("192.168.1.20", 50000))
    assert _enrol(lan, token, FakeAuthenticator()).status_code == 403
    tunnel = TestClient(client.app, base_url=ORIGIN, client=("127.0.0.1", 50000), headers={"X-Forwarded-For": "8.8.8.8"})
    assert _enrol(tunnel, token, FakeAuthenticator()).status_code == 403
    assert fake.items == {}


def test_an_ip_address_page_is_told_to_use_localhost(client, fake):
    """Browsers refuse an IP address as an RP id."""
    local = TestClient(client.app, base_url="http://127.0.0.1:8795", client=("127.0.0.1", 50000))
    token = local.post("/auth/setup", json={"password": PASSWORD}).json()["token"]
    got = local.post("/auth/hello/enrol/begin", json={"current_password": PASSWORD}, headers=_auth(token))
    assert got.status_code == 409
    assert "localhost" in got.json()["detail"]


def test_enrolment_with_the_prf_from_create_alone(client, fake):
    local, token, note = _notebook(client)
    device = FakeAuthenticator()
    assert _enrol(local, token, device, with_assertion=False).status_code == 200
    _restart()
    opened = local.post("/auth/hello/unlock", json=_assertion(local, device))
    assert opened.status_code == 200, opened.text


def test_a_registration_for_another_challenge_is_refused(client, fake):
    local, token, _ = _notebook(client)
    device = FakeAuthenticator()
    b = local.post("/auth/hello/enrol/begin", json={"current_password": PASSWORD}, headers=_auth(token)).json()
    forged = {**b, "create_challenge": b64url(b"x" * 32)}
    body = {"ticket": b["ticket"], **device.create(forged, ORIGIN), "prf": b64url(device.prf(b"s" * 32))}
    assert local.post("/auth/hello/enrol/finish", json=body, headers=_auth(token)).status_code == 400
    assert fake.items == {}


def test_a_registration_without_user_verification_is_refused(client, fake):
    local, token, _ = _notebook(client)
    device = FakeAuthenticator()
    b = local.post("/auth/hello/enrol/begin", json={"current_password": PASSWORD}, headers=_auth(token)).json()
    body = {"ticket": b["ticket"], **device.create(b, ORIGIN, flags=0x41), "prf": b64url(device.prf(b"s" * 32))}
    assert local.post("/auth/hello/enrol/finish", json=body, headers=_auth(token)).status_code == 400


def test_no_protected_store_means_no_hello(client):
    pinstore.set_store(FakeStore(ok=False))
    try:
        local, token, _ = _notebook(client)
        got = local.post("/auth/hello/enrol/begin", json={"current_password": PASSWORD}, headers=_auth(token))
        assert got.status_code == 409
    finally:
        pinstore.set_store(None)


# --- unlocking ---------------------------------------------------------------------


@pytest.mark.parametrize("alg", [webauthn.ES256, webauthn.RS256])
def test_hello_opens_the_same_vault_on_this_computer(client, fake, alg):
    local, device, note = _with_hello(client, FakeAuthenticator(alg=alg))
    opened = local.post("/auth/hello/unlock", json=_assertion(local, device))
    assert opened.status_code == 200, opened.text
    assert opened.json()["vault_open"] is True
    token = opened.json()["token"]
    got = local.get(f"/entries/{note}", headers=_auth(token))
    assert got.status_code == 200 and got.json()["content"] == SECRET


def test_the_password_still_unlocks_with_hello_set(client, fake):
    local, _, _ = _with_hello(client)
    assert local.post("/auth/unlock", json={"password": PASSWORD}).status_code == 200


def test_a_bad_signature_opens_nothing(client, fake):
    local, device, _ = _with_hello(client)
    body = _assertion(local, device)
    sig = bytearray(unb64url(body["signature"]))
    sig[-1] ^= 1
    body["signature"] = b64url(bytes(sig))
    assert local.post("/auth/hello/unlock", json=body).status_code == 401
    assert vault.key() is None


def test_another_authenticator_opens_nothing(client, fake):
    local, _, _ = _with_hello(client)
    stranger = FakeAuthenticator()
    begin = local.post("/auth/hello/begin").json()
    body = {"ticket": begin["ticket"], **stranger.get(begin["challenge"], begin["rp_id"], ORIGIN), "prf": b64url(stranger.prf(b"s" * 32))}
    assert local.post("/auth/hello/unlock", json=body).status_code == 401
    assert vault.key() is None


def test_a_right_signature_with_the_wrong_prf_opens_nothing(client, fake):
    """Never a yes-or-no gate: the key is opened by the PRF output itself."""
    local, device, _ = _with_hello(client)
    body = _assertion(local, device, prf=b64url(b"\0" * 32))
    assert local.post("/auth/hello/unlock", json=body).status_code == 401
    assert vault.key() is None


def test_a_challenge_is_single_use(client, fake):
    local, device, _ = _with_hello(client)
    body = _assertion(local, device)
    assert local.post("/auth/hello/unlock", json=body).status_code == 200
    _restart()
    assert local.post("/auth/hello/unlock", json=body).status_code == 401


def test_a_challenge_expires(client, fake, monkeypatch):
    local, device, _ = _with_hello(client)
    body = _assertion(local, device)
    later = hellostore._now() + hellostore.CHALLENGE_SECONDS + 1
    monkeypatch.setattr(hellostore, "_now", lambda: later)
    assert local.post("/auth/hello/unlock", json=body).status_code == 401


def test_an_assertion_for_another_origin_or_without_verification_is_refused(client, fake):
    local, device, _ = _with_hello(client)
    begin = local.post("/auth/hello/begin").json()
    body = {"ticket": begin["ticket"], **device.get(begin["challenge"], begin["rp_id"], "http://localhost:9999"), "prf": b64url(device.prf(unb64url(begin["prf_salt"])))}
    assert local.post("/auth/hello/unlock", json=body).status_code == 401
    begin = local.post("/auth/hello/begin").json()
    body = {"ticket": begin["ticket"], **device.get(begin["challenge"], begin["rp_id"], ORIGIN, flags=0x01), "prf": b64url(device.prf(unb64url(begin["prf_salt"])))}
    assert local.post("/auth/hello/unlock", json=body).status_code == 401


def test_a_sign_count_that_goes_backwards_is_a_clone(client, fake):
    local, device, _ = _with_hello(client)
    assert local.post("/auth/hello/unlock", json=_assertion(local, device)).status_code == 200
    _restart()
    device.count = 0  # a copy of the key that never saw the later uses
    assert local.post("/auth/hello/unlock", json=_assertion(local, device)).status_code == 401


def test_an_authenticator_without_a_count_still_works(client, fake):
    local, device, _ = _with_hello(client, FakeAuthenticator(counts=False))
    for _ in range(2):
        assert local.post("/auth/hello/unlock", json=_assertion(local, device)).status_code == 200
        _restart()


def test_hello_is_never_offered_or_taken_from_another_device(client, fake):
    local, device, _ = _with_hello(client)
    body = _assertion(local, device)
    lan = TestClient(client.app, base_url="http://192.168.1.10:8795", client=("192.168.1.20", 50000))
    assert lan.post("/auth/hello/begin").status_code == 403
    assert lan.post("/auth/hello/unlock", json=body).status_code == 403
    tunnel = TestClient(client.app, base_url=ORIGIN, client=("127.0.0.1", 50000), headers={"X-Forwarded-For": "8.8.8.8"})
    assert tunnel.post("/auth/hello/unlock", json=body).status_code == 403
    assert vault.key() is None


def test_begin_without_a_record_says_to_use_the_password(client, fake):
    local, _, _ = _notebook(client)
    assert local.post("/auth/hello/begin").status_code == 404


# --- what drops it -------------------------------------------------------------------


def test_a_password_change_clears_hello(client, fake):
    local, device, _ = _with_hello(client)
    token = local.post("/auth/unlock", json={"password": PASSWORD}).json()["token"]
    answer = local.post(
        "/auth/change-password", json={"current_password": PASSWORD, "new_password": NEW_PASSWORD}, headers=_auth(token),
    )
    assert answer.status_code == 200, answer.text
    assert answer.json()["hello_cleared"] is True
    assert fake.items == {}


def test_a_vault_re_key_clears_hello(client, fake):
    local, _, _ = _with_hello(client)
    token = local.post("/auth/unlock", json={"password": PASSWORD}).json()["token"]
    assert local.post("/auth/rotate-vault-key", json={"current_password": PASSWORD}, headers=_auth(token)).status_code == 200
    assert fake.items == {}


def test_ending_every_session_for_a_restore_clears_hello(client, fake):
    _with_hello(client)
    routes_auth.end_every_session()
    assert fake.items == {}


def test_every_place_that_drops_the_pin_drops_hello_too():
    """The Hello record is bound like the PIN's, so it goes wherever the PIN goes."""
    for path in (ROOT / "src" / "tessellate").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        # `forgotten = pinstore.forget(` is "Forget PIN" itself, which leaves Hello be.
        for match in re.finditer(r"(?<!forgotten = )pinstore\.forget\(", text):
            after = text[match.end() : match.end() + 200]
            assert "hellostore.forget(" in after, f"{path.name}: a pinstore.forget without hellostore.forget"


def test_forget_removes_it_and_the_account_reports_the_state(client, fake):
    local, _, _ = _with_hello(client)
    token = local.post("/auth/unlock", json={"password": PASSWORD}).json()["token"]
    assert local.get("/auth/account", headers=_auth(token)).json()["hello"] == {"available": True, "set": True, "here": True}
    assert local.post("/auth/hello/forget", headers=_auth(token)).json() == {"forgotten": True}
    assert local.get("/auth/account", headers=_auth(token)).json()["hello"]["set"] is False
    assert fake.items == {}


def test_no_hello_material_in_the_database_or_data_dir(client, fake):
    local, device, _ = _with_hello(client)
    record = next(iter(fake.items.values()))
    data_dir = deps.get_config().data_dir
    for path in data_dir.rglob("*"):
        if path.is_file():
            blob = path.read_bytes()
            assert record.encode() not in blob, path
            assert device.cred_id not in blob, path


# --- private spaces -------------------------------------------------------------------


def test_hello_opens_the_private_spaces(client, fake):
    local, device, _ = _with_hello(client)
    token = local.post("/auth/unlock", json={"password": PASSWORD}).json()["token"]
    local.headers.update(_auth(token))
    assert local.post("/spaces", json={"name": "Vault", "is_private": True}).status_code == 200
    spacelock.close_all()
    status = local.get("/private-spaces/status").json()
    assert status["open"] is False and status["hello"] is True
    bad = _assertion(local, device, prf=b64url(b"\1" * 32))
    assert local.post("/private-spaces/unlock-hello", json=bad).status_code == 401
    assert local.get("/private-spaces/status").json()["open"] is False
    assert local.post("/private-spaces/unlock-hello", json=_assertion(local, device)).status_code == 200
    assert local.get("/private-spaces/status").json()["open"] is True


def test_pressing_the_hello_button_never_locks_out_the_password(client, fake):
    """Review 2026-11-10: `begin` once left a throttle attempt open each press,
    so six presses answered 429 to the password too."""
    local, _device, _ = _with_hello(client)
    for _ in range(10):
        assert local.post("/auth/hello/begin").status_code == 200
    assert local.post("/auth/unlock", json={"password": PASSWORD}).status_code == 200
