"""No bare `fetch(` outside the API door (WORLD_CLASS_PLAN section 10, F5).

"13 raw `fetch()` calls beside `api()`. Each re-implements the auth header,
the error contract and the offline path; one is `/chat/stream`, the most
important call in the app." Each of those had already broken once in its own
way: `/chat/stream` went a release without `X-Workspace-ID`, `/help/ask/stream`
without `X-Auth-Token`, an upload landed in the wrong space.

`api()` (app.js) is now the one door for every request to the server:

- a `FormData` body keeps the browser's multipart type instead of being
  stamped JSON, and a caller's own `headers` are merged rather than
  replacing the auth and space headers;
- it returns the `Response`, so a streamed body is still read as it arrives;
- `api.upload(path, form)` and `api.stream(path, options)` name the two
  shapes the hand-rolled calls existed for.

What remains, each with its reason, is the allowlist below; a new bare
`fetch(` anywhere else fails here.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"

#: file -> bare `fetch(` calls it may make, and why.
ALLOWED = {
    # The door itself, and the two sign-in calls before a session exists
    # whose refusal is an answer rather than a lockout.
    "app.js": 2,
    # Loaded before app.js to report a page that failed to start; `api()` may
    # not exist when it runs.
    "boot-guard.js": 1,
    # The server-down banner's own "is anything listening" probes: going
    # through `api()` would raise the banner they exist to lower.
    "status.js": 2,
    # A staged picture's `blob:` address in this tab, not a request.
    "attachment-actions.js": 1,
    # A pasted picture's `blob:` or `data:` address on the way into a Word
    # file, not a request; the notebook's own pictures go through `api()`.
    "documents-word.js": 1,
    # Pages of their own with no app.js and so no `api()`: the quick capture
    # window (capture.html) and the web clipper (clip.html), one request each,
    # carrying the token themselves.
    "capture.js": 1,
    "clip.js": 1,
    # The desktop companion's window (desktop-companion.html): a page of its
    # own as well, one `call` carrying the token.
    "desk-companion.js": 1,
    # A Web Worker (the offline translator, Brief 83) has no app.js and so no
    # `api()`: its engine (.wasm) and model files, from an open route.
    "translate-worker.js": 2,
}

#: `fetch(` as a call: not `.fetch(` (a method), not a word ending in fetch.
CALL = re.compile(r"(?<![\w.$])fetch\(")


def _calls(text: str) -> int:
    count = 0
    for line in text.splitlines():
        code = line.split("//", 1)[0] if not line.lstrip().startswith(("*", "/*")) else ""
        count += len(CALL.findall(code))
    return count


def test_no_bare_fetch_outside_the_door() -> None:
    found = {}
    for path in sorted(JS.glob("*.js")):
        n = _calls(path.read_text(encoding="utf-8"))
        if n:
            found[path.name] = n
    extra = {name: n for name, n in found.items() if n > ALLOWED.get(name, 0)}
    assert not extra, f"use api(), api.upload() or api.stream() instead of a bare fetch: {extra}"
    gone = {name: (n, found.get(name, 0)) for name, n in ALLOWED.items() if found.get(name, 0) < n}
    assert not gone, f"a fetch moved onto api(): lower ALLOWED to match (was, now): {gone}"


def test_the_door_has_both_helpers_and_keeps_multipart() -> None:
    app = (JS / "app.js").read_text(encoding="utf-8")
    assert "api.upload = " in app and "api.stream = " in app
    assert "body instanceof FormData" in app
    assert "...fetchOptions.headers" in app


def test_the_lint_sees_a_bare_fetch() -> None:
    assert _calls('const r = await fetch("/x");') == 1
    assert _calls("const r = await window.fetch('/x');") == 0
    assert _calls("// fetch(\"/x\") in a comment") == 0
    assert _calls("prefetch(x); refetch(y);") == 0
