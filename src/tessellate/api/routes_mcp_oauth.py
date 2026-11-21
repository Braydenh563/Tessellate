"""OAuth 2.1 routes for a remote MCP client (L-world-class-560; core/mcp_oauth.py).

Open (an outside client has no session; each answers 403 to another device
unless LAN mode is on, the same gate as `/mcp`):

- `GET /.well-known/oauth-protected-resource[/mcp]` and
  `GET /.well-known/oauth-authorization-server`: the metadata.
- `POST /oauth/register`: dynamic client registration.
- `GET /oauth/authorize`: checks the request and sends the browser to a page
  that waits, reloading itself (a meta refresh, no script, so the app's CSP
  is untouched), until the person approves or denies it in Settings.
- `POST /oauth/token`: a code and its PKCE verifier, or a refresh token.

Behind the lock and answering only on this computer: the Settings list of
waiting sign-ins and its Approve and Deny.
"""

from __future__ import annotations

import html
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel

from tessellate.api.routes_mcp import NOT_HERE, _from_this_computer
from tessellate.core import deps, mcp_clients, mcp_oauth, netbind

open_router = APIRouter(tags=["mcp"])
router = APIRouter(tags=["mcp"])

NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}
WAIT_SECONDS = 3


def _base(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def _allowed(request: Request) -> bool:
    return _from_this_computer(request) or netbind.lan_enabled(deps.get_config())


def _oauth_error(error: mcp_oauth.OAuthError, status: int = 400) -> JSONResponse:
    return JSONResponse({"error": error.code, "error_description": error.why}, status_code=status, headers=NO_STORE)


def _not_here() -> JSONResponse:
    return JSONResponse({"error": "access_denied", "error_description": NOT_HERE}, status_code=403)


@open_router.get("/.well-known/oauth-protected-resource")
@open_router.get("/.well-known/oauth-protected-resource/mcp")
def resource_metadata(request: Request) -> Response:
    """RFC 9728: the tool server and the authorization server that guards it (this app)."""
    if not _allowed(request):
        return _not_here()
    base = _base(request)
    return JSONResponse({
        "resource": f"{base}/mcp",
        "authorization_servers": [base],
        "scopes_supported": list(mcp_oauth.SCOPES),
        "bearer_methods_supported": ["header"],
        "resource_name": "Tessellate",
    })


@open_router.get("/.well-known/oauth-authorization-server")
def server_metadata(request: Request) -> Response:
    """RFC 8414: every endpoint is on this app's own port."""
    if not _allowed(request):
        return _not_here()
    base = _base(request)
    return JSONResponse({
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "registration_endpoint": f"{base}/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": list(mcp_oauth.SCOPES),
    })


@open_router.post("/oauth/register")
async def register(request: Request) -> Response:
    if not _allowed(request):
        return _not_here()
    try:
        body = await request.json()
    except ValueError:
        body = None
    if not isinstance(body, dict):
        return _oauth_error(mcp_oauth.OAuthError("invalid_client_metadata", "Send the registration as a JSON object."))
    try:
        return JSONResponse(mcp_oauth.register(body), status_code=201, headers=NO_STORE)
    except mcp_oauth.OAuthError as error:
        return _oauth_error(error)


def _page(title: str, lines: list[str], refresh: str | None = None) -> HTMLResponse:
    """The browser's side of the wait: plain HTML, escaped, no script or inline style."""
    meta = f'<meta http-equiv="refresh" content="{WAIT_SECONDS};url={html.escape(refresh)}">' if refresh else ""
    body = "".join(f"<p>{html.escape(line)}</p>" for line in lines)
    return HTMLResponse(
        f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)}</title>{meta}</head>'
        f"<body><h1>{html.escape(title)}</h1>{body}</body></html>",
        headers=NO_STORE,
    )


@open_router.get("/oauth/authorize")
def authorize(request: Request) -> Response:
    if not _allowed(request):
        return _not_here()
    try:
        row = mcp_oauth.begin(dict(request.query_params))
    except mcp_oauth.OAuthError as error:
        #: Never a redirect for a bad client or address (RFC 6749 4.1.2.1): the page says why.
        return _page("This sign-in cannot go on", [error.why])
    return RedirectResponse(f"/oauth/authorize/wait?{urlencode({'request': row['id']})}", status_code=303)


def _back(uri: str, query: dict) -> RedirectResponse:
    return RedirectResponse(f"{uri}{'&' if '?' in uri else '?'}{urlencode(query)}", status_code=303)


@open_router.get("/oauth/authorize/wait")
def authorize_wait(request: Request) -> Response:
    if not _allowed(request):
        return _not_here()
    rid = request.query_params.get("request", "")
    row = mcp_oauth.finish(rid)
    if row is None:
        return _page("This sign-in has ended", ["It was not approved within ten minutes. Start again from the app."])
    if row["status"] == "approved":
        query = {"code": row["auth_code"], **({"state": row["state"]} if row["state"] else {})}
        return _back(row["redirect_uri"], query)
    if row["status"] == "denied":
        return _back(row["redirect_uri"], {"error": "access_denied", **({"state": row["state"]} if row["state"] else {})})
    return _page(
        f"Approve {row['client_name']} in Tessellate",
        [
            f"{row['client_name']} asks to use your notebook. On the computer Tessellate runs on, open Settings, Tools it can use, and approve the sign-in with this code:",
            row["code"],
            "Choose there which notes it may reach. This page moves on by itself.",
        ],
        refresh=f"/oauth/authorize/wait?{urlencode({'request': rid})}",
    )


@open_router.post("/oauth/token")
async def token(request: Request) -> Response:
    if not _allowed(request):
        return _not_here()
    form = await request.form()
    try:
        return JSONResponse(mcp_oauth.exchange({key: str(value) for key, value in form.items()}), headers=NO_STORE)
    except mcp_oauth.OAuthError as error:
        return _oauth_error(error)


class Approval(BaseModel):
    writes: bool = False
    #: `{"categories": [...], "tags": [...]}`; empty is the whole notebook (core/mcp_scope.py).
    scope: dict = {}


def _this_computer(request: Request) -> None:
    """A grant is approved on this computer only, even with LAN mode on."""
    if not _from_this_computer(request):
        raise HTTPException(status_code=403, detail="Approve a sign-in on the computer Tessellate runs on.")


@router.get("/mcp-oauth/requests")
def list_requests() -> dict:
    return {"requests": mcp_oauth.waiting()}


@router.post("/mcp-oauth/requests/{request_id}/approve")
def approve_request(request_id: str, body: Approval, request: Request) -> dict:
    _this_computer(request)
    try:
        grant = mcp_oauth.approve(request_id, writes=body.writes, scope=body.scope)
    except mcp_clients.TooMany:
        raise HTTPException(status_code=409, detail=f"There are already {mcp_clients.MAX_CLIENTS} tokens. Revoke one first.") from None
    if grant is None:
        raise HTTPException(status_code=404, detail="That sign-in has ended. Start again from the app.")
    return {"client": grant}


@router.post("/mcp-oauth/requests/{request_id}/deny")
def deny_request(request_id: str, request: Request) -> dict:
    _this_computer(request)
    if not mcp_oauth.deny(request_id):
        raise HTTPException(status_code=404, detail="That sign-in has ended.")
    return {"denied": request_id}
