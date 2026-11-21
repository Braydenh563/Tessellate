"""Shared seed and driver for the composer round 5 tests (2026-11-08): `driver` seeds the
notebook and returns a function that asks `/chat/stream` with no model and a fixed clock."""

from __future__ import annotations

import json
from datetime import datetime

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests._seed_r2_1107 import TODAY, raw

NOW = datetime(2026, 11, 7, 12, 0)

EXTRA = [
    ("Sara", "Sara is my sister. Her birthday is on 14 March.", 30),
    ("Gift ideas", "Sara wants a jazz record, lilies, or tickets to the theatre. Do not buy perfume again.", 20),
    ("Sara likes jazz", "Sara likes jazz", 10),
    ("Weekend plans", "Lunch with Sara on Saturday. Park with Tom.", 5),
    ("Sara's favourite colour", "Sara's favourite colour is green.", 9),
    ("Sara and Tom", "Sara and Tom met at uni.", 8),
    ("Wedding", "Sara is the maid of honour.", 7),
    ("Atlas", "Project Atlas kicks off in January. Lisbon offsite maybe.", 12),
    ("Gym", "Squats on Monday.", 12),
    ("Gym plan", "Gym £30 a month", 13),
    ("Dentist said to floss more", "Dentist said to floss more and use the soft brush", 3),
]


def driver(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for title, body, ago in [*raw, *EXTRA]:
        entry = manager.create_entry(session, f"# {title}\n\n{body}" if body != title else title, category_name="Uncategorised")
        entry.created_at = entry.updated_at = datetime.fromordinal(TODAY.toordinal() - ago).replace(hour=10)
    session.commit()

    def go(question: str, history: list | None = None) -> dict:
        text, chips = "", []
        body: dict = {"question": question, "use_tools": False}
        if history:
            body["history"] = history
        with client.stream("POST", "/chat/stream", json=body) as response:
            for line in response.iter_lines():
                if not line.strip():
                    continue
                event = json.loads(line)
                if event["type"] == "answer":
                    text += event["delta"]
                if event.get("next"):
                    chips = event["next"]
        return {"text": text, "chips": chips}

    return go


def chain(ask, *questions: str) -> list[str]:
    history: list[dict] = []
    said: list[str] = []
    for question in questions:
        text = ask(question, history or None)["text"]
        history.append({"question": question, "answer": text})
        said.append(text)
    return said
