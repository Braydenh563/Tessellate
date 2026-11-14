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
from datetime import date, datetime, timedelta

import pytest

from tessellate.ai import composer_story, librarian
from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tessellate.entry import manager_links
from tests import _courses_1665 as fx

NOW = datetime(2026, 11, 11, 10, 30)
QUESTIONS = [
    "What have I saved about courses & study?",
    "what do I have on courses and study",
    "Tell me about my courses & study notes",
    "what do I know about courses & study",
    "what do I know about courses and study",
]


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
            manager_links.create_link(session, entry, made[i], reason=reason)
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


def test_a_know_about_ask_for_the_whole_category_is_the_overview_not_the_count_list(answer):
    """"what do I know about courses & study" took the notebook-count list (an empty bullet, "Plus eight more")."""
    assert "Your notebook holds" not in answer["text"] and "Plus " not in answer["text"], answer["text"]


def test_a_list_never_has_an_empty_bullet(client, notebook):
    text = ask(client, "what do I know about courses")["text"]
    assert not re.search(r"^- *$", text, re.M), text


# --- the pure parts ----------------------------------------------------------------


def test_a_pair_is_not_woven_but_three_notes_are():
    """Under five notes used to keep the lines; the owner's second note (1743) wove them too, from three."""
    days = [date(2026, 7, 1), date(2026, 7, 2), date(2026, 7, 3)]
    assert composer_story.plan(days[:2], ["a", "b"]) is None
    assert composer_story.plan(days, ["a", "b", "c"]).chunks == [[0, 1, 2]]


def test_many_notes_are_cut_into_paragraphs_of_eight_at_most():
    days = [date(2026, 3, 1) + timedelta(days=4 * i) for i in range(30)]
    plan = composer_story.plan(days, [""] * 30)
    assert [i for run in plan.chunks for i in run] == list(range(30))
    assert max(len(run) for run in plan.chunks) <= composer_story.PARAGRAPH_NOTES
    assert min(len(run) for run in plan.chunks) >= 3
    assert composer_story.plan([date(2026, 1, 1) + timedelta(days=i) for i in range(41)], [""] * 41) is None


def test_notes_of_one_theme_share_a_sentence_and_a_sentence_holds_three_at_most():
    assert composer_story._beats([0, 1, 2, 3, 4, 5], [[0, 2, 3, 4, 5]]) == [[0, 2, 3], [1], [4, 5]]
    assert composer_story._beats([0, 1, 2], [[0, 5]]) == [[0], [1], [2]], "a theme with one note here is no theme"


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
    for rule in ("two to four short paragraphs", "naming the arc", "one insight", "quote slang", "your note defines", "share a tag or a link", "never \"and N more\""):
        assert rule in brief
    assert "Do NOT end by offering to do anything else" in brief


# --- fewer than five and more than fourteen notes (follow-ups, 1743) ----------------


def _fill(session, rows):
    for content, category, tags, when in rows:
        entry = manager.create_entry(session, content, category, tags)
        entry.created_at = entry.updated_at = datetime.fromisoformat(when)
        manager.record_dates(session, entry, now=entry.created_at)
    session.commit()


GARDEN = ["I planted the tomatoes by the fence", "I sowed carrots in the long bed", "I watered the beans before work", "I pruned the roses at the gate"]


def test_four_notes_a_frame_would_pad_are_an_overview_not_the_lines():
    """Under five notes the plain lines have no filler; four with some "more loosely related" are told as the story."""
    from tessellate.ai import composer_digest
    from tests import _social_1420 as social

    text = composer_digest.answer("what have I written about uni", social.uni_notes(), today=social.TODAY)["text"]
    assert text.startswith("You have four notes about university, all written in July."), text
    for filler in ("Show ", "more on the right", "More from", "More loosely", "Two notes more"):
        assert filler not in text, text


def test_twenty_notes_are_told_in_short_paragraphs_with_no_filler(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    things = ["tomatoes", "carrots", "beans", "roses", "leeks", "peas"]
    _fill(session, [
        (f"I tended the {things[i % 6]} bed number {i}", "Garden", ["soil"] if i % 3 == 0 else ["seeds"] if i % 3 == 1 else [], f"2026-{3 + i // 5:02d}-{1 + (i % 5) * 5:02d}T09:00")
        for i in range(20)
    ])
    got = ask(client, "what do I know about garden")
    paragraphs = [p for p in got["text"].split("\n\n") if p.strip()]
    assert got["text"].startswith("You have 20 notes about garden"), got["text"]
    assert len(paragraphs) >= 4 and all(len(p.split(". ")) <= 12 for p in paragraphs[1:-1]), got["text"]
    for filler in ("Show ", "more on the right", "More from", "Two notes more", "Plus "):
        assert filler not in got["text"], got["text"]
    assert len({row["note_id"] for row in _rows(got)}) >= 20
    assert not (got["support"] or {}).get("more")


def test_notes_that_go_together_are_one_sentence_not_time_alone(answer):
    """The linked July notes (uni days, Cloud computing, the lectures) are one sentence, each still cited."""
    first = next(p for p in answer["text"].split("\n\n") if p.startswith("In July"))
    sentence = first.split(". ")[0]
    assert "uni days" in sentence and "Cloud computing note defines" in sentence, first
    assert "you had three lectures" in sentence or "three lectures" in first


def test_a_volunteered_insight_quotes_slang_as_the_story_does():
    from tessellate.ai import insights

    note = {"id": 1, "content": "I got sent home after an hour at work lol. need to lock-in for my assignments lmao", "created_at": datetime(2026, 8, 9, 9, 0), "tags": []}
    found = insights.drift([note], date(2026, 11, 11))
    assert found, "the plan is not picked up by a later note"
    assert "this plan: “need to lock-in for my assignments lmao”." in found[0].text, found[0].text
    assert found[0].slots["plan"] == "need to lock-in for my assignments lmao", "the slot stays the note's own words"
    plain = {"id": 2, "content": "I plan to repaint the shed fence", "created_at": datetime(2026, 8, 2, 9, 0), "tags": []}
    assert "“" not in insights.drift([plain], date(2026, 11, 11))[0].text


def test_the_woven_lead_names_the_category_as_typed_and_says_each_count_once():
    #: The grouped path's lead and count rules (form_1301, timing_1461) hold for the woven one: the topic as the
    #: person typed it, one count in the lead, the sections of a guide never said as notes of their own.
    from tessellate.ai import composer_digest
    from tests.test_gold_answers import FIXTURE, TODAY, _notebook

    item = next(a for a in FIXTURE["answers"] if a["n"] == 22)
    text = composer_digest.answer(item["question"], _notebook(item), today=TODAY)["text"]
    lead = text.split("\n\n")[0]
    assert lead.startswith("You have five notes about social connections"), lead
    assert len(re.findall(r"\b(?:five|5)\b", lead)) == 1 and "Phase note" not in text and ";" not in text
