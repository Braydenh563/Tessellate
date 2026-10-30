"""Every input has a bound at the model (audit 1029 H10, X26, N18, G27)."""

from __future__ import annotations

import pytest

from tessellate.api import bounds


def _note(client, text="a note"):
    return client.post("/entries", json={"content": text}).json()


def test_history_over_the_cap_is_refused_before_any_work(client):
    turns = [{"question": "q", "answer": "a"}] * (bounds.HISTORY_MAX_TURNS + 1)
    response = client.post("/chat", json={"question": "hi", "history": turns})
    assert response.status_code == 422


def test_one_history_turn_over_the_text_cap_is_refused(client):
    turn = {"question": "q", "answer": "x" * (bounds.TURN_TEXT_MAX + 1)}
    response = client.post("/chat", json={"question": "hi", "history": [turn]})
    assert response.status_code == 422


def test_the_page_history_fits_under_the_cap():
    # capture-ask.js sends the last MAX_CLIENT_HISTORY turns plus one summary.
    assert bounds.HISTORY_MAX_TURNS >= 5 + 1


def test_media_upload_refuses_empty_and_markup_posing_as_an_image(client):
    empty = client.post("/media/upload", files={"file": ("a.png", b"", "image/png")})
    assert empty.status_code == 422
    markup = client.post("/media/upload", files={"file": ("a.png", b"<svg onload=1>", "image/png")})
    assert markup.status_code == 415
    ok = client.post("/media/upload", files={"file": ("a.png", b"\x89PNG\r\n\x1a\n", "image/png")})
    assert ok.status_code == 200


def test_media_upload_keeps_a_short_name_without_folders(client):
    long_name = "x" * 400 + ".png"
    body = client.post("/media/upload", files={"file": (long_name, b"\x89PNG\r\n\x1a\n", "image/png")}).json()
    assert len(body["filename"]) <= bounds.NAME_MAX and body["filename"].endswith(".png")
    evil = client.post("/media/upload", files={"file": ("../../evil.png", b"\x89PNG\r\n\x1a\n", "image/png")}).json()
    assert evil["filename"] == "evil.png"


def test_attachment_name_is_capped_on_upload_and_rename(client):
    note = _note(client)
    long_name = "n" * 400 + ".txt"
    added = client.post(f"/entries/{note['id']}/files", files={"file": (long_name, b"hello", "text/plain")})
    assert added.status_code == 201
    names = [a["filename"] for a in added.json()["attachments"]]
    assert names and all(len(n) <= bounds.NAME_MAX for n in names)
    attachment_id = added.json()["attachments"][0]["id"]
    renamed = client.put(f"/files/{attachment_id}", json={"filename": "y" * 300 + ".txt"})
    assert renamed.status_code == 422


@pytest.mark.parametrize("value", [1e308, -1e30, 1e7])
def test_pin_coordinates_are_bounded(client, value):
    note = _note(client)
    one = client.put(f"/graph/pin/{note['id']}", json={"x": value, "y": 0})
    many = client.put("/graph/pins", json={"pins": [{"id": note["id"], "x": 0, "y": value}]})
    assert (one.status_code, many.status_code) == (422, 422)


def test_a_sane_pin_still_saves(client):
    note = _note(client)
    ok = client.put(f"/graph/pin/{note['id']}", json={"x": 120.5, "y": -40})
    assert ok.status_code == 200 and ok.json()["graph_pin_x"] == 120.5


def test_unknown_graph_id_is_a_404(client):
    missing = client.get("/graph/local/99999")
    assert missing.status_code == 404


def test_tool_execute_body_is_bounded(client):
    many = [{"tool": "x", "arguments": {}}] * (bounds.BATCH_STEPS_MAX + 1)
    response = client.post("/chat/tools/execute", json={"name": "batch", "steps": many})
    assert response.status_code == 422
    response = client.post("/chat/tools/execute", json={"name": "n" * 500})
    assert response.status_code == 422


def test_chat_request_names_are_bounded(client):
    response = client.post("/chat", json={"question": "hi", "persona": "p" * 500})
    assert response.status_code == 422
    response = client.post("/chat", json={"question": "hi", "mode": "m" * 500})
    assert response.status_code == 422


def test_file_text_over_the_file_cap_is_refused_at_the_model(client):
    note = _note(client)
    added = client.post(f"/entries/{note['id']}/files", files={"file": ("a.txt", b"hi", "text/plain")})
    attachment_id = added.json()["attachments"][0]["id"]
    too_big = "x" * (bounds.FILE_TEXT_MAX + 1)
    response = client.put(f"/files/{attachment_id}/text", json={"text": too_big})
    assert response.status_code == 422


def test_request_models_in_the_busy_routes_bound_every_text_and_list_field():
    # The class lint for "request caps": a new str, list or dict field on a body
    # in these routes reaches for a bound instead of arriving unbounded.
    import ast
    from pathlib import Path

    unbounded = []
    for name in ("routes_chat", "routes_files", "routes_graph"):
        path = Path("src/tessellate/api") / f"{name}.py"
        for cls in ast.walk(ast.parse(path.read_text())):
            if not isinstance(cls, ast.ClassDef) or cls.name.endswith(("Out", "Response")):
                continue
            if not any(getattr(b, "id", getattr(b, "attr", "")) == "BaseModel" for b in cls.bases):
                continue
            for field in cls.body:
                if not isinstance(field, ast.AnnAssign):
                    continue
                shape, value = ast.unparse(field.annotation), ast.unparse(field.value or ast.Constant(""))
                free = shape.startswith(("str", "list", "dict")) and "Literal" not in shape
                if free and not any(k in shape + value for k in ("max_length", "pattern")):
                    unbounded.append(f"{name}.{cls.name}.{field.target.id}")
    assert not unbounded, unbounded


def test_display_name_helper():
    assert bounds.display_name("a/b\\c.txt", "z") == "c.txt"
    assert bounds.display_name("", "fallback.png") == "fallback.png"
    assert bounds.display_name("bad\x00name\n.png", "z") == "badname.png"
