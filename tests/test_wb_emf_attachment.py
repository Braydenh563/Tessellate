"""The original EMF is kept as a note's attachment (L-whiteboard-48): stored, never shown inline, size-capped."""

from __future__ import annotations

import io
import struct

from tessellate.entry import manager
from tests._app_js import frontend_text


def _emf() -> bytes:
    header = struct.pack("<II", 1, 88) + struct.pack("<4i", 0, 0, 31, 15) + struct.pack("<4i", 0, 0, 800, 400) + struct.pack("<I", 0x464D4520)
    return header + b"\x00" * 200


def _attach(client, session, body: bytes, name="drawing.emf"):
    entry = manager.create_entry(session, "EMF kept")
    session.commit()
    return client.post(f"/entries/{entry.id}/files", files={"file": (name, io.BytesIO(body), "image/emf")})


def test_the_emf_bytes_round_trip(ai_client, session):
    sent = _emf()
    up = _attach(ai_client, session, sent)
    assert up.status_code == 201, up.text
    got = ai_client.get(f"/files/{up.json()['attachments'][0]['id']}")
    assert got.status_code == 200 and got.content == sent


def test_the_download_is_never_inline(ai_client, session):
    up = _attach(ai_client, session, _emf())
    got = ai_client.get(f"/files/{up.json()['attachments'][0]['id']}")
    assert got.headers["content-type"].startswith("application/octet-stream"), "a generic type, not image/emf"
    assert got.headers["content-disposition"].startswith("attachment")
    assert got.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in got.headers["content-security-policy"]


def test_the_size_cap_still_holds(ai_client, session, monkeypatch):
    from tessellate.api import routes_files

    monkeypatch.setattr(routes_files, "MAX_FILE_BYTES", 1000)
    assert _attach(ai_client, session, _emf() + b"\x00" * 2000).status_code == 413


def test_the_board_keeps_the_file_and_the_note_links_to_it():
    js = frontend_text("whiteboard-convert.js")
    assert '/files`' in js or "/files" in js
    assert "cvKeepEmf" in js and "keepEmf" in js
