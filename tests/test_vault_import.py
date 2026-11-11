"""Importing an Obsidian-style vault keeps its shape.

Asked for directly: *"kortex and obsidian files and md file trees and being
able to link notes and obsidian md files and stuff is I think the largest gap
that is missing right now."*

The importer already read a whole vault before this, and threw two things
away: the folders, and the **filename**. The filename is the one that breaks
links: Obsidian's `[[wiki links]]` name the file, so a vault imported without
it arrives with every internal link pointing at nothing.
"""

from __future__ import annotations

import pytest

from tessellate.api import routes_settings_transfer
from tessellate.core.database import AuditLog, Entry
from sqlalchemy import select

from tessellate.entry import manager
from tessellate.entry import manager_wiki


@pytest.fixture(autouse=True)
def _vaults_live_in_home(tmp_path, monkeypatch):
    """A vault is read only from inside home or the data folder (§12 S3),
    and these build theirs under `tmp_path`, so `tmp_path` is home here."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))


def _vault(tmp_path):
    root = tmp_path / "vault"
    (root / "Projects").mkdir(parents=True)
    (root / "Projects" / "Roadmap.md").write_text("The plan for next quarter.", encoding="utf-8")
    (root / "Daily.md").write_text("# Daily\n\nSee [[Roadmap]] for the plan.", encoding="utf-8")
    return root


def test_the_folder_a_note_came_from_is_kept(tmp_path, session):
    routes_settings_transfer._run_directory_import(str(_vault(tmp_path)))
    paths = sorted(e.source_path for e in session.scalars(select(Entry)).all())
    assert paths == ["Daily.md", "Projects/Roadmap.md"]


def test_the_import_does_not_rewrite_the_file(tmp_path, session):
    """An earlier attempt prepended `# <filename>` so the note would carry its
    vault name, and three existing tests caught it. An importer that edits
    what it imports is a data-loss bug waiting to be reported, and it was
    never needed: the name lives on `source_path`, where the wiki-link
    resolver reads it."""
    routes_settings_transfer._run_directory_import(str(_vault(tmp_path)))
    roadmap = session.scalars(
        select(Entry).where(Entry.source_path == "Projects/Roadmap.md")
    ).first()
    assert roadmap.content == "The plan for next quarter."


def test_a_wiki_link_resolves_to_the_file_it_names(tmp_path, session):
    """The whole point. `[[Roadmap]]` is a *filename*, and the note's own text
    starts with the heading rather than the name."""
    routes_settings_transfer._run_directory_import(str(_vault(tmp_path)))
    found = manager_wiki.find_by_wiki_name(session, "Roadmap")
    assert found is not None
    assert found.source_path == "Projects/Roadmap.md"


def test_a_vault_name_beats_a_note_that_merely_starts_with_it(tmp_path, session):
    """A file called "Index" should not lose to a note that opens with the
    word "index", which is why the vault pass runs first and matches
    exactly."""
    manager.create_entry(session, "Index of everything I own", category_name=manager.UNCATEGORISED)
    session.commit()
    root = tmp_path / "v2"
    root.mkdir()
    (root / "Index.md").write_text("The real index file.", encoding="utf-8")
    routes_settings_transfer._run_directory_import(str(root))
    assert manager_wiki.find_by_wiki_name(session, "Index").source_path == "Index.md"


def test_a_note_written_here_has_no_path(session):
    """Everything not imported groups under "(written here)" in the index: 
    an empty string, not NULL, so the additive auto-migrator can backfill."""
    entry = manager.create_entry(session, "typed straight in", category_name=manager.UNCATEGORISED)
    session.commit()
    assert entry.source_path == ""


def test_an_oversize_file_is_skipped_not_read_whole(tmp_path, session):
    """INBOX 310, finding 2: unlike every other import path (`import_markdown`
    caps at `MAX_IMPORT_BYTES` before reading), the directory importer used
    to call `f.read_text()` on every `.md` file with no ceiling at all. A
    file over the cap must be skipped, the smaller one still imported, and
    the skip counted and reported in the activity log detail rather than
    silently dropped."""
    root = tmp_path / "vault3"
    root.mkdir()
    (root / "Small.md").write_text("a normal note", encoding="utf-8")
    huge = "x" * (routes_settings_transfer.MAX_IMPORT_BYTES + 1)
    (root / "Huge.md").write_text(huge, encoding="utf-8")

    routes_settings_transfer._run_directory_import(str(root))

    entries = session.scalars(select(Entry)).all()
    assert [e.content for e in entries] == ["a normal note"]

    logged = session.scalars(
        select(AuditLog)
        .where(AuditLog.action == "imported", AuditLog.entity_type == "data")
        .order_by(AuditLog.id.desc())
    ).first()
    assert logged is not None
    assert logged.detail == "markdown dir x1, skipped 1 (1 over 1 MB)"


def test_an_uploaded_markdown_file_keeps_its_name(client):
    """The other import door, the file picker, had the same two losses."""
    files = [("files", ("Notes/Meeting.md", b"what we agreed", "text/markdown"))]
    body = client.post("/import/markdown", files=files).json()
    assert body["imported"] == 1
    listed = client.get("/entries").json()
    imported = [e for e in listed if e["source_path"]]
    assert imported[0]["source_path"] == "Notes/Meeting.md"
    assert imported[0]["content"] == "what we agreed"
