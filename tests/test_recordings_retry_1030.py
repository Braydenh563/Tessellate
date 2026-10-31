"""Audit 1030 Y1: a recording whose slices fail to save said nothing until
Stop, never retried the slice, and appended the later ones after the gap.
Now the browser keeps unsaved slices in order and retries them, saying so at
once; the server takes the size the sender expects (`at`), so a retried slice
that did land is not written twice, and a write cut short by a full disk is
cut back so the retry starts where the saved audio ends."""

from __future__ import annotations

import errno
from pathlib import Path

import pytest

from tessellate.api import routes_recordings
from tessellate.core import recordings
from tessellate.core.database import Recording

WEBM_HEAD = b"\x1a\x45\xdf\xa3" + b"\x00" * 60
JS = (Path(__file__).resolve().parents[1] / "frontend/js/meetings.js").read_text(encoding="utf-8")


def _make(client):
    return client.post("/recordings", json={"title": "Standup", "mime": "audio/webm"}).json()["id"]


def _chunk(client, rid, data, at):
    return client.post(f"/recordings/{rid}/chunk", files={"file": ("chunk.webm", data, "audio/webm")}, data={"duration_ms": "2000", "at": str(at)})


def test_a_retried_slice_that_landed_is_not_written_twice(client, session):
    rid = _make(client)
    assert _chunk(client, rid, WEBM_HEAD, 0).json()["size_bytes"] == 64
    assert _chunk(client, rid, b"\x01" * 10, 64).json()["size_bytes"] == 74
    again = _chunk(client, rid, b"\x01" * 10, 64)
    assert again.status_code == 200 and again.json()["size_bytes"] == 74
    assert recordings.path_of(session.get(Recording, rid)).stat().st_size == 74


def test_a_slice_out_of_step_is_refused(client):
    rid = _make(client)
    _chunk(client, rid, WEBM_HEAD, 0)
    assert _chunk(client, rid, b"\x01" * 10, 30).status_code == 409


def test_a_write_cut_short_is_cut_back(tmp_path):
    target = tmp_path / "take.webm"
    target.write_bytes(b"a" * 10)

    class Full:
        def __init__(self):
            self.calls = 0

        def open(self, mode):
            self.calls += 1
            handle = target.open(mode)
            if self.calls == 1:
                real = handle.write

                def write(data):
                    real(data[:3])
                    handle.flush()
                    raise OSError(errno.ENOSPC, "No space left on device")

                handle.write = write
            return handle

    with pytest.raises(OSError):
        routes_recordings._append(Full(), b"b" * 8, 10)
    assert target.read_bytes() == b"a" * 10


def test_the_browser_queues_and_retries_and_says_it_stopped_saving():
    assert "meetingTake.queue.push(" in JS
    assert 'form.append("at", String(meetingTake.bytes));' in JS
    assert "Not saving: " in JS and "Retrying." in JS
    assert "meetingSay(meetingStatusLine(), Boolean(meetingTake.failed))" in JS
    assert "could not be saved" in JS and "The rest is kept." in JS
