"""A name instead of localhost, and a domain behind a proxy, set in Settings (the owner: "customise the domain name")."""

from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from tessellate.api import routes_auth
from tessellate.core import netbind
from tests._js_scope import unwrapped

PASSWORD = "testpassword123"
PHONE = ("192.168.0.50", 50000)


@pytest.fixture(autouse=True)
def _clean_names(monkeypatch):
    monkeypatch.delenv(netbind.LOCAL_NAME_ENV, raising=False)
    monkeypatch.delenv(netbind.ALLOWED_HOSTS_ENV, raising=False)
    monkeypatch.setattr(netbind, "_pref_hosts", frozenset())
    monkeypatch.setattr(netbind, "_pref_local", "")


@pytest.fixture()
def here(app_state):
    from tessellate.api.app import create_app

    routes_auth._active_tokens.clear()
    routes_auth._clear_unlock_failures()
    client = TestClient(create_app(), base_url="http://localhost:8000", client=("127.0.0.1", 50001))
    token = client.post("/auth/setup", json={"password": PASSWORD}).json()["token"]
    client.headers["X-Auth-Token"] = token
    return client


def test_parse_host_reads_a_name_a_url_or_host_and_port_and_refuses_the_rest():
    assert netbind.parse_host("Notes.Example.com") == "notes.example.com"
    assert netbind.parse_host("https://notes.example.com/path") == "notes.example.com"
    assert netbind.parse_host("notes.example.com:8443") == "notes.example.com"
    for bad in ("*", "*.example.com", "10.0.0.5", "a b", "", "-x.com", "bad_name.com"):
        assert netbind.parse_host(bad) == "", bad
    assert netbind.parse_hosts("a.com; B.com, a.com ,") == ["a.com", "b.com"]


def test_the_settings_names_join_the_environments(app_state, monkeypatch):
    from tessellate.core import deps

    config = deps.get_config()
    config.set_preference(netbind.LOCAL_NAME_PREF, "notes")
    config.set_preference(netbind.ALLOWED_HOSTS_PREF, ["notes.example.com"])
    netbind.apply_address_prefs(config)
    assert netbind.local_name() == "notes.localhost"
    assert netbind.extra_allowed_hosts() == {"notes.example.com"}
    monkeypatch.setenv(netbind.LOCAL_NAME_ENV, "other")
    monkeypatch.setenv(netbind.ALLOWED_HOSTS_ENV, "proxy.example.com")
    assert netbind.local_name() == "other.localhost", "the environment wins for the short name"
    assert netbind.extra_allowed_hosts() == {"notes.example.com", "proxy.example.com"}


def test_a_saved_short_name_is_accepted_on_loopback_only(here):
    reply = here.post("/auth/address-names", json={"local_name": "notes"})
    assert reply.status_code == 200 and reply.json()["names"]["local_name"] == "notes"
    assert netbind.host_allowed("notes.localhost:8000", on_loopback=True)
    assert not netbind.host_allowed("notes.localhost:8000", on_loopback=False)
    assert not netbind.host_allowed("evil.localhost:8000", on_loopback=True)
    assert here.post("/auth/address-names", json={"local_name": ""}).json()["names"]["local_name"] == ""
    assert not netbind.host_allowed("notes.localhost:8000", on_loopback=True)


def test_a_new_domain_asks_for_the_password_and_is_then_allowed(here):
    refused = here.post("/auth/address-names", json={"allowed_hosts": ["notes.example.com"]})
    assert refused.status_code == 401
    wrong = here.post("/auth/address-names", json={"allowed_hosts": ["notes.example.com"], "current_password": "nope-nope-nope"})
    assert wrong.status_code == 401
    assert not netbind.host_allowed("notes.example.com")
    ok = here.post("/auth/address-names", json={"allowed_hosts": ["Notes.Example.com"], "current_password": PASSWORD})
    assert ok.status_code == 200 and ok.json()["names"]["allowed_hosts"] == ["notes.example.com"]
    assert netbind.host_allowed("notes.example.com")


def test_removing_a_domain_or_keeping_the_list_needs_no_password(here):
    here.post("/auth/address-names", json={"allowed_hosts": ["a.example.com", "b.example.com"], "current_password": PASSWORD})
    keep = here.post("/auth/address-names", json={"allowed_hosts": ["b.example.com", "a.example.com"]})
    assert keep.status_code == 200
    fewer = here.post("/auth/address-names", json={"allowed_hosts": ["b.example.com"]})
    assert fewer.json()["names"]["allowed_hosts"] == ["b.example.com"]
    assert not netbind.host_allowed("a.example.com")


def test_bad_names_are_refused_with_a_plain_sentence(here):
    for body in ({"local_name": "has space"}, {"local_name": "x" * 64}):
        reply = here.post("/auth/address-names", json=body)
        assert reply.status_code in (400, 422), body
    star = here.post("/auth/address-names", json={"allowed_hosts": ["*"], "current_password": PASSWORD})
    assert star.status_code == 400 and "isn't a domain name" in star.json()["detail"]
    many = here.post("/auth/address-names", json={"allowed_hosts": [f"h{i}.example.com" for i in range(9)], "current_password": PASSWORD})
    assert many.status_code == 400 and "At most 8" in many.json()["detail"]


def test_a_phone_cannot_change_the_names(here, app_state):
    from tessellate.api.app import create_app
    from tessellate.core import deps, lantrust

    lantrust.set_flag(deps.get_config().data_dir, "ask_new_devices", False)
    phone = TestClient(create_app(), client=PHONE)
    phone.headers["X-Auth-Token"] = phone.post("/auth/unlock", json={"password": PASSWORD}).json()["token"]
    reply = phone.post("/auth/address-names", json={"local_name": "notes"})
    assert reply.status_code == 403


def test_the_lan_state_carries_the_names_and_what_the_environment_sets(here, monkeypatch):
    monkeypatch.setenv(netbind.LOCAL_NAME_ENV, "fromenv")
    names = here.get("/auth/lan-access").json()["names"]
    assert names["local_name_env"] == "fromenv" and names["allowed_hosts"] == []


# --- the Settings group ---------------------------------------------------------


def test_the_settings_group_is_wired_and_a_new_domain_asks_for_the_password():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    html = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    js = unwrapped((root / "frontend" / "js" / "settings-controls.js").read_text(encoding="utf-8"))
    for ident in ("account-local-name", "account-domains", "account-names-save", "address-names-help"):
        assert f'id="{ident}"' in html, ident
    assert 'data-help-for="address-names-help"' in html
    body = js[js.index("async function saveAddressNames("):]
    body = body[: body.index("\n}\n")]
    assert "askPasswordPrompt" in body and "/auth/address-names" in body
    # Only a name not already saved asks; removing one does not.
    assert "added" in body and "dataset.saved" in js
    assert "renderAddressNames(state)" in js
