"""L-world-class-411: a folder of more than 1,000 notes goes in as one import.

A vault picked as a folder is one part per file. Starlette's form parser refuses a
request with more than 1,000 files before the route's own cap (`MAX_FILES`, 5,000) is
reached, so a 5,000-note folder was refused and only a zip worked."""

from __future__ import annotations

from tessellate.api import routes_import


def _parts(count: int) -> list:
    return [("files", (f"vault/note {i}.md", f"# Note {i}\n\nBody {i}.".encode(), "text/markdown")) for i in range(count)]


def test_a_folder_of_1200_notes_is_read_not_refused(client):
    response = client.post("/import/app?source=obsidian&dry_run=1", files=_parts(1200))
    assert response.status_code == 200, response.text[:200]
    assert response.json()["found"] == 1200


def test_the_unticked_notes_still_arrive_with_a_big_folder(client):
    parts = _parts(1100)
    first = client.post("/import/app?source=obsidian&dry_run=1", files=parts).json()
    key = first["notes"][0]["key"]
    response = client.post("/import/app?source=obsidian", files=parts, data={"exclude": f'["{key}"]'})
    assert response.status_code == 201, response.text[:200]
    assert response.json()["imported"] == 1099


def test_more_than_the_route_cap_is_refused_in_plain_words(client, monkeypatch):
    monkeypatch.setattr(routes_import, "MAX_FILES", 1050)
    response = client.post("/import/app?source=obsidian&dry_run=1", files=_parts(1060))
    assert response.status_code == 422
    assert "than one import takes" in response.json()["detail"]


def test_more_files_than_the_import_cap_still_get_the_imports_own_words(client, monkeypatch):
    monkeypatch.setattr(routes_import, "MAX_FILES", 5)
    response = client.post("/import/app?source=obsidian&dry_run=1", files=_parts(6))
    assert response.status_code == 422
    assert "more than one import takes (5)" in response.text
