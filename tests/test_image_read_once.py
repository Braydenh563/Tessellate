"""INBOX 1484: a picture is read once per stored file, however its note is edited.

The owner aligned an image in a note and Activity, Agent runs showed "Reading
an image with the vision model" again. The 1465 guard (`media_process._ASKED`)
lives in memory, so a restart forgot it, and a picture the model found no text
in stores "" (falsy), which every later save took for "never read".

Queued jobs are counted at `jobs.enqueue`, the one place a reader starts, so
nothing here depends on a model; a read that found nothing is stored the way
`vision_ocr_and_store` stores it (an empty string, not NULL).
"""

from __future__ import annotations

import pytest

from tessellate.core import deps, jobs, media_process
from tessellate.core.database import MediaUpload

PNG = b"\x89PNG\r\n\x1a\n"


@pytest.fixture()
def queued(monkeypatch):
    """Every job started while the test runs, as (kind, display name)."""
    seen: list[tuple[str, str]] = []

    def fake_enqueue(kind, func, *args, name="", dedupe_key=None, **kwargs):
        seen.append((kind, name))
        return len(seen)

    monkeypatch.setattr(jobs, "enqueue", fake_enqueue)
    return seen


def _vision(queued) -> list[str]:
    return [name for kind, name in queued if kind == "vision"]


def _reads(queued) -> list[tuple[str, str]]:
    """Reader jobs only: a note save also queues its own embedding."""
    return [(kind, name) for kind, name in queued if kind in {"ocr", "caption", "vision", "vision-pdf"}]


def _upload(client, name="shot.png") -> dict:
    return client.post("/media/upload", files={"file": (name, PNG, "image/png")}).json()


def _mark_read(url: str, text: str = "") -> None:
    """What a finished vision read leaves behind; "" is 'looked, no text'."""
    with deps.get_db().session() as session:
        row = session.query(MediaUpload).filter_by(filename=url.rsplit("/", 1)[1]).one()
        row.vision_ocr_text = text
        row.vision_ocr_model = "moondream"
        session.commit()


def _restart() -> None:
    media_process._ASKED.clear()


def test_a_picture_that_held_no_text_is_not_read_again_after_a_restart(ai_client, queued):
    up = _upload(ai_client)
    note = ai_client.post("/entries", json={"content": f"![Gary]({up['url']})"}).json()
    assert len(_vision(queued)) == 1
    _mark_read(up["url"], "")
    _restart()
    queued.clear()
    for body in (
        f"![Gary|center]({up['url']})",
        f"![Gary|320|center]({up['url']})",
        f"![Gary|320|center|Gary at home]({up['url']})",
        f"intro\n\n![Gary|right]({up['url']})\n\nmore words",
    ):
        saved = ai_client.put(f"/entries/{note['id']}", json={"content": body})
        assert saved.status_code == 200
    assert _vision(queued) == []


def test_a_picture_with_text_is_not_read_again_after_a_restart(ai_client, queued):
    up = _upload(ai_client)
    note = ai_client.post("/entries", json={"content": f"![Sign]({up['url']})"}).json()
    _mark_read(up["url"], "OPEN")
    _restart()
    queued.clear()
    ai_client.put(f"/entries/{note['id']}", json={"content": f"![Sign|200|left]({up['url']})"})
    assert _vision(queued) == []


def test_align_resize_and_caption_saves_queue_no_read(ai_client, queued):
    up = _upload(ai_client)
    note = ai_client.post("/entries", json={"content": f"![Gary]({up['url']})"}).json()
    queued.clear()
    for body in (
        f"![Gary|center]({up['url']})",
        f"![Gary|480|center]({up['url']})",
        f"![Gary|480|center|A moss monster]({up['url']})",
    ):
        ai_client.put(f"/entries/{note['id']}", json={"content": body})
    assert _reads(queued) == []


def test_a_new_picture_queues_one_read(ai_client, queued):
    first = _upload(ai_client, "a.png")
    note = ai_client.post("/entries", json={"content": f"![A]({first['url']})"}).json()
    queued.clear()
    second = _upload(ai_client, "b.png")
    ai_client.put(
        f"/entries/{note['id']}",
        json={"content": f"![A]({first['url']})\n\n![B]({second['url']})"},
    )
    assert _vision(queued) == [second["url"].rsplit("/", 1)[1]]


def test_replacing_a_picture_queues_one_read(ai_client, queued):
    first = _upload(ai_client, "a.png")
    note = ai_client.post("/entries", json={"content": f"![A]({first['url']})"}).json()
    _mark_read(first["url"], "")
    queued.clear()
    second = _upload(ai_client, "a.png")
    ai_client.put(f"/entries/{note['id']}", json={"content": f"![A]({second['url']})"})
    assert _vision(queued) == [second["url"].rsplit("/", 1)[1]]


def test_one_picture_in_two_notes_is_read_once(ai_client, queued):
    """Keyed by the stored file name (a random name per upload, so not a
    content hash): two notes naming one upload share its one read."""
    up = _upload(ai_client)
    ai_client.post("/entries", json={"content": f"first ![G]({up['url']})"})
    ai_client.post("/entries", json={"content": f"second ![G|right]({up['url']})"})
    assert len(_vision(queued)) == 1


def test_a_read_that_failed_is_tried_again_on_the_next_save(ai_client, queued):
    """NULL means never read (no model yet, backend down): still retried."""
    up = _upload(ai_client)
    note = ai_client.post("/entries", json={"content": f"![G]({up['url']})"}).json()
    _restart()
    queued.clear()
    ai_client.put(f"/entries/{note['id']}", json={"content": f"![G|center]({up['url']})"})
    assert len(_vision(queued)) == 1


def test_the_explicit_read_again_still_reads_a_stored_empty_reading(app_state, monkeypatch, tmp_path):
    from tessellate.ai import vision_ocr

    up_path = tmp_path / "x.png"
    up_path.write_bytes(PNG)
    with deps.get_db().session() as session:
        row = MediaUpload(filename="x.png", original_name="x.png", vision_ocr_text="", vision_ocr_model="m")
        session.add(row)
        session.commit()
        upload_id = row.id
    calls: list[str] = []
    monkeypatch.setattr(vision_ocr, "vision_ocr_text", lambda *a: calls.append("read") or "HELLO")
    monkeypatch.setattr(
        deps.get_model_manager(), "resolve_vision_model", lambda *_: "m", raising=False
    )
    assert vision_ocr.vision_ocr_and_store(upload_id, up_path) == ""
    assert calls == []
    assert vision_ocr.vision_ocr_and_store(upload_id, up_path, force=True) == "HELLO"
    assert calls == ["read"]
