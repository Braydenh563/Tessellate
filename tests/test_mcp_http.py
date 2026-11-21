"""The tool server over streamable HTTP at `/mcp` (INBOX 1860, L687, B52).

Each outside client has its own token, made in Settings and shown once; only
its hash is kept. A request without a live token is refused, a revoked token
stops working at once, a token reads only unless it was made able to change
notes, and a request from another device is refused unless LAN mode is on.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from tessellate.core import deps, mcp_clients

ROOT = Path(__file__).resolve().parents[1]
FIXED_NOW = 1_785_000_000.0  # 2026-07-25, the suite's clock, never the real one


def _rpc(method, msg_id=1, **params):
    return {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params}


def _post(client, token, body):
    headers = {"Accept": "application/json, text/event-stream"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return client.post("/mcp", json=body, headers=headers)


def _made(client, name="Claude", writes=False):
    reply = client.post("/mcp-clients", json={"name": name, "writes": writes})
    assert reply.status_code == 200, reply.text
    return reply.json()


def test_a_request_without_a_live_token_is_refused(client):
    made = _made(client)
    for token in (None, "", "nope", made["token"] + "x", made["token"][:-1]):
        reply = _post(client, token, _rpc("tools/list"))
        assert reply.status_code == 401, token
        assert reply.headers["www-authenticate"].startswith("Bearer")
    reply = _post(client, made["token"], _rpc("tools/list"))
    assert reply.status_code == 200


def test_the_token_is_shown_once_and_only_its_hash_is_kept(client):
    made = _made(client)
    assert made["token"].startswith(mcp_clients.TOKEN_PREFIX)
    listed = client.get("/mcp-clients").json()["clients"]
    assert [row["name"] for row in listed] == ["Claude"]
    assert "token" not in listed[0] and "hash" not in listed[0]
    saved = deps.get_config().preferences_path.read_text(encoding="utf-8")
    assert made["token"] not in saved


def test_a_revoked_token_is_refused_at_once(client):
    made = _made(client)
    reply = _post(client, made["token"], _rpc("ping"))
    assert reply.status_code == 200
    revoked = client.delete(f"/mcp-clients/{made['client']['id']}")
    assert revoked.status_code == 200
    reply = _post(client, made["token"], _rpc("ping"))
    assert reply.status_code == 401
    reply = client.get("/mcp-clients")
    assert reply.json()["clients"] == []
    again = client.delete(f"/mcp-clients/{made['client']['id']}")
    assert again.status_code == 404


def test_undo_brings_a_revoked_token_back_within_the_hour(client, monkeypatch):
    """Revoke and Make a link are each other's Undo (test_undo_coverage, no exemption)."""
    clock = [FIXED_NOW]
    monkeypatch.setattr(mcp_clients, "_now", lambda: clock[0])
    made = _made(client)
    cid = made["client"]["id"]
    reply = client.delete(f"/mcp-clients/{cid}")
    assert reply.status_code == 200
    reply = client.post(f"/mcp-clients/{cid}/restore")
    assert reply.status_code == 200
    reply = _post(client, made["token"], _rpc("ping"))
    assert reply.status_code == 200
    reply = client.post(f"/mcp-clients/{cid}/restore")
    assert reply.status_code == 404
    reply = client.delete(f"/mcp-clients/{cid}")
    assert reply.status_code == 200
    clock[0] += mcp_clients.RESTORE_WINDOW + 1
    reply = client.post(f"/mcp-clients/{cid}/restore")
    assert reply.status_code == 404
    reply = _post(client, made["token"], _rpc("ping"))
    assert reply.status_code == 401
    saved = deps.get_config().get_preference(mcp_clients.PREF, [])
    reply = client.get("/mcp-clients")
    assert reply.json()["clients"] == []
    _made(client, "Next")
    assert [row["name"] for row in deps.get_config().get_preference(mcp_clients.PREF, [])] == ["Next"], saved


def test_a_token_reads_only_unless_made_to_write(client):
    reader = _made(client, "Reader")
    writer = _made(client, "Writer", writes=True)
    names = lambda token: {t["name"] for t in _post(client, token, _rpc("tools/list")).json()["result"]["tools"]}  # noqa: E731
    assert "count_notes" in names(reader["token"]) and "create_note" not in names(reader["token"])
    assert "create_note" in names(writer["token"])
    refused = _post(client, reader["token"], _rpc("tools/call", name="create_note", arguments={"content": "x"}))
    assert refused.json()["result"]["isError"] is True
    made = _post(client, writer["token"], _rpc("tools/call", name="create_note", arguments={"content": "From outside"}))
    assert made.json()["result"]["isError"] is False
    deleted = _post(client, writer["token"], _rpc("tools/call", name="delete_note", arguments={"id": 1}))
    assert deleted.json()["result"]["isError"] is True, "destructive tools are never offered"


def test_a_token_does_not_change_the_stdio_writes_switch(client):
    from tessellate import mcp_server

    _post(client, _made(client, writes=True)["token"], _rpc("tools/list"))
    assert mcp_server.writes_allowed() is False


def test_each_call_is_counted_on_the_token_row(client, monkeypatch):
    monkeypatch.setattr(mcp_clients, "_now", lambda: FIXED_NOW)
    made = _made(client)
    _post(client, made["token"], _rpc("tools/call", name="count_notes", arguments={}))
    _post(client, made["token"], _rpc("tools/list", msg_id=2))
    row = client.get("/mcp-clients").json()["clients"][0]
    assert row["calls"] == 2 and row["last_used"] == FIXED_NOW
    assert row["created_at"] == FIXED_NOW


def test_a_notification_gets_202_and_no_body(client):
    made = _made(client)
    reply = _post(client, made["token"], {"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert reply.status_code == 202 and reply.content == b""


def test_initialize_answers_the_protocol_and_names_the_client(client):
    made = _made(client, "Desk Claude")
    reply = _post(client, made["token"], _rpc("initialize", protocolVersion="2025-06-18", clientInfo={"name": "x"}))
    assert reply.status_code == 200
    assert reply.json()["result"]["protocolVersion"] == "2025-06-18"
    from tessellate import mcp_server

    assert mcp_server._client["name"] == "", "an HTTP client never renames the stdio one"


def test_a_get_is_405_and_a_bad_body_is_a_parse_error(client):
    made = _made(client)
    reply = client.get("/mcp", headers={"Authorization": f"Bearer {made['token']}"})
    assert reply.status_code == 405
    bad = client.post("/mcp", content=b"{nope", headers={"Authorization": f"Bearer {made['token']}", "Content-Type": "application/json"})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == -32700


def test_another_device_is_refused_unless_lan_mode_is_on(client):
    from tessellate.api.app import create_app
    from tessellate.core import netbind

    made = _made(client)
    away = TestClient(create_app(), client=("192.168.1.40", 51000))
    reply = _post(away, made["token"], _rpc("ping"))
    assert reply.status_code == 403
    deps.get_config().set_preference(netbind.LAN_PREF, True)
    reply = _post(away, made["token"], _rpc("ping"))
    assert reply.status_code == 200


def test_the_client_list_is_behind_the_lock(client):
    """Making a token is a Settings act: the route sits behind `require_unlock`
    like every other one (tests/test_every_route_is_locked.py); `/mcp` itself is
    open there and checks its own bearer token."""
    from tessellate.api import app as app_module
    from tessellate.api import routes_mcp

    rows = {id(router): gate for router, gate in app_module.ROUTERS}
    assert rows[id(routes_mcp.router)] == app_module.LOCKED
    assert rows[id(routes_mcp.open_router)] == app_module.OPEN


def test_names_are_cleaned_and_the_count_is_capped(client):
    blank = client.post("/mcp-clients", json={"name": "   ", "writes": False})
    assert blank.status_code == 422
    for n in range(mcp_clients.MAX_CLIENTS):
        _made(client, f"Client {n}")
    over = client.post("/mcp-clients", json={"name": "One more", "writes": False})
    assert over.status_code == 409


def test_starting_and_listing_load_no_embedding_model(tmp_path):
    """L687: the tool server never loads an embedding model to start or to
    list its tools; the first search that needs one loads it (ledger 319)."""
    probe = (
        "import io, json, sys\n"
        "from tessellate import mcp_server\n"
        "from tessellate.core import deps\n"
        "deps.init_app_state()\n"
        "mcp_server.handle_request({'jsonrpc':'2.0','id':1,'method':'initialize','params':{}})\n"
        "mcp_server.handle_request({'jsonrpc':'2.0','id':2,'method':'tools/list'})\n"
        "heavy = [m for m in ('fastembed','onnxruntime','sentence_transformers','torch','numpy') if m in sys.modules]\n"
        "print(json.dumps({'heavy': heavy, 'model': deps.get_embeddings()._st_model is not None}))\n"
    )
    env = {"PYTHONPATH": str(ROOT / "src"), "TESSELLATE_DATA_DIR": str(tmp_path), "PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}
    out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, env=env, timeout=60, check=True)
    import json

    seen = json.loads(out.stdout.strip().splitlines()[-1])
    assert seen == {"heavy": [], "model": False}
