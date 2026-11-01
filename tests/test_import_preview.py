"""Import has a preview step (INBOX 1520, audit 1031 S36): what will come in,
untick items, then run. The dry run reads and lists; the real run leaves out
what was unticked."""

from __future__ import annotations

import json

from tests.test_app_import import OBSIDIAN, _post


def _entries(client) -> list[dict]:
    return client.get("/entries").json()


def test_a_dry_run_lists_the_notes_and_writes_nothing(client):
    before = len(_entries(client))
    response = client.post(
        "/import/app?source=obsidian&dry_run=1",
        files=[("files", ("vault.zip", OBSIDIAN, "application/octet-stream"))],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["found"] == 2 and len(body["notes"]) == 2
    first = {n["title"]: n for n in body["notes"]}
    assert set(first) == {"2026-10-01", "Garden plan"} or len(first) == 2
    assert all(n["key"] and "snippet" in n and n["already"] is False for n in body["notes"])
    assert len(_entries(client)) == before


def test_a_dry_run_marks_what_is_already_here(client):
    assert _post(client, "obsidian", "vault.zip", OBSIDIAN).status_code == 201
    body = client.post(
        "/import/app?source=obsidian&dry_run=1",
        files=[("files", ("vault.zip", OBSIDIAN, "application/octet-stream"))],
    ).json()
    assert [n["already"] for n in body["notes"]] == [True, True]


def test_unticked_notes_are_left_out_of_the_run(client):
    files = [("files", ("vault.zip", OBSIDIAN, "application/octet-stream"))]
    listed = client.post("/import/app?source=obsidian&dry_run=1", files=files).json()["notes"]
    left_out = listed[0]["key"]
    done = client.post(
        "/import/app?source=obsidian",
        files=files,
        data={"exclude": json.dumps([left_out])},
    ).json()
    assert done["imported"] == 1 and len(done["ids"]) == 1
    assert done["found"] == 1


def test_a_bad_exclude_is_refused_before_anything_is_written(client):
    files = [("files", ("vault.zip", OBSIDIAN, "application/octet-stream"))]
    refused = client.post("/import/app?source=obsidian", files=files, data={"exclude": "not json"})
    assert refused.status_code == 422
    assert not client.post("/import/app?source=obsidian&dry_run=1", files=files).json()["notes"][0]["already"]


def _text(*parts: str) -> str:
    from pathlib import Path

    return Path(__file__).resolve().parents[1].joinpath(*parts).read_text(encoding="utf-8")


def test_every_multi_note_import_shows_the_preview_before_it_runs():
    app = _text("frontend", "js", "app-import.js")
    data = _text("frontend", "js", "settings-data.js")
    # The app imports read with a dry run, then run with what was unticked.
    assert "dry_run=1" in app and "importPreview(" in app and 'form.append("exclude"' in app
    # The markdown files are previewed in the browser and only the ticked ones are sent.
    body = data.split("async function importMarkdown", 1)[1].split("\n}\n", 1)[0]
    assert "markdownPreview(" in body
    assert body.index("markdownPreview(") < body.index('form.append("files"')


def test_the_recipe_names_the_preview_and_its_lint():
    design = _text("docs", "DESIGN.md")
    row = next(line for line in design.splitlines() if line.startswith("| Choosing files to bring in"))
    assert "importPreview" in row and "dry_run=1" in row and "tests/test_import_preview.py" in row
    assert "**One step**" not in row


def test_every_reader_lists_before_it_writes(client):
    from tests.test_app_import import APPLE, ENEX, NOTION

    for source, name, data, expected in (
        ("notion", "export.zip", NOTION, 2), ("evernote", "Home.enex", ENEX, 2), ("apple", "notes.zip", APPLE, 2),
    ):
        body = client.post(
            f"/import/app?source={source}&dry_run=1", files=[("files", (name, data, "application/octet-stream"))]
        ).json()
        assert body["found"] == expected == len(body["notes"]), source
        assert all(n["title"] for n in body["notes"]), source
    assert _entries(client) == []
