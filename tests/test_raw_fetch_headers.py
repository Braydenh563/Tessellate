"""Every hand-rolled `fetch()` to a locked route carries the auth header.

`api()`/`apiJson()` (app.js) add `X-Auth-Token` to everything they send. A
few calls cannot go through them (a streaming body, a multipart upload, an
event stream) and are written as a bare `fetch()`, and each of those has to
add the header itself. Two forgot, months apart, and both failed the same
quiet way: a locked app answered 401, the caller fell back to something that
worked, and the feature was reported as "broken" while its tests were green
(`/chat/stream` lost the space header; `/help/ask/stream` never sent the
token, so the Guide never streamed on a locked notebook).

The lint reads the source, since the suite cannot log a browser in: a
`fetch(` whose first argument is an app path must name `X-Auth-Token` within
the call. Routes served before login are listed, not exempted by shape.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

#: Routes on `open_router` (no session needed), by path prefix. `/health`
#: is open by design (app.py: "/auth itself and /health stay open"); the
#: server-down banner probes it precisely because it needs no session.
#: `/vendor/` is the static mount (app.py `RevalidatedStatic`), served with no session
#: like every css and js file; the PDF export fetches its icon font there (DX13).
OPEN_ROUTES = ("/logs/client", "/health", "/vendor/")

FETCH = re.compile(r"""fetch\(\s*(["'`])(/[^"'`]*)""")


def _raw_fetches():
    for path in sorted((FRONTEND / "js").glob("*.js")):
        text = path.read_text(encoding="utf-8")
        for match in FETCH.finditer(text):
            route = match.group(2)
            if route.startswith(OPEN_ROUTES):
                continue
            #: The call's argument list: up to the matching close paren, or
            #: 1,200 characters, whichever is first. Headers sit at its top.
            window = text[match.start() : match.start() + 1200]
            line = text.count("\n", 0, match.start()) + 1
            yield path.name, line, route, window


def test_every_raw_fetch_to_a_locked_route_sends_the_auth_token():
    missing = [
        f"{name}:{line} fetch({route!r})"
        for name, line, route, window in _raw_fetches()
        if "X-Auth-Token" not in window and "authHeaders()" not in window
    ]
    assert not missing, "raw fetch without X-Auth-Token (use api() or add the header):\n" + "\n".join(missing)


def test_the_lint_sees_the_fetches_it_is_for():
    """A regex that matches nothing passes for the wrong reason."""
    routes = {route for _, _, route, _ in _raw_fetches()}
    # The two streams it was written for went through `api.stream` on
    # 2026-10-05 (F5, `tests/test_no_bare_fetch.py`); the raw fetches left
    # are the sign-in calls (the media session went through `api()` too, in
    # shell-reminders.js's `refreshMediaSession`).
    assert "/auth/auto-session" in routes
