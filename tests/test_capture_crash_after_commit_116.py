"""A crash between the commit and the answer keeps the note once (L-world-class-116).

The capture bar sends a `client_key`; if the server dies after the commit and
before the response, the client sees a failure and retries. The note is on
disk, so the retry must return it, not make a second one.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tessellate.api import routes_entries


def _crashing_client(monkeypatch):
    from tessellate.api.app import create_app

    real = routes_entries._to_out
    state = {"armed": True}

    def to_out(*args, **kwargs):
        if state["armed"]:
            state["armed"] = False
            raise RuntimeError("server died after the commit")
        return real(*args, **kwargs)

    monkeypatch.setattr(routes_entries, "_to_out", to_out)
    return TestClient(create_app(), raise_server_exceptions=False)


def _count(client) -> int:
    return int(client.get("/entries", params={"limit": 5}).headers["X-Total-Count"])


@pytest.mark.parametrize("restart", [False, True], ids=["same process", "after a restart"])
def test_the_note_is_kept_once_and_the_retry_does_not_duplicate_it(client, monkeypatch, restart):
    crashing = _crashing_client(monkeypatch)
    body = {"content": "captured just before the crash", "client_key": f"k-crash-{restart}"}
    failed = crashing.post("/entries", json=body)
    assert failed.status_code >= 500
    assert _count(client) == 1  # the commit happened, the answer did not
    if restart:
        routes_entries._DELIVERED.clear()  # what a restart forgets
    retry = crashing.post("/entries", json=body)
    assert retry.status_code in (200, 201), retry.text
    assert _count(client) == 1
    assert retry.json()["content"].startswith("captured just before the crash")
    again = crashing.post("/entries", json=body)
    assert again.json()["id"] == retry.json()["id"]
    assert _count(client) == 1
