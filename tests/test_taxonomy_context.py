"""The pack's word-sense rules run in filing (L663): `taxonomy.in_context` reads the 30 seed rules
against the 50 context fixtures, and `lexical_filing.decide` reads topics through it."""

from __future__ import annotations

import json
import re
from pathlib import Path

from tessellate.ai import lexical_filing, taxonomy
from tessellate.entry import manager

FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "taxonomy" / "context_acceptance_fixtures.json").read_text(encoding="utf-8"))

#: Fixtures whose word a seed rule names but whose sense the 30 rules cannot yet tell (no cue for it).
#: A ratchet: an id leaves this list when a rule is added, and may not join it.
GAPS = {"10", "12", "13", "15", "39", "43", "44"}


def _about_a_ruled_word(case: dict) -> bool:
    terms = {r["term"] for r in taxonomy.context_rules()["rules"]}
    return any(re.search(rf"\b{re.escape(t)}s?\b", case["text"].lower()) for t in terms)


def _read(case: dict) -> bool:
    got = set(taxonomy.in_context(case["text"], taxonomy.topic_hits(case["text"])))
    return all(t in got for t in case["expected_topic_candidates"]) and not any(t in got for t in case["forbidden_automatic_topics"])


def test_the_fixtures_about_a_ruled_word_pass_but_the_known_gaps():
    ruled = [c for c in FIXTURES if _about_a_ruled_word(c)]
    assert len(FIXTURES) == 50 and len(ruled) >= 25
    failing = {c["id"] for c in ruled if not _read(c)}
    assert failing == GAPS, f"new failures {failing - GAPS}, fixed (remove from GAPS) {GAPS - failing}"


def test_a_sense_the_sentence_argues_against_loses_the_phrase_and_one_it_argues_for_gains_it():
    hits = taxonomy.topic_hits("We walked along the river bank.")
    assert "Finance" in hits
    read = taxonomy.in_context("We walked along the river bank.", hits)
    assert "Finance" not in read and "Geography" in read
    assert hits == taxonomy.topic_hits("We walked along the river bank.")
    assert "Finance" in taxonomy.in_context("The bank is nearby.", taxonomy.topic_hits("The bank is nearby."))


def test_filing_decides_through_the_word_sense_rules(session):
    for content, category in (
        ("Paid the bank loan and checked the account balance", "Finance"),
        ("Opened a savings account at the bank, deposit on Friday", "Finance"),
        ("Hiked the river valley, the stream and the bank were flooded", "Geography"),
        ("Mapped the coast and the river delta", "Geography"),
    ):
        manager.create_entry(session, content, category_name=category)
    session.commit()
    decision = lexical_filing.decide(session, "We walked along the river bank.")
    assert decision.ranked and decision.ranked[0].name == "Geography", [(c.name, c.score) for c in decision.ranked]
