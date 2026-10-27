"""The recogniser suite (CHAT_PLAN "The deterministic foundation", module 1,
decisions 46 and 56): one reader of numbers, dates, durations, units and
contacts, measured on `fixtures/composer/recognise_1010.json` (written by
`scripts/recognise_fixture.py`, expected values worked out by hand).
"""

from __future__ import annotations

import ast
import json
import time as clock
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pytest

from tessellate.ai import recognise as rec

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests/fixtures/composer/recognise_1010.json").read_text(encoding="utf-8"))
NOW = datetime.fromisoformat(FIXTURE["now"])


def _num(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def _value(span: rec.Span) -> str:
    v = span.value
    if span.kind == "range":
        first, last, grain = v
        fmt = (lambda t: t.strftime("%H:%M")) if isinstance(first, time) else (lambda d: d.isoformat())
        return f"{fmt(first)}..{fmt(last)}/{grain}"
    if span.kind == "datetime":
        return v.strftime("%Y-%m-%dT%H:%M")
    if span.kind == "time":
        return v.strftime("%H:%M")
    if span.kind == "date":
        return v.isoformat()
    if span.kind == "duration":
        return str(int(v.total_seconds()))
    if span.kind in ("money", "quantity", "temperature"):
        return f"{_num(v[0])} {v[1]}"
    if span.kind == "number":
        return _num(v)
    return str(v)


def _text(text: str) -> str:
    low = text.strip()
    for lead in ("on ", "at ", "by ", "for "):
        if low.lower().startswith(lead):
            low = low[len(lead):]
    return low


def _brief(span: rec.Span) -> str:
    return f"{span.kind}|{_text(span.text)}|{_value(span)}"


def _norm(expected: str) -> str:
    kind, text, value = expected.split("|", 2)
    return f"{kind}|{_text(text)}|{value}"


def _run(row: dict) -> tuple[list[str], list[str]]:
    spans = rec.recognise(row["text"], now=NOW, locale=row["locale"])
    return [_brief(s) for s in spans if s.rank == 0], [_brief(s) for s in spans if s.rank > 0]


def test_the_fixture_reads_at_one():
    rows = FIXTURE["rows"]
    assert len(rows) >= 200
    wrong = []
    for row in rows:
        got, alt = _run(row)
        want = [_norm(e) for e in row["expect"]]
        want_alt = [_norm(e) for e in row["alt"]]
        if got != want or any(a not in alt for a in want_alt):
            wrong.append((row["text"], row["locale"], got, alt, want, want_alt))
    assert not wrong, f"{len(wrong)} of {len(rows)} wrong:\n" + "\n".join(map(repr, wrong[:25]))


def test_spans_point_at_their_text():
    for row in FIXTURE["rows"]:
        for span in rec.recognise(row["text"], now=NOW, locale=row["locale"]):
            assert row["text"][span.start:span.end] == span.text
            assert span.read_as


def test_each_phrase_reads_inside_its_budget():
    """5 ms a phrase, best of five (CHAT_PLAN section 3: the chips draw as you type)."""
    rec.recognise("warm up", now=NOW, locale="en-GB")
    best = None
    for _ in range(5):
        start = clock.perf_counter()
        for row in FIXTURE["rows"]:
            rec.recognise(row["text"], now=NOW, locale=row["locale"])
        took = (clock.perf_counter() - start) / len(FIXTURE["rows"])
        best = took if best is None else min(best, took)
    assert best < 0.005, f"{best * 1000:.2f} ms a phrase"


def test_no_network_and_no_app_imports():
    """Decision 56: nothing in the deterministic layer reaches past the computer."""
    tree = ast.parse((ROOT / "src/tessellate/ai/recognise.py").read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    # contextlib and contextvars (2026-10-27): the call's locale for season words
    # rides a ContextVar; both are stdlib with no I/O, so the intent stands.
    assert names <= {"__future__", "re", "dataclasses", "datetime", "typing", "contextlib", "contextvars"}, names


def test_the_unit_table_has_150_units():
    assert len({said for _dim, _size, said in rec.UNITS.values()}) >= 150


def test_the_json_form_is_plain():
    spans = rec.recognise("dentist 21st 9am, £4.50, every tuesday, next week", now=NOW, locale="en-GB")
    body = json.dumps([s.json() for s in spans])
    assert '"kind": "datetime"' in body and '"currency": "GBP"' in body and "FREQ=WEEKLY" in body


def test_tense_is_read_from_the_sentence():
    past = rec.recognise("what did I do on friday", now=NOW, locale="en-GB")[0]
    future = rec.recognise("see Sam on friday", now=NOW, locale="en-GB")
    assert past.value == date(2026, 10, 2)
    assert [s.value for s in future if s.kind == "date"] == [date(2026, 10, 9)]
    assert rec.recognise("in 20 minutes", now=NOW, locale="en-GB")[0].value == NOW + timedelta(minutes=20)


# A monthly repeat set for a day some months lack keeps that day.


def test_a_monthly_repeat_from_the_31st_keeps_its_day(client):
    """Row 414: "monthly" from the 31st landed on 28 February and stayed on
    the 28th. The day it was set for is kept (BYMONTHDAY) from the first
    roll on, so March is the 31st again; a day the store collapsed to
    "monthly" keeps its rule when the month may not hold it."""
    assert rec.stored_repeat("FREQ=MONTHLY;BYMONTHDAY=31") == "FREQ=MONTHLY;BYMONTHDAY=31"
    assert rec.stored_repeat("FREQ=MONTHLY;BYMONTHDAY=5") == "monthly"
    made = client.post("/reminders", json={"text": "Pay rent", "due_at": "2030-01-31T09:00:00Z", "recurring": "monthly"}).json()
    february = client.post(f"/reminders/{made['id']}/complete").json()
    assert february["due_at"].startswith("2030-02-28T09:00"), february
    march = client.post(f"/reminders/{made['id']}/complete").json()
    assert march["due_at"].startswith("2030-03-31T09:00"), march
    assert march["repeat_words"] == "monthly"
    plain = client.post("/reminders", json={"text": "Water", "due_at": "2030-01-10T09:00:00Z", "recurring": "monthly"}).json()
    rolled = client.post(f"/reminders/{plain['id']}/complete").json()
    assert rolled["recurring"] == "monthly"


# Recurrence beyond four, and early alerts (TIMELINE_PLAN 11 row 8): every
# weekday, every 2 weeks, the last Friday of the month, every other Monday, and
# "1 day before" / "an hour before", read by `ai/recognise.py` (the one reader,
# `tests/test_one_reader.py`), kept by the reminder store as the rule itself, and
# rolled on by `next_occurrence` when one is done. The 20 phrases in
# `fixtures/composer/recurrence_1010.json` score 1.0.

RECURRENCE_FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "composer" / "recurrence_1010.json").read_text(encoding="utf-8"))
RECURRENCE_NOW = datetime.fromisoformat(RECURRENCE_FIXTURE["now"])


def _got(text: str) -> dict:
    parsed = rec.parse_reminder_text(text, RECURRENCE_NOW)
    assert parsed is not None, text
    return {
        "title": parsed["text"],
        "due_at": parsed["due_at"].isoformat(timespec="minutes"),
        "recurring": parsed.get("recurring", "none"),
        "alert_minutes": parsed.get("alert_minutes"),
    }


def test_the_twenty_phrases_score_one():
    phrases = RECURRENCE_FIXTURE["phrases"]
    assert len(phrases) == 20
    wrong = [(p["text"], _got(p["text"]), p["expect"]) for p in phrases if _got(p["text"]) != p["expect"]]
    assert not wrong, wrong


def test_the_set_covers_what_the_row_names():
    kept = {p["expect"]["recurring"] for p in RECURRENCE_FIXTURE["phrases"]}
    assert {"FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR", "FREQ=WEEKLY;INTERVAL=2", "FREQ=MONTHLY;BYDAY=-1FR",
            "FREQ=WEEKLY;INTERVAL=2;BYDAY=MO"} <= kept
    assert {1440, 60} <= {p["expect"]["alert_minutes"] for p in RECURRENCE_FIXTURE["phrases"]}


def test_last_friday_alone_is_a_day_gone_not_a_repeat():
    spans = rec.recognise("what did I do last friday", now=RECURRENCE_NOW)
    assert not [s for s in spans if s.kind == "recurrence"]


@pytest.mark.parametrize(
    ("rule", "after", "expected"),
    [
        ("FREQ=MONTHLY;BYDAY=-1FR", "2026-10-30T12:30", "2026-11-27T12:30"),
        ("FREQ=MONTHLY;BYDAY=2WE", "2026-10-14T19:00", "2026-11-11T19:00"),
        ("FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR", "2026-10-16T09:00", "2026-10-19T09:00"),
        ("FREQ=WEEKLY;INTERVAL=2;BYDAY=MO", "2026-10-19T07:00", "2026-11-02T07:00"),
        ("FREQ=WEEKLY;INTERVAL=2", "2026-10-15T09:00", "2026-10-29T09:00"),
        ("FREQ=MONTHLY;INTERVAL=3", "2026-10-15T09:00", "2027-01-15T09:00"),
        ("daily", "2026-10-15T08:00", "2026-10-16T08:00"),
        ("weekly", "2026-10-18T18:00", "2026-10-25T18:00"),
        ("monthly", "2026-01-31T09:00", "2026-02-28T09:00"),
    ],
)
def test_next_occurrence(rule, after, expected):
    assert rec.next_occurrence(rule, datetime.fromisoformat(after)).isoformat(timespec="minutes") == expected


def test_alert_words_say_the_alert_back():
    assert [rec.alert_words(m) for m in (30, 60, 120, 1440, 10080)] == [
        "30 minutes before", "1 hour before", "2 hours before", "1 day before", "1 week before"]


def test_the_store_keeps_a_rule_and_an_alert_and_rolls_a_rule_on(client):
    """`/reminders` keeps the rule as itself and the alert in minutes; the ICS
    says both; `/reminders/{id}/complete` rolls a rule on, in the person's
    own days, and marks a one-off done."""
    made = client.post("/reminders", json={"text": "Team lunch", "due_at": "2030-01-25T12:30:00Z",
                                           "recurring": "FREQ=MONTHLY;BYDAY=-1FR", "alert_minutes": 1440})
    assert made.status_code == 201, made.text
    body = made.json()
    assert (body["recurring"], body["alert_minutes"]) == ("FREQ=MONTHLY;BYDAY=-1FR", 1440)
    assert (body["repeat_words"], body["alert_words"]) == ("every last Friday of the month", "1 day before")
    ics = client.get(f"/reminders/{body['id']}/export.ics").text
    assert "RRULE:FREQ=MONTHLY;BYDAY=-1FR" in ics and "TRIGGER:-PT1440M" in ics
    rolled = client.post(f"/reminders/{body['id']}/complete").json()
    assert rolled["done"] is False and rolled["due_at"].startswith("2030-02-22T12:30")
    assert rolled["was_due_at"].startswith("2030-01-25T12:30")
    # 9am Monday in Auckland (UTC+13) is 20:00 Sunday in UTC: the next
    # weekday is Tuesday 9am there, not Monday's evening in UTC.
    weekday = client.post("/reminders", json={"text": "Standup", "due_at": "2030-01-27T20:00:00Z",
                                              "recurring": "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"}).json()
    nz = client.post(f"/reminders/{weekday['id']}/complete?tz_offset_minutes=780").json()
    assert nz["due_at"].startswith("2030-01-28T20:00")
    once = client.post("/reminders", json={"text": "Once", "due_at": "2030-01-25T12:30:00Z"}).json()
    done = client.post(f"/reminders/{once['id']}/complete").json()
    assert done["done"] is True
    cleared = client.put(f"/reminders/{body['id']}", json={"alert_minutes": 0}).json()
    assert cleared["alert_minutes"] is None
    refused = client.post("/reminders", json={"text": "x", "due_at": "2030-01-25T12:30:00Z", "recurring": "sometimes"})
    assert refused.status_code == 422


def test_quick_add_by_words_keeps_the_rule_and_the_alert(client):
    made = client.post("/reminders/parse", json={"text": "gym every other monday at 7am, an hour before", "tz_offset_minutes": 0})
    assert made.status_code in (200, 201), made.text
    body = made.json()
    assert body["recurring"] == "FREQ=WEEKLY;INTERVAL=2;BYDAY=MO" and body["alert_minutes"] == 60


def test_a_monthly_repeat_from_the_31st_goes_back_to_31_when_the_month_allows(client):
    """Brief 101b: the clamp is per month, not forever. Ticking a reminder
    off on 31 January lands it on 28 February, then on 31 March, 30 April."""
    made = client.post("/reminders", json={"text": "Pay rent", "due_at": "2030-01-31T09:00:00Z", "recurring": "monthly"}).json()
    seen = []
    for _ in range(4):
        seen.append(client.post(f"/reminders/{made['id']}/complete").json()["due_at"][:10])
    assert seen == ["2030-02-28", "2030-03-31", "2030-04-30", "2030-05-31"]


def test_editing_the_due_day_moves_the_anchor(client):
    made = client.post("/reminders", json={"text": "Pay rent", "due_at": "2030-01-31T09:00:00Z", "recurring": "monthly"}).json()
    first = client.post(f"/reminders/{made['id']}/complete").json()
    assert first["due_at"][:10] == "2030-02-28"
    # The person moves it to the 15th: that is the day it keeps from now on.
    client.put(f"/reminders/{made['id']}", json={"due_at": "2030-03-15T09:00:00Z"})
    after = client.post(f"/reminders/{made['id']}/complete").json()
    assert after["due_at"][:10] == "2030-04-15"


def test_an_alert_can_be_changed_and_cleared_by_the_edit(client):
    """The reminder edit form sends `alert_minutes` with every save: a number
    sets it, 0 clears it, and leaving it out leaves it as it is."""
    made = client.post("/reminders", json={"text": "Dentist", "due_at": "2030-01-25T12:30:00Z", "alert_minutes": 1440}).json()
    changed = client.put(f"/reminders/{made['id']}", json={"alert_minutes": 60}).json()
    assert (changed["alert_minutes"], changed["alert_words"]) == (60, "1 hour before")
    kept = client.put(f"/reminders/{made['id']}", json={"text": "Dentist at 12"}).json()
    assert kept["alert_minutes"] == 60
    cleared = client.put(f"/reminders/{made['id']}", json={"alert_minutes": 0}).json()
    assert cleared["alert_minutes"] is None and not cleared.get("alert_words")
    added = client.put(f"/reminders/{made['id']}", json={"alert_minutes": 10080}).json()
    assert added["alert_minutes"] == 10080
