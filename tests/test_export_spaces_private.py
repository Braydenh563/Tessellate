"""Brief 101b: exports of private notes and of more than one space.

Every export reads through the session's space filter, so what leaves is the
space the person is in (or every visible space under "All spaces"), and a
private note leaves readable only while the vault is open. Nothing held
either, so these hold both:

1. A space's export carries that space's notes and no other's, for the four
   formats (JSON, Markdown, CSV, folder); "All spaces" carries all.
2. A private note is exported readable with the vault open and never as
   ciphertext or plaintext once it is locked (the folder alone keeps the
   sealed text, flagged, so a locked export loses nothing and opens nothing).
3. A folder exported from one space and imported while another is open lands
   in that other space, private flag and all.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile

import pytest

from tessellate.core import crypto, vault
from tessellate.core.database import Entry

PLAIN_A = "alpha note kept in the default space"
PLAIN_B = "beta note kept in the work space"
SECRET = "the safe code is 4715 in the work space"


@pytest.fixture(autouse=True)
def open_vault(session):
    vault.close()
    vault.create(session, "test-passphrase")
    session.commit()
    yield
    vault.close()


@pytest.fixture()
def two_spaces(client):
    work = client.post("/spaces", json={"name": "Client work"}).json()["id"]

    def note(text: str, space: str) -> dict:
        response = client.post("/entries", json={"content": text}, headers={"X-Workspace-ID": space})
        assert response.status_code == 201, response.text
        return response.json()

    note(PLAIN_A, "default")
    note(PLAIN_B, work)
    secret = note(SECRET, work)
    made = client.post(f"/entries/{secret['id']}/privacy", json={"private": True}, headers={"X-Workspace-ID": work})
    assert made.status_code == 200, made.text
    return work


def _texts(client, fmt: str, space: str | None) -> str:
    """Everything an export of `fmt` says, as one string to search."""
    headers = {"X-Workspace-ID": space} if space else {}
    path = {"json": "/export/json", "markdown": "/export/markdown", "csv": "/export/csv", "folder": "/export/folder"}[fmt]
    response = client.get(path, headers=headers)
    assert response.status_code == 200, response.text
    if fmt in ("json", "csv"):
        return response.text
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        return "\n".join(archive.read(name).decode("utf-8", "replace") for name in archive.namelist())


FORMATS = ("json", "markdown", "csv", "folder")


@pytest.mark.parametrize("fmt", FORMATS)
def test_a_space_s_export_carries_that_space_and_no_other(client, two_spaces, fmt):
    in_default = _texts(client, fmt, "default")
    assert PLAIN_A in in_default and PLAIN_B not in in_default and SECRET not in in_default
    in_work = _texts(client, fmt, two_spaces)
    assert PLAIN_B in in_work and PLAIN_A not in in_work


@pytest.mark.parametrize("fmt", FORMATS)
def test_all_spaces_exports_every_space(client, two_spaces, fmt):
    everything = _texts(client, fmt, "all")
    assert PLAIN_A in everything and PLAIN_B in everything


@pytest.mark.parametrize("fmt", FORMATS)
def test_a_private_note_is_exported_readable_while_the_vault_is_open(client, two_spaces, fmt):
    assert SECRET in _texts(client, fmt, two_spaces)


@pytest.mark.parametrize("fmt", ("json", "markdown", "csv"))
def test_a_locked_vault_exports_neither_the_words_nor_the_ciphertext(client, session, two_spaces, fmt):
    sealed = session.query(Entry).filter(Entry.is_private.is_(True)).one().content
    assert crypto.is_encrypted(sealed)
    vault.close()
    said = _texts(client, fmt, two_spaces)
    assert SECRET not in said
    assert sealed not in said
    assert PLAIN_B in said, "the rest of the space still exports"


def test_a_locked_folder_export_keeps_the_sealed_text_flagged_and_not_the_words(client, session, two_spaces):
    vault.close()
    response = client.get("/export/folder", headers={"X-Workspace-ID": two_spaces})
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        everything = "\n".join(archive.read(name).decode("utf-8", "replace") for name in archive.namelist())
        sidecars = [json.loads(archive.read(name)) for name in archive.namelist() if name.endswith(".json") and name != "index.json"]
    assert SECRET not in everything
    sealed = [record for record in sidecars if isinstance(record, dict) and record.get("sealed")]
    assert len(sealed) == 1 and crypto.is_encrypted(sealed[0]["content"]) and sealed[0]["is_private"] is True


def test_a_json_export_marks_the_private_note_and_exports_each_space_s_categories(client, two_spaces):
    body = json.loads(_texts(client, "json", two_spaces))
    secret = next(e for e in body["entries"] if e["content"] == SECRET)
    assert secret["is_private"] is True
    assert all(e["content"] != PLAIN_A for e in body["entries"])


def test_a_csv_export_has_one_row_per_note_of_the_space(client, two_spaces):
    rows = list(csv.DictReader(io.StringIO(_texts(client, "csv", two_spaces))))
    assert sorted(r["content"] for r in rows) == sorted([PLAIN_B, SECRET])


def test_a_folder_from_one_space_imports_into_the_space_that_is_open(client, session, two_spaces):
    data = client.get("/export/folder", headers={"X-Workspace-ID": two_spaces}).content
    other = client.post("/spaces", json={"name": "Elsewhere"}).json()["id"]
    response = client.post(
        "/import/app?source=memorymap",
        files=[("files", ("tessellate-notebook.zip", data, "application/zip"))],
        headers={"X-Workspace-ID": other},
    )
    assert response.status_code == 201, response.text
    assert response.json()["imported"] == 2
    listed = client.get("/entries?limit=50", headers={"X-Workspace-ID": other}).json()
    texts = sorted(e["content"] for e in listed)
    assert texts == sorted([PLAIN_B, SECRET])
    secret = next(e for e in listed if e["content"] == SECRET)
    assert secret.get("is_private") is True
    # And the space it came from still holds its own, undisturbed.
    home = client.get("/entries?limit=50", headers={"X-Workspace-ID": two_spaces}).json()
    assert len(home) == 2
