"""L-world-class-670: a private space's files are sealed as they are written.

The live-caption spool, a background thread's generated WAV and an imported
folder's attachments used to land plain until the next unlock sealed them; a
private space deleted into an ordinary one carried its sealed bytes along
unreadable. Each writer now seals as it writes (a background thread as the
session that started it, SECURITY.md T28, never with a copied key), writes
nothing plain when the door is shut, and a space's delete unseals what moves.
"""

from __future__ import annotations

import io
import wave
import zipfile

import pytest

from tessellate.ai import captions
from tessellate.core import (
    activity,
    deps,
    recording_make,
    recordings,
    sealed_files,
    spacelock,
    vault,
)
from tessellate.core.database import Attachment, Recording, impersonate_workspace
from tests.test_captions import CHUNK, fake

PASSWORD = "first-pass"
SECRET = b"the locker code is 4715 behind the boathouse"


@pytest.fixture()
def signed_in(client):
    spacelock.close_all()
    token = client.post("/auth/setup", json={"password": PASSWORD}).json()["token"]
    client.headers.update({"X-Auth-Token": token})
    made = client.post("/spaces", json={"name": "Vault", "is_private": True})
    assert made.status_code == 200, made.text
    got = client.post("/private-spaces/unlock", json={"secret": PASSWORD})
    assert got.status_code == 200, got.text
    client.space = {"X-Workspace-ID": made.json()["id"]}
    client.space_id = made.json()["id"]
    client.token = token
    yield client
    spacelock.close_all()


@pytest.fixture()
def helper(monkeypatch):
    monkeypatch.delenv("TESSELLATE_CAPTIONS_URL", raising=False)
    captions._probe.update(at=0.0, url="", ok=False)
    captions._sessions.clear()
    activity.clear()
    server = fake.serve()
    monkeypatch.setenv("TESSELLATE_CAPTIONS_URL", f"http://127.0.0.1:{server.server_address[1]}")
    yield server
    server.shutdown()
    captions._sessions.clear()
    activity.clear()


def _wav(seconds: float = 0.2) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(16000)
        out.writeframes(b"\x01\x00" * int(16000 * seconds))
    return buf.getvalue()


def _recording_file(rid: int):
    session = deps.get_db().session()
    try:
        with impersonate_workspace(session, ""):
            return recordings.path_of(session.get(Recording, rid))
    finally:
        session.close()


def _attachment_files():
    session = deps.get_db().session()
    try:
        with impersonate_workspace(session, ""):
            return [
                deps.get_config().uploads_dir / a.stored_name
                for a in session.query(Attachment).all()
            ]
    finally:
        session.close()


def _recording_files():
    return sorted(p for p in recordings.directory().glob("*") if p.is_file())


# --- the background WAV -------------------------------------------------------------


def test_a_background_wav_in_a_private_space_is_written_sealed(signed_in):
    client = signed_in
    wav = _wav()
    rid = recording_make.save_generated(
        "overview", wav, [], derived="overview", workspace=client.space_id, token=client.token
    )
    path = _recording_file(rid)
    assert sealed_files.is_sealed(path)
    assert wav not in path.read_bytes()
    played = client.get(f"/media/recordings/{rid}", headers=client.space)
    assert played.content == wav


def test_a_background_wav_writes_nothing_when_the_door_is_shut(signed_in):
    client = signed_in
    client.post("/private-spaces/lock")
    before = _recording_files()
    with pytest.raises(sealed_files.SealedLocked) as shut:
        recording_make.save_generated(
            "overview",
            _wav(),
            [],
            derived="overview",
            workspace=client.space_id,
            token=client.token,
        )
    assert str(shut.value) == sealed_files.BACKGROUND_LOCKED_DETAIL
    assert _recording_files() == before


def test_a_background_wav_in_an_ordinary_space_is_plain_as_before(signed_in):
    wav = _wav()
    rid = recording_make.save_generated(
        "overview", wav, [], derived="overview", workspace="default"
    )
    assert _recording_file(rid).read_bytes() == wav


def test_the_studio_thread_says_the_space_locked_and_keeps_nothing(signed_in, monkeypatch):
    from tessellate.api import routes_studio
    from tessellate.ai import natural_voice

    client = signed_in
    client.post("/private-spaces/lock")
    monkeypatch.setattr(natural_voice, "render", lambda lines, **kw: (_wav(), []))
    job = activity.start("studio", "Making it", stoppable=True)
    routes_studio._set(job.id, state="running", progress=0.0, error="", recording_id=None)
    before = _recording_files()
    routes_studio._make(job, ["Hello."], "t", "overview", client.space_id, client.token)
    run = routes_studio._runs[job.id]
    assert run["state"] == "failed" and run["error"] == sealed_files.BACKGROUND_LOCKED_DETAIL
    assert _recording_files() == before


def test_the_studio_route_hands_the_thread_the_session_not_the_key(signed_in, monkeypatch):
    from tessellate.api import routes_studio
    from tessellate.ai import natural_voice

    client = signed_in
    seen = {}
    monkeypatch.setattr(natural_voice, "available", lambda: True)
    monkeypatch.setattr(routes_studio.studio, "script", lambda *a, **k: ["Hello."])
    monkeypatch.setattr(routes_studio.jobs, "thread", lambda name, fn, **k: seen.update(fn=fn))
    got = client.post("/studio/overview", json={"topic": "x"}, headers=client.space)
    assert got.status_code == 202, got.text
    monkeypatch.setattr(routes_studio, "_make", lambda *args: seen.update(args=args))
    seen["fn"]()
    assert seen["args"][-1] == client.token
    assert isinstance(seen["args"][-1], str) and vault.is_granted(seen["args"][-1])


# --- the live-caption spool ---------------------------------------------------------


def _speech() -> bytes:
    gap = b"\x00\x00" * 16000
    return fake.tone_words([0, 1]) + gap + fake.tone_words([6, 7]) + gap


def _spools():
    return list(recordings.directory().glob(f"{captions.SPOOL_PREFIX}*.pcm"))


def test_the_caption_spool_of_a_private_space_is_sealed_while_it_runs(signed_in, helper):
    client = signed_in
    pcm = _speech()
    sid = client.post(
        "/voice/captions/start", json={"keep_audio": True}, headers=client.space
    ).json()["id"]
    for i in range(0, len(pcm), CHUNK):
        got = client.post(
            f"/voice/captions/{sid}/audio", content=pcm[i : i + CHUNK], headers=client.space
        )
        assert got.status_code == 200, got.text
    (spool,) = _spools()
    assert sealed_files.is_sealed(spool)
    assert pcm[: 4 * CHUNK] not in spool.read_bytes()
    with vault.acting_for(client.token):
        assert sealed_files.read(spool) == pcm
    done = client.post(f"/voice/captions/{sid}/stop", headers=client.space).json()
    assert done["recording_id"]
    assert _spools() == []
    kept = _recording_file(done["recording_id"])
    assert sealed_files.is_sealed(kept)
    with wave.open(
        io.BytesIO(
            client.get(f"/media/recordings/{done['recording_id']}", headers=client.space).content
        )
    ) as w:
        assert w.getnframes() * 2 == len(pcm)


def test_the_caption_spool_of_an_ordinary_space_stays_plain(signed_in, helper):
    client = signed_in
    pcm = _speech()
    sid = client.post("/voice/captions/start", json={"keep_audio": True}).json()["id"]
    client.post(f"/voice/captions/{sid}/audio", content=pcm[:CHUNK])
    (spool,) = _spools()
    assert not sealed_files.is_sealed(spool)
    client.post(f"/voice/captions/{sid}/stop", json={"save": False})


# --- an import ---------------------------------------------------------------------


def _folder_with_a_file(client):
    note = client.post("/entries", json={"content": "host note"}, headers=client.space)
    nid = note.json()["id"]
    got = client.post(
        f"/entries/{nid}/files",
        files={"file": ("plan.txt", SECRET, "text/plain")},
        headers=client.space,
    )
    assert got.status_code == 201, got.text
    exported = client.get(
        "/export/folder", params={"include_private_spaces": "1"}, headers={"X-Workspace-ID": "all"}
    )
    assert exported.status_code == 200
    return exported.content


def _import(client, data, headers):
    return client.post(
        "/import/app?source=memorymap",
        files=[("files", ("tessellate-notebook.zip", data, "application/zip"))],
        headers=headers,
    )


def test_an_imported_note_file_in_a_private_space_is_written_sealed(signed_in):
    client = signed_in
    data = _folder_with_a_file(client)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert any(archive.read(n) == SECRET for n in archive.namelist()), (
            "the export carries the file readable"
        )
    other = client.post("/spaces", json={"name": "Vault two", "is_private": True}).json()["id"]
    unlocked = client.post("/private-spaces/unlock", json={"secret": PASSWORD})
    assert unlocked.status_code == 200
    before = set(_attachment_files())
    got = _import(client, data, {"X-Workspace-ID": other})
    assert got.status_code == 201, got.text
    assert got.json()["imported"] == 1
    (made,) = set(_attachment_files()) - before
    assert sealed_files.is_sealed(made)
    assert SECRET not in made.read_bytes()
    with vault.acting_for(client.token):
        assert sealed_files.read(made) == SECRET


def test_an_import_into_an_ordinary_space_writes_the_file_plain(signed_in):
    client = signed_in
    data = _folder_with_a_file(client)
    before = set(_attachment_files())
    got = _import(client, data, {"X-Workspace-ID": "default"})
    assert got.status_code == 201, got.text
    (made,) = set(_attachment_files()) - before
    assert made.read_bytes() == SECRET


def test_an_import_with_the_door_shut_writes_no_plain_file(signed_in, session):
    client = signed_in
    data = _folder_with_a_file(client)
    other = client.post("/spaces", json={"name": "Vault two", "is_private": True}).json()["id"]
    client.post("/private-spaces/lock")
    before = set(_attachment_files())
    try:
        got = _import(client, data, {"X-Workspace-ID": other})
        assert got.status_code >= 400
    except sealed_files.SealedLocked:
        pass
    new = set(_attachment_files()) - before
    uploads = deps.get_config().uploads_dir
    stray = [p for p in uploads.glob("*") if p not in before and p.read_bytes() == SECRET]
    assert not stray and not new


# --- deleting a private space into an ordinary one -------------------------------------


def test_deleting_a_private_space_into_an_ordinary_one_unseals_the_moved_files(signed_in):
    client = signed_in
    note = client.post("/entries", json={"content": "host"}, headers=client.space).json()["id"]
    got = client.post(
        f"/entries/{note}/files",
        files={"file": ("plan.txt", SECRET, "text/plain")},
        headers=client.space,
    )
    assert got.status_code == 201, got.text
    rid = client.post(
        "/recordings", json={"title": "t", "mime": "audio/wav"}, headers=client.space
    ).json()["id"]
    client.post(
        f"/recordings/{rid}/chunk",
        files={"file": ("c", _wav(), "audio/wav")},
        data={"at": "0"},
        headers=client.space,
    )
    (attached,) = _attachment_files()
    assert sealed_files.is_sealed(attached) and sealed_files.is_sealed(_recording_file(rid))
    gone = client.delete(f"/spaces/{client.space_id}?move_to=default")
    assert gone.status_code == 200, gone.text
    assert attached.read_bytes() == SECRET
    assert not sealed_files.is_sealed(_recording_file(rid))
    played = client.get(f"/media/recordings/{rid}")
    assert played.content == _wav()
    # Undo puts the space back and seals them again.
    back = client.post("/spaces/restore", json=gone.json()["restore"])
    assert back.status_code == 200, back.text
    assert sealed_files.is_sealed(attached) and sealed_files.is_sealed(_recording_file(rid))


def test_deleting_into_another_private_space_keeps_the_files_sealed(signed_in):
    client = signed_in
    other = client.post("/spaces", json={"name": "Vault two", "is_private": True}).json()["id"]
    unlocked = client.post("/private-spaces/unlock", json={"secret": PASSWORD})
    assert unlocked.status_code == 200
    note = client.post("/entries", json={"content": "host"}, headers=client.space).json()["id"]
    client.post(
        f"/entries/{note}/files",
        files={"file": ("plan.txt", SECRET, "text/plain")},
        headers=client.space,
    )
    (attached,) = _attachment_files()
    gone = client.delete(f"/spaces/{client.space_id}?move_to={other}")
    assert gone.status_code == 200, gone.text
    assert sealed_files.is_sealed(attached)
