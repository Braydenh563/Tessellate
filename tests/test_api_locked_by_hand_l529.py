"""After Lock, `api()` sends nothing until a key is back (L529).

The 2026-11-21 sweep locked the app on the dashboard and six loaders that
woke afterwards (/chat/recent, /chat/suggestions, /ask-history/stats,
/entries/most-accessed, /conversations, /skills) went out with no key, each
answered 401 and logged an error behind the lock. With the guard: none sent,
and an unlock reads /entries with 200.
"""

from __future__ import annotations

from tests._app_js import app_js_text


def _api_body() -> str:
    js = app_js_text()
    start = js.index("async function api(path, options = {})")
    return js[start : js.index("\n}\n", start)]


def test_a_hand_lock_without_a_key_refuses_before_fetch():
    body = _api_body()
    guard = body.index("if (lockedByHand && !authToken() && !ownsAuthErrors")
    assert guard < body.index("await fetch(path")
    line = body[guard : body.index("\n", guard)]
    #: Sign-in itself and the health probe still go out.
    assert '!path.startsWith("/auth/")' in line and '!path.startsWith("/health")' in line
    #: Refused as the lockout every caller already stays quiet for.
    assert "isLockout: true" in body[guard : guard + 400]
