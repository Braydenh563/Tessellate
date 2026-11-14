"""A stdio MCP (Model Context Protocol) server over this app's own tool
registry (ROADMAP.md item 38, ANALYSIS.md §60).

Why expose rather than consume: this app already has a local-process trust
boundary: anyone who can run a process on this machine can already open
`tessellate.db` directly: so a *stdio* server needs no new trust model, it's
the same boundary the app's own SQLite file already sits behind. Consuming
an external MCP server is the harder half (BACKLOG.md §29's missing trust
model for tool calls arriving *from* somewhere else) and is deliberately
not attempted here.

Only non-destructive, currently-enabled tools are offered. `ai.tools`'s own
`destructive` flag exists because a destructive tool needs a human to see
and confirm it before it runs, the chat UI does that with a confirm card
(`agent.py`'s tool loop parks it rather than running it), but a bare
`execute_tool()` call has no such gate built in, and an MCP client (Claude
Desktop, or anything else) has no confirm card to show. So the safe default
here is to never even list `delete_note`/`delete_tag`/`delete_category`/
`delete_document`/`delete_skill`/`merge_categories`, rather than run one
unconfirmed. `tool_enabled()` is reused as-is, so a tool the user turned off
in Settings -> Tools (including the `web_search`/`read_url` online opt-in)
is invisible here too, the same as it already is to the in-app chat model.

Run with `python -m tessellate.mcp_server`, with `TESSELLATE_DATA_DIR` set the
same way the main app expects, it operates on the same notebook, not a
second one. The packaged app runs the same loop as `Tessellate --mcp`.

Besides tools it serves **resources** (notes, `memorymap://note/<id>`, read
through the `list_notes` and `get_note` tools so the private-note guard and the
Settings switches apply unchanged) and **prompts** (the saved skills, filled
the way a skill run fills them). Both stay stdio and read-only: a prompt is
text for the client's model to act on with the tools listed above, never a run.
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import re
import sys
from typing import TextIO

from tessellate.ai import tools
from tessellate.core import deps

logger = logging.getLogger(__name__)

#: Newest first. `initialize` answers with the client's own version when it is
#: one of these (the spec's negotiation), else the newest we speak. The
#: default for a client that names none stays the oldest, as before.
SUPPORTED_PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "memorymap-ai"
SERVER_VERSION = "0.1.0"


#: Tools that mean something only inside the chat window. `ends_turn` is the
#: registry's own mark for "stops and waits for the person" (`ask_user`,
#: `make_plan`, `run_skill`, `compress_chat`): a bare client has no card to
#: answer, so the call would park for ever. The two names are read-only but
#: describe this app's own screens and one conversation's history.
CHAT_ONLY = frozenset({"get_app_navigation", "search_chat_history"})


def writes_allowed() -> bool:
    """Whether an outside client may change notes. Off until the person turns
    it on (audit 1028 K13): a prompt-injected client could otherwise edit notes
    silently, and the activity panel is the only trace."""
    return bool(deps.get_config().get_preference("mcp_writes_enabled", False))


def offered_tools() -> list[tools.ToolSpec]:
    """Every tool this server will list and run: not destructive, not
    interactive, not turned off in Settings -> Tools, and, unless writes are
    switched on, read-only."""
    writes = writes_allowed()
    return [
        spec
        for spec in tools.TOOLS.values()
        if not spec.destructive
        and not spec.ends_turn
        and spec.name not in CHAT_ONLY
        and tools.tool_enabled(spec.name)
        and (writes or _is_read_only(spec))
    ]


#: One token per notebook, made on first use and shown in the snippet Settings
#: hands an outside client (Q22, owner 2026-11-11). The client passes it back
#: as `TESSELLATE_MCP_TOKEN`; a process that does not has no way to read or
#: change notes through this server, so "any local process" stops being enough.
TOKEN_ENV = "TESSELLATE_MCP_TOKEN"
NOT_AUTHORISED = -32001
#: Set by `serve()` once, from the environment; `handle_request` stays pure.
_auth = {"denied": ""}


def token() -> str:
    """This notebook's MCP token, made and kept (as a secret setting) on first ask."""
    import secrets

    config = deps.get_config()
    value = str(config.get_preference("mcp_token", "") or "")
    if not value:
        value = secrets.token_urlsafe(32)
        config.set_preference("mcp_token", value)
    return value


def _check_token(given: str) -> str:
    """Empty when `given` is this notebook's token, else what to tell the client."""
    expected = str(deps.get_config().get_preference("mcp_token", "") or "")
    if not expected:
        return "The tool server has no token yet. Open Settings, Tools it can use, and copy the connection snippet into your client."
    if not hmac.compare_digest(given.encode(), expected.encode()):
        return f"The tool server needs {TOKEN_ENV} set to this notebook's token. Open Settings, Tools it can use, and copy the connection snippet."
    return ""


#: Tools that change nothing, so a client may auto-approve them. The registry
#: already lists the writers (`tools.WRITE_TOOLS`, the list the agent loop
#: trusts); `save_user_preference` writes a preference and is not in it.
#: `destructiveHint` is False for everything offered here by construction
#: (the spec's default is True, which would make a client ask before a
#: harmless note edit).
_ALSO_WRITES = frozenset({"save_user_preference"})


def _is_read_only(spec: tools.ToolSpec) -> bool:
    return spec.name not in tools.WRITE_TOOLS and spec.name not in _ALSO_WRITES


def _annotations(spec: tools.ToolSpec) -> dict:
    return {
        "readOnlyHint": _is_read_only(spec),
        "destructiveHint": bool(spec.destructive),
        "openWorldHint": spec.name in ("web_search", "read_url"),
    }


NOTE_URI = re.compile(r"^memorymap://note/(\d+)$")
#: Notes per `resources/list` page (the registry's own page maximum), and the
#: JSON-RPC code the spec gives a resource that is not there.
RESOURCE_PAGE = 25
RESOURCE_NOT_FOUND = -32002
INVALID_PARAMS = -32602
INVALID_REQUEST = -32600
INTERNAL_ERROR = -32603


def _resources_offered() -> bool:
    names = {spec.name for spec in offered_tools()}
    return {"list_notes", "get_note"} <= names


def _run_tool(name: str, arguments: dict) -> dict:
    """One offered tool, run against a fresh session, its plain result."""
    session = deps.get_db().session()
    try:
        return tools.execute_tool(session, name, arguments, agent=_client["name"] or "mcp client")
    finally:
        session.close()


def _first_line(text: str, limit: int = 80) -> str:
    line = next((row.strip() for row in str(text).splitlines() if row.strip()), "")
    line = line.lstrip("#").strip()
    return line[:limit] or "Untitled note"


def _resources_list(params: dict) -> dict:
    if not _resources_offered():
        return {"resources": []}
    try:
        offset = max(0, int((params or {}).get("cursor") or 0))
    except (TypeError, ValueError):
        offset = 0
    result = _run_tool("list_notes", {"limit": RESOURCE_PAGE, "offset": offset})
    resources = [
        {
            "uri": f"memorymap://note/{note['id']}",
            "name": _first_line(note.get("content", "")),
            "description": " · ".join(
                part for part in (f"Note #{note['id']}", note.get("category") or "") if part
            ),
            "mimeType": "text/markdown",
        }
        for note in result.get("notes", [])
    ]
    page = {"resources": resources}
    if result.get("has_more") and result.get("next_offset") is not None:
        page["nextCursor"] = str(result["next_offset"])
    return page


def _resource_templates() -> dict:
    if not _resources_offered():
        return {"resourceTemplates": []}
    return {
        "resourceTemplates": [
            {
                "uriTemplate": "memorymap://note/{id}",
                "name": "A note",
                "description": "One note in full, by its number.",
                "mimeType": "text/markdown",
            }
        ]
    }


def _resources_read(params: dict) -> tuple[dict | None, str]:
    """(`result`, "") or (None, why)."""
    uri = str((params or {}).get("uri") or "")
    match = NOTE_URI.match(uri)
    if not match or not _resources_offered():
        return None, f"No resource at {uri or 'that address'}."
    note = _run_tool("get_note", {"id": int(match.group(1))})
    if not isinstance(note, dict) or "error" in note or "content" not in note:
        return None, f"No resource at {uri}."
    tags = ", ".join(note.get("tags") or [])
    head = [f"Note #{note['id']}"]
    if note.get("category"):
        head.append(f"category: {note['category']}")
    if tags:
        head.append(f"tags: {tags}")
    text = f"<!-- {' · '.join(head)} -->\n\n{note['content']}"
    return {"contents": [{"uri": uri, "mimeType": "text/markdown", "text": text}]}, ""


def _skills() -> list[dict]:
    from tessellate.ai import skills

    return skills.catalog(deps.get_config(), set(tools.TOOLS))


def _prompts_list() -> dict:
    return {
        "prompts": [
            {
                "name": skill["name"],
                "description": skill.get("description") or skill.get("when_to_use") or skill.get("prompt", "")[:120],
                "arguments": [
                    {
                        "name": item["name"],
                        "description": item.get("label", ""),
                        "required": bool(item.get("required")) and not item.get("default"),
                    }
                    for item in skill.get("inputs") or []
                ],
            }
            for skill in _skills()
        ]
    }


def _prompts_get(params: dict) -> tuple[dict | None, str]:
    from tessellate.ai import skills

    name = str((params or {}).get("name") or "")
    skill = next((s for s in _skills() if s["name"] == name), None)
    if skill is None:
        return None, f"There is no skill called '{name}'."
    given = (params or {}).get("arguments")
    given = given if isinstance(given, dict) else {}
    missing = skills.missing_inputs(skill, given)
    if missing:
        return None, "Missing: " + ", ".join(missing) + "."
    text = skills.run_instruction(skill, skills.input_values(skill, given))
    return {
        "description": skill.get("description", ""),
        "messages": [{"role": "user", "content": {"type": "text", "text": text}}],
    }, ""


def _error(msg_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def _tool_list_payload() -> list[dict]:
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "inputSchema": spec.parameters,
            "annotations": _annotations(spec),
        }
        for spec in offered_tools()
    ]


_ICON_PREFIX = re.compile(r"^ph:[\w-]+\s*")


def _clean_label(result):  # noqa: ANN001  # whatever the tool returned
    """The app's `label` leads with an icon token (`ph:folders Listed your
    categories`) for its own UI; an outside client reads that as text."""
    if isinstance(result, dict) and isinstance(result.get("label"), str):
        result = {**result, "label": _ICON_PREFIX.sub("", result["label"])}
    return result


#: Who is on the other end, from `initialize`'s `clientInfo.name` (H4): every
#: write a tool call makes is filed under it in the event log, so the activity
#: panel says "Claude Desktop" rather than "Atlas" for a change Atlas never made.
_client = {"name": ""}


def _call_tool(name: str, arguments: dict) -> dict:
    """Runs one tool call against a fresh session, in MCP's own result
    shape (a `content` list plus `isError`, not this app's own
    `{"error": ...}` convention `execute_tool` returns internally)."""
    if name not in {spec.name for spec in offered_tools()}:
        return {
            "content": [{"type": "text", "text": f"Unknown or unavailable tool '{name}'"}],
            "isError": True,
        }
    session = deps.get_db().session()
    try:
        result = tools.execute_tool(
            session, name, arguments or {}, agent=_client["name"] or "mcp client"
        )
    finally:
        session.close()
    result = _clean_label(result)
    is_error = isinstance(result, dict) and "error" in result
    return {"content": [{"type": "text", "text": json.dumps(result)}], "isError": is_error}


class _Refused(Exception):
    """A method that answers with a JSON-RPC error rather than a result."""

    def __init__(self, code: int, why: str) -> None:
        super().__init__(why)
        self.code = code
        self.why = why


def _initialize(message: dict) -> dict:
    params = message.get("params") or {}
    info = params.get("clientInfo") or {}
    _client["name"] = str(info.get("name") or "") if isinstance(info, dict) else ""
    asked = params.get("protocolVersion")
    if asked in SUPPORTED_PROTOCOLS:
        version = asked
    elif asked:
        version = SUPPORTED_PROTOCOLS[0]
    else:
        version = PROTOCOL_VERSION
    capabilities: dict = {"tools": {}, "prompts": {}}
    if _resources_offered():
        capabilities["resources"] = {}
    return {
        "protocolVersion": version,
        "capabilities": capabilities,
        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
    }


def _tools_call(message: dict) -> dict:
    params = message.get("params") or {}
    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict) or not isinstance(params.get("name", ""), str):
        raise _Refused(INVALID_PARAMS, "name must be a string and arguments an object")
    return _call_tool(params.get("name", ""), arguments)


def _resources_read_method(message: dict) -> dict:
    result, why = _resources_read(message.get("params") or {})
    if result is None:
        raise _Refused(RESOURCE_NOT_FOUND, why)
    return result


def _prompts_get_method(message: dict) -> dict:
    result, why = _prompts_get(message.get("params") or {})
    if result is None:
        raise _Refused(INVALID_PARAMS, why)
    return result


#: Each method's answer. Notifications that get no reply are not here: they
#: fall to the same `None` an unknown notification does.
_METHODS = {
    "initialize": _initialize,
    "ping": lambda message: {},
    "tools/list": lambda message: {"tools": _tool_list_payload()},
    "tools/call": _tools_call,
    "resources/list": lambda message: _resources_list(message.get("params") or {}),
    "resources/templates/list": lambda message: _resource_templates(),
    "resources/read": _resources_read_method,
    "prompts/list": lambda message: _prompts_list(),
    "prompts/get": _prompts_get_method,
}


def handle_request(message: dict) -> dict | None:
    """One JSON-RPC message in, one response out, or `None` for a
    notification, which gets no reply at all (a bare `id`-less message, per
    JSON-RPC 2.0). Kept pure, no stdio touched here, so the protocol
    logic is directly testable without a real subprocess or a live client.
    """
    if not isinstance(message, dict):
        return _error(None, INVALID_REQUEST, "A JSON-RPC message is an object")
    method = message.get("method")
    msg_id = message.get("id")
    is_notification = "id" not in message
    if _auth["denied"] and method != "ping":
        return None if is_notification else _error(msg_id, NOT_AUTHORISED, _auth["denied"])
    handler = _METHODS.get(method)
    if handler is None:
        if is_notification or str(method).startswith("notifications/"):
            return None
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Unknown method '{method}'"},
        }
    try:
        if not isinstance(message.get("params") or {}, dict):
            raise _Refused(INVALID_PARAMS, "params must be an object")
        result = handler(message)
    except _Refused as refused:
        return None if is_notification else _error(msg_id, refused.code, refused.why)
    except (AttributeError, TypeError, ValueError, KeyError):
        # A shape the handlers did not expect is the caller's, not a crash.
        return None if is_notification else _error(msg_id, INVALID_PARAMS, "Invalid params")
    if is_notification:
        return None
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def serve(stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> None:
    """The stdio loop: one JSON-RPC message per line in, one per line out, 
    MCP's stdio transport, no `Content-Length` framing. A line that isn't
    valid JSON is dropped rather than crashing the server; a client sending
    garbage shouldn't take down an otherwise-working session.
    """
    deps.init_app_state()
    _auth["denied"] = _check_token(os.environ.get(TOKEN_ENV, ""))
    try:
        _serve_lines(stdin, stdout)
    finally:
        _auth["denied"] = ""


def _serve_lines(stdin: TextIO, stdout: TextIO) -> None:
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            response = handle_request(message)
        except Exception:  # one bad message never ends the server
            logger.exception("mcp message failed")
            response = _error(message.get("id") if isinstance(message, dict) else None, INTERNAL_ERROR, "Internal error")
        if response is not None:
            stdout.write(json.dumps(response) + "\n")
            stdout.flush()


def skill_md(command: list[str], data_dir: str) -> str:
    """A SKILL.md an agent (Claude Code and the like) keeps in its skills folder
    (L-general-34): its description routes "my notes" intents here, and its body
    runs `tool NAME --json` per offered tool. No token: the CLI runs in the
    person's own shell, the same boundary as stdio."""
    import shlex

    rows = "\n".join(
        f"- `{spec.name}`: {spec.description.strip().splitlines()[0]}" for spec in offered_tools()
    )
    #: Shell-quoted, not wrapped in double quotes: a `"`, `$` or backtick in
    #: the folder or the interpreter's path broke out of them (review).
    command, env = shlex.join(command), shlex.quote(f"TESSELLATE_DATA_DIR={data_dir}")
    return (
        "---\nname: tessellate\ndescription: Read and search the person's Tessellate "
        "notebook. Use when they ask about their notes, what they wrote, or what is due.\n---\n\n"
        f"Run with {env} set:\n\n"
        f"    {command} tool NAME --args '{{\"key\": \"value\"}}' --json\n\n"
        f"`{command} tool --json` lists every tool with its arguments. "
        "Output is one JSON line; exit 1 means the tool failed.\n\n"
        f"Tools:\n{rows}\n"
    )


def cli(argv: list[str], out: TextIO) -> int:
    """`python -m tessellate tool [NAME] [--args JSON] [--json]`: list the
    offered tools, or run one and print its result. Always JSON on `out`
    (`--json` is accepted so a script states what it expects). Exit 0 on
    success, 1 for a tool that is unavailable or errored, 2 for bad arguments.
    The shell already has the notebook's files, the same boundary as stdio."""
    import argparse

    parser = argparse.ArgumentParser(prog="tessellate tool", add_help=False)
    parser.add_argument("name", nargs="?")
    parser.add_argument("--args", default="{}")
    parser.add_argument("--json", action="store_true")
    try:
        given = parser.parse_args(argv)
    except SystemExit:
        out.write(json.dumps({"error": "usage: tool [NAME] [--args JSON] [--json]"}) + "\n")
        return 2
    deps.init_app_state()
    if not given.name:
        out.write(json.dumps({"tools": _tool_list_payload()}) + "\n")
        return 0
    try:
        arguments = json.loads(given.args)
    except json.JSONDecodeError:
        arguments = None
    if not isinstance(arguments, dict):
        out.write(json.dumps({"error": "--args must be a JSON object"}) + "\n")
        return 2
    reply = _call_tool(given.name, arguments)
    text = json.loads(reply["content"][0]["text"]) if not reply["isError"] or reply["content"][0]["text"].startswith("{") else None
    if text is None:
        out.write(json.dumps({"tool": given.name, "error": reply["content"][0]["text"]}) + "\n")
        return 1
    out.write(json.dumps({"tool": given.name, "result": text}) + "\n")
    return 1 if reply["isError"] else 0


if __name__ == "__main__":
    serve()
