"""INBOX 1743 (the owner, 2026-11-11): the Ask answer to "what do I know about
courses & study" was one retold sentence per note, with filler between them.
It is now an overview a person would write: a lead naming the span and the arc,
a few paragraphs by stretch, a read of how it went, one citation per claim.
Fixture: the owner's courses & study notes (tests/_courses_1665.py). Clock:
Wednesday 11 November 2026, 10:30. Model up: the Ask brief carries the same
rules (decision 75)."""

from __future__ import annotations

import json
import re
from datetime import date, datetime

import pytest

from tessellate.ai import composer_story, librarian
from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests import _courses_1665 as fx

NOW = datetime(2026, 11, 11, 10, 30)
QUESTIONS = ["What have I saved about courses & study?", "what do I have on courses and study", "Tell me about my courses & study notes"]


@pytest.fixture
def notebook(session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    made = []
    for content, category, tags, when, _links in fx.NOTES:
        entry = manager.create_entry(session, content, category, tags)
        entry.created_at = entry.updated_at = datetime.fromisoformat(when)
        manager.record_dates(session, entry, now=entry.created_at)
        made.append(entry)
    session.commit()
    for (_c, _cat, _t, _w, links), entry in zip(fx.NOTES, made, strict=True):
        for i, reason in links.items():
            manager.create_link(session, entry, made[i], reason=reason)
    session.commit()
    return made


def ask(client, question: str) -> dict:
    body = {"question": question, "answer_from": "notes", "notes_only": True, "use_tools": False}
    got: dict = {"text": "", "grounding": [], "support": None}
    with client.stream("POST", "/chat/stream", json=body) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                if event["type"] == "answer":
                    got["text"] += event["delta"]
                elif event["type"] == "grounding":
                    got["grounding"].append(event)
                    got["support"] = event.get("support")
    return got


@pytest.fixture(params=QUESTIONS)
def answer(request, client, notebook):
    return ask(client, request.param)


def _rows(got: dict) -> list[dict]:
    return [row for event in got["grounding"] for row in event["sentences"]]


def test_it_is_a_few_paragraphs_not_a_column(answer):
    paragraphs = [p for p in answer["text"].split("\n\n") if p.strip()]
    assert 3 <= len(paragraphs) <= 6, answer["text"]
    assert len(answer["text"].split()) > 90


def test_the_lead_names_the_span_and_the_arc(answer):
    lead = answer["text"].split("\n\n")[0]
    assert lead.startswith("You have eleven notes about") and "follow one semester, July to early November" in lead, lead


@pytest.mark.parametrize("filler", ["Show ", "more on the right", "More from", "More loosely", "Two notes more", "Nothing yet on"])
def test_no_filler_and_no_read_back(answer, filler):
    assert filler not in answer["text"], answer["text"]
    assert not (answer["support"] or {}).get("more")


def test_a_definition_is_defined_not_retold_as_said(answer):
    assert "You mentioned that Cloud computing" not in answer["text"]
    assert re.search(r"[Yy]our Cloud computing note defines the term as the delivery of computing services", answer["text"])


def test_slang_is_quoted_not_revoiced(answer):
    assert "“I didnt lock in”" in answer["text"]
    assert "You didnt" not in answer["text"]
    assert "“Uni is done”" in answer["text"]


def test_a_time_opener_is_never_said_twice_in_a_row(answer):
    openers = re.findall(r"(?:^|\. |\n\n)((?:In|By|Come|Early|Mid|Late|Soon after|After that|Then|Next)\b[^,]*),", answer["text"])
    assert len(openers) >= 6, openers
    assert all(a != b for a, b in zip(openers, openers[1:], strict=False)), openers
    assert "Back in July" not in answer["text"]


def test_the_finish_is_congratulated_and_a_hard_stretch_acknowledged_plainly(answer):
    assert "Congratulations on getting it done." in answer["text"]
    assert "That reads like a hard stretch." in answer["text"]
    assert "!" not in answer["text"].replace("Uni is done!!", "")


def test_every_note_is_cited_and_each_claim_cites_one_note(answer):
    rows = _rows(answer)
    assert len({row["note_id"] for row in rows}) >= 11
    for row in rows:
        assert row["sentence"] in answer["text"], row
        assert not row.get("parts"), row
    sentences = [row["sentence"] for row in rows]
    assert len(sentences) == len(set(sentences)), "one citation per claim line"


def test_the_notes_close_with_one_insight(answer):
    last = answer["text"].split("\n\n")[-1]
    assert "fall between mid July and early August" in last or "no later note" in last, last


# --- the pure parts ----------------------------------------------------------------


def test_a_short_stretch_is_not_woven():
    days = [date(2026, 7, 1), date(2026, 7, 2), date(2026, 7, 3)]
    assert composer_story.plan(days, ["a", "b", "c"]) is None


def test_the_paragraphs_break_at_the_biggest_gaps_and_stay_about_even():
    days = [date(2026, 7, d) for d in (17, 20, 26, 27)] + [date(2026, 8, d) for d in (4, 9, 10)] + [date(2026, 10, 8), date(2026, 10, 15), date(2026, 11, 3)]
    plan = composer_story.plan(days, ["this semester"] + [""] * 9)
    assert plan.arc == "one semester"
    assert 2 <= len(plan.chunks) <= composer_story.MAX_PARAGRAPHS
    assert [i for run in plan.chunks for i in run] == list(range(10))
    assert min(len(run) for run in plan.chunks) >= 2


def test_the_span_is_said_in_months():
    assert composer_story.span_words(date(2026, 7, 17), date(2026, 11, 3)) == "July to early November"


# --- model up (decision 75) --------------------------------------------------------


def test_the_ask_brief_for_a_model_asks_for_the_same_overview():
    brief = librarian.ASK_OVERVIEW
    for rule in ("two to four short paragraphs", "naming the arc", "one insight", "quote slang", "your note defines"):
        assert rule in brief
    assert "Do NOT end by offering to do anything else" in brief
