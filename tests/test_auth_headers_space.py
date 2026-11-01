"""A hand-built request that replaces `api()`'s headers keeps the space header.

`api()` sends `X-Auth-Token` and `X-Workspace-ID` by default. A call that
passes its own `headers` object (a FormData upload must not carry the JSON
Content-Type) replaces both. `chat-attach.js` passed `{ "X-Auth-Token": ... }`
alone, so a document imported through the chat's paperclip landed in the
default space whichever space was open (audit 2026-10-05). The fix is one
helper, `authHeaders()`; this lint fails on any header literal naming the
token without the space, outside the auth calls that run before a space means
anything.
"""

from __future__ import annotations

import re
from pathlib import Path
from tests._app_js import with_pieces

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"

# Literal objects that carry the token on purpose without a space: the auth
# handshakes (no space is chosen before the session exists) and `api()` and
# `authHeaders()` themselves, which build the pair.
ALLOWED_URLS = ("/auth/media-session", "/auth/auto-session")


def _header_literals(text: str):
    """Yield (offset, literal) for every `{ ... }` holding "X-Auth-Token"."""
    for match in re.finditer(r'"X-Auth-Token"', text):
        start = text.rfind("{", 0, match.start())
        end = text.find("}", match.end())
        yield match.start(), text[start : end + 1]


def test_every_token_header_literal_carries_the_space():
    offenders = []
    for path in sorted(JS.glob("*.js")):
        text = path.read_text(encoding="utf-8")
        for offset, literal in _header_literals(text):
            if "X-Workspace-ID" in literal:
                continue
            before = text[max(0, offset - 300) : offset]
            if any(url in before for url in ALLOWED_URLS):
                continue
            line = text.count("\n", 0, offset) + 1
            offenders.append(f"{path.name}:{line}")
    assert not offenders, (
        "headers that replace api()'s defaults drop X-Workspace-ID; use "
        f"authHeaders(): {offenders}"
    )


def test_chat_attach_imports_use_the_shared_headers():
    text = with_pieces("chat-attach.js")
    call = text[text.index('"/documents/import"') :][:200]
    assert "authHeaders()" in call


def test_auth_headers_helper_sends_both():
    text = (JS / "spaces-find.js").read_text(encoding="utf-8")
    body = text[text.index("function authHeaders()") :][:300]
    assert '"X-Auth-Token": authToken()' in body
    assert '"X-Workspace-ID"' in body and "activeSpaceId()" in body


def test_active_space_id_is_defined_in_the_app_head_for_the_first_request():
    """`api()` calls `activeSpaceId()` on every request and the first is made
    at load, before the later classic scripts run (a boot error on GET /health)."""
    app = (JS / "app.js").read_text(encoding="utf-8")
    assert re.search(r"^function activeSpaceId\(", app, re.M)
    assert app.index("function activeSpaceId(") < app.index("async function api(")
    assert not re.search(r"^function activeSpaceId\(", (JS / "spaces-find.js").read_text(encoding="utf-8"), re.M)
