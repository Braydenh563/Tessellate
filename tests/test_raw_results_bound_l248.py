"""L248: the chat meta event's `raw_results` is bounded on a big notebook.

The money scan keeps at most `composer_money.SCAN_HITS` notes, so a 450-note
notebook where every note holds an amount sends 400 rows, 425 KB measured,
and the answer stays a short list. Measured here on a fixed clock."""

from __future__ import annotations

import json
from datetime import datetime

from tessellate.ai import composer_money
from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager

NOW = datetime(2026, 10, 30, 12, 0)


def test_a_450_note_money_question_sends_at_most_the_scan_cap(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for i in range(450):
        entry = manager.create_entry(session, f"# Coffee {i}\n\nSpent £{i + 1} on coffee.")
        entry.created_at = entry.updated_at = datetime(2026, 10, 1 + i % 28, 9, 0)
    session.commit()
    meta, text = {}, ""
    with client.stream("POST", "/chat/stream", json={"question": "how much did I spend on coffee", "answer_from": "notes", "notes_only": True, "use_tools": False}) as response:
        for line in response.iter_lines():
            if not line.strip():
                continue
            event = json.loads(line)
            if event["type"] == "meta" and len(event.get("raw_results") or []) >= len(meta.get("raw_results") or []):
                meta = event
            elif event["type"] == "answer":
                text += event["delta"]
    sent = len(meta.get("raw_results") or [])
    assert 0 < sent <= composer_money.SCAN_HITS, sent
    #: Measured 2026-11-14: 400 rows, 425 KB of meta for 450 notes of one line each.
    assert len(json.dumps(meta)) < 600_000, len(json.dumps(meta))
    assert text and text.count("\n") < 60, text
