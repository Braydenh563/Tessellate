"""The typed reading (CHAT_PLAN "The deterministic foundation", module 2;
decisions 47 to 49): one reading per input, its confidence band measured on
`fixtures/composer/reading_1010.json`, the repair ladder as one contract, and
`GET /read` serving it.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from tessellate.ai import reading

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests/fixtures/composer/reading_1010.json").read_text(encoding="utf-8"))
NOW = datetime.fromisoformat(FIXTURE["now"])


def test_every_row_lands_in_its_band():
    """The eval that set `reading.BANDS` (decision 48): 1.0 on intent and band."""
    wrong = []
    for row in FIXTURE["rows"]:
        got = reading.read(row["text"], now=NOW, context=row["context"])
        if (got.intent, got.band) != (row["intent"], row["band"]):
            wrong.append((row["text"], row["context"], got.intent, got.band, round(got.confidence, 2)))
    assert not wrong, f"{len(wrong)} of {len(FIXTURE['rows'])}:\n" + "\n".join(map(repr, wrong))


def test_the_scores_sit_clear_of_every_floor():
    floors = [floor for _name, floor in reading.BANDS if floor > 0]
    for score in reading.SCORES.values():
        assert all(round(abs(score - floor), 6) >= 0.1 for floor in floors), score


def test_an_unsure_reading_asks_one_question_naming_both_readings():
    got = reading.read("remind me on 3/11 to call the bank", now=NOW)
    assert got.band == "unsure"
    assert got.question.startswith("Do you mean ") and "3 November" in got.question and "11 March" in got.question
    step = reading.repair(got)
    assert step.step == "ask" and step.line == got.question


def test_a_missing_slot_is_asked_never_guessed():
    got = reading.read("remind me to call the bank", now=NOW)
    assert got.slots["due_at"] is None and got.question == "Remind you when?"


def test_a_likely_reading_says_what_it_read():
    got = reading.read("what did I write last week", now=NOW)
    assert got.band == "likely" and got.said == "Read as notes from Tuesday 29 September 2026 to Tuesday 6 October 2026."
    assert reading.repair(got) is None


def test_quick_add_slots_carry_the_repeat_and_the_offer():
    weekly = reading.read("water the plants every tuesday", now=NOW, context={"surface": "reminder"})
    assert weekly.slots["text"] == "Water the plants" and weekly.slots["recurring"] == "weekly"
    assert weekly.slots["repeat"] == "FREQ=WEEKLY;BYDAY=TU"
    rent = reading.read("pay rent on the 1st", now=NOW, context={"surface": "reminder"})
    assert rent.slots["due_at"] == datetime(2026, 11, 1, 9, 0) and rent.slots["offer_recurring"] == "monthly"
    birthday = reading.read("call Sam on my birthday", now=NOW, context={"surface": "reminder", "birthday": "1990-11-20"})
    assert birthday.slots["due_at"] == datetime(2026, 11, 20, 9, 0)


def test_the_ladder_has_four_steps():
    assert reading.repair(None).step == "no_input" and reading.repair(None).line is None
    mash = reading.read("asdfgh", now=NOW)
    step = reading.repair(mash)
    assert step.step == "no_match" and "remind me to call mum" in step.line
    assert reading.repair(mash, closest="the Harbor launch note").line.startswith("The closest I have is the Harbor launch note.")
    stopped = reading.repair(None, error="timeout", composed="Your boiler note says 1.2 bar.")
    assert stopped.step == "error" and stopped.keep == "Your boiler note says 1.2 bar."
    for line in (step.line, stopped.line, reading.NO_MATCH):
        assert "!" not in line and chr(0x2014) not in line


def test_the_route_serves_the_reading_signed_in(client):
    token = client.post("/auth/setup", json={"password": "first-pass"}).json()["token"]
    got = client.get("/read", params={"q": "dentist 21st 9am", "surface": "reminder", "tz_offset_minutes": 0,
                                      "now": "2026-10-14T10:00:00+00:00"},
                     headers={"X-Auth-Token": token})
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["intent"] == "reminder" and body["band"] == "sure"
    assert body["slots"]["text"] == "Dentist" and "T09:00" in body["slots"]["due_at"]
    assert any(s["kind"] == "datetime" and s["text"] == "21st 9am" for s in body["spans"])
    assert client.get("/api/v1/read", params={"q": "hello"}, headers={"X-Auth-Token": token}).json()["intent"] == "smalltalk"


def test_the_route_reads_on_a_given_clock(client):
    """`now` fixes the clock (Brief 66's sweep); a bad one is ignored, never a 422."""
    token = client.post("/auth/setup", json={"password": "first-pass"}).json()["token"]
    headers = {"X-Auth-Token": token}
    got = client.get("/read", params={"q": "tomorrow at 9", "now": "2026-10-14T10:00:00+00:00"}, headers=headers).json()
    assert got["spans"][0]["value"] == "2026-10-15T09:00+00:00"
    assert client.get("/read", params={"q": "tomorrow", "now": "not a time"}, headers=headers).status_code == 200


def test_dated_surfaces_read_the_whole_input():
    meeting = reading.read("standup friday 9:30", now=NOW, context={"surface": "meeting"})
    assert meeting.intent == "meeting" and meeting.slots["due_at"] == datetime(2026, 10, 9, 9, 30)
    assert reading.read("standup", now=NOW, context={"surface": "meeting"}).question == "When is it?"
    assert reading.read("buy milk", now=NOW, context={"surface": "note"}).intent == "question"


def test_the_route_needs_the_unlock(client):
    client.post("/auth/setup", json={"password": "first-pass"})
    assert client.get("/read", params={"q": "hello"}).status_code == 401


def test_the_quick_add_sweeps_misses():
    """Brief 66's sweep, four misses on 05ecc1006, each now read."""
    from datetime import timezone

    now = datetime(2026, 10, 14, 10, 0, tzinfo=timezone.utc)
    weekly = reading.read("weekly review every friday at 4pm", now=now, context={"surface": "reminder"})
    assert weekly.slots["text"] == "Weekly review" and [s.kind for s in weekly.spans if s.rank == 0] == ["recurrence"]
    meeting = reading.read("Kickoff with Priya and Sam on 22 october at 9:30am", now=now, context={"surface": "meeting"})
    assert [s.value for s in meeting.spans if s.kind == "person"] == ["Priya", "Sam"]
    past = reading.read("on 3 october", now=now, context={"surface": "timeline"})
    assert past.slots["due_at"].date().isoformat() == "2026-10-03"
    palette = reading.read("remind me friday 9 dentist", now=now)
    assert palette.slots["text"] == "Dentist" and palette.slots["due_at"].hour == 9
    asked = reading.read("review budget friday", now=now, context={"surface": "reminder"})
    assert asked.band == "unsure" and asked.question == "What time on Friday 16 October?"


def test_my_birthday_is_the_one_the_notes_give(client, session):
    """OPEN-ledger row 459: no setting holds a birthday, so "on my birthday"
    reads the one a note gives; a month alone is no day."""
    from tessellate.ai import personal
    from tessellate.entry import manager

    assert personal.birthday([{"id": 1, "content": "My birthday is 3 December."}], NOW) == "2000-12-03"
    assert personal.birthday([{"id": 1, "content": "My birthday is in March."}], NOW) is None
    manager.create_entry(session, "# About me\n\nMy birthday is on 20 November.")
    session.commit()
    token = client.post("/auth/setup", json={"password": "first-pass"}).json()["token"]
    got = client.get("/read", params={"q": "call Sam on my birthday", "surface": "reminder", "now": "2026-10-07T10:00:00+00:00"},
                     headers={"X-Auth-Token": token}).json()
    assert got["slots"]["due_at"].startswith("2026-11-20"), got


def test_a_typed_reminder_command_reads_a_numeric_date_in_the_locales_order():
    """"remind me 3/4 at 9am" is 3 April in en-GB and 4 March in en-US. The
    reminder surface already honoured the locale; the command path
    (`commands.read`) took none, so the same words read day first for everyone."""
    now = datetime(2026, 10, 17, 10, 0)
    gb = reading.read("remind me 3/4 at 9am", now=now, context={"locale": "en-GB"})
    us = reading.read("remind me 3/4 at 9am", now=now, context={"locale": "en-US"})
    assert gb.slots["due_at"] == datetime(2027, 4, 3, 9, 0)
    assert us.slots["due_at"] == datetime(2027, 3, 4, 9, 0)
