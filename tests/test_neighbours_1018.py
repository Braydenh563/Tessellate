"""Retrieval that reads a topic whole (CHAT_PLAN decision 70, INBOX 812).

Measured on the running app with no model and keyword-only search: the gold
answers for "how's the gym going?", "what's the plan for Lisbon?" and
"Logitech or Razer?" scored 45, 67 and 36 because the search is every-word-or-
nothing: "gym going" found the one note that also says "going", and the
second gym note, the one with the new weights, was never read. In process,
with every note handed over, the same answers scored 96, 95 and 94. A note
that shares a rare tag with a note the search found is part of the same
topic, and an overview, a comparison and a "what's left" read it whole.
"""

from __future__ import annotations

import json

import pytest

from tessellate.ai import neighbours
from tessellate.entry import manager


def test_a_rare_shared_tag_makes_a_neighbour_and_a_crowded_one_does_not():
    rows = [
        (1, ["gym"]),
        (2, ["gym"]),
        (3, ["golf"]),
        *[(10 + i, ["ideas"]) for i in range(12)],
        (30, ["ideas", "gym"]),
    ]
    assert neighbours.pick([1], rows) == [2, 30]
    #: A tag carried by a dozen notes says little about any one of them.
    assert neighbours.pick([10], rows) == []
    assert neighbours.pick([30], rows) == [1, 2]
    assert neighbours.pick([3], rows) == []


def test_neighbours_are_ranked_by_the_tags_they_share_and_capped():
    rows = [(1, ["a", "b"]), (2, ["a"]), (3, ["a", "b"]), (4, ["b"]), (5, ["a"]), (6, ["a"]), (7, ["a"])]
    assert neighbours.pick([1], rows, limit=3) == [3, 2, 4]


def test_a_note_already_found_is_not_added_twice_and_untagged_notes_have_none():
    rows = [(1, ["x"]), (2, ["x"]), (3, [])]
    assert neighbours.pick([1, 2], rows) == []
    assert neighbours.pick([3], rows) == []


def test_only_the_kinds_that_read_a_topic_whole_widen():
    for question in ("how's the gym going?", "what's the plan for Lisbon?", "Logitech or Razer?", "what do I have on uni?"):
        assert neighbours.reads_whole(question), question
    for question in ("when are my uni days?", "who is Sam?", "how much did I spend on groceries?", "do I like golf?"):
        assert not neighbours.reads_whole(question), question


def _ask(client, question: str) -> str:
    text = ""
    with client.stream("POST", "/chat/stream", json={"question": question, "notes_only": True, "use_tools": False}) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                if event["type"] == "answer":
                    text += event.get("delta", "")
    return text


@pytest.fixture()
def notebook(session):
    for content, category, tags in (
        ("Gym: squats 80 kg for 5, bench 60 kg for 5. Going Monday, Wednesday and Friday.", "Fitness", ["gym"]),
        ("Gym: squats up to 90 kg for 5. Knee felt fine.", "Fitness", ["gym"]),
        ("Looking at a new gaming mouse. The Logitech G Pro X Superlight is about $230 and the Razer Viper V3 is $200.", "Tech", ["gaming", "shopping"]),
        ("Mouse update: tried the Viper at JB Hi-Fi and it felt too small for my hand. Leaning towards the Logitech.", "Tech", ["gaming"]),
        ("Groceries: oat milk, eggs, spinach, rice, chicken thighs.", "Shopping", ["groceries"]),
    ):
        manager.create_entry(session, content, category, tags)
    session.commit()


def test_the_gym_answer_reads_both_gym_notes(client, notebook):
    text = _ask(client, "how's the gym going?")
    assert "90 kg" in text and "80 kg" in text, text
    assert "only note" not in text, text


def test_the_comparison_reads_the_note_that_decided_it(client, notebook):
    text = _ask(client, "Logitech or Razer?")
    assert "too small" in text, text


def test_what_is_left_to_buy_reads_the_shopping_list_the_word_buy_never_names(client, notebook, session):
    manager.create_entry(session, "Lisbon trip planned for May. Hotel in Alfama is booked for 5 nights, flights still to book.", "Travel", ["lisbon"])
    session.commit()
    text = _ask(client, "what do I need to buy?")
    assert "oat milk" in text and "chicken thighs" in text, text
    assert "nothing in your notes" not in text.lower(), text


def test_a_fact_question_reads_only_the_notes_the_search_found(client, notebook):
    """Widening is for a topic asked about as a whole, not for a fact."""
    ids = []
    with client.stream("POST", "/chat/stream", json={"question": "what is the Viper?", "notes_only": True, "use_tools": False}) as response:
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                if event["type"] == "meta":
                    ids = [r["id"] for r in event["raw_results"]]
    assert 1 <= len(ids) <= 2, ids


#: The questions of the gold set whose answers do not turn on today's date,
#: through the route with no model and keyword-only search. Measured
#: 2026-10-18 against `scratchpad/ui-sweeps/gold.js` on the running app:
#: 12, 16, 18, 19 were 67, 36, 29, 45 before the neighbours and the progress
#: reading, then 93, 94, 98, 96. The floor sits under them.
ROUTE_GOLD = {1: 90, 2: 80, 9: 80, 10: 90, 11: 75, 12: 85, 13: 80, 15: 90, 16: 85, 18: 90, 19: 85, 20: 75}
ROUTE_FLOOR_MEAN = 85


def test_the_gold_answers_through_the_route_keep_their_floors(client, session, monkeypatch):
    from datetime import datetime

    from tessellate.api import routes_chat
    from tests import _gold

    fixture = _gold.load()
    #: The fixture's own day, never the real clock: the route words dates and
    #: due windows from today, so a real clock moved these scores with the date.
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: datetime.fromisoformat(f"{fixture['today']}T10:00:00"))
    for note in fixture["notes"]:
        entry = manager.create_entry(session, note["content"], note["category"], note["tags"])
        entry.created_at = datetime.fromisoformat(f"{note['date']}T10:00:00")
    session.commit()
    items = {a["n"]: a for a in fixture["answers"]}
    totals = {}
    for n, floor in ROUTE_GOLD.items():
        item = items[n]
        totals[n] = _gold.score(_ask(client, item["question"]), item)["total"]
        assert totals[n] >= floor, (n, totals[n], floor)
    assert sum(totals.values()) / len(totals) >= ROUTE_FLOOR_MEAN, totals
