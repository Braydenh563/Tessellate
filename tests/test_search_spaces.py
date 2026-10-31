"""`GET /search` keeps to the space it is asked in (audit 2026-10-05, ARCH-03).

Measured before this: a note written in "work" came back from
`/search?q=zebracorn` asked with `X-Workspace-ID: personal`, while
`/entries/query`, the graph, the timeline and chat retrieval all returned
nothing. The index is raw SQL, so the space hook that narrows every ORM read
never saw it, and the finder and the palette call `/search` with no `space`.
"""

from __future__ import annotations


def _contents(client, q: str, workspace: str) -> list[int]:
    reply = client.get("/search", params={"q": q}, headers={"X-Workspace-ID": workspace})
    return [hit["id"] for hit in reply.json()["hits"] if hit["kind"] == "note"]


def test_a_note_in_one_space_is_not_found_from_another(client):
    work = client.post("/spaces", json={"name": "Client work"}).json()["id"]
    personal = client.post("/spaces", json={"name": "Home life"}).json()["id"]
    at_work = client.post(
        "/entries", json={"content": "zebracorn launch plan"}, headers={"X-Workspace-ID": work}
    ).json()["id"]
    at_home = client.post(
        "/entries", json={"content": "zebracorn birthday cake"}, headers={"X-Workspace-ID": personal}
    ).json()["id"]

    assert _contents(client, "zebracorn", work) == [at_work]
    assert _contents(client, "zebracorn", personal) == [at_home]
    assert set(_contents(client, "zebracorn", "all")) == {at_work, at_home}


def test_all_spaces_leaves_out_a_space_hidden_from_it(client):
    journal = client.post("/spaces", json={"name": "Journal"}).json()["id"]
    work = client.post("/spaces", json={"name": "Client work"}).json()["id"]
    secret = client.post(
        "/entries", json={"content": "quokkafish diary"}, headers={"X-Workspace-ID": journal}
    ).json()["id"]
    plain = client.post(
        "/entries", json={"content": "quokkafish budget"}, headers={"X-Workspace-ID": work}
    ).json()["id"]
    client.put(f"/spaces/{journal}", json={"hidden_from_all": True})

    assert _contents(client, "quokkafish", "all") == [plain]
    # Still found where it lives.
    assert _contents(client, "quokkafish", journal) == [secret]
