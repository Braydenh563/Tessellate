"""K30: a topic answer counts the records the search matched, and says how
many of them are filed under the topic (the owner: "a lot more than just the
two notes it showed relate to academics and tech")."""

from __future__ import annotations

from datetime import date

from tessellate.ai import composer
from tests._composer_eval import trace_failures

TODAY = date(2026, 10, 10)
MEANING = [
    "Revision plan for the calculus midterm and the physics lab report",
    "Read the paper on transformers for the machine learning seminar",
    "Laptop upgrade: 32GB of RAM so compiling stops being slow",
    "Notes from the databases lecture on indexing and joins",
    "Thesis outline: chapter two covers the literature on networks",
]


def _notes(matched: bool) -> list[dict]:
    notes = []
    for i, text in enumerate(["Academics and tech: course list for next term", "Tech and academics reading list"], start=1):
        notes.append({"id": i, "created_at": f"2026-09-0{i}T10:00:00", "tags": [], "category": "Academics & Tech", "content": text})
    for i, text in enumerate(MEANING, start=3):
        note = {"id": i, "created_at": f"2026-09-1{i - 3}T10:00:00", "tags": [], "category": "Study", "content": text}
        if matched:
            note["match_info"] = {"why": "similar in meaning"}
        notes.append(note)
    return notes


def test_a_topic_counts_the_matched_records_and_says_how_many_are_filed():
    question = "What have I saved about academics & tech?"
    result = composer.compose(question, _notes(True), today=TODAY)
    first = result["text"].split("\n", 1)[0]
    assert "seven" in first and "two" in first and "filed under it" in first
    assert not trace_failures(result, question, _notes(True), TODAY)


def test_without_a_search_match_the_count_stays_the_filed_notes():
    result = composer.compose("What have I saved about academics & tech?", _notes(False), today=TODAY)
    assert "two" in result["text"].split("\n", 1)[0]
    assert "filed under it" not in result["text"]
