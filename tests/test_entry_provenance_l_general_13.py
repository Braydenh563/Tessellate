"""Every note says where it came from (L-general-13): clipped from a page
(`source_url`), imported from a file or extracted from a document
(`source_path`), transcribed from a recording (`recording`). The first two
were chips already; a recording's note had none, and a PDF's sections read
as "imported" like a markdown vault.
"""

from __future__ import annotations

from tessellate.core.database import Recording
from tests._app_js import frontend_text


def _note(client, text):
    response = client.post("/entries", json={"content": text})
    assert response.status_code == 201
    return response.json()["id"]


def test_a_recordings_note_names_its_recording_on_get_and_list(client, session):
    note = _note(client, "Standup transcript")
    plain = _note(client, "Shopping list")
    session.add(Recording(title="Standup 12 Nov", entry_id=note, state="saved"))
    session.commit()
    one = client.get(f"/entries/{note}").json()
    assert one["recording"]["title"] == "Standup 12 Nov"
    listed = {e["id"]: e for e in client.get("/entries").json()}
    assert listed[note]["recording"]["title"] == "Standup 12 Nov"
    assert listed[plain]["recording"] is None


def test_the_card_draws_each_provenance():
    card = frontend_text("entry-card.js")
    assert "entry.recording" in card and "Transcribed from" in card
    assert "Extracted from" in card and "Imported from" in card
