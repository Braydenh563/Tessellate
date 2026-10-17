"""A folder import reads only inside home and the data folder (§12, S3).

`POST /import/directory` takes a filesystem path from the request body and
walks it. For the one person at their own machine that is the Obsidian
import; for anyone holding a token over a network it was a read of any
directory the server can see. So the resolved folder must sit inside the
user's home or the notebook's data folder, and every file the walk reaches
must resolve inside the folder that was chosen: a symlink out of it (a file
or a whole directory) is skipped, not followed.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import select

from tessellate.api import routes_settings
from tessellate.core import deps
from tessellate.core.database import Entry
from tests._pool_wait import pool_idle


@pytest.fixture()
def home(tmp_path, monkeypatch):
    path = tmp_path / "home"
    path.mkdir()
    monkeypatch.setenv("HOME", str(path))
    monkeypatch.setenv("USERPROFILE", str(path))
    return path


def _vault(root, name="vault"):
    vault = root / name
    vault.mkdir(parents=True)
    (vault / "a note.md").write_text("inside the vault", encoding="utf-8")
    return vault


def _contents(session):
    return {e.content for e in session.scalars(select(Entry))}


def test_a_folder_in_home_imports(client, home, session):
    response = client.post("/import/directory", json={"path": str(_vault(home))})
    pool_idle()
    assert response.status_code == 202
    assert "inside the vault" in _contents(session)


def test_a_folder_in_the_data_folder_imports(client, home, session):
    vault = _vault(deps.get_config().data_dir, "imports")
    assert client.post("/import/directory", json={"path": str(vault)}).status_code == 202
    pool_idle()


def test_a_folder_outside_home_and_data_is_refused(client, home, tmp_path):
    elsewhere = _vault(tmp_path / "elsewhere")
    response = client.post("/import/directory", json={"path": str(elsewhere)})
    pool_idle()
    assert response.status_code == 400


def test_a_symlink_in_home_to_a_folder_outside_is_refused(client, home, tmp_path):
    elsewhere = _vault(tmp_path / "elsewhere")
    link = home / "looks-local"
    os.symlink(elsewhere, link, target_is_directory=True)
    assert client.post("/import/directory", json={"path": str(link)}).status_code == 400


def test_a_symlinked_file_pointing_out_of_the_vault_is_not_read(client, home, tmp_path, session):
    secret = tmp_path / "secret.md"
    secret.write_text("a file outside the vault", encoding="utf-8")
    vault = _vault(home)
    os.symlink(secret, vault / "innocent.md")
    assert client.post("/import/directory", json={"path": str(vault)}).status_code == 202
    pool_idle()
    contents = _contents(session)
    assert "inside the vault" in contents
    assert "a file outside the vault" not in contents


def test_a_symlinked_directory_inside_the_vault_is_not_walked(client, home, tmp_path, session):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "far.md").write_text("from a linked folder", encoding="utf-8")
    vault = _vault(home)
    os.symlink(outside, vault / "linked", target_is_directory=True)
    client.post("/import/directory", json={"path": str(vault)})
    pool_idle()
    assert "from a linked folder" not in _contents(session)


def test_the_background_job_checks_again(home, tmp_path, session):
    """The route checks, and so does the job it schedules: the job is also
    reachable on its own (the CLI, a test), and a check that lives only at
    the door is one refactor from gone."""
    elsewhere = _vault(tmp_path / "elsewhere")
    routes_settings._run_directory_import(str(elsewhere))
    assert "inside the vault" not in _contents(session)
