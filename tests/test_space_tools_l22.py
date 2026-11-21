"""WORLD_CLASS_PLAN 27.1 (L-world-class-22): a space's own tools. A move keeps
every link (decision: never drop a link the user made), backlinks resolve from
both ends across spaces, and a space exports on its own."""

from __future__ import annotations

import io
import zipfile

from sqlalchemy import func, select

from tessellate.core.database import EntryLink


def _note(client, text, space=None):
    headers = {"X-Workspace-ID": space} if space else {}
    return client.post("/entries", json={"content": text}, headers=headers).json()


def _link_count(session) -> int:
    session.info["workspace_id"] = "all"
    return session.scalar(select(func.count()).select_from(EntryLink))


def _ends(client, entry_id, space):
    got = client.get(f"/entries/{entry_id}/connections", headers={"X-Workspace-ID": space}).json()
    return {r["id"] for r in got["outgoing"]}, {r["id"] for r in got["incoming"]}, got


def test_a_move_keeps_every_link_and_both_ends_see_it(client):
    a = _note(client, "Passport renewal plan")
    b = _note(client, "Hotel in Kyoto booking")
    c = _note(client, "Third note stays too")
    made = [client.post(f"/entries/{a['id']}/links", json={"target_id": b["id"]}),
            client.post(f"/entries/{c['id']}/links", json={"target_id": a["id"]})]
    moved = client.post("/spaces/work/move-notes", json={"ids": [a["id"]]}).json()
    assert [r.status_code for r in made] == [200, 200] and moved["moved"] == 1
    # a is now in work; b and c stayed in default.
    out_a, in_a, got_a = _ends(client, a["id"], "work")
    assert out_a == {b["id"]} and in_a == {c["id"]}, got_a
    assert {r["space_name"] for r in got_a["outgoing"] + got_a["incoming"]} == {"Default space"}
    _out_b, in_b, got_b = _ends(client, b["id"], "default")
    assert in_b == {a["id"]}, got_b
    assert got_b["incoming"][0]["space_name"] == "Work"
    out_c, _in_c, _ = _ends(client, c["id"], "default")
    assert out_c == {a["id"]}


def test_the_link_rows_survive_a_move_and_a_move_back(client, session):
    a = _note(client, "One")
    b = _note(client, "Two")
    client.post(f"/entries/{a['id']}/links", json={"target_id": b["id"]})
    before = _link_count(session)
    client.post("/spaces/work/move-notes", json={"ids": [a["id"]]})
    assert _link_count(session) == before
    client.post("/spaces/default/move-notes", json={"ids": [a["id"]]})
    assert _link_count(session) == before
    out_a, _in, got = _ends(client, a["id"], "default")
    assert out_a == {b["id"]} and "space_name" in got["outgoing"][0]
    assert got["outgoing"][0]["space_name"] is None  # same space: no chip suffix


def _zip_text(response) -> tuple[str, dict]:
    assert response.status_code == 200, response.text
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    import json

    manifest = json.loads(archive.read("index.json")) if "index.json" in archive.namelist() else {}
    return "\n".join(archive.read(n).decode("utf8", "ignore") for n in archive.namelist() if n.endswith((".md", ".json"))), manifest


def test_a_space_exports_only_its_own_notes_documents_and_boards(client):
    work = client.post("/spaces", json={"name": "Client work"}).json()["id"]
    _note(client, "alpha stays in the default space")
    _note(client, "beta lives in the client space", work)
    doc = client.post("/documents", json={"title": "Client brief", "content": "brief text"}, headers={"X-Workspace-ID": work})
    assert doc.status_code in (200, 201), doc.text
    other = client.post("/documents", json={"title": "Home doc", "content": "home text"})
    assert other.status_code in (200, 201), other.text
    got = client.get(f"/spaces/{work}/export", headers={"X-Workspace-ID": "default"})
    text, manifest = _zip_text(got)
    assert "beta lives in the client space" in text and "Client brief" in text
    assert "alpha stays" not in text and "Home doc" not in text
    assert manifest["counts"]["notes"] == 1 and manifest["counts"]["documents"] == 1
    assert "client-work" in got.headers["content-disposition"]


def test_exporting_a_missing_space_is_404_and_all_is_refused(client):
    missing, everything = client.get("/spaces/nope/export"), client.get("/spaces/all/export")
    assert missing.status_code == 404 and everything.status_code in (400, 404)


def test_a_locked_private_space_will_not_export_and_an_open_one_does(client):
    from tessellate.core import spacelock

    spacelock.close_all()
    token = client.post("/auth/setup", json={"password": "first-pass"}).json()["token"]
    client.headers.update({"X-Auth-Token": token})
    secret = client.post("/spaces", json={"name": "Vault room", "is_private": True}).json()["id"]
    opened = client.post("/private-spaces/unlock", json={"secret": "first-pass"})
    assert opened.status_code == 200
    _note(client, "the safe code is 4715", secret)
    text, _ = _zip_text(client.get(f"/spaces/{secret}/export"))
    assert "the safe code is 4715" in text
    spacelock.close_all()
    locked = client.get(f"/spaces/{secret}/export")
    assert locked.status_code == 423


def test_the_dashboard_summary_counts_what_the_space_shows(client):
    work = client.post("/spaces", json={"name": "Counted"}).json()["id"]
    first = _note(client, "one kept", work)
    gone = _note(client, "one binned", work)
    binned = client.delete(f"/entries/{gone['id']}", headers={"X-Workspace-ID": work})
    assert binned.status_code in (200, 204)
    got = client.get(f"/spaces/{work}/summary").json()
    assert got == {"notes": 1, "documents": 0, "boards": 0}, (got, first)
    missing = client.get("/spaces/nope/summary")
    assert missing.status_code == 404
