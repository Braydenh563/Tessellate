"""A slash command that raises is not a 500: the turn carries on as an
ordinary one, and the log names the failure without the user's text."""

from __future__ import annotations

import json
import logging

from tessellate.ai import slash
from tessellate.entry import manager


def _events(client, question: str) -> list[dict]:
    with client.stream("POST", "/chat/stream", json={"question": question}) as response:
        assert response.status_code == 200
        return [json.loads(line) for line in response.iter_lines() if line.strip()]


def test_a_slash_command_that_raises_falls_through_to_the_normal_turn(client, session, monkeypatch, caplog):
    manager.create_entry(session, "Golf after work", "Sport", ["golf"])
    session.commit()

    def boom(*args, **kwargs):
        raise RuntimeError("secret-note-text\nFORGED log line")

    monkeypatch.setattr(slash, "answer", boom)
    with caplog.at_level(logging.WARNING, logger="tessellate.chat"):
        events = _events(client, "/count golf secret-note-text")
    kinds = [e["type"] for e in events]
    assert kinds[-1] == "done" and "meta" in kinds
    assert any(e["type"] == "answer" for e in events)
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert "slash command failed" in logged and "RuntimeError" in logged
    assert "secret-note-text" not in logged and "FORGED" not in logged
