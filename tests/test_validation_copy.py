"""Validation copy and the memory cap (audit 1031 BK8, HR13).

A bad request is answered in the person's words: the field by its label and
the limit in the message, never pydantic's text or a code name. One preference
cap is shared by the field, the route and the tool.
"""

from __future__ import annotations

import re
from pathlib import Path

from tessellate.ai import memory, tools
from tessellate.core import validation_copy

ROOT = Path(__file__).resolve().parents[1]


def test_a_bad_reminder_time_names_the_time_not_the_column(client):
    reply = client.post("/reminders", json={"text": "x", "due_at": "not a time"})
    body = reply.json()
    assert reply.status_code == 422
    assert "due at" not in body["detail"]
    assert body["detail"] == "The due time isn't a date or time that can be read."


def test_a_long_category_says_the_limit_not_the_library(client):
    reply = client.post("/categories", json={"name": "x" * 5000})
    body = reply.json()
    assert reply.status_code == 422
    assert "String should" not in reply.text
    assert re.search(r"at most [\d,]+ characters", body["detail"]), body["detail"]
    assert "String should" not in body["fields"][0]["message"]


def test_a_too_large_document_says_the_limit(client):
    made = client.post("/documents", json={"title": "d", "content": ""})
    assert made.status_code in (200, 201)
    reply = client.put(f"/documents/{made.json()['id']}", json={"content": "x" * 500_001})
    assert reply.status_code == 422
    assert "500,000 characters" in reply.json()["detail"]


def test_sentences_per_error_type():
    s = validation_copy.sentence
    assert s("string_too_long", "name", {"max_length": 80}) == "The name can be at most 80 characters."
    assert s("string_too_short", "text", {"min_length": 1}) == "The text can't be empty."
    assert s("greater_than_equal", "offset", {"ge": 0}) == "Offset must be 0 or more."
    assert s("less_than", "limit", {"lt": 5}) == "Limit must be less than 5."
    assert s("int_parsing", "entry_id") == "The note id must be a whole number."
    assert s("list_type", "tags") == "Check the tags and try again."
    for out in (s("missing", "due_at"), s("string_too_long", "q", {"max_length": 9})):
        assert "\u2014" not in out and "!" not in out


def test_the_input_is_never_read():
    detail, fields = validation_copy.describe([{"type": "string_too_long", "loc": ("body", "x"), "input": "SECRET", "ctx": {"max_length": 3}}])
    assert "SECRET" not in detail and fields[0]["field"] == "x"


def test_one_memory_cap_in_the_field_the_route_and_the_tool(client):
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    field = re.search(r'<input id="memory-new"[^>]*maxlength="(\d+)"', html)
    assert field and int(field.group(1)) == memory.MAX_PREFERENCE_CHARS
    assert tools.MAX_PREFERENCE_CHARS == memory.MAX_PREFERENCE_CHARS
    over = client.post("/memory", json={"content": "x" * (memory.MAX_PREFERENCE_CHARS + 1)})
    assert over.status_code == 422
    assert str(memory.MAX_PREFERENCE_CHARS) in over.json()["detail"]
    ok = client.post("/memory", json={"content": "x" * memory.MAX_PREFERENCE_CHARS})
    assert ok.status_code == 201
