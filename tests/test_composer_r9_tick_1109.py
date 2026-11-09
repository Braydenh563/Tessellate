"""R9-9: "tick the first one" after a task list acts on the task the list showed, in Chat.
Seed: `tests/_seed_r9_1109.py`."""

from __future__ import annotations

import tests._seed_r9_1109 as sd


def test_tick_the_first_one_names_the_listed_task(client, session, monkeypatch):
    sd.seed(session)
    go = sd.asker(client, monkeypatch, chat=True)
    listing = go("what's on my todo")[0]
    text, _events = go("tick the first one", history=[{"question": "what's on my todo", "answer": listing}])
    assert "oat milk" in text.lower()
