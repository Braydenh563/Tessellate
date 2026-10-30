"""What a phone on the network may and may not make this computer do.

The owner, 2026-10-11: "I dont want to invite potential hacking though my open
lan connection to either my phone or my computer", "even downloading files
... i just worry that someone coule use that to download malicious files to
my computer" and "do a really deep security and bug scan". The route guard
itself is `api/this_computer.py`; tests/test_this_computer_only.py lists the
routes. These are the cases a route list cannot see: a preference that
points the computer somewhere, a page that thought it was the desktop app,
a notebook with no password while the network port is still open.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tessellate.api import routes_auth
from tessellate.core import netbind

PHONE = ("192.168.0.50", 50000)
PASSWORD = "testpassword123"


@pytest.fixture()
def app(app_state):
    from tessellate.api.app import create_app
    from tessellate.core import deps
    from tests.fakes import FakeEmbeddingService, FakeOllama

    deps.override_ai(ollama=FakeOllama(running=False), embeddings=FakeEmbeddingService(available=False))
    routes_auth._active_tokens.clear()
    routes_auth._clear_unlock_failures()
    return create_app()


def _signed_in(client: TestClient) -> TestClient:
    token = client.post("/auth/unlock", json={"password": PASSWORD}).json()["token"]
    client.headers["X-Auth-Token"] = token
    return client


@pytest.fixture()
def here(app):
    client = TestClient(app)
    token = client.post("/auth/setup", json={"password": PASSWORD}).json()["token"]
    client.headers["X-Auth-Token"] = token
    return client


@pytest.fixture()
def phone(app, here):
    from tessellate.core import deps, lantrust

    #: These tests are about what a signed-in phone may change, not about the
    #: new-device question (tests/test_lan.py holds that).
    lantrust.set_flag(deps.get_config().data_dir, "ask_new_devices", False)
    return _signed_in(TestClient(app, client=PHONE))


# --- the page knows which side it is on (root of the owner's report) -------


def test_health_says_the_desktop_only_to_this_computer(app, monkeypatch):
    """A phone read `desktop: true` and so saved exports onto this computer's
    disk and offered "Open folder" there, which opened Explorer."""
    monkeypatch.setenv("TESSELLATE_DESKTOP", "1")
    mine = TestClient(app).get("/health").json()
    theirs = TestClient(app, client=PHONE).get("/health").json()
    assert mine["desktop"] is True and mine["this_computer"] is True
    assert theirs["desktop"] is False and theirs["this_computer"] is False
    assert theirs["os_notify"] is False


# --- no password, network still open -----------------------------------------


def test_a_notebook_with_no_password_answers_no_other_device(app):
    """After "I don't have it" (reset) the LAN listener keeps running until
    the next launch, and with no password every route used to wave anyone in:
    measured 200 on /entries and a 200 /auth/setup that took the notebook."""
    phone = TestClient(app, client=PHONE)
    assert phone.get("/entries").status_code == 401
    assert phone.post("/auth/setup", json={"password": PASSWORD}).status_code == 403
    assert TestClient(app).get("/entries").status_code == 200


def test_a_container_still_sets_up_from_the_network(app, monkeypatch):
    """Brief 40: a published container port has no window to set up from."""
    monkeypatch.setattr(netbind, "explicit_bind", lambda: True)
    phone = TestClient(app, client=PHONE)
    assert phone.post("/auth/setup", json={"password": PASSWORD}).status_code == 200


# --- account and network switches --------------------------------------------


def test_the_phone_cannot_loosen_the_computers_own_sign_in(phone, here):
    off = {"enabled": False, "current_password": PASSWORD}
    assert phone.post("/auth/password-on-open", json=off).status_code == 403
    assert phone.post("/auth/password-on-open", json={"enabled": True}).status_code == 200
    assert here.post("/auth/password-on-open", json=off).status_code == 200


def test_the_phone_cannot_turn_the_network_on_or_remake_its_certificate(phone):
    on = {"enabled": True, "current_password": PASSWORD}
    assert phone.post("/auth/lan-access", json=on).status_code == 403
    assert phone.post("/auth/lan-certificate").status_code == 403
    # Off is open to any signed-in device (it only lets fewer in), and it
    # signs every other device out, the phone that asked included.
    assert phone.post("/auth/lan-access", json={"enabled": False}).status_code == 200
    assert phone.post("/auth/lan-certificate").status_code == 401


def test_a_short_old_pin_cannot_open_the_notebook_to_the_network(app, session):
    """Unlock still takes a 4-character password from before the 8-character
    floor; putting the notebook on a network (a campus wifi) does not."""
    from tessellate.core.database import User

    here = TestClient(app)
    here.post("/auth/setup", json={"password": PASSWORD})
    user = session.query(User).one()
    user.password_hash = routes_auth._hash_password("1234")
    session.commit()
    here = _signed_in_with(here, "1234")
    answer = here.post("/auth/lan-access", json={"enabled": True, "current_password": "1234"})
    assert answer.status_code == 400 and "at least 8 characters" in answer.json()["detail"]


def _signed_in_with(client: TestClient, password: str) -> TestClient:
    token = client.post("/auth/unlock", json={"password": password}).json()["token"]
    client.headers["X-Auth-Token"] = token
    return client


def test_live_budgets_replay_only_from_this_computer(phone):
    """The live bench replays reads to 127.0.0.1 with the caller's token."""
    assert phone.get("/models/bench/budgets?live=true").status_code == 403
    assert phone.get("/models/bench/budgets").status_code == 200


def test_the_recovery_key_save_dialog_opens_only_here(phone):
    assert phone.post("/auth/recovery-key/save", json={"text": "x" * 40}).status_code == 403


# --- files written to this computer's disk -----------------------------------


def test_the_phone_cannot_write_a_file_into_the_exports_folder(phone, here):
    import base64

    body = {"filename": "invoice.exe", "content_base64": base64.b64encode(b"MZ").decode()}
    assert phone.post("/files/save", json=body).status_code == 403
    assert here.post("/files/save", json=body).status_code == 200


# --- preferences that point this computer somewhere ---------------------------


@pytest.mark.parametrize(
    "key, start, looser, tighter",
    [
        ("searxng_url", "", "http://192.168.0.1:8080", None),
        ("export_save_dir", "", "/tmp", None),
        #: lansec-1025: where every backup is copied on this computer. A phone
        #: could name a UNC path (`\\\\host\\share`), which Windows opens over
        #: SMB with the owner's NTLM sign-in, and copy the notebook there.
        ("backup_copy_dir", "", "/tmp", None),
        ("update_beta", False, True, False),
        ("update_channel", "stable", "main", None),
        ("show_console_on_startup", False, True, None),
        ("close_to_tray", False, True, None),
        ("new_window_on_launch", False, True, None),
        ("desktop_companion", False, True, None),
        ("searxng_autostart", False, True, False),
        ("semantic_auto_install", False, True, False),
        ("auto_update_enabled", False, True, False),
        ("update_check_enabled", False, True, False),
        ("web_search_enabled", False, True, False),
        ("local_only_ai", True, False, True),
        ("session_idle_ttl_minutes", 60, 100000, 5),
    ],
)
def test_host_preferences_only_tighten_from_another_device(phone, here, key, start, looser, tighter):
    assert here.put("/preferences", json={key: start}).status_code == 200
    refused = phone.put("/preferences", json={key: looser})
    assert refused.status_code == 403, (key, refused.text)
    assert "Not available on this device" in refused.json()["detail"]
    assert phone.put("/preferences", json={key: start}).status_code == 200  # no change is no loosening
    if tighter is not None:
        assert phone.put("/preferences", json={key: tighter}).status_code == 200
    assert here.put("/preferences", json={key: looser}).status_code == 200


def test_the_phone_keeps_every_ordinary_preference(phone):
    assert phone.put("/preferences", json={"display_name": "Bray", "recycle_bin_days": 10}).status_code == 200


def test_an_imported_settings_file_skips_host_settings_from_a_phone(phone):
    from tessellate.api.routes_settings import SETTINGS_FILE_KIND, SETTINGS_FILE_VERSION

    payload = {
        "kind": SETTINGS_FILE_KIND,
        "version": SETTINGS_FILE_VERSION,
        "preferences": {"searxng_url": "http://10.0.0.9:8080", "display_name": "Bray"},
    }
    answer = phone.post("/preferences/import", json=payload).json()
    assert answer["applied"] == ["display_name"]
    assert {s["key"] for s in answer["skipped"]} == {"searxng_url"}


def test_the_update_question_cannot_be_answered_yes_from_a_phone(phone):
    assert phone.post("/update/choice", json={"check": True}).status_code == 403
    assert phone.post("/update/choice", json={"check": False}).status_code == 200


# --- path traversal on every file route ---------------------------------------


@pytest.mark.parametrize(
    "method, path",
    [
        ("get", "/files/exports/..%2F..%2Fconfig.json"),
        ("get", "/files/exports/..%5C..%5Cconfig.json"),
        ("get", "/media/..%2Fmemorymap.db"),
        ("get", "/media/meta/..%2F..%2Fpreferences.json"),
        ("get", "/media/text/..%2F..%2Fpreferences.json"),
        ("get", "/import/reports/..%2F..%2Fpreferences"),
        ("get", "/translate/files/..%2F..%2Fpreferences.json"),
        ("delete", "/backups/..%2Fmemorymap.db"),
        ("delete", "/backups/..%2F..%2Fpreferences.json"),
        ("delete", "/backups/.."),
        ("delete", "/backups/%2E%2E"),
    ],
)
def test_no_file_route_reaches_outside_its_folder(here, app_state, method, path):
    before = sorted(p.name for p in app_state.data_dir.iterdir())
    answer = getattr(here, method)(path)
    # 405: a decoded "/" leaves no route that matches, which is also no file.
    assert answer.status_code in (400, 404, 405, 422), (path, answer.status_code)
    assert set(before) <= {p.name for p in app_state.data_dir.iterdir()}  # nothing deleted


# --- headers on the network port ----------------------------------------------


def test_https_answers_carry_hsts_and_plain_http_does_not(app):
    secure = TestClient(app, base_url="https://192.168.0.5:8443", client=PHONE).get("/health")
    plain = TestClient(app).get("/health")
    assert secure.headers.get("strict-transport-security", "").startswith("max-age=")
    assert "strict-transport-security" not in plain.headers


def test_a_phone_cannot_loosen_the_lan_options_or_allow_a_network_even_with_the_password(phone):
    """secscan-1011 guards the loosening direction inline (the Host is checked
    too, which a dependency would not), so the proof is the answer: 403 to the
    phone for each, 200 for the safer direction."""
    loosen = phone.post(
        "/auth/lan-options", json={"name": "any_network", "enabled": True, "current_password": PASSWORD}
    )
    assert loosen.status_code == 403 and "Not available on this device" in loosen.json()["detail"]
    stop_asking = phone.post(
        "/auth/lan-options", json={"name": "ask_new_devices", "enabled": False, "current_password": PASSWORD}
    )
    assert stop_asking.status_code == 403
    allow = phone.post("/auth/lan-networks/allow", json={"current_password": PASSWORD})
    assert allow.status_code == 403 and "Not available on this device" in allow.json()["detail"]
    #: Answering a waiting device is the same call a phone must not make.
    assert phone.post("/auth/lan-devices/abc/allow").status_code == 403
    safer = phone.post("/auth/lan-options", json={"name": "ask_new_devices", "enabled": True})
    assert safer.status_code == 200
