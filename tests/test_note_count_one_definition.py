"""One definition of "how many notes" (INBOX 1439, audit 1029 N13).

A note is every entry not in the bin, archived included; boards and drafts
(a blank one most of all) are not notes. Six surfaces used to count it six ways (282, 279, 277 in
the same minute); `manager.count_notes` now holds the rule and each calls it.

The notebook below: a normal note, an archived one and a private one count;
a binned note, a draft with words in it and a blank empty draft do not.
So the answer is 3.
"""

from __future__ import annotations

from tessellate.api import routes_diag
from tessellate.core.database import Entry
from tessellate.entry import manager


def _build(client, session):
    ids = {}
    for key, text in (
        ("normal", "a normal note"),
        ("archived", "an archived note"),
        ("binned", "a binned note"),
        ("private", "a private note"),
        ("draft", "a half-typed draft"),
    ):
        made = client.post("/entries", json={"content": text}).json()
        client.put(f"/entries/{made['id']}", json={"category": "Work"})
        ids[key] = made["id"]
    client.post(f"/entries/{ids['archived']}/archive")
    client.delete(f"/entries/{ids['binned']}")
    session.add(Entry(content="   ", is_draft=True))
    session.get(Entry, ids["private"]).is_private = True
    session.get(Entry, ids["draft"]).is_draft = True
    session.commit()
    return ids


def test_every_surface_reports_the_same_note_count(client, session):
    _build(client, session)
    routes_diag._counts.update(at=0.0, value={})
    counts = {
        "manager.count_notes": manager.count_notes(session),
        "GET /entries/count: count": client.get("/entries/count").json()["count"],
        "GET /diagnostics: counts.notes": client.get("/diagnostics").json()["counts"]["notes"],
        "GET /statistics: notebook.notes": client.get("/statistics").json()["notebook"]["notes"],
        "GET /graph: len(nodes)": len(client.get("/graph").json()["nodes"]),
    }
    assert set(counts.values()) == {3}, counts


def test_subsets_build_on_the_same_base(client, session):
    ids = _build(client, session)
    listed = client.get("/entries")
    # The list leaves the archive to its own view and still returns the draft
    # row (the client sorts drafts out): normal, private and the draft.
    total = manager.count_notes(session, include_archived=False, include_drafts=True)
    assert int(listed.headers["X-Total-Count"]) == total == 3
    assert ids["archived"] not in {e["id"] for e in listed.json()}
    # A category counts what the Notes list shows under it: no archive, no
    # draft, so normal and private only.
    assert {c["name"]: c["count"] for c in client.get("/categories").json()}["Work"] == 2
