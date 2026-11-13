"""Ask's dated story tells each record as a clause (L-chat-39).

The L-chat-37 check in the app (2026-11-13), with meaning search on, told the
five uni notes as a story: "In November, you wrote “Core Concepts”." (the
title, none of what the note says) and "Soon after, your uni days the week of
9 November are Tuesday and Thursday" (a present-tense line after a time
opener).
"""

from __future__ import annotations

from tessellate.ai import composer_story


def test_a_note_that_says_this_note_is_told_by_its_title():
    clause = composer_story._clause(
        "This note pulls together the main ideas from your university study so far, from your Core Concepts note",
        "Core Concepts",
        "This note pulls together the main ideas from my university study so far",
    )
    assert clause == "your “Core Concepts” note pulls together the main ideas from your university study so far", clause


def test_a_present_tense_line_is_what_you_noted():
    clause = composer_story._clause(
        "Your uni days the week of 9 November are Tuesday and Thursday, so you can work the other days", "",
        "My uni days this week are tuesday and thursday, so I can work the other days",
    )
    assert clause == "you noted that your uni days the week of 9 November are Tuesday and Thursday, so you can work the other days", clause


def test_a_past_line_keeps_its_own_words():
    clause = composer_story._clause("You missed the bus to uni this morning", "", "x")
    assert clause == "you missed the bus to uni this morning", clause


def test_a_line_about_the_note_is_not_what_you_noted():
    clause = composer_story._clause("Your Ice Breakers note lists three questions", "", "Ice breakers: three questions")
    assert clause == "your Ice Breakers note lists three questions", clause
