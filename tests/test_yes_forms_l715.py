"""L715: a typed yes to an offer is read in many forms (owner, 2026-11-12), one reader for acts and offers."""

import pytest

from tessellate.ai import composer_talk, consent

YES = ["yes", "Yeah", "yep", "yup", "sure", "ok", "okay", "go ahead", "do it", "please do", "Yes please!", "sure, go ahead", "ya", "absolutely", "sounds good", "ok do it"]
NO = ["no", "nope", "nah", "no thanks", "don't", "not now", "never mind", "cancel"]


@pytest.mark.parametrize("text", YES)
def test_many_forms_of_yes(text):
    assert consent.says(text) == "yes"
    assert composer_talk.is_yes(text)


@pytest.mark.parametrize("text", NO)
def test_many_forms_of_no(text):
    assert consent.says(text) == "no"
    assert not composer_talk.is_yes(text)


@pytest.mark.parametrize("text", ["yes but only the first", "what is the weather", "okay so what is a tag"])
def test_not_a_bare_yes(text):
    assert not composer_talk.is_yes(text)
