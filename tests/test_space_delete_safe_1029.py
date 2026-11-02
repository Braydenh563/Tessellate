"""Audit 1029 X5: the space delete dialog preselects the safe option and counts."""
from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import app_js_text

HTML = (Path(__file__).resolve().parents[1] / "frontend" / "index.html").read_text(encoding="utf-8")


def test_counts_route_reports_notes_and_documents(client):
    sid = client.post("/spaces", json={"name": "Counted"}).json()["id"]
    h = {"X-Workspace-ID": sid}
    client.post("/entries", json={"content": "one"}, headers=h)
    client.post("/entries", json={"content": "two"}, headers=h)
    got = client.get(f"/spaces/{sid}/counts")
    assert got.status_code == 200
    assert got.json() == {"notes": 2, "documents": 0}


def test_counts_route_404s_for_unknown_space(client):
    assert client.get("/spaces/nope-1029/counts").status_code == 404


def test_dialog_preselects_a_move_not_the_wipe():
    js = app_js_text()
    body = js[js.index("function rmSpace"):]
    body = body[: body.index("\nasync function spaceDeleteSubmit")]
    assert "fate.value = " in body, "a safe move target is selected first"
    assert "/counts" in body and "notes" in body and "documents" in body
    assert "Delete everything in it" in body


def test_dialog_has_a_count_line():
    assert re.search(r'id="space-delete-count"', HTML)
