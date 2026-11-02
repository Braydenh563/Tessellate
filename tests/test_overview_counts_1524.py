"""INBOX 1524, the owner: "it said 4 notes but only showed or mentioned 2??".
An overview's count and what it says share one set: every note the opening
counts is told, named or counted."""

from __future__ import annotations

import re

from tests.test_composer_titles_1515 import ask, make  # noqa: F401  (fixture)

THOUGHTS = [
    ("Some ideas for features I had:\n\nOffline handling for web browsing, an icon in the status bar.\n\nSpaces for notes, like Apple Notes folders.", ["ideas"]),
    ("考え：仕事を済ませてから、練習としてゴルフを数球打った（笑）", []),
    ("test draft", []),
    ("something lol", []),
]
COUNT_WORDS = {"two": 2, "three": 3, "four": 4, "five": 5}


def test_every_counted_note_is_told_or_named(client, make):  # noqa: F811
    make(THOUGHTS, category="Thoughts & Ideas")
    answer = ask(client, "What have I saved about thoughts & ideas?")
    said = re.search(r"\b(two|three|four|five) notes\b", answer)
    assert said, answer
    assert COUNT_WORDS[said.group(1)] == 4, answer
    for words in ("test draft", "something lol", "ゴルフ"):
        assert words in answer, (words, answer)


def test_a_cjk_quote_ends_on_its_own_punctuation(client, make):  # noqa: F811
    make(THOUGHTS, category="Thoughts & Ideas")
    answer = ask(client, "What have I saved about thoughts & ideas?")
    assert "（笑）" in answer and "（笑）." not in answer, answer


def test_notes_written_the_same_day_are_not_one_sentence(client, session, make):  # noqa: F811
    """The live case of 1524: four notes written on one day were told as one
    "1 November" line that glued two notes' words under one citation, and the
    second note was then named again as untold (audit 1031 C5, every label)."""
    from datetime import datetime

    from tessellate.entry import manager

    for content, _tags in THOUGHTS:
        manager.create_entry(session, content, "Thoughts & Ideas", []).created_at = datetime(2026, 11, 1, 11, 0)
    for i in range(10):
        manager.create_entry(session, f"Study note {i}: ideas about chapter {i} and the thoughts it raised.", "Core Concepts", []).created_at = datetime(2026, 11, 1, 11, 0)
    session.commit()
    answer = ask(client, "What have I saved about thoughts & ideas?")
    paragraphs = answer.split("\n\n")
    assert not any("ゴルフ" in p and "Offline handling" in p for p in paragraphs), answer
    assert "Some ideas for features" not in paragraphs[-1], answer
    for words in ("test draft", "something lol", "ゴルフ", "Offline handling"):
        assert words in answer, (words, answer)
