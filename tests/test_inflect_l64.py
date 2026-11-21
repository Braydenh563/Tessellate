"""L-chat-64, `inflect`'s first use: `realise.count_noun` counted "two boxs", "three matchs" and said "a hour"; the
plural and the article of a plain word now come from `inflect`, and a word it should not touch (a unit, a capital) keeps
the old rule."""

from __future__ import annotations

import pytest

from tessellate.ai import realise


@pytest.mark.parametrize(
    ("n", "noun", "said"),
    [(2, "box", "two boxes"), (3, "match", "three matches"), (2, "wish", "two wishes"), (2, "analysis", "two analyses"),
     (2, "category", "two categories"), (5, "note", "five notes"), (2, "person", "two people"), (2, "day", "two days"), (3, "key", "three keys")],
)
def test_the_plural_of_a_plain_word(n, noun, said):
    assert realise.count_noun(n, noun) == said


@pytest.mark.parametrize(("noun", "said"), [("hour", "an hour"), ("note", "a note"), ("umbrella", "an umbrella"), ("day", "a day"), ("user", "a user"), ("hour", "an hour")])
def test_the_article_follows_the_sound(noun, said):
    assert realise.count_noun(1, noun, article=True) == said


def test_a_unit_or_a_name_keeps_the_old_rule():
    assert realise.count_noun(2, "km") == "two kms" and realise.count_noun(1, "km") == "one km"
    assert realise.count_noun(2, "MP") == "two MPs"
