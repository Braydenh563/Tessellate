"""F5 (WORLD_CLASS I2): the margin reader in the note editor, on the document
editor's reader and its one switch."""

from __future__ import annotations

from pathlib import Path


JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def test_the_note_form_mounts_the_reader_under_the_text():
    form = (JS / "note-edit-panels.js").read_text(encoding="utf-8")
    assert 'new CustomEvent("note-margin-mount"' in form
    assert "li.append(surface, marginHost, chipsHost, foot)" in form
    assert "foot.append(count, marginBtn, row)" in form


def test_the_reader_reads_a_textarea_and_sends_the_note_id():
    reader = (JS / "margin-reader.js").read_text(encoding="utf-8")
    assert 'addEventListener("note-margin-mount"' in reader
    assert "entry_id: marginNote()?.entryId ?? null" in reader
    # one switch: the note's button runs the document button's toggle
    assert 'addEventListener("click", marginToggle)' in reader


def test_a_note_in_the_margin_is_never_the_one_being_written(client):
    other = client.post("/entries", json={"content": "The boathouse key lives under the blue pot by the door."}).json()
    mine = client.post("/entries", json={"content": "The boathouse key lives under the blue pot by the door."}).json()
    reply = client.post(
        "/editor/read",
        json={"paragraph": "The boathouse key lives under the blue pot by the door.", "entry_id": mine["id"]},
    ).json()
    sources = {card.get("source_entry_id") for card in reply["cards"]}
    assert mine["id"] not in sources
    assert other["id"] in sources
