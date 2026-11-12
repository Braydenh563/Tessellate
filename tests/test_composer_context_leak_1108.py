"""A helper the digest runs outside its public entries must not leave state for the next test
(coordinator row, 2026-11-08: `-n 2` failed the age and voice tests that pass alone)."""

from __future__ import annotations

from tessellate.ai import composer_digest as digest
from tessellate.ai import composer_digest_lines
from tessellate.ai import composer_digest_sentences


def test_a_direct_gap_lead_is_not_remembered_by_the_next_test_a():
    composer_digest_sentences._VOICE.set("playful")
    composer_digest_lines._next_gap(1)
    assert len(composer_digest_sentences._GAPS.get()) == 1


def test_a_direct_gap_lead_is_not_remembered_by_the_next_test_b():
    assert composer_digest_sentences._GAPS.get() == () and composer_digest_sentences._VOICE.get() == "natural"
    composer_digest_lines._next_gap(1)
    assert len(composer_digest_sentences._GAPS.get()) == 1


def test_answer_runs_in_its_own_context():
    from tessellate.ai import composer

    assert getattr(digest.answer, "__wrapped__", None) is not None, "answer lost its _isolated decorator"
    assert composer is not None
