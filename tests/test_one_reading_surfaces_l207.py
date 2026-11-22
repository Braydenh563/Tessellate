"""CHAT_PLAN decision 47 (L-chat-207): one typed reading per input. Chat reads
through `reading.read`; quick add reads `GET /read`; the palette's act rows
read `GET /read/act`; the search box's phrase reads through `filters.read`,
which takes the same `query.understand` the reading's question step takes, so
the two never disagree about a phrase."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from tessellate.ai import filters, reading
from tessellate.search import query

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "composer" / "filters_1010.json"


def _text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_each_surface_reaches_the_reading():
    assert "reading.read(" in _text("src/tessellate/api/chat_service.py")
    assert '"/read" + query' in _text("frontend/js/quickadd.js")
    assert "`/read/act?q=" in _text("frontend/js/app-palette.js")
    assert "reading.read(" in _text("src/tessellate/api/routes_read.py")
    assert "/read/filter" in _text("frontend/js/search.js") or "/read/answer" in _text("frontend/js/search.js")


def test_search_phrases_and_the_reading_share_one_parse():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    now = datetime.fromisoformat(data["now"])
    for row in data["rows"]:
        said = reading.read(row["text"], now=now)
        if said.intent != "question":
            continue
        understood = query.understand(row["text"], now, "en")
        assert said.slots["subject"] == understood.subject, row["text"]
        assert said.slots["filters"] == {k: v for k, v in understood.filters.items() if v}, row["text"]
    assert filters.read(data["rows"][0]["text"], now)["filters"]
