"""Every route answers 401 to a stranger, and this test walks them all.

The gate is per router: `app.include_router(..., dependencies=locked)` in
`api/app.py`. That works, and it is invisible when it is missing. A new router
added without `dependencies=locked` reads exactly like one with it, ships
open, and nothing in the suite notices, because each feature's own tests send
a token. WORLD_CLASS_PLAN section 10, F9, which is why this walks
`app.routes` rather than naming endpoints: a route that does not exist yet is
the one this is for.

The allowlist below is the whole security decision, in one place and with a
reason per line. Anything not in it must refuse an unauthenticated caller.

**A route missing from the app is not the failure this catches.** The test
sends nonsense path parameters on purpose (`1` for an int, `x` for the rest):
a locked route refuses before it ever looks at them, which is the property
being asserted. A route that answers 404 or 422 to this request looked at the
request first, and that is the finding.
"""

from __future__ import annotations

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from tessellate.api import routes_auth

#: Paths that must stay reachable without a token, each for a stated reason.
#: A path is matched exactly; a prefix entry ends in `/`.
OPEN = {
    # The unlock itself, and the "is a password set?" question the lock screen
    # asks before it can draw the right mode.
    "/auth/status",
    "/auth/unlock",
    "/auth/setup",
    "/auth/lock",
    # The password-free session for this computer when "Ask for a password
    # when the app opens" is off (INBOX 426 aa). It decides for itself, from
    # the connection's own address and never a header, and answers 403 to
    # everyone else; `test_sign_in_off_opens_no_route_by_itself` below and
    # tests/test_optional_sign_in.py hold that.
    "/auth/auto-session",
    # The lock screen's "Forgot your password?" card (INBOX 663): whoever
    # calls them has no password by definition. Each answers 403 to anything
    # but this computer (`_from_this_computer`), `/auth/recover` needs the
    # recovery key and is throttled like an unlock, and `/auth/reset` needs
    # RESET typed, the same reset the terminal command already did;
    # tests/test_forgot_password.py holds all three.
    "/auth/recover",
    "/auth/reset",
    "/auth/reset-code",
    # The LAN authority's public certificate (INBOX 866): iOS installs a
    # profile only from a plain navigation, which carries no token, and every
    # TLS handshake on the LAN port already sends it. Never a key.
    "/auth/lan-certificate.pem",
    # Liveness, deliberately: the launcher polls it before the vault exists.
    "/health",
    # Which notebook this server serves, as a hash of its data dir, so a
    # launch can tell its own server from another notebook's (WC 423 g).
    "/instance",
    # A second desktop launch asking this one to bring its window forward.
    # It has no session; it carries the token from this server's own
    # `instance.lock` in the data directory instead, and a wrong or missing
    # token is a 403 (`tests/test_instance_lock.py`).
    "/instance/focus",
    # The browser's own crash reports, which have to reach the log *before*
    # unlock, because that is when the failure they describe happens
    # (`routes_settings.open_router`).
    "/logs/client",
    # The page itself and its assets. Serving the lock screen to someone who
    # has not unlocked is the point of a lock screen.
    "/",
    "/favicon.svg",
    "/manifest.webmanifest",
    "/sw.js",
    # What the service worker shows when the server cannot be reached
    # (frontend/sw.js, tests/test_pwa_shell.py): static markup, and the
    # one page a stopped notebook's owner must always be able to see.
    "/offline.html",
    # The Run button's sandbox page (INBOX 404): static markup with no data in
    # it, served under its own `sandbox allow-scripts; connect-src 'none'`
    # policy, and framed by an iframe, which cannot send the token header
    # (`api/run_sandbox.py`; tests/test_run_sandbox.py holds the policy).
    "/documents/run-sandbox",
    # Its Python twin and the Pyodide runtime files it loads (INBOX 404): the
    # same opaque origin, so no token; the files are the public Pyodide
    # release out of the extra's folder, only the names the extra unpacks,
    # 404 until it is installed (tests/test_run_sandbox.py).
    "/documents/run-sandbox/python",
    "/documents/pyodide/{name}",
    #: The offline translator's engine and model (routes_translate.files_router):
    #: a Worker's fetch carries no token, and the files are public, nothing of
    #: the notebook's (Brief 83).
    "/translate/files/{name}",
    #: A reminder notification's Done and Snooze, pressed by the service worker
    #: after the tab is gone. It holds no session on purpose (a session token
    #: in the notification store opened the whole notebook); it carries a token
    #: the server minted for that one reminder and those two actions, signed
    #: and good for 24 hours, checked before the reminder is looked at
    #: (core/reminder_token.py; tests/test_reminder_scoped_token.py holds that
    #: a forged, expired or other reminder's token is refused and that the
    #: token opens no other route).
    "/reminders/{reminder_id}/notification-act",
}

#: Prefixes, for the same reason, where the path carries a file name.
OPEN_PREFIXES = ("/static/", "/css/", "/js/", "/assets/", "/icons/", "/fonts/")

#: Methods that are never asserted: HEAD and OPTIONS are handled by Starlette
#: itself (CORS preflight must answer without a token or no browser can make
#: the real request).
SKIP_METHODS = {"HEAD", "OPTIONS", "TRACE"}


def _fill(path: str) -> str:
    """A path with its parameters filled in with values a locked route never
    reads. `{entry_id:int}` style converters are handled too."""
    out = []
    for part in path.split("/"):
        if part.startswith("{") and part.endswith("}"):
            name = part[1:-1]
            out.append("1" if ("int" in name or name.endswith("_id") or name == "id") else "x")
        else:
            out.append(part)
    return "/".join(out)


def _routes(app):
    """Every (method, path) the app serves, included routers walked through.

    `app.routes` is not the list it looks like: this FastAPI keeps an included
    router as one lazy `_IncludedRouter` entry holding the real router, so a
    plain `isinstance(route, APIRoute)` filter over `app.routes` sees three
    routes out of two hundred and passes with the whole API unchecked. That is
    the shape of bug this file exists to catch, so it is worth the recursion.
    """
    seen = set()

    def walk(routes, prefix=""):
        for route in routes:
            inner = getattr(route, "original_router", None)
            if inner is not None:
                context = getattr(route, "include_context", None)
                yield from walk(inner.routes, prefix + getattr(context, "prefix", ""))
                continue
            if not isinstance(route, APIRoute):
                continue
            for method in sorted(set(route.methods or []) - SKIP_METHODS):
                pair = (method, prefix + route.path)
                if pair not in seen:
                    seen.add(pair)
                    yield pair

    yield from walk(app.routes)


@pytest.fixture()
def locked_client(app_state):
    """A notebook with a password set and nobody unlocked."""
    from tessellate.api.app import create_app

    client = TestClient(create_app())
    made = client.post("/auth/setup", json={"password": "correct horse battery"})
    assert made.status_code in (200, 201), made.text
    routes_auth._active_tokens.clear()  # the setup call hands back a token
    return client


def test_every_route_refuses_a_caller_with_no_token(locked_client):
    app = locked_client.app
    open_now = []
    for method, path in _routes(app):
        if path in OPEN or path.startswith(OPEN_PREFIXES):
            continue
        response = locked_client.request(method, _fill(path))
        if response.status_code != 401:
            open_now.append(f"{method} {path} -> {response.status_code}")
    assert not open_now, (
        "these routes answered an unauthenticated caller with something other "
        "than 401, so they are either open or they validate the request before "
        "they check who is asking: " + "; ".join(open_now)
    )


def test_the_allowlist_names_only_routes_that_exist(locked_client):
    """An allowlist entry for a route that has been renamed or removed is a
    hole waiting for the name to be reused."""
    paths = {path for _method, path in _routes(locked_client.app)}
    # `/` and the static files are served by mounts rather than API routes, so
    # they are checked by reaching them rather than by name.
    named = {entry for entry in OPEN if entry.startswith("/auth") or entry in {"/health", "/instance", "/logs/client"}}
    missing = sorted(entry for entry in named if entry not in paths)
    assert not missing, f"allowlisted but no longer routed: {missing}"


def test_the_lock_screen_itself_is_still_served(locked_client):
    """The other half of the same decision: if `/` were locked, a locked
    notebook would answer its owner with JSON instead of a way back in."""
    page = locked_client.get("/")
    assert page.status_code == 200
    assert "lock-password" in page.text


@pytest.mark.parametrize("address", ["127.0.0.1", "192.168.1.50"])
def test_sign_in_off_opens_no_route_by_itself(locked_client, address):
    """Sign-in off hands this computer a session through one route,
    `/auth/auto-session`; it never makes the gate itself wave a tokenless
    caller through, from loopback or from anywhere else. A gate that did
    would open every route to any page that can reach the port."""
    from tessellate.core import deps

    deps.get_config().set_preference("ask_password_on_open", False)
    caller = TestClient(
        locked_client.app, base_url="http://127.0.0.1:8795", client=(address, 50000)
    )
    open_now = []
    for method, path in _routes(locked_client.app):
        if path in OPEN or path.startswith(OPEN_PREFIXES):
            continue
        response = caller.request(method, _fill(path))
        if response.status_code != 401:
            open_now.append(f"{method} {path} -> {response.status_code}")
    assert not open_now, "open with sign-in off: " + "; ".join(open_now)
