"""The note editor's offers (CHAT_PLAN section 2, the note editor row):
dates become reminder offers, sums are checked, `[[links]]` are suggested
from the names other notes open with, and the filing suggestion comes with
its reason; never on quoted words; at most five. `ai/offers.py`,
`POST /read/offers`, `frontend/js/quickadd.js`."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from tessellate.ai import offers
from tessellate.core.database import Category, Entry

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 10, 14, 0, tzinfo=timezone.utc)


def _kinds(found):
    return [o["kind"] for o in found]


def test_a_day_in_the_text_is_a_reminder_offer(session):
    found = offers.offers(session, "Call the plumber on Friday at 3pm about the boiler.", now=NOW)
    assert _kinds(found) == ["reminder"]
    offer = found[0]
    assert offer["value"]["due_at"] == "2026-10-16T15:00+00:00"
    assert offer["value"]["text"] == "Call the plumber about the boiler"
    assert offer["label"].startswith("Remind me Friday 16 October 2026")


def test_a_day_with_no_time_says_so_and_a_past_day_is_no_offer(session):
    found = offers.offers(session, "Dentist next tuesday. Met Ana yesterday.", now=NOW)
    assert _kinds(found) == ["reminder"]
    assert found[0]["value"]["due_at"] == "2026-10-13T09:00+00:00"
    assert "no time was said" in found[0]["reason"]


def test_quoted_words_are_never_offered_on(session):
    text = 'He said "see you on friday at 9", and `12 + 1 = 14` is code.\n> remind me monday\n'
    assert offers.offers(session, text, now=NOW) == []


def test_a_wrong_sum_is_caught_and_a_right_one_left(session):
    found = offers.offers(session, "Shopping: 12 + 7 = 21 and 3 * 4 = 12 and 10 / 4 =", now=NOW)
    sums = [o for o in found if o["kind"] == "sum"]
    assert [o["reason"] for o in sums] == ["12 + 7 is 19, not 21", "10 / 4 is 2.5"]
    assert sums[0]["said"] == "21" and sums[0]["value"]["replace"] == "19"


def test_a_total_under_a_column_of_amounts_is_checked(session):
    """OPEN 1100: a "Total:" line under amounts, not only a sum written with =."""
    text = "Shopping\n\nMilk £3.50\nBread £1.20\nEggs £2\n**Total:** £7.20\n"
    sums = [o for o in offers.offers(session, text, now=NOW) if o["kind"] == "sum"]
    assert [o["reason"] for o in sums] == ["the 3 amounts above add up to 6.70, not 7.20"]
    assert text[sums[0]["start"] : sums[0]["end"]] == "7.20" and sums[0]["value"]["replace"] == "6.70"
    right = "Rent 1200\nFood 300\nTotal: 1500\n"
    assert not [o for o in offers.offers(session, right, now=NOW) if o["kind"] == "sum"]
    one = "Rent 1200\nTotal: 1400\n"
    assert not [o for o in offers.offers(session, one, now=NOW) if o["kind"] == "sum"]
    fenced = "```\na 1\nb 2\nTotal: 9\n```\n"
    assert not [o for o in offers.offers(session, fenced, now=NOW) if o["kind"] == "sum"]


def test_a_name_another_note_opens_with_is_a_link_offer(session):
    session.add(Entry(content="Harbor House\nThe boat shed by the water."))
    session.commit()
    found = offers.offers(session, "Lunch at Harbor House with the crew", now=NOW)
    links = [o for o in found if o["kind"] == "link"]
    assert links and links[0]["value"]["replace"] == "[[Harbor House]]"
    already = offers.offers(session, "Lunch at [[Harbor House]] with the crew", now=NOW)
    assert not [o for o in already if o["kind"] == "link"]


def test_the_filing_offer_carries_its_reason(session):
    cat = Category(name="Fitness")
    session.add(cat)
    session.flush()
    for text in ("Squat 5x5 at 100kg then deadlift", "Deadlift and squat day, felt strong", "Squat form notes and deadlift cues"):
        session.add(Entry(content=text, category_id=cat.id))
    session.commit()
    found = offers.offers(session, "Squat and deadlift session this morning, new best", now=NOW)
    filing = [o for o in found if o["kind"] == "filing"]
    assert filing and filing[0]["value"]["category"] == "Fitness" and filing[0]["reason"]
    assert not [o for o in offers.offers(session, "Squat and deadlift session this morning, new best", now=NOW,
                                         category="Fitness") if o["kind"] == "filing"]


def test_never_more_than_five(session):
    text = "Mon 9am a. Tue 9am b. Wed 9am c. 1+1=3. 2+2=5. 3+3=7."
    assert len(offers.offers(session, text, now=NOW)) <= offers.LIMIT


def test_the_route_serves_the_offers(client):
    token = client.post("/auth/setup", json={"password": "first-pass"}).json()["token"]
    headers = {"X-Auth-Token": token}
    got = client.post("/read/offers", json={"content": "2 + 2 = 5", "now": "2026-10-10T14:00:00+00:00"}, headers=headers)
    assert got.status_code == 200
    assert got.json()["offers"][0]["kind"] == "sum"
    locked = client.post("/read/offers", json={"content": "x"})
    assert locked.status_code == 401


def test_the_editor_asks_through_the_route_and_reads_nothing_itself():
    js = (ROOT / "frontend/js/quickadd.js").read_text(encoding="utf-8")
    assert '"/read/offers"' in js
    assert "entry-content" in js


def test_a_sum_alone_on_its_line_is_offered_its_answer_without_an_equals_sign(session):
    """L577: "12 + 30" written alone, no "=". A range, a date or a sum in prose is left."""
    for text, label, after in (("12 + 30\n", "12 + 30 = 42", "12 + 30 = 42\n"), ("- 4.5 * 3 ?\n", "4.5 * 3 = 13.5", "- 4.5 * 3 = 13.5 ?\n"), ("Shopping\n10 / 4", "10 / 4 = 2.5", "Shopping\n10 / 4 = 2.5")):
        sums = [o for o in offers.offers(session, text, now=NOW) if o["kind"] == "sum"]
        assert [o["label"] for o in sums] == [label], (text, sums)
        assert text[: sums[0]["start"]] + sums[0]["value"]["replace"] + text[sums[0]["end"] :] == after
    for text in ("It takes 3-4 days", "Booked for 2026-11-12", "I paid 12 + 30 pounds for it", "12 +30", "5 - 3 days"):
        assert not [o for o in offers.offers(session, text, now=NOW) if o["kind"] == "sum"], text


def test_a_total_line_with_no_amount_is_offered_the_column_sum(session):
    text = "Milk £3.50\nBread £1.20\nEggs £2\nTotal:"
    sums = [o for o in offers.offers(session, text, now=NOW) if o["kind"] == "sum"]
    assert [o["reason"] for o in sums] == ["the 3 amounts above add up to 6.70"], sums
    assert text[: sums[0]["start"]] + sums[0]["value"]["replace"] == text + " 6.70"
    one = "Rent 1200\nTotal:"
    assert not [o for o in offers.offers(session, one, now=NOW) if o["kind"] == "sum"]


def test_an_equals_with_no_answer_gets_it_on_the_same_line_not_after_the_blank_lines(session):
    """L574 (measured on the Edit form): "12 + 30 =" then a blank line took the
    answer on the line below, because the span ran on through the whitespace."""
    for text, after in (
        ("12 + 30 =\n\nNext.", "12 + 30 = 42\n\nNext."),
        ("12 + 30 =", "12 + 30 = 42"),
        ("12 + 30 = \nNext.", "12 + 30 = 42 \nNext."),
    ):
        sums = [o for o in offers.offers(session, text, now=NOW) if o["kind"] == "sum"]
        assert len(sums) == 1, (text, sums)
        assert text[: sums[0]["start"]] + sums[0]["value"]["replace"] + text[sums[0]["end"] :] == after, text
