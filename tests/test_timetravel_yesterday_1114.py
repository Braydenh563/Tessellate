"""L-chat-70/A11 follow-up: "yesterday" alone is the as-of day; "Christmas" alone stays the topic."""

from __future__ import annotations

from datetime import datetime

from tessellate.ai import timetravel

#: A fixed clock: Saturday 31 October 2026, 11:30.
NOW = datetime(2026, 10, 31, 11, 30)


def test_yesterday_alone_is_the_as_of_day():
    assert timetravel.as_of_in("what did my gym plan say yesterday", NOW).isoformat() == "2026-10-30"
    assert timetravel.as_of_in("what did the budget note say yesterday", NOW).isoformat() == "2026-10-30"


def test_one_time_word_that_is_a_topic_is_still_not_a_date():
    assert timetravel.as_of_in("what do my notes say about Christmas", NOW) is None
    assert timetravel.as_of_in("what did my plan say about Christmas", NOW) is None
    assert timetravel.as_of_in("what did my plan say last month", NOW).isoformat() == "2026-09-30"
