"""Importing from Notion, Obsidian, Evernote and Apple Notes (WORLD_CLASS_PLAN
H6 and 5.7, row 25): one round trip per format, and every import idempotent
by source (the second import of the same export makes nothing)."""

from __future__ import annotations

import io
import zipfile

import pytest

from tessellate.core.database import Entry
from tessellate.entry import app_import, manager


def _zip(members: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, text in members.items():
            #: A fixed date: the bytes are a parametrize value, and xdist
            #: workers must collect the same test ids.
            archive.writestr(zipfile.ZipInfo(name, date_time=(2026, 10, 1, 12, 0, 0)), text)
    return buffer.getvalue()


NOTION = _zip({
    "Export/Projects 0123456789abcdef0123456789abcdef.md": "# Projects\n\nSee [Garden plan](Projects%200123456789abcdef0123456789abcdef/Garden%20plan%20fedcba9876543210fedcba9876543210.md).\n",
    "Export/Projects 0123456789abcdef0123456789abcdef/Garden plan fedcba9876543210fedcba9876543210.md": "# Garden plan\n\nPlant the beans in May.\n",
    "Export/Projects 0123456789abcdef0123456789abcdef/Tasks aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.csv": "Name,Status\nBeans,Done\n",
})

OBSIDIAN = _zip({
    "Vault/.obsidian/app.json": "{}",
    "Vault/Daily/2026-10-01.md": "---\ncategory: Journal\ntags: [morning]\n---\nWoke early, wrote about [[Garden plan]].\n",
    "Vault/Garden plan.md": "Beans go in in May.\n",
})

ENEX = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE en-export SYSTEM "http://xml.evernote.com/pub/evernote-export3.dtd">
<en-export export-date="20261001T120000Z" application="Evernote" version="10">
  <note>
    <title>Boiler service</title>
    <content><![CDATA[<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd"><en-note><div>Booked with <b>Hendry Heating</b> for October.</div><div><en-todo checked="true"/>Pay the deposit</div></en-note>]]></content>
    <created>20240312T091500Z</created>
    <tag>house</tag><tag>bills</tag>
  </note>
  <note>
    <title>Recipe</title>
    <content><![CDATA[<en-note><p>Toast the cumin first.</p><en-media type="image/png" hash="abc"/></en-note>]]></content>
    <created>20240401T100000Z</created>
  </note>
</en-export>
""".encode()

APPLE = _zip({
    "Notes/Home/Window repair.html": "<html><body><h1>Window repair</h1><p>Call the glazier on <b>Thursday</b>.</p></body></html>",
    "Notes/Work/Standup.txt": "Ship the importer.\nReview the margin reader.",
})


def _post(client, source: str, name: str, data: bytes):
    return client.post(f"/import/app?source={source}", files=[("files", (name, data, "application/octet-stream"))])


@pytest.mark.parametrize(
    "source,name,data,expected",
    [
        ("notion", "export.zip", NOTION, 2),
        ("obsidian", "vault.zip", OBSIDIAN, 2),
        ("evernote", "Home.enex", ENEX, 2),
        ("apple", "notes.zip", APPLE, 2),
    ],
    ids=["notion", "obsidian", "evernote", "apple"],
)
def test_each_format_imports_once_and_only_once(client, source, name, data, expected):
    first = _post(client, source, name, data)
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["imported"] == expected
    assert len(body["ids"]) == expected
    second = _post(client, source, name, data).json()
    assert second["imported"] == 0
    assert second["already"] == expected


def test_notion_titles_lose_their_ids_and_links_become_wiki_links(client, session):
    ids = _post(client, "notion", "export.zip", NOTION).json()["ids"]
    notes = {session.get(Entry, i).content.split("\n", 1)[0]: session.get(Entry, i) for i in ids}
    assert set(notes) == {"# Projects", "# Garden plan"}
    assert "[[Garden plan]]" in notes["# Projects"].content
    assert notes["# Garden plan"].source_path == "notion:fedcba9876543210fedcba9876543210"
    skipped = _post(client, "notion", "again.zip", NOTION).json()["skipped"]
    assert any("database table" in reason for reason in skipped)


def _notes(client, ids):
    return [client.get(f"/entries/{i}").json() for i in ids]


def test_obsidian_keeps_front_matter_meaning_and_skips_its_settings(client):
    ids = _post(client, "obsidian", "vault.zip", OBSIDIAN).json()["ids"]
    daily = next(n for n in _notes(client, ids) if "Woke early" in n["content"])
    assert daily["category"] == "Journal"
    assert "morning" in daily["tags"]
    assert "[[Garden plan]]" in daily["content"]


def test_evernote_keeps_title_dates_tags_and_todo(client, session):
    ids = _post(client, "evernote", "Home.enex", ENEX).json()["ids"]
    boiler = next(n for n in _notes(client, ids) if "Boiler" in n["content"])
    assert boiler["content"].startswith("# Boiler service")
    assert "Hendry Heating" in boiler["content"] and "[x]" in boiler["content"]
    assert boiler["created_at"].startswith("2024-03-12")
    assert {"house", "bills"} <= set(boiler["tags"])
    assert boiler["category"] == "Home"
    # Imported text is someone else's words for the injection guard.
    assert manager.came_from_outside(session.get(Entry, boiler["id"]))


def test_an_evernote_file_with_an_entity_bomb_is_refused_not_expanded(client):
    bomb = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;">]><en-export><note><title>&b;</title></note></en-export>'
    body = _post(client, "evernote", "bomb.enex", bomb).json()
    assert body["imported"] == 0
    assert body["skipped"] and "not a readable Evernote export" in body["skipped"][0]


def test_apple_notes_folders_become_categories(client):
    ids = _post(client, "apple", "notes.zip", APPLE).json()["ids"]
    window = next(n for n in _notes(client, ids) if "glazier" in n["content"])
    assert window["category"] == "Home"
    assert window["content"].count("Window repair") == 1


def test_an_unknown_source_is_refused(client):
    assert _post(client, "onenote", "x.zip", APPLE).status_code == 422


def test_a_zip_too_large_unpacked_is_refused(monkeypatch):
    monkeypatch.setattr(app_import, "MAX_ARCHIVE_BYTES", 10)
    with pytest.raises(app_import.TooBig):
        app_import.expand([("a.zip", _zip({"a.md": "x" * 100}))])


@pytest.mark.parametrize(
    "call, text",
    [
        (app_import._enml, "<en-media" * 20000),
        (app_import._enml, "<en-media>" * 20000),
        (app_import._enml, "<en-todo" * 20000),
        (app_import._enml, "<?xml" * 20000),
        (app_import._notion_links, "[](" * 20000),
        (app_import._notion_links, "[a](b" * 20000),
        (app_import._notion_name, "a" + " " * 20000 + "x"),
    ],
    ids=["media-open", "media-pair", "todo", "xml", "link-open", "link-text", "notion-id"],
)
def test_an_import_regex_is_linear_on_a_hostile_file(call, text):
    """Each of these took two to ten seconds on 20 to 180 KB before (the
    final scan, 2026-10-06: CodeQL's `py/polynomial-redos` shape, an
    uploaded export reaching an unanchored `[^>]*` or a lazy run). A real
    ENEX is up to 200 MB, so quadratic is a hang, not a slow import."""
    import time

    started = time.process_time()
    call(text)
    assert time.process_time() - started < 0.5


def test_the_linear_import_regexes_still_read_real_files():
    assert app_import._notion_name("Garden plan fedcba9876543210fedcba9876543210") == (
        "Garden plan",
        "fedcba9876543210fedcba9876543210",
    )
    assert app_import._notion_name("Plain") == ("Plain", None)
    assert app_import._notion_links("See [x](A%20b%200123456789abcdef0123456789abcdef.md).") == "See [[A b]]."
    body = app_import._notion_links("[web](https://x.org/a.html)")
    assert body == "[web](https://x.org/a.html)"
    enml = app_import._enml(
        '<?xml version="1.0"?><!DOCTYPE en-note SYSTEM "x"><en-note><en-todo checked="true"/>done'
        '<en-todo/>open<en-media type="image/png" hash="ab"/><en-media hash="c"></en-media></en-note>'
    )
    assert "[x] done" in enml and "[ ] open" in enml and enml.count("[attachment]") == 2
    assert "xml" not in enml and "DOCTYPE" not in enml


def _many(count: int) -> bytes:
    return _zip({f"Vault/Note {i}.md": f"---\ntags: [t{i % 3}]\n---\nHarbour tide {i}, call Ana tomorrow.\n" for i in range(count)})


def test_a_big_import_commits_in_batches_and_reads_each_note_for_dates_once(client, session, monkeypatch):
    """One commit and two date reads per note was the cost of a 5,000-note
    import (45.9 s, data-1011): now a commit per hundred notes and one read."""
    from sqlalchemy.orm import Session

    reads: list[int] = []
    commits: list[int] = []
    real_dates = manager.record_dates
    real_commit = Session.commit
    monkeypatch.setattr(manager, "record_dates", lambda s, e: (reads.append(e.id), real_dates(s, e))[1])
    monkeypatch.setattr(Session, "commit", lambda self: (commits.append(1), real_commit(self))[1])
    body = _post(client, "obsidian", "vault.zip", _many(250)).json()
    assert body["imported"] == 250
    assert len(reads) == 250, f"{len(reads)} date reads for 250 notes"
    assert len(commits) < 40, f"{len(commits)} commits for 250 notes"
    assert session.query(Entry).filter(Entry.source_path.like("obsidian:%")).count() == 250


def test_create_entry_without_a_commit_still_gives_the_note_its_id(session):
    entry = manager.create_entry(session, "held until the caller commits", commit=False, dates=False)
    assert entry.id is not None
    session.rollback()
    assert session.get(Entry, entry.id) is None  # nothing was committed
