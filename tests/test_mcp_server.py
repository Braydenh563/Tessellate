"""The stdio MCP server (mcp_server.py, ROADMAP.md item 38).

`handle_request` is pure, no stdio touched, so every case here calls it
directly rather than spawning a subprocess. `serve()`'s own line-reading
loop gets one end-to-end test over real StringIO streams.
"""

from __future__ import annotations

import io
import json

from tessellate.ai import tools
from tessellate.core import deps
from tessellate.mcp_server import handle_request, offered_tools, serve, writes_allowed


def test_offered_tools_excludes_every_destructive_tool(app_state):
    names = {spec.name for spec in offered_tools()}
    for spec in tools.TOOLS.values():
        if spec.destructive:
            assert spec.name not in names


def test_offered_tools_excludes_a_tool_disabled_in_settings(app_state):
    from tessellate.core import deps

    deps.get_config().set_preference("disabled_tools", ["count_notes"])
    names = {spec.name for spec in offered_tools()}
    assert "count_notes" not in names


def test_initialize_returns_protocol_info(app_state):
    response = handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert response["id"] == 1
    assert response["result"]["protocolVersion"]
    assert response["result"]["serverInfo"]["name"] == "memorymap-ai"


def test_a_notification_gets_no_response():
    assert handle_request({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert handle_request({"jsonrpc": "2.0", "method": "notifications/cancelled"}) is None


def test_ping():
    response = handle_request({"jsonrpc": "2.0", "id": "abc", "method": "ping"})
    assert response == {"jsonrpc": "2.0", "id": "abc", "result": {}}


def test_an_unknown_method_is_a_json_rpc_error():
    response = handle_request({"jsonrpc": "2.0", "id": 2, "method": "not/a/real/method"})
    assert response["error"]["code"] == -32601


def test_an_unknown_method_notification_gets_no_response():
    assert handle_request({"jsonrpc": "2.0", "method": "not/a/real/method"}) is None


def test_tools_list_shape(app_state):
    response = handle_request({"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
    listed = response["result"]["tools"]
    assert listed  # the registry is never empty
    for entry in listed:
        assert set(entry) == {"name", "description", "inputSchema", "annotations"}


def test_tools_call_runs_a_real_tool(app_state):
    response = handle_request(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "count_notes", "arguments": {}},
        }
    )
    result = response["result"]
    assert result["isError"] is False
    payload = json.loads(result["content"][0]["text"])
    assert "total" in payload or "count" in payload or isinstance(payload, dict)


def test_tools_call_rejects_an_unknown_tool(app_state):
    response = handle_request(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "not_a_real_tool", "arguments": {}},
        }
    )
    result = response["result"]
    assert result["isError"] is True
    assert "Unknown or unavailable" in result["content"][0]["text"]


def test_tools_call_rejects_a_destructive_tool_even_by_name(app_state):
    destructive = next(name for name, spec in tools.TOOLS.items() if spec.destructive)
    response = handle_request(
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {"name": destructive, "arguments": {}},
        }
    )
    result = response["result"]
    assert result["isError"] is True


def test_serve_reads_one_line_writes_one_line(app_state):
    request = json.dumps({"jsonrpc": "2.0", "id": 7, "method": "ping"})
    stdin = io.StringIO(request + "\n")
    stdout = io.StringIO()
    serve(stdin=stdin, stdout=stdout)
    lines = [line for line in stdout.getvalue().splitlines() if line]
    assert len(lines) == 1
    assert json.loads(lines[0])["result"] == {}


def test_serve_skips_blank_and_malformed_lines(app_state):
    stdin = io.StringIO("\n   \nnot json at all\n" + json.dumps({"jsonrpc": "2.0", "id": 8, "method": "ping"}) + "\n")
    stdout = io.StringIO()
    serve(stdin=stdin, stdout=stdout)
    lines = [line for line in stdout.getvalue().splitlines() if line]
    assert len(lines) == 1
    assert json.loads(lines[0])["id"] == 8


def test_chat_only_and_interactive_tools_are_not_listed(app_state):
    names = {spec.name for spec in offered_tools()}
    for spec in tools.TOOLS.values():
        if spec.ends_turn:
            assert spec.name not in names
    for name in ("ask_user", "make_plan", "compress_chat", "run_skill", "get_app_navigation", "search_chat_history"):
        assert name not in names


def test_annotations_mark_reads_and_writes(app_state):
    app_state.set_preference("mcp_writes_enabled", True)
    listed = {
        entry["name"]: entry["annotations"]
        for entry in handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]
    }
    assert listed["count_notes"]["readOnlyHint"] is True
    assert listed["create_note"]["readOnlyHint"] is False
    assert all(a["destructiveHint"] is False for a in listed.values())


def test_the_icon_prefix_is_stripped_from_a_label(app_state):
    response = handle_request(
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "list_categories", "arguments": {}}}
    )
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload.get("label") and not payload["label"].startswith("ph:")


def test_protocol_version_follows_a_supported_client(app_state):
    def init(version):
        params = {"protocolVersion": version} if version else {}
        return handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": params})["result"]

    assert init("2025-03-26")["protocolVersion"] == "2025-03-26"
    assert init("2025-06-18")["protocolVersion"] == "2025-06-18"
    assert init("2099-01-01")["protocolVersion"] == "2025-06-18"  # the newest we speak
    assert init(None)["protocolVersion"] == "2024-11-05"


# --- resources (notes) and prompts (skills): OPEN ledger 319 -----------------


def _rpc(method, params=None, msg_id=1):
    message = {"jsonrpc": "2.0", "id": msg_id, "method": method}
    if params is not None:
        message["params"] = params
    return handle_request(message)


def _make_note(text):
    deps.get_config().set_preference("mcp_writes_enabled", True)
    response = _rpc("tools/call", {"name": "create_note", "arguments": {"content": text}})
    payload = json.loads(response["result"]["content"][0]["text"])
    return payload.get("id") or payload["note"]["id"]


def test_the_server_declares_what_it_serves(app_state):
    caps = _rpc("initialize")["result"]["capabilities"]
    assert set(caps) == {"tools", "resources", "prompts"}


def test_resources_list_names_notes_by_uri_and_read_returns_the_text(app_state):
    note_id = _make_note("Garden plan\nPlant the beans in May.")
    listed = _rpc("resources/list")["result"]["resources"]
    entry = next(r for r in listed if r["uri"] == f"memorymap://note/{note_id}")
    assert entry["name"].startswith("Garden plan")
    assert entry["mimeType"] == "text/markdown"
    read = _rpc("resources/read", {"uri": entry["uri"]})["result"]["contents"][0]
    assert read["uri"] == entry["uri"] and read["mimeType"] == "text/markdown"
    assert "Plant the beans in May." in read["text"]


def test_a_resource_template_describes_the_note_uri(app_state):
    templates = _rpc("resources/templates/list")["result"]["resourceTemplates"]
    assert templates[0]["uriTemplate"] == "memorymap://note/{id}"


def test_reading_an_unknown_or_malformed_resource_is_an_error_not_a_crash(app_state):
    missing = _rpc("resources/read", {"uri": "memorymap://note/99999"})
    assert missing["error"]["code"] == -32002
    bad = _rpc("resources/read", {"uri": "file:///etc/passwd"})
    assert bad["error"]["code"] == -32002


def test_a_private_note_is_neither_listed_nor_readable(app_state):
    from tessellate.core import deps
    from tessellate.core.database import Entry

    note_id = _make_note("Private diary entry")
    with deps.get_db().session() as session:
        session.get(Entry, note_id).is_private = True
        session.commit()
    uris = [r["uri"] for r in _rpc("resources/list")["result"]["resources"]]
    assert f"memorymap://note/{note_id}" not in uris
    read = _rpc("resources/read", {"uri": f"memorymap://note/{note_id}"})
    assert "error" in read


def test_resources_vanish_when_the_note_tools_are_turned_off(app_state):
    from tessellate.core import deps

    deps.get_config().set_preference("disabled_tools", ["get_note", "list_notes"])
    assert _rpc("resources/list")["result"]["resources"] == []
    assert "resources" not in _rpc("initialize")["result"]["capabilities"]


def test_prompts_list_the_skills_with_their_inputs(app_state):
    prompts = _rpc("prompts/list")["result"]["prompts"]
    assert prompts
    with_args = next(p for p in prompts if p.get("arguments"))
    assert {"name", "description", "arguments"} <= set(with_args)
    assert all({"name", "required"} <= set(a) for a in with_args["arguments"])


def test_prompts_get_fills_a_skill_into_a_user_message(app_state):
    prompts = _rpc("prompts/list")["result"]["prompts"]
    skill = next(p for p in prompts if p.get("arguments"))
    values = {a["name"]: "gardening" for a in skill["arguments"]}
    got = _rpc("prompts/get", {"name": skill["name"], "arguments": values})["result"]
    message = got["messages"][0]
    assert message["role"] == "user" and message["content"]["type"] == "text"
    assert "gardening" in message["content"]["text"]
    assert "{{" not in message["content"]["text"]


def test_prompts_get_refuses_a_missing_required_input_and_an_unknown_skill(app_state):
    prompts = _rpc("prompts/list")["result"]["prompts"]
    skill = next(p for p in prompts if any(a["required"] for a in p.get("arguments", [])))
    assert _rpc("prompts/get", {"name": skill["name"]})["error"]["code"] == -32602
    assert _rpc("prompts/get", {"name": "no such skill"})["error"]["code"] == -32602


def test_startup_does_not_load_the_embedding_model(app_state):
    """OPEN ledger 319: `serve` builds the embedder lazily, so starting the
    tool server never loads a model (measured by hand with `-X importtime`:
    no sentence_transformers or torch import at startup)."""
    from tessellate.core import deps

    serve(stdin=io.StringIO(""), stdout=io.StringIO())
    assert deps.get_embeddings()._st_model is None


def test_a_notification_that_carries_an_id_still_gets_no_reply():
    from tessellate.mcp_server import handle_request

    for method in ("notifications/initialized", "notifications/cancelled"):
        assert handle_request({"jsonrpc": "2.0", "id": 9, "method": method}) is None


def test_shape_errors_answer_invalid_params_not_a_crash(app_state):
    for params in ("text", ["a"], 7):
        for method in ("tools/call", "resources/read", "prompts/get", "initialize"):
            response = handle_request({"jsonrpc": "2.0", "id": 5, "method": method, "params": params})
            assert response["error"]["code"] == -32602, (method, params)
    call = {"name": "count_notes", "arguments": "x"}
    bad_args = handle_request({"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": call})
    assert bad_args["error"]["code"] == -32602


def test_a_non_object_message_gets_invalid_request(app_state):
    assert handle_request([1, 2])["error"]["code"] == -32600
    assert handle_request("hi")["error"]["code"] == -32600


def test_serve_survives_a_bad_shape_and_a_raising_handler(app_state, monkeypatch):
    from tessellate import mcp_server

    lines = [
        json.dumps([1, 2]),
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": "x"}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "boom"}),
        json.dumps({"jsonrpc": "2.0", "id": 3, "method": "ping"}),
    ]
    monkeypatch.setitem(mcp_server._METHODS, "boom", lambda message: 1 / 0)
    deps.init_app_state()
    monkeypatch.setenv(mcp_server.TOKEN_ENV, mcp_server.token())
    out = io.StringIO()
    serve(io.StringIO("\n".join(lines) + "\n"), out)
    replies = [json.loads(x) for x in out.getvalue().splitlines()]
    assert [r.get("id") for r in replies] == [None, 1, 2, 3]
    assert replies[2]["error"]["code"] == -32603 and replies[3]["result"] == {}


# --- Q22 / audit 1028 K13: a token, and read-only until writes are switched on ---


def test_a_client_sees_only_readers_until_writes_are_switched_on(app_state):
    names = {spec.name for spec in offered_tools()}
    assert "count_notes" in names and "create_note" not in names
    refused = handle_request(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "create_note", "arguments": {"content": "x"}}}
    )
    assert refused["result"]["isError"] is True
    app_state.set_preference("mcp_writes_enabled", True)
    assert "create_note" in {spec.name for spec in offered_tools()}


def _serve_one(message, monkeypatch, env_token):
    from tessellate import mcp_server

    deps.init_app_state()
    if env_token is None:
        monkeypatch.delenv(mcp_server.TOKEN_ENV, raising=False)
    else:
        monkeypatch.setenv(mcp_server.TOKEN_ENV, env_token)
    out = io.StringIO()
    serve(io.StringIO(json.dumps(message) + "\n"), out)
    return json.loads(out.getvalue())


def test_a_client_without_the_token_is_refused_and_one_with_it_is_served(app_state, monkeypatch):
    from tessellate import mcp_server

    ask = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    right = mcp_server.token()
    assert right == mcp_server.token(), "one token per notebook, kept"
    for wrong in (None, "", "nope", right + "x"):
        reply = _serve_one(ask, monkeypatch, wrong)
        assert reply["error"]["code"] == mcp_server.NOT_AUTHORISED, wrong
    assert "tools" in _serve_one(ask, monkeypatch, right)["result"]
    assert mcp_server._auth["denied"] == "", "handle_request is pure again after serve"


def test_the_token_is_a_secret_setting_and_the_snippet_carries_it(client):
    from tessellate import mcp_server

    env = client.get("/capabilities").json()["features"]["mcp"]["config"]["env"]
    assert env[mcp_server.TOKEN_ENV] == mcp_server.token()
    saved = deps.get_config().preferences_path.read_text(encoding="utf-8")
    assert env[mcp_server.TOKEN_ENV] not in saved


def test_the_writes_switch_round_trips_through_the_settings_api(client):
    """Q22 K13: the Settings checkbox (#pref-mcp-writes) saves and reads back this key."""
    assert client.get("/preferences").json()["mcp_writes_enabled"] is False
    client.put("/preferences", json={"mcp_writes_enabled": True})
    assert client.get("/preferences").json()["mcp_writes_enabled"] is True
    assert writes_allowed() is True


def test_the_skill_snippet_routes_intents_to_the_tool_command(client):
    """L-general-34: Settings' MCP row also offers a SKILL.md an agent can drop in
    its skills folder; it names every offered tool and the `tool NAME --json`
    command, and never carries the server token (the shell is its own boundary)."""
    from tessellate import mcp_server

    mcp = client.get("/capabilities").json()["features"]["mcp"]
    skill = mcp["skill"]
    assert skill.startswith("---\nname: tessellate\ndescription: ")
    assert " tool " in skill and "--json" in skill and "TESSELLATE_DATA_DIR" in skill
    for spec in offered_tools():
        assert f"`{spec.name}`" in skill
    assert mcp_server.token() not in skill


def test_the_skill_snippet_quotes_a_hostile_path_for_the_shell(app_state):  # noqa: ARG001
    """Source text: review (mcp_server skill_md): the data folder and command went
    into the shell line inside double quotes, so a `"`, `$` or backtick in a path
    broke out of them; both are shlex-quoted now."""
    import shlex

    from tessellate import mcp_server

    folder = '/home/a "b" $HOME `id`/data'
    exe = "/opt/py $x/bin/python"
    skill = mcp_server.skill_md([exe, "-m", "tessellate"], folder)
    line = next(ln for ln in skill.splitlines() if ln.startswith("Run with "))
    assert shlex.split(line.removeprefix("Run with ").removesuffix(" set:")) == [f"TESSELLATE_DATA_DIR={folder}"]
    run = next(ln.strip() for ln in skill.splitlines() if " tool NAME " in ln)
    assert shlex.split(run)[:5] == [exe, "-m", "tessellate", "tool", "NAME"]
