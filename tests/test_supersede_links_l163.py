"""O11 (L163, INBOX 1842): a note can be marked as superseding another, and
the older one shows a link to the newer, with no table beside the link-type
system: `supersedes` is a built-in kind whose inverse reads "Superseded by"."""

from __future__ import annotations


def _note(client, text: str) -> int:
    return client.post("/entries", json={"content": text}).json()["id"]


def test_the_older_note_reads_superseded_by_the_newer(client):
    old = _note(client, "The gym opens at 6am on weekdays")
    new = _note(client, "The gym now opens at 5am on weekdays")
    made = client.post(f"/entries/{new}/links", json={"target_id": old, "link_type": "supersedes"})
    assert made.status_code == 200, made.text

    newer = next(link for link in client.get(f"/entries/{new}").json()["links"] if link["entry_id"] == old)
    older = next(link for link in client.get(f"/entries/{old}").json()["links"] if link["entry_id"] == new)
    assert (newer["link_type"], newer["link_label"], newer["direction"]) == ("supersedes", "Supersedes", "out")
    assert (older["link_type"], older["link_label"], older["direction"]) == ("supersedes", "Superseded by", "in")


def test_the_kind_is_offered_beside_the_others(client):
    keys = [t["key"] for t in client.get("/relation-types").json()]
    assert "supersedes" in keys
