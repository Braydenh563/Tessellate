"""The owner's two no-model reminders from the Windows log, 2026-11-22, read as meant.

Source text (the owner's chat, Ollama off): "Remind me to go to the Commonwealth Bank tomorrow" and
"can you also remind me to buy the pitbull tickets at 930?? they come out at 10pm". The first was
read right (a Confirm card for tomorrow at 9, the default). The second was set for 10pm, with
"at 930?? they come out" left in its words: "930" was not read as a clock, and the time in the
second sentence (a fact about the tickets) was taken as the reminder's.
"""

from __future__ import annotations

import datetime as dt

from tessellate.ai import acts

NOW = dt.datetime(2026, 11, 22, 13, 15)


def test_tomorrow_with_no_clock_is_tomorrow_at_the_default_hour():
    got = acts.parse("Remind me to go to the Commonwealth Bank tomorrow", NOW)
    assert got["intent"] == "reminder"
    assert got["text"] == "Go to the Commonwealth Bank"
    assert got["due_at"] == dt.datetime(2026, 11, 23, 9, 0) and got["clock_unsaid"]


def test_a_clock_without_its_colon_is_a_clock():
    got = acts.parse("remind me to buy the pitbull tickets at 930", NOW)
    assert got["text"] == "Buy the pitbull tickets"
    #: The next 9:30 after 1:15pm is this evening, as "at 9:30" already reads.
    assert got["due_at"] == dt.datetime(2026, 11, 22, 21, 30)
    assert acts.parse("remind me to call Sam at 1045 tomorrow", NOW)["due_at"] == dt.datetime(2026, 11, 23, 10, 45)


def test_a_twenty_four_hour_clock_still_reads_as_one():
    assert acts.parse("remind me to call Sam at 1930", NOW)["due_at"] == dt.datetime(2026, 11, 22, 19, 30)


def test_a_second_sentence_is_a_fact_about_the_reminder_not_its_time():
    got = acts.parse("can you also remind me to buy the pitbull tickets at 930?? they come out at 10pm", NOW)
    assert got["intent"] == "reminder"
    assert got["due_at"] == dt.datetime(2026, 11, 22, 21, 30)
    assert got["text"] == "Buy the pitbull tickets (they come out at 10pm)"


def test_a_period_before_a_new_lowercase_sentence_splits_but_a_title_does_not():
    got = acts.parse("remind me to buy tickets at 9:30. they come out at 10pm", NOW)
    assert got["due_at"] == dt.datetime(2026, 11, 22, 21, 30)
    assert got["text"] == "Buy tickets (they come out at 10pm)"
    doctor = acts.parse("remind me at 3pm to call Dr. Smith", NOW)
    assert doctor["text"] == "Call Dr. Smith" and doctor["due_at"] == dt.datetime(2026, 11, 22, 15, 0)


def test_when_only_the_second_sentence_has_the_time_it_is_still_the_reminders():
    got = acts.parse("remind me to call mum? at 6pm", NOW)
    assert got["intent"] == "reminder" and got["due_at"] == dt.datetime(2026, 11, 22, 18, 0)


def test_the_chat_route_offers_the_reminder_with_its_time_and_its_fact(client):
    """No model: the composer proposes it (a Confirm card) and says the time and the words."""
    from tests.test_composer_route_688 import _ask

    for tools in (False, True):
        events = _ask(client, "can you also remind me to buy the pitbull tickets at 930?? they come out at 10pm", use_tools=tools)
        act = events["act"][0]
        step = act["steps"][0]
        assert step["name"] == "set_reminder"
        assert step["arguments"]["text"] == "Buy the pitbull tickets (they come out at 10pm)"
        assert "9:30pm" in events["text"] and "930??" not in events["text"]
