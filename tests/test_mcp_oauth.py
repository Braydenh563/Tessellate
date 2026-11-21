"""OAuth 2.1 for a remote MCP client (L-world-class-560, B52; core/mcp_oauth.py).

The MCP authorization spec's flow end to end, on the app's own port: the
metadata, dynamic registration, the authorize page that waits for the person,
approval on this computer with a scope, the code traded with its PKCE
verifier for a token that `/mcp` takes, and a refresh that rotates.
"""

from __future__ import annotations

import base64
import hashlib
import json
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from tessellate.core import deps, mcp_clients, mcp_oauth

REDIRECT = "https://claude.ai/api/mcp/auth_callback"
VERIFIER = "v" * 20 + "erifier-for-the-pkce-check-1234567890"
CHALLENGE = base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b"=").decode()


@pytest.fixture(autouse=True)
def _fresh():
    mcp_oauth.reset()
    yield
    mcp_oauth.reset()


def _register(client, **extra):
    reply = client.post("/oauth/register", json={"client_name": "Claude", "redirect_uris": [REDIRECT], **extra})
    return reply


def _authorize(client, cid, **extra):
    params = {
        "response_type": "code", "client_id": cid, "redirect_uri": REDIRECT, "state": "s1",
        "code_challenge": CHALLENGE, "code_challenge_method": "S256", "scope": "notes:read notes:write", **extra,
    }
    return client.get("/oauth/authorize", params=params, follow_redirects=False)


def _waiting_page(client, client_id):
    started = _authorize(client, client_id)
    assert started.status_code == 303, started.text
    return started.headers["location"]


def _signed_in(client, scope=None, writes=False):
    client_id = _register(client).json()["client_id"]
    wait = _waiting_page(client, client_id)
    (row,) = client.get("/mcp-oauth/requests").json()["requests"]
    rid = row["id"]
    approved = client.post(f"/mcp-oauth/requests/{rid}/approve", json={"writes": writes, "scope": scope or {}})
    assert approved.status_code == 200, approved.text
    back = client.get(wait, follow_redirects=False)
    assert back.status_code == 303
    code = parse_qs(urlsplit(back.headers["location"]).query)["code"][0]
    tokens = client.post("/oauth/token", data={
        "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT,
        "client_id": client_id, "code_verifier": VERIFIER,
    })
    assert tokens.status_code == 200, tokens.text
    return client_id, tokens.json()


def test_the_metadata_names_every_endpoint_on_this_port(client):
    resource = client.get("/.well-known/oauth-protected-resource").json()
    assert resource["resource"] == "http://testserver/mcp"
    assert resource["authorization_servers"] == ["http://testserver"]
    under_mcp = client.get("/.well-known/oauth-protected-resource/mcp").json()
    assert under_mcp == resource
    server = client.get("/.well-known/oauth-authorization-server").json()
    assert server["issuer"] == "http://testserver"
    assert server["code_challenge_methods_supported"] == ["S256"]
    for key in ("authorization_endpoint", "token_endpoint", "registration_endpoint"):
        assert server[key].startswith("http://testserver/oauth/")
    refused = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert refused.status_code == 401
    assert 'resource_metadata="http://testserver/.well-known/oauth-protected-resource"' in refused.headers["www-authenticate"]


def test_registration_takes_only_safe_redirects_and_public_clients(client):
    made = _register(client)
    assert made.status_code == 201
    body = made.json()
    assert body["client_id"].startswith("tsl_oc_") and body["token_endpoint_auth_method"] == "none"
    for uris in ([], ["http://evil.example/cb"], ["https://x.example/cb#frag"], ["javascript:alert(1)"]):
        reply = client.post("/oauth/register", json={"redirect_uris": uris})
        assert reply.status_code == 400 and reply.json()["error"] == "invalid_redirect_uri", uris
    local = client.post("/oauth/register", json={"redirect_uris": ["http://127.0.0.1:6274/cb"]})
    assert local.status_code == 201
    secret = _register(client, token_endpoint_auth_method="client_secret_post")
    assert secret.status_code == 400


def test_authorize_refuses_a_bad_request_without_redirecting(client):
    client_id = _register(client).json()["client_id"]
    for extra in ({"client_id": "nope"}, {"redirect_uri": "https://evil.example/cb"}, {"code_challenge_method": "plain"},
                  {"code_challenge": ""}, {"response_type": "token"}, {"scope": "everything"}):
        reply = _authorize(client, client_id, **extra)
        assert reply.status_code == 200 and "cannot go on" in reply.text, extra
    listed = client.get("/mcp-oauth/requests")
    assert listed.json()["requests"] == []


def test_the_waiting_page_shows_the_code_settings_shows_and_moves_on_after_approval(client):
    client_id = _register(client).json()["client_id"]
    wait = _waiting_page(client, client_id)
    page = client.get(wait)
    (row,) = client.get("/mcp-oauth/requests").json()["requests"]
    assert row["code"] in page.text and 'http-equiv="refresh"' in page.text
    assert "<script" not in page.text and "style=" not in page.text
    assert row["client_name"] == "Claude" and row["redirect_host"] == "claude.ai" and row["asks_writes"] is True
    assert "challenge" not in json.dumps(row)


def test_the_full_flow_gives_a_scoped_token_that_mcp_takes(client):
    from tessellate.entry import manager

    with deps.get_db().session() as session:
        inside = manager.create_entry(session, "Inside note", category_name="Work").id
        outside = manager.create_entry(session, "Outside note", category_name="Home").id
    _cid, tokens = _signed_in(client, scope={"categories": ["Work"]})
    assert tokens["token_type"] == "Bearer" and tokens["scope"] == "notes:read"
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    call = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "list_notes", "arguments": {}}}
    listed = json.loads(client.post("/mcp", json=call, headers=headers).json()["result"]["content"][0]["text"])
    assert {n["id"] for n in listed["notes"]} == {inside}
    assert outside not in {n["id"] for n in listed["notes"]}
    (grant,) = client.get("/mcp-clients").json()["clients"]
    assert grant["kind"] == "oauth" and grant["scope"]["categories"] == ["Work"] and grant["writes"] is False
    saved = deps.get_config().preferences_path.read_text(encoding="utf-8")
    assert tokens["access_token"] not in saved and tokens["refresh_token"] not in saved


def test_a_code_is_single_use_and_needs_its_verifier(client):
    client_id = _register(client).json()["client_id"]
    wait = _waiting_page(client, client_id)
    (row,) = client.get("/mcp-oauth/requests").json()["requests"]
    rid = row["id"]
    client.post(f"/mcp-oauth/requests/{rid}/approve", json={})
    code = parse_qs(urlsplit(client.get(wait, follow_redirects=False).headers["location"]).query)["code"][0]
    form = {"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT, "client_id": client_id}
    wrong = client.post("/oauth/token", data={**form, "code_verifier": "x" * 50})
    assert wrong.status_code == 400 and wrong.json()["error"] == "invalid_grant"
    again = client.post("/oauth/token", data={**form, "code_verifier": VERIFIER})
    assert again.status_code == 400, "a code tried once is gone, right or wrong"


def test_deny_sends_access_denied_back_and_a_refresh_rotates(client):
    client_id = _register(client).json()["client_id"]
    wait = _waiting_page(client, client_id)
    (row,) = client.get("/mcp-oauth/requests").json()["requests"]
    rid = row["id"]
    denied = client.post(f"/mcp-oauth/requests/{rid}/deny")
    assert denied.status_code == 200
    back = parse_qs(urlsplit(client.get(wait, follow_redirects=False).headers["location"]).query)
    assert back == {"error": ["access_denied"], "state": ["s1"]}
    client_id, tokens = _signed_in(client, writes=True)
    assert tokens["scope"] == "notes:read notes:write"
    fresh = client.post("/oauth/token", data={"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"], "client_id": client_id})
    assert fresh.status_code == 200
    ping = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
    old = client.post("/mcp", json=ping, headers={"Authorization": f"Bearer {tokens['access_token']}"})
    new = client.post("/mcp", json=ping, headers={"Authorization": f"Bearer {fresh.json()['access_token']}"})
    assert old.status_code == 401 and new.status_code == 200
    reused = client.post("/oauth/token", data={"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"], "client_id": client_id})
    assert reused.status_code == 400


def test_a_revoked_grant_stops_and_cannot_refresh(client):
    client_id, tokens = _signed_in(client)
    (grant,) = client.get("/mcp-clients").json()["clients"]
    client.delete(f"/mcp-clients/{grant['id']}")
    fresh = client.post("/oauth/token", data={"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"], "client_id": client_id})
    assert fresh.status_code == 400


def test_approval_is_on_this_computer_only_and_behind_the_lock(client):
    from tessellate.api import app as app_module
    from tessellate.api import routes_mcp_oauth
    from tessellate.api.app import create_app
    from tessellate.core import netbind

    rows = {id(router): gate for router, gate in app_module.ROUTERS}
    assert rows[id(routes_mcp_oauth.router)] == app_module.LOCKED
    assert rows[id(routes_mcp_oauth.open_router)] == app_module.OPEN
    client_id = _register(client).json()["client_id"]
    _waiting_page(client, client_id)
    (row,) = client.get("/mcp-oauth/requests").json()["requests"]
    deps.get_config().set_preference(netbind.LAN_PREF, True)
    away = TestClient(create_app(), client=("192.168.1.40", 51000))
    rid = row["id"]
    approved = away.post(f"/mcp-oauth/requests/{rid}/approve", json={})
    assert approved.status_code in (401, 403)
    deps.get_config().set_preference(netbind.LAN_PREF, False)
    meta = away.get("/.well-known/oauth-authorization-server")
    registered = away.post("/oauth/register", json={"redirect_uris": [REDIRECT]})
    assert meta.status_code == 403 and registered.status_code == 403


def test_the_grant_count_is_shared_with_the_tokens(client, monkeypatch):
    monkeypatch.setattr(mcp_clients, "MAX_CLIENTS", 1)
    client.post("/mcp-clients", json={"name": "One", "writes": False})
    client_id = _register(client).json()["client_id"]
    _waiting_page(client, client_id)
    (row,) = client.get("/mcp-oauth/requests").json()["requests"]
    rid = row["id"]
    approved = client.post(f"/mcp-oauth/requests/{rid}/approve", json={})
    assert approved.status_code == 409
    still = client.get("/mcp-oauth/requests").json()["requests"]
    assert still, "a refused approval leaves the sign-in waiting"


def test_the_docker_bridge_counts_as_this_computer_only_when_compose_says_so(client, monkeypatch):
    """docker/compose.yaml publishes on the host's loopback and sets the switch:
    the host then arrives from the bridge's private address. A public address
    is never trusted that way, and without the switch the bridge is another device."""
    from tessellate.api.app import create_app
    from tessellate.api.routes_mcp import PUBLISHED_ENV

    bridge = TestClient(create_app(), client=("172.17.0.1", 51000))
    public = TestClient(create_app(), client=("8.8.8.8", 51000))
    path = "/.well-known/oauth-authorization-server"
    without = bridge.get(path)
    monkeypatch.setenv(PUBLISHED_ENV, "1")
    with_switch, from_public = bridge.get(path), public.get(path)
    assert without.status_code == 403 and with_switch.status_code == 200
    assert from_public.status_code == 403
