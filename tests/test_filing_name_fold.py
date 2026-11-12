"""A category's name is said in a note by its folded forms, as tags are (1010 leftover)."""

from __future__ import annotations

from tessellate.ai import lexical_filing


def test_a_name_is_said_by_an_ending_a_plural_or_an_abbreviation():
    said = lexical_filing._name_said  # noqa: SLF001
    assert said(("running",), ["run", "today"])
    assert said(("run",), ["running", "club"])
    assert said(("statistic",), ["stat", "homework"])
    assert said(("university",), ["uni", "friends"])
    assert said(("garden", "shed"), ["shed", "garden"])


def test_a_name_with_a_word_the_note_lacks_is_not_said():
    said = lexical_filing._name_said  # noqa: SLF001
    assert not said(("garden", "shed"), ["garden", "party"])
    assert not said((), ["anything"])


def test_a_feeling_grounds_journal_and_company_grounds_friends_and_nothing_else_does():
    from tessellate.ai import tagging

    assert tagging.grounds("journal", "Felt anxious all morning")
    assert tagging.grounds("friends", "Coffee with Priya and Jordan")
    assert not tagging.grounds("journal", "Felt the fabric of the coat")
    assert not tagging.grounds("friends", "Meeting with the bank about the loan")
    assert not tagging.grounds("travel", "Felt anxious all morning")
