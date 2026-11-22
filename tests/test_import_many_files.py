"""A vault picked as a folder can hold thousands of files (L979).

`routes_import.MAX_FILES` says 5,000, but Starlette's form parser stopped any
upload at 1,000 files with "Too many files. Maximum number of files is 1000."
before the route ran, so a 5,000-file Obsidian vault failed at the preview
step with a bare 400. Found by driving the real browser upload
(scratchpad/ui-sweeps/upload5000.js)."""
from __future__ import annotations

from tessellate.api import routes_import


def _files(count: int) -> list:
    return [("files", (f"vault/n{i}.md", f"# n{i}\n\nbody {i}\n".encode(), "text/markdown")) for i in range(count)]


def test_an_obsidian_folder_of_1200_files_previews(client):
    response = client.post("/import/app?source=obsidian&dry_run=1", files=_files(1200))
    assert response.status_code == 200, response.text
    assert response.json()["found"] == 1200


def test_the_files_cap_is_the_apps_own_message_not_the_parsers(client, monkeypatch):
    monkeypatch.setattr(routes_import, "MAX_FILES", 1100)
    response = client.post("/import/app?source=obsidian&dry_run=1", files=_files(1101))
    assert response.status_code == 422
    assert "more than one import takes" in response.json()["detail"]
