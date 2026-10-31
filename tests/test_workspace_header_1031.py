"""`X-Workspace-ID` must name a space (audit 1031 BK3, AR1).

The header became an ORM filter with no lookup: `None`, `bogus` and `../x` all
answered 200, and a note created under `None` was readable from the default
workspace and from `/export/json` but 404 from workspace 1. A header now names a
`Space` row or `all`; anything else is 422 `unknown_space`, and the auth routes
(which run before a space means anything) ignore it, so a stale id in a browser
can never lock the person out."""

from __future__ import annotations

import pytest


@pytest.mark.parametrize("bad", ["None", "bogus", "../x", "null", "undefined", "0"])
def test_a_header_that_names_no_space_is_refused(client, bad):
    r = client.get("/entries", headers={"X-Workspace-ID": bad})
    assert r.status_code == 422
    assert r.json()["code"] == "unknown_space"
    assert "space" in r.json()["detail"].lower()


def test_a_note_cannot_be_created_under_an_unknown_space(client):
    r = client.post("/entries", json={"content": "stray"}, headers={"X-Workspace-ID": "None"})
    assert r.status_code == 422
    resp = client.get("/entries", headers={"X-Workspace-ID": "all"})
    assert resp.json() == []


@pytest.mark.parametrize("good", ["all", "default", "work"])
def test_all_and_known_spaces_pass(client, good):
    resp = client.get("/entries", headers={"X-Workspace-ID": good})
    assert resp.status_code == 200


def test_no_header_still_means_every_space(client):
    resp = client.get("/entries")
    assert resp.status_code == 200


def test_a_new_space_is_accepted_at_once_and_a_deleted_one_is_refused(client):
    made = client.post("/spaces", json={"name": "Garden", "icon": "ph-circles-four"}).json()
    sid = made["id"]
    resp = client.get("/entries", headers={"X-Workspace-ID": sid})
    assert resp.status_code == 200
    resp = client.delete(f"/spaces/{sid}")
    assert resp.status_code == 200
    r = client.get("/entries", headers={"X-Workspace-ID": sid})
    assert r.status_code == 422 and r.json()["code"] == "unknown_space"


def test_the_auth_routes_ignore_a_stale_space(client):
    r = client.get("/auth/status", headers={"X-Workspace-ID": "gone"})
    assert r.status_code == 200
