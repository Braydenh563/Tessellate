"""The stdio MCP server (mcp_server.py, ROADMAP.md item 38).

`handle_request` is pure, no stdio touched, so every case here calls it
directly rather than spawning a subprocess. `serve()`'s own line-reading
loop gets one end-to-end test over real StringIO streams.
"""

from __future__ import annotations

import io
import json

from tessellate.ai import tools
from tessellate.mcp_server import handle_request, offered_tools, serve


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
