"""Library's activity honours the query and the space (audit 2026-10-05, ARCH-24).

Measured before: `/library?q=zebracorn` in "personal" returned 200 activity
rows from every space: `_activity` took no `q`, and the audit log has no
space column, so nothing narrowed it.
"""

from __future__ import annotations


def _activity(client, q: str, workspace: str) -> list[dict]:
    reply = client.get("/library", params={"q": q}, headers={"X-Workspace-ID": workspace})
    assert reply.status_code == 200
    return [item for item in reply.json()["items"] if item["kind"] == "activity"]


def test_activity_keeps_to_the_query_and_the_space(client):
    work = client.post("/spaces", json={"name": "Client work"}).json()["id"]
    personal = client.post("/spaces", json={"name": "Home life"}).json()["id"]
    note = client.post(
        "/entries", json={"content": "zebracorn launch plan"}, headers={"X-Workspace-ID": work}
    ).json()["id"]
    client.post("/entries", json={"content": "a walk in the park"}, headers={"X-Workspace-ID": personal})

    in_work = _activity(client, "zebracorn", work)
    assert in_work
    assert any(item["entry_id"] == note for item in in_work)
    assert not [item for item in _activity(client, "zebracorn", personal) if item["entry_id"] == note]
    # No query: personal still sees nothing about the work note.
    assert not [item for item in _activity(client, "", personal) if item["entry_id"] == note]
