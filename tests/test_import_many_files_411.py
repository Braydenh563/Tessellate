"""A folder import of more than 1,000 files (L-world-class-411).

Starlette's multipart parser refuses a request with more than 1,000 file
parts by default, so a vault picked as a folder of 5,000 notes was refused
before `MAX_FILES` (5,000) was ever read. The import routes parse the form
with the import's own cap instead.
"""

from tessellate.api import routes_import


def _files(count: int) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [("files", (f"vault/note-{i}.md", f"# Note {i}\n\nBody {i}.".encode(), "text/markdown")) for i in range(count)]


def test_a_folder_of_1200_notes_is_read_not_refused(client):
    response = client.post("/import/app?source=obsidian&dry_run=1", files=_files(1200))
    assert response.status_code == 200, response.text
    assert response.json()["found"] == 1200


def test_more_files_than_the_import_cap_still_get_the_imports_own_words(client, monkeypatch):
    monkeypatch.setattr(routes_import, "MAX_FILES", 5)
    response = client.post("/import/app?source=obsidian&dry_run=1", files=_files(6))
    assert response.status_code == 422
    assert "more than one import takes (5)" in response.text
