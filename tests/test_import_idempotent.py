"""A folder import is safe to run again (SEC-10, audit 2026-10-05).

The audit's reproduction: a 3,000-file import killed mid-way left 20 notes and
no way to finish but "import again", and importing a 10-file vault twice gave
every note twice. Now a file whose path in the vault and whose text are
already in the notebook is passed over, so running an interrupted import
again finishes it; and one file that fails does not take the rest with it.
"""

from __future__ import annotations

import pytest

from tests._pool_wait import pool_idle


@pytest.fixture()
def vault(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    folder = tmp_path / "vault"
    (folder / "sub").mkdir(parents=True)
    for i in range(5):
        (folder / f"d{i}.md").write_text(f"note number {i}", encoding="utf-8")
    (folder / "sub" / "d0.md").write_text("note number 0", encoding="utf-8")
    return folder


def _contents(client):
    return sorted(e["content"] for e in client.get("/entries?limit=200").json())


def test_importing_the_same_folder_twice_adds_nothing_the_second_time(client, vault):
    assert client.post("/import/directory", json={"path": str(vault)}).status_code == 202
    pool_idle()
    first = _contents(client)
    # Same text at two different paths is two files, so two notes.
    assert len(first) == 6
    assert client.post("/import/directory", json={"path": str(vault)}).status_code == 202
    pool_idle()
    assert _contents(client) == first


def test_an_interrupted_import_run_again_finishes_it(client, vault):
    """What the audit's kill -9 left: some files in, the rest not."""
    keep = vault.parent / "later"
    keep.mkdir()
    for name in ("d3.md", "d4.md"):
        (vault / name).rename(keep / name)
    client.post("/import/directory", json={"path": str(vault)})
    pool_idle()
    assert len(_contents(client)) == 4
    for name in ("d3.md", "d4.md"):
        (keep / name).rename(vault / name)
    client.post("/import/directory", json={"path": str(vault)})
    pool_idle()
    assert len(_contents(client)) == 6


def test_a_changed_file_comes_in_again(client, vault):
    client.post("/import/directory", json={"path": str(vault)})
    pool_idle()
    (vault / "d1.md").write_text("note number 1, edited since", encoding="utf-8")
    client.post("/import/directory", json={"path": str(vault)})
    pool_idle()
    contents = _contents(client)
    assert "note number 1, edited since" in contents and "note number 1" in contents
    assert len(contents) == 7


def test_a_note_made_private_is_not_brought_back_in_the_clear(client, app_state, vault):
    """Its text is encrypted, so it cannot be compared: its path is enough."""
    from tessellate.core import deps
    from tessellate.core.database import Entry

    client.post("/import/directory", json={"path": str(vault)})
    pool_idle()
    with deps.get_db().session() as session:
        row = session.query(Entry).filter(Entry.source_path == "d2.md").one()
        row.is_private = True
        row.content = "(encrypted)"
        session.commit()
    client.post("/import/directory", json={"path": str(vault)})
    pool_idle()
    with deps.get_db().session() as session:
        assert session.query(Entry).filter(Entry.source_path == "d2.md").count() == 1


def test_one_failing_file_does_not_take_the_rest_with_it(client, vault, monkeypatch):
    """A failed flush poisons the session for every later file unless the
    failure is rolled back (the audit's code read)."""
    from tessellate.api import routes_settings
    from tessellate.core.database import Entry

    real = routes_settings.manager.create_entry

    def flaky(session, content, **kwargs):
        if content == "note number 2":
            session.add(Entry(content=None))  # NOT NULL: the flush fails
            session.flush()
        return real(session, content, **kwargs)

    monkeypatch.setattr(routes_settings.manager, "create_entry", flaky)
    client.post("/import/directory", json={"path": str(vault)})
    pool_idle()
    contents = _contents(client)
    assert "note number 2" not in contents
    assert len(contents) == 5
