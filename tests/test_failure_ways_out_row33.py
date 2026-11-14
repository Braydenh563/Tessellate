"""WORLD_CLASS_PLAN section 21, the survey's last items (section 8, row 33), built:
rows 1 and 2 on the notice recipe, row 12's "check the address" in the status
line, row 13's update size before the button is pressed."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_a_custom_address_nothing_answers_is_named(client):
    from tessellate.core import deps

    fake = deps.get_ollama()
    assert client.get("/models/status").json()["unreachable_hint"] is None
    fake.base_url = "http://192.168.1.50:11434"
    status = client.get("/models/status").json()
    assert status["ollama_running"] is False
    assert status["unreachable_hint"].startswith("Nothing answered at http://192.168.1.50:11434")


def test_the_frontend_uses_the_hint_the_notice_and_the_size():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert '<p id="embedding-error" class="notice notice-warn hidden"' in html
    status = (ROOT / "frontend" / "js" / "status.js").read_text(encoding="utf-8")
    assert "status.unreachable_hint ||" in status
    assert "setLabel(embeddingError, `ph:warning" in status
    updates = (ROOT / "frontend" / "js" / "update-dialogs.js").read_text(encoding="utf-8")
    assert "result.asset.size" in updates and "download" in updates
