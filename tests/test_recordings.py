"""Recordings as objects (WORLD_CLASS_PLAN 28.5 rows 1, 5 and 6).

Record never refuses: with no Whisper add-on the audio is kept as its own
object, named by the container the browser made (decision 3), saved in
chunks so a killed tab keeps what it sent, binned rather than deleted.
"""

from __future__ import annotations

from datetime import timedelta

from tessellate.ai import voice
from tessellate.core import deps, recordings
from tessellate.core.database import Recording, utcnow

WEBM_HEAD = b"\x1a\x45\xdf\xa3" + b"\x00" * 60


def _make(client, title="Standup", mime="audio/webm;codecs=opus"):
    response = client.post("/recordings", json={"title": title, "mime": mime})
    assert response.status_code == 201, response.text
    return response.json()


def _chunk(client, rid, data, duration_ms):
    return client.post(
        f"/recordings/{rid}/chunk",
        files={"file": ("chunk.webm", data, "audio/webm")},
        data={"duration_ms": str(duration_ms)},
    )


def test_record_with_no_addon_keeps_the_audio_with_its_length(client, monkeypatch):
    monkeypatch.setattr(voice, "whisper_available", lambda: False)
    made = _make(client)
    assert made["mime"] == "audio/webm" and made["state"] == "recording"
    response = _chunk(client, made["id"], WEBM_HEAD, 10_000)
    assert response.status_code == 200
    response = _chunk(client, made["id"], b"\x01" * 200, 20_000)
    assert response.status_code == 200
    done = client.post(
        f"/recordings/{made['id']}/finish",
        json={"duration_ms": 23_400, "peaks": [0, 40, 120, -5], "markers": [5000, 99_000_000]},
    ).json()
    assert done["state"] == "saved"
    assert done["duration_ms"] == 23_400
    assert done["size_bytes"] == len(WEBM_HEAD) + 200
    assert done["peaks"] == [0, 40, 100, 0]
    assert done["markers"] == [5000]
    listed = client.get("/recordings").json()["recordings"]
    assert [r["id"] for r in listed] == [made["id"]]
    # Transcription is the add-on's: offered only when it is there.
    response = client.post(f"/recordings/{made['id']}/transcribe")
    assert response.status_code == 503


def test_never_called_mp3_and_type_checked():
    assert recordings.container("audio/mpeg") is None
    assert recordings.container("video/webm;codecs=opus") == "audio/webm"
    assert all("mp3" not in suffix for suffix, _ in recordings.CONTAINERS.values())


def test_unknown_type_refused(client):
    response = client.post("/recordings", json={"mime": "audio/mpeg"})
    assert response.status_code == 415


def test_first_chunk_must_match_its_container(client):
    made = _make(client)
    response = _chunk(client, made["id"], b"<html>nope</html>", 1000)
    assert response.status_code == 415


def test_audio_served_with_its_real_type(client):
    made = _make(client)
    _chunk(client, made["id"], WEBM_HEAD, 1000)
    client.post(f"/recordings/{made['id']}/finish", json={"duration_ms": 1000})
    response = client.get(f"/media/recordings/{made['id']}")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/webm")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.content == WEBM_HEAD


def test_killed_tab_is_recovered_once(client):
    made = _make(client)
    _chunk(client, made["id"], WEBM_HEAD, 110_000)
    session = deps.get_db().session()
    try:
        row = session.get(Recording, made["id"])
        row.updated_at = utcnow() - timedelta(minutes=2)
        session.commit()
    finally:
        session.close()
    first = client.get("/recordings").json()
    assert [r["id"] for r in first["recovered"]] == [made["id"]]
    assert first["recordings"][0]["duration_ms"] == 110_000
    assert first["recordings"][0]["recovered"] is True
    response = client.get("/recordings")
    assert response.json()["recovered"] == []


def test_live_recording_is_not_recovered(client):
    made = _make(client)
    _chunk(client, made["id"], WEBM_HEAD, 10_000)
    body = client.get("/recordings").json()
    assert body["recovered"] == [] and body["recordings"] == []


def test_bin_restore_and_purge(client):
    made = _make(client)
    _chunk(client, made["id"], WEBM_HEAD, 1000)
    client.post(f"/recordings/{made['id']}/finish", json={"duration_ms": 1000})
    session = deps.get_db().session()
    try:
        path = recordings.path_of(session.get(Recording, made["id"]))
    finally:
        session.close()
    assert path.exists()
    response = client.delete(f"/recordings/{made['id']}")
    assert response.status_code == 200
    response = client.get("/recordings")
    assert response.json()["recordings"] == []
    items = client.get("/library").json()["items"]
    assert any(i["kind"] == "archived" and i.get("subtype") == "recording" for i in items)
    response = client.post(f"/recordings/{made['id']}/restore")
    assert response.status_code == 200
    response = client.get("/recordings")
    assert len(response.json()["recordings"]) == 1
    client.delete(f"/recordings/{made['id']}")
    response = client.post(f"/recordings/{made['id']}/purge")
    assert response.status_code == 200
    assert not path.exists()


def test_trim_is_a_new_object_and_keeps_the_original(client):
    made = _make(client)
    _chunk(client, made["id"], WEBM_HEAD, 1000)
    client.post(f"/recordings/{made['id']}/finish", json={"duration_ms": 1000})
    trim = client.post(
        "/recordings", json={"title": "Standup (trimmed)", "mime": "audio/wav", "source_id": made["id"]}
    ).json()
    assert trim["source_id"] == made["id"]
    wav = b"RIFF\x00\x00\x00\x00WAVEfmt " + b"\x00" * 40
    response = _chunk(client, trim["id"], wav, 500)
    assert response.status_code == 200
    ids = {r["id"] for r in client.get("/recordings").json()["recordings"]}
    assert made["id"] in ids


def test_rename_and_markers(client):
    made = _make(client)
    _chunk(client, made["id"], WEBM_HEAD, 9000)
    client.post(f"/recordings/{made['id']}/finish", json={"duration_ms": 9000})
    body = client.patch(f"/recordings/{made['id']}", json={"title": "Kiln call", "markers": [3000, 1000, 3000]}).json()
    assert body["title"] == "Kiln call" and body["markers"] == [1000, 3000]


def test_recover_route_finishes_a_killed_take_once(client):
    """Row 5: the app asks at each start; a take with no chunk for 45 s is
    finished with what it sent and listed once."""
    made = _make(client)
    _chunk(client, made["id"], WEBM_HEAD, 110_000)
    response = client.post("/recordings/recover")
    assert response.json() == []
    session = deps.get_db().session()
    try:
        session.get(Recording, made["id"]).updated_at = utcnow() - recordings.STALE_AFTER * 2
        session.commit()
    finally:
        session.close()
    response = client.post("/recordings/recover")
    assert [(r["id"], r["duration_ms"]) for r in response.json()] == [(made["id"], 110_000)]
    response = client.post("/recordings/recover")
    assert response.json() == []


def test_the_recorder_saves_a_slice_every_two_seconds():
    # Intent moved with audit 1029 X3: ten seconds of audio lost to a crash was too much.
    from pathlib import Path

    js = (Path(__file__).resolve().parents[1] / "frontend/js/meetings.js").read_text(encoding="utf-8")
    assert "const MEETING_CHUNK_MS = 2000;" in js
    assert "recorder.start(MEETING_CHUNK_MS)" in js
    assert "/recordings/${id}/chunk" in js


def test_finish_transcribe_and_purge_by_id(client, monkeypatch):
    """The three id routes, called by a path the route-naming ratchet can read
    (a plain variable in the f-string, not a subscript)."""
    monkeypatch.setattr(voice, "whisper_available", lambda: False)
    rid = _make(client)["id"]
    _chunk(client, rid, WEBM_HEAD, 1000)
    finished = client.post(f"/recordings/{rid}/finish", json={"duration_ms": 1000})
    assert finished.json()["state"] == "saved"
    transcribed = client.post(f"/recordings/{rid}/transcribe")
    assert transcribed.status_code == 503
    early = client.post(f"/recordings/{rid}/purge")
    assert early.status_code == 409  # not in the bin yet
    client.delete(f"/recordings/{rid}")
    purged = client.post(f"/recordings/{rid}/purge")
    assert purged.status_code == 200


def test_the_list_pages_and_counts(client):
    for n in range(3):
        rid = _make(client, title=f"Take {n}")["id"]
        _chunk(client, rid, WEBM_HEAD, 1000)
        client.post(f"/recordings/{rid}/finish", json={"duration_ms": 1000})
    page = client.get("/recordings?limit=2")
    assert len(page.json()["recordings"]) == 2
    assert page.headers["X-Total-Count"] == "3"
    assert "X-Next-Cursor" in page.headers
    rest = client.get("/recordings?limit=2&offset=2")
    assert len(rest.json()["recordings"]) == 1 and "X-Next-Cursor" not in rest.headers


def test_marks_carry_a_comment_and_old_markers_still_read(client):
    """Brief 96: a mark is a time and an optional comment; a plain number is
    a mark with no comment, so markers saved before keep working."""
    made = _make(client)
    _chunk(client, made["id"], WEBM_HEAD, 9000)
    client.post(f"/recordings/{made['id']}/finish", json={"duration_ms": 9000, "markers": [2000]})
    body = client.patch(
        f"/recordings/{made['id']}",
        json={"markers": [2000, {"at": 4500, "note": "  budget question  "}, {"at": 99_000, "note": "past the end"}]},
    ).json()
    assert body["markers"] == [2000, 4500]
    assert body["marks"] == [{"at": 2000, "note": ""}, {"at": 4500, "note": "budget question"}]
    # The same time twice keeps one mark, the later comment winning.
    body = client.patch(
        f"/recordings/{made['id']}", json={"markers": [{"at": 4500, "note": "a"}, {"at": 4500, "note": "b"}]}
    ).json()
    assert body["marks"] == [{"at": 4500, "note": "b"}]
    long_note = "x" * 2000
    body = client.patch(f"/recordings/{made['id']}", json={"markers": [{"at": 1, "note": long_note}]}).json()
    assert len(body["marks"][0]["note"]) == recordings.MARK_NOTE_MAX


def test_an_enhanced_copy_says_so_and_keeps_its_original(client):
    """UI_MODERNISATION V3: the cleaned audio is a new object marked
    `derived: "enhanced"` pointing at the original, which is kept until the
    transcript is accepted; a trim says `trim`, and an unknown kind is refused."""
    made = _make(client)
    _chunk(client, made["id"], WEBM_HEAD, 1000)
    client.post(f"/recordings/{made['id']}/finish", json={"duration_ms": 1000})
    clean = client.post(
        "/recordings", json={"title": "Standup", "mime": "audio/wav", "source_id": made["id"], "derived": "enhanced"}
    ).json()
    odd = client.post("/recordings", json={"mime": "audio/wav", "derived": "louder"})
    plain = client.get(f"/recordings/{made['id']}").json()
    assert clean["derived"] == "enhanced" and clean["source_id"] == made["id"]
    assert plain["derived"] == ""
    assert odd.status_code == 422
