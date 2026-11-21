"""The tool server over streamable HTTP, and the tokens that open it (INBOX 1860).

`POST /mcp` takes one JSON-RPC message (or a list of them) and answers with
JSON, the streamable HTTP transport without its optional event stream, so
`GET /mcp` is 405 as the spec allows. The trust model, the owner's B52 ask
("a token that the user can control") as recommended in INBOX 1860:

- **A token per client**, made in Settings and shown once (`core/mcp_clients.py`
  keeps only its hash). No token, a wrong one or a revoked one is 401 before
  anything is read; it is the route's own gate, which is why `open_router` sits
  outside `require_unlock` (tests/test_every_route_is_locked.py).
- **This computer only**, unless LAN mode is on: a request from another
  device is 403 even with a good token. LAN mode is itself behind the
  password and HTTPS, and the Host and Origin checks run before this route.
- **Reads only**, unless the token was made with "Can add and change notes";
  deletes and the other destructive tools are never offered at all.
- **Every call is counted** on the token's row and in the app log, and a write
  is filed under the token's name in the activity panel (`execute_tool`'s agent).
"""

from __future__ import annotations

import ipaddress
import json
import logging
import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from tessellate.core import deps, mcp_clients, netbind

logger = logging.getLogger("tessellate.mcp")

open_router = APIRouter(tags=["mcp"])
router = APIRouter(tags=["mcp"])

PARSE_ERROR = -32700
NOT_HERE = "The tool server answers only on this computer. Turn on LAN mode in Settings to use it from another device."
NO_TOKEN = "This needs a tool server token from Settings, Tools it can use, sent as Authorization: Bearer, or an OAuth sign-in approved there."


#: Set by docker/compose.yaml, which publishes the port on the host's loopback
#: only: there a request from the host arrives from the bridge's private
#: gateway address, never from loopback (docs/DOCKER.md, L-world-class-560).
PUBLISHED_ENV = "TESSELLATE_PUBLISHED_ON_LOOPBACK"
#: The private ranges a container bridge hands out (RFC 1918); Python's
#: `is_private` also takes documentation and reserved ranges, which a bridge never is.
BRIDGE_NETWORKS = tuple(ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))


def _through_the_published_port(client) -> bool:  # noqa: ANN001  # an ASGI scope's `client`
    """In a container whose port is published on the host's loopback, a private
    (bridge) address is the host. A public one is never trusted this way."""
    if os.environ.get(PUBLISHED_ENV) != "1" or not isinstance(client, (tuple, list)) or not client:
        return False
    try:
        address = ipaddress.ip_address(str(client[0]))
    except ValueError:
        return False
    return any(address in network for network in BRIDGE_NETWORKS)


def _from_this_computer(request: Request) -> bool:
    """Both ends of the connection on loopback: the socket that accepted it
    and the address it came from (a name, as the test client sends, is read as
    local by `arrived_on_loopback`); or, in the Docker setup, the published port."""
    scope = request.scope
    if _through_the_published_port(scope.get("client")):
        return True
    return netbind.arrived_on_loopback(scope.get("server")) and netbind.arrived_on_loopback(scope.get("client"))


def _bearer(request: Request) -> str:
    raw = request.headers.get("authorization", "")
    scheme, _, value = raw.partition(" ")
    return value.strip() if scheme.lower() == "bearer" else ""


def _refuse(status: int, why: str, request: Request | None = None) -> JSONResponse:
    #: Where an OAuth client finds how to sign in (RFC 9728, routes_mcp_oauth.py).
    meta = f', resource_metadata="{str(request.base_url).rstrip("/")}/.well-known/oauth-protected-resource"' if request else ""
    headers = {"WWW-Authenticate": f'Bearer realm="tessellate-mcp"{meta}'} if status == 401 else None
    return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32001, "message": why}}, status_code=status, headers=headers)


def _client_for(request: Request) -> dict | JSONResponse:
    if not _from_this_computer(request) and not netbind.lan_enabled(deps.get_config()):
        return _refuse(403, NOT_HERE)
    row = mcp_clients.match(_bearer(request))
    if row is None:
        logger.info("mcp over http refused: no live token")
        return _refuse(401, NO_TOKEN, request)
    return row


@open_router.post("/mcp")
async def mcp_post(request: Request) -> Response:
    from starlette.concurrency import run_in_threadpool

    from tessellate import mcp_server

    row = _client_for(request)
    if isinstance(row, JSONResponse):
        return row
    try:
        body = json.loads(await request.body() or b"null")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": PARSE_ERROR, "message": "Parse error"}}, status_code=400)
    caller = {"name": row.get("name") or "mcp client", "writes": bool(row.get("writes")), "scope": row.get("scope")}
    messages = body if isinstance(body, list) else [body]

    def answer() -> list:
        replies = []
        for message in messages:
            if isinstance(message, dict) and "id" in message:
                logger.info("mcp over http: %s from client %s", str(message.get("method"))[:40], row["id"])
                mcp_clients.note_use(row["id"])
            reply = mcp_server.handle_as(caller, message)
            if reply is not None:
                replies.append(reply)
        return replies

    replies = await run_in_threadpool(answer)
    if not replies:
        return Response(status_code=202)
    return JSONResponse(replies if isinstance(body, list) else replies[0])


@open_router.get("/mcp")
def mcp_get() -> Response:
    """No server-sent stream is offered; the spec's answer for that is 405."""
    return Response(status_code=405, headers={"Allow": "POST"})


class NewClient(BaseModel):
    name: str
    writes: bool = False
    #: `{"categories": [...], "tags": [...]}`; empty is the whole notebook (core/mcp_scope.py).
    scope: dict = {}


@router.get("/mcp-clients")
def list_clients() -> dict:
    return {"clients": mcp_clients.listing()}


@router.post("/mcp-clients")
def make_client(body: NewClient) -> dict:
    name = mcp_clients.clean_name(body.name)
    if not name:
        raise HTTPException(status_code=422, detail="Give the app a name.")
    try:
        client, token = mcp_clients.create(name, writes=body.writes, scope=body.scope)
    except mcp_clients.TooMany:
        raise HTTPException(status_code=409, detail=f"There are already {mcp_clients.MAX_CLIENTS} tokens. Revoke one first.") from None
    return {"client": client, "token": token}


@router.delete("/mcp-clients/{client_id}")
def revoke_client(client_id: str) -> dict:
    if not mcp_clients.revoke(client_id):
        raise HTTPException(status_code=404, detail="No such token.")
    return {"revoked": client_id}


@router.post("/mcp-clients/{client_id}/restore")
def restore_client(client_id: str) -> dict:
    """The Undo of Revoke (and the Redo of an undone Make a link), within the hour."""
    if not mcp_clients.restore(client_id):
        raise HTTPException(status_code=404, detail="That link can no longer come back. Make a new one.")
    return {"restored": client_id}
