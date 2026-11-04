"""INBOX 1665 (the owner, 2026-11-04, Ask, no model): "still some issues with
the composer", on "What have I saved about courses & study?". Fixed by class
(1357), model on and off alike (CHAT_PLAN decision 75)."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests import _courses_1665 as fx

NOW = datetime(2026, 11, 4, 10, 5)
QUESTION = "What have I saved about courses & study?"


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


def ask(client, question: str = QUESTION) -> tuple[str, list]:
    body = {"question": question, "answer_from": "notes", "notes_only": True, "use_tools": False}
    text, grounding = [], []
    ask.events = {}
    with client.stream("POST", "/chat/stream", json=body) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                ask.events.setdefault(event["type"], []).append(event)
                if event["type"] == "answer":
                    text.append(event["delta"])
                elif event["type"] == "grounding":
                    grounding.append(event)
    return "".join(text), grounding


@pytest.mark.skipif(not os.environ.get("COMPOSER_1665_DUMP"), reason="dump, run by hand")
def test_dump(client, notebook):
    text, grounding = ask(client)
    print("\n" + text)
    for kind, events in ask.events.items():
        if kind not in ("answer", "grounding"):
            print(kind, json.dumps(events, default=str)[:3500])


# --- the classes ---------------------------------------------------------------

#: What a paragraph that tells no note says: the count, a group's line, a heading.
_FRAME = ("You have", "Your university", "More from", "More loosely")
QUESTIONS = [QUESTION, "what do I have on courses and study", "Tell me about my courses & study notes"]
_NUMBERS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}


def _cited(grounding) -> set[int]:
    ids = set()
    for event in grounding:
        for row in event["sentences"]:
            ids.add(row["note_id"])
            ids.update(p["note_id"] for p in row.get("parts") or [])
    return ids


@pytest.fixture
def answer(client, notebook):
    text, grounding = ask(client)
    return text, grounding, ask.events


@pytest.mark.parametrize("question", QUESTIONS)
def test_a_one_count_from_one_pool_and_every_note_said_or_counted(client, notebook, question):
    text, grounding = ask(client, question)
    said = re.search(r"You have (\w+) notes? (?:about|on)", text)
    assert said, text
    pool = [r["id"] for r in ask.events["meta"][0]["raw_results"]]
    assert _NUMBERS.get(said.group(1), said.group(1)) in (len(pool), str(len(pool)))
    in_category = {e.id for e, (_c, cat, *_r) in zip(notebook, fx.NOTES, strict=True) if cat == fx.COURSES}
    more = re.search(r"and (\w+) more", text)
    counted = _NUMBERS.get(more.group(1), 0) if more else 0
    assert len(in_category - _cited(grounding)) <= counted, (in_category - _cited(grounding), text)
    assert len(in_category) == 11


def test_b_the_opening_says_what_the_notes_are_about_in_one_short_sentence(answer):
    text, _g, _e = answer
    group = next(p for p in text.split("\n\n") if p.startswith("Your university"))
    first = re.split(r"(?<=[.!?])\s+", group)[0]
    assert len(first.split()) <= 25, first
    assert first.count("“") <= 1, first
    assert len(re.findall(r"\blinked\b", group)) <= 2, group


def test_c_a_long_note_is_said_briefly_and_never_with_a_spaced_hyphen(answer):
    text, grounding, _e = answer
    assert not re.search(r"\s[-\u2013\u2014]\s", text), text
    rows = {r["note_id"]: r for event in grounding for r in event["sentences"]}
    for i, (content, *_rest) in enumerate(fx.NOTES, start=1):
        body = re.sub(r"^#.*\n+", "", content)
        if len(body.split()) > 25 and i in rows:
            assert len(rows[i]["sentence"].split()) <= 25, rows[i]["sentence"]
            assert "without needing to manage" not in rows[i]["sentence"]


@pytest.mark.parametrize("gap", range(7, 35))
def test_d_the_answers_weeks_ago_is_the_cards(gap):
    from datetime import date, timedelta

    from tessellate.ai import composer_digest, realise

    said = composer_digest._ago(date(2026, 11, 4) - timedelta(days=gap), date(2026, 11, 4))
    card = int(gap / 7 + 0.5)  # Math.round(days / 7), frontend/js/sheets-selects.js relativeTime
    assert said == ("a week ago" if card == 1 else f"{realise.count_word(card)} weeks ago")


def test_d_the_card_still_rounds_the_way_the_answer_does():
    from pathlib import Path

    js = Path("frontend/js/sheets-selects.js").read_text(encoding="utf-8")
    assert "const weeks = Math.round(days / 7);" in js


def test_d_the_answer_and_the_card_agree_on_the_missed_bus_note(answer):
    text, _g, _e = answer
    assert "Four weeks ago, on 8 October" in text and "Three weeks ago" not in text


@pytest.mark.parametrize(
    ("note", "written", "day"),
    [
        ("Just finished my final assignment on friday at 3:30am", "2026-11-03", "2026-10-30"),
        ("I missed the bus on thursday", "2026-11-04", "2026-10-29"),
        ("I went to the gym on tuesday", "2026-11-03", "2026-11-03"),
        ("We had pizza on sunday", "2026-11-04", "2026-11-01"),
        ("I have to hand it in on friday", "2026-11-03", "2026-11-06"),
        ("my uni days this week are on tuesday and thursday", "2026-11-03", "2026-11-03"),
        ("The exam is on friday", "2026-11-03", "2026-11-06"),
        ("I booked the dentist on Friday", "2026-11-04", "2026-11-06"),
        ("I got tickets for the gig on Friday", "2026-11-04", "2026-11-06"),
        ("I made plans for dinner on friday", "2026-11-04", "2026-11-06"),
        ("I did say I would come on Friday", "2026-11-04", "2026-11-06"),
        ("I was told the exam is on Friday", "2026-11-04", "2026-11-06"),
        ("I paid for the course, which starts on Friday", "2026-11-04", "2026-11-06"),
    ],
)
def test_e_a_weekday_in_a_note_that_says_it_happened_is_the_past_one(note, written, day):
    from datetime import date

    from tessellate.entry import timewords

    found = timewords.find(note, date.fromisoformat(written))
    assert [m.at.isoformat() for m in found if m.phrase.startswith("on ")][:1] == [day]


def test_e_no_note_mentions_a_day_after_it_was_written(session, notebook):
    from tessellate.core.database import EntryDate

    for entry in notebook:
        for found in session.query(EntryDate).filter(EntryDate.entry_id == entry.id):
            #: Only a note that says it happened: "the party on Saturday" is ahead.
            if found.phrase.startswith("on ") and re.search(r"\b(?:finished|missed)\b", entry.content):
                assert found.at.date() <= entry.created_at.date(), (entry.content, found.at)


def test_f_no_note_is_said_twice_no_phrase_is_cut_every_sentence_is_cited(answer):
    text, grounding, _e = answer
    rows = [r for event in grounding for r in event["sentences"]]
    assert [r["sentence"] for r in rows if r["sentence"] not in text] == [], text
    per_note: dict[int, int] = {}
    for r in rows:
        per_note[r["note_id"]] = per_note.get(r["note_id"], 0) + 1
    assert all(n == 1 for n in per_note.values()), per_note
    for paragraph in text.split("\n\n"):
        if not paragraph.startswith(_FRAME):
            assert any(r["sentence"] in paragraph for r in rows), paragraph
    assert "You didnt lock in" in text and "You didnt lock." not in text
    assert "at work need to" not in text
    assert text.lower().count("lock-in") + text.lower().count("lock in") <= 2


@pytest.mark.parametrize("text", ["I got sent home today lol. need to lock-in for my assignments lmao", "so tired haha. going to bed now"])
def test_f_a_chat_sign_off_ends_a_sentence(text):
    from tessellate.ai import composer_read

    view = composer_read.read_note({"id": 1, "content": text, "tags": [], "category": "x"}, 0)
    assert len(view.sentences) == 2


@pytest.mark.parametrize(("sentence", "last"), [("you didnt lock in", "in"), ("you need to log in", "in"), ("you never give up", "up")])
def test_f_a_phrasal_verb_a_whole_sentence_ends_on_is_not_cut(sentence, last):
    from tessellate.ai import composer_digest as digest

    assert digest.whole_clause(sentence, frozenset({last})) == sentence
    assert digest.whole_clause("you went to the footer and") == "you went to the footer"


def test_g_a_title_that_says_something_counts_when_the_body_loses_the_point(answer):
    text, _g, _e = answer
    assert "uni is done" in text.lower()


@pytest.mark.parametrize(
    ("title", "body", "expected"),
    [
        ("Uni is done!! :D", "Just finished my final assignment on friday but it's done haha!", True),
        ("Cloud computing", "It is the delivery of computing services.", False),
        ("Meeting", "Agenda for it", False),
        ("Trip is booked", "Flights are booked, the trip is booked and it's sorted.", False),
    ],
)
def test_g_title_is_content_only_when_the_body_leans_on_it(title, body, expected):
    from tessellate.ai import composer_read

    assert composer_read.title_is_content(title, body) is expected


# --- h: the meaning floor ---------------------------------------------------------


class _E:
    def __init__(self, id, content, tags="[]"):  # noqa: A002
        self.id, self.content, self.tags = id, content, tags


def test_h_a_weak_meaning_only_match_with_no_shared_word_leaves_the_list():
    from tessellate.search import search_manager as sm

    entries = [_E(1, "uni lecture on cloud study"), _E(2, "course notes on study"), _E(3, "study plan"), _E(4, "social skills guide"), _E(5, "a joke")]
    info = {
        1: {"type": "hybrid", "score": 0.7, "terms": ["study"]},
        2: {"type": "hybrid", "score": 0.6, "terms": ["study"]},
        3: {"type": "keyword", "terms": ["study"]},
        4: {"type": "semantic", "score": 0.46},
        5: {"type": "semantic", "score": 0.31},
    }
    kept = sm.meaning_floor(entries, info, ["study"])
    assert [e.id for e in kept] == [1, 2, 3]


def test_h_a_question_with_no_word_match_is_left_alone():
    from tessellate.search import search_manager as sm

    entries = [_E(2, "exam revision notes"), _E(3, "x")]
    only = {2: {"type": "semantic", "score": 0.3}, 3: {"type": "semantic", "score": 0.2}}
    assert [e.id for e in sm.meaning_floor(entries, only, ["study"])] == [2, 3]


def test_h_a_strong_meaning_match_and_a_tagged_one_stay():
    from tessellate.search import search_manager as sm

    entries = [_E(1, "study"), _E(2, "study here"), _E(3, "study too"), _E(4, "exam revision", '["study"]'), _E(5, "exam revision notes"), _E(6, "x")]
    info = {
        1: {"type": "keyword", "terms": ["study"]},
        2: {"type": "keyword", "terms": ["study"]},
        3: {"type": "keyword", "terms": ["study"]},
        4: {"type": "semantic", "score": 0.3},
        5: {"type": "semantic", "score": 0.66},
        6: {"type": "semantic", "score": 0.2},
    }
    assert [e.id for e in sm.meaning_floor(entries, info, ["study"])] == [1, 2, 3, 4, 5]


# --- INBOX 1668: separate notes are separate events ---------------------------------

GOLF = [
    ("I had work and hit some golf balls as practice after haha", "Hobbies", [], "2026-10-04T20:00:00"),
    (
        "Played a game of golf for 18 holes at Windaroo on Monday which was fun but the greens were kinda ass and really dry, I shot like 130",
        "Hobbies",
        [],
        "2026-11-04T18:00:00",
    ),
]


@pytest.fixture
def golf(session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    made = []
    for content, category, tags, when in GOLF:
        entry = manager.create_entry(session, content, category, tags)
        entry.created_at = entry.updated_at = datetime.fromisoformat(when)
        manager.record_dates(session, entry, now=entry.created_at)
        made.append(entry)
    session.commit()
    return made


def test_i_a_weak_cue_never_heads_a_separate_notes_event(client, golf):
    text, _g = ask(client, "golf notes")
    print(text)
    assert "How it went" not in text, text
    #: Two paragraphs, one per note, neither under a label. Days stay unsaid:
    #: the question did not ask for time (INBOX 1441).
    assert len([p for p in text.split("\n\n") if "golf" in p and not p.startswith("You have")]) == 2, text


def test_i_a_weak_cue_still_tells_parts_of_one_note_apart():
    from tessellate.ai import composer_digest as digest

    assert digest._cue_for("it was fun", "", "", False, "", True) == "How it went"
    assert digest._cue_for("it was fun", "", "", False, "", False) == ""


def test_i_b_a_past_tense_weekday_mention_is_the_past_one(session, golf):
    from tessellate.core.database import EntryDate

    mentions = {r.phrase: r.at.date().isoformat() for r in session.query(EntryDate).filter(EntryDate.entry_id == golf[1].id)}
    assert mentions == {"on Monday": "2026-11-02"}


def test_i_b_a_stored_wrong_day_is_read_again(session, golf):
    from tessellate.core.database import EntryDate
    from tessellate.entry import redate

    row = session.query(EntryDate).filter(EntryDate.entry_id == golf[1].id).one()
    row.at = datetime(2026, 11, 9)
    session.commit()
    assert redate._reread(session, golf[1]) is True
    session.commit()
    assert session.query(EntryDate).filter(EntryDate.entry_id == golf[1].id).one().at.date().isoformat() == "2026-11-02"
