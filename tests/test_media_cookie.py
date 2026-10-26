"""The session token never travels in a media URL (WORLD_CLASS_PLAN §12, S1).

`mediaSrc()` used to append `?token=<session token>` to every `/media` and
`/files` URL, because a declarative load (`<img src>`, an `<iframe>`, a CSS
background) cannot attach the `X-Auth-Token` header. So the one credential
that opens the whole notebook landed in browser history, in uvicorn's access
log and in any note a person pasted an image address into.

Now unlocking sets an HttpOnly, SameSite=Strict cookie scoped to `/media` and
`/files` only, holding a media ticket rather than the session token: it rides
along on those loads by itself, scripts cannot read it, other sites cannot
make the browser send it, and it opens nothing but media. A `?token=` in a
media URL is refused.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tessellate.api import routes_auth
from tessellate.core import deps
from tests._app_js import app_js_text

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
COOKIE = routes_auth.MEDIA_COOKIE


@pytest.fixture(autouse=True)
def _clear_sessions():
    routes_auth._active_tokens.clear()
    routes_auth._failed_unlocks.clear()
    yield
    routes_auth._active_tokens.clear()
    routes_auth._failed_unlocks.clear()


@pytest.fixture()
def picture(app_state):
    media = deps.get_config().data_dir / "media"
    media.mkdir(parents=True, exist_ok=True)
    (media / "pic.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)
    return "/media/pic.png"


def _media_cookies(response) -> list[str]:
    return [
        value
        for key, value in response.headers.multi_items()
        if key.lower() == "set-cookie" and value.startswith(f"{COOKIE}=")
    ]


def _setup(client) -> str:
    response = client.post("/auth/setup", json={"password": "correct horse"})
    assert response.status_code == 200
    return response.json()["token"]


def test_unlocking_sets_a_media_cookie_scoped_to_the_two_media_paths(client):
    client.post("/auth/setup", json={"password": "correct horse"})
    client.cookies.clear()
    response = client.post("/auth/unlock", json={"password": "correct horse"})
    cookies = _media_cookies(response)
    assert sorted(re.search(r"Path=([^;]+)", c).group(1) for c in cookies) == ["/files", "/media"]
    for cookie in cookies:
        assert "HttpOnly" in cookie
        assert "SameSite=strict" in cookie or "SameSite=Strict" in cookie
    ticket = cookies[0].split(";", 1)[0].split("=", 1)[1]
    assert ticket and ticket != response.json()["token"], "the cookie holds a ticket, not the session token"


def test_a_picture_loads_with_the_cookie_alone(client, picture):
    _setup(client)
    assert client.get(picture).status_code == 200


def test_the_session_token_in_a_media_url_is_refused(client, picture):
    token = _setup(client)
    client.cookies.clear()
    assert client.get(picture, params={"token": token}).status_code == 401
    assert client.get(picture, headers={"X-Auth-Token": token}).status_code == 200


def test_the_media_cookie_opens_nothing_but_media(client):
    _setup(client)
    assert client.get("/entries").status_code == 401


def test_locking_ends_the_ticket(client, picture):
    token = _setup(client)
    ticket = client.cookies.get(COOKIE, path="/media")
    response = client.post("/auth/lock", headers={"X-Auth-Token": token})
    assert any("Max-Age=0" in c or "max-age=0" in c.lower() for c in _media_cookies(response))
    client.cookies.clear()
    client.cookies.set(COOKIE, ticket, path="/media")
    assert client.get(picture).status_code == 401


def test_a_ticket_dies_with_its_session(client, picture):
    token = _setup(client)
    routes_auth._active_tokens.pop(token)
    assert client.get(picture).status_code == 401


def test_a_restored_token_can_ask_for_its_cookie_again(client, picture):
    """A browser restart drops nothing here (the cookie has a Max-Age), but a
    token kept in localStorage in a profile that lost its cookies must not
    leave every picture broken until the next unlock."""
    token = _setup(client)
    client.cookies.clear()
    assert client.get(picture).status_code == 401
    response = client.post("/auth/media-session", headers={"X-Auth-Token": token})
    assert response.status_code == 200
    assert _media_cookies(response)
    assert client.get(picture).status_code == 200


def test_the_media_session_route_needs_the_header(client):
    _setup(client)
    client.cookies.clear()
    assert client.post("/auth/media-session").status_code == 401


def test_changing_the_password_moves_the_cookie_to_the_new_session(client, picture):
    token = _setup(client)
    old_ticket = client.cookies.get(COOKIE, path="/media")
    response = client.post(
        "/auth/change-password",
        json={"current_password": "correct horse", "new_password": "battery staple"},
        headers={"X-Auth-Token": token},
    )
    assert response.status_code == 200
    assert _media_cookies(response)
    assert client.get(picture).status_code == 200
    client.cookies.clear()
    client.cookies.set(COOKIE, old_ticket, path="/media")
    assert client.get(picture).status_code == 401


def test_media_src_puts_no_credential_in_the_url():
    app = app_js_text()
    start = app.index("function mediaSrc(url)")
    body = app[start : app.index("\n}\n", start)]
    code = "\n".join(line.split("//", 1)[0] for line in body.splitlines())
    assert "token" not in code.lower(), code


def test_no_frontend_file_builds_a_token_query():
    offenders = []
    for path in sorted((FRONTEND / "js").glob("*.js")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("//", 1)[0]
            if re.search(r"[?&]token=", code):
                offenders.append(f"{path.name}:{number}: {line.strip()}")
    assert offenders == []


def test_the_boot_path_asks_for_the_media_cookie_before_the_app_starts():
    app = app_js_text()
    assert "/auth/media-session" in app
    # The stored-token path. The password-free path above it (sign-in off,
    # INBOX 426 aa) needs no second ask: `/auth/auto-session` sets the cookie
    # in its own response, as unlock does.
    init = app[app.index("async function initAuth("):]
    boot = init[init.index("  if (!authToken()) {"):]
    boot = boot[: boot.index("startApp();") + len("startApp();")]
    assert "refreshMediaSession" in boot


def test_asking_again_replaces_the_ticket_rather_than_adding_one(client):
    token = _setup(client)
    for _ in range(5):
        client.post("/auth/media-session", headers={"X-Auth-Token": token})
    assert list(routes_auth._media_tickets.values()).count(token) == 1


def test_the_media_cookie_is_secure_on_loopback_and_https_only():
    """CodeQL py/insecure-cookie: `Secure` wherever the browser will still
    store it (https, or http on a loopback host, which is how the desktop
    window and a local browser tab reach the app), and not on a plain-http
    LAN host, where a `Secure` cookie is dropped and every picture breaks."""
    from starlette.requests import Request

    def req(url):
        scheme, rest = url.split("://", 1)
        host = rest.split("/", 1)[0]
        name, _, port = host.partition(":")
        return Request({
            "type": "http", "scheme": scheme, "server": (name, int(port or 80)),
            "path": "/", "headers": [(b"host", host.encode())], "query_string": b"",
        })

    assert routes_auth._cookie_secure(req("http://127.0.0.1:8000/"))
    assert routes_auth._cookie_secure(req("http://localhost:8000/"))
    assert routes_auth._cookie_secure(req("https://notebook.lan/"))
    assert not routes_auth._cookie_secure(req("http://192.168.1.20:8000/"))
    assert not routes_auth._cookie_secure(req("http://testserver/"))


# --- the desktop window's "Open in a new tab" (the owner, 2026-10-27) ---
#
# The window hands a link to the system browser, which has its own cookie
# jar and so no media cookie: the tab showed "The app is locked". A one-file
# link that lives two minutes opens it there without the session token ever
# being in a URL.


def test_a_one_file_link_opens_that_file_in_a_browser_without_the_cookie(client, picture):
    token = _setup(client)
    response = client.post("/auth/media-link", json={"path": picture}, headers={"X-Auth-Token": token})
    assert response.status_code == 200
    url = response.json()["url"]
    assert url.startswith(picture + "?once=") and token not in url
    client.cookies.clear()
    first, again = client.get(url), client.get(url)  # a viewer may ask twice (PDF ranges)
    assert first.status_code == 200 and again.status_code == 200


def test_the_link_opens_no_other_file_and_no_api(client, picture):
    token = _setup(client)
    url = client.post("/auth/media-link", json={"path": picture}, headers={"X-Auth-Token": token}).json()["url"]
    once = url.split("once=")[1]
    client.cookies.clear()
    other = client.get("/media/other.png", params={"once": once})
    api = client.get("/entries", params={"once": once})
    assert other.status_code == 401 and api.status_code == 401


def test_the_link_expires_and_dies_with_its_session(client, picture, monkeypatch):
    token = _setup(client)
    url = client.post("/auth/media-link", json={"path": picture}, headers={"X-Auth-Token": token}).json()["url"]
    clock = [routes_auth.time.time() + routes_auth.MEDIA_LINK_SECONDS + 1]
    monkeypatch.setattr(routes_auth.time, "time", lambda: clock[0])
    client.cookies.clear()
    late = client.get(url)
    assert late.status_code == 401
    monkeypatch.undo()
    url = client.post("/auth/media-link", json={"path": picture}, headers={"X-Auth-Token": token}).json()["url"]
    client.post("/auth/lock", headers={"X-Auth-Token": token})
    client.cookies.clear()
    locked = client.get(url)
    assert locked.status_code == 401


@pytest.mark.parametrize("path", ["/entries", "/media", "/media/../auth/x", "https://evil.example/media/a.png", "/media/a.png?x=1"])
def test_a_link_is_only_for_a_media_or_file_path(client, path):
    token = _setup(client)
    response = client.post("/auth/media-link", json={"path": path}, headers={"X-Auth-Token": token})
    assert response.status_code == 422


def test_the_link_route_needs_the_header(client):
    _setup(client)
    response = client.post("/auth/media-link", json={"path": "/media/pic.png"})
    assert response.status_code == 401


def test_the_viewer_asks_for_a_link_in_the_desktop_window():
    view = (FRONTEND / "js" / "lightbox-view.js").read_text(encoding="utf-8")
    body = view[view.index('"Open in a new tab"'):][:1200]
    assert "/auth/media-link" in body and "desktopShell()" in body
