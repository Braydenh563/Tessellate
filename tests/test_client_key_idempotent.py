"""A resent note is saved once, across restarts and races (audit 2026-10-05,
ARCH-23; INBOX 434 for restarts).

The offline queue resends a save whose answer was lost, with the same
`client_key`. The guard was an in-memory dict, checked, then created, then
remembered: two concurrent resends both created, and a resend after a
restart was a second note. The key is now a column with a unique index.
"""

from __future__ import annotations

import threading

from fastapi.testclient import TestClient

from tessellate.entry import filing_background
from tessellate.core import deps


def _count(client) -> int:
    return int(client.get("/entries", params={"limit": 5}).headers["X-Total-Count"])


def test_a_resend_after_a_restart_is_the_same_note(client):
    first = client.post("/entries", json={"content": "written offline", "client_key": "k-restart"}).json()
    filing_background._DELIVERED.clear()  # what a restart forgets
    again = client.post("/entries", json={"content": "written offline", "client_key": "k-restart"})
    assert again.json()["id"] == first["id"]
    assert _count(client) == 1


def test_two_resends_at_once_make_one_note(client, app_state):
    from tessellate.api.app import create_app

    app = create_app()
    ids: list[int] = []
    barrier = threading.Barrier(2)

    def send() -> None:
        local = TestClient(app)
        barrier.wait()
        reply = local.post("/entries", json={"content": "sent twice", "client_key": "k-race"})
        assert reply.status_code in (200, 201), reply.text
        ids.append(reply.json()["id"])

    threads = [threading.Thread(target=send) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    assert len(ids) == 2 and ids[0] == ids[1], ids
    with deps.get_db().engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT count(*) FROM entries WHERE client_key = 'k-race'").scalar() == 1
