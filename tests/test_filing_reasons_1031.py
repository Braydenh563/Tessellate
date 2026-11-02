"""The no-model filing reason (notes audit 1031, N7 and N33)."""

from tessellate.ai import lexical_filing, notebook_stats, plain_words


def _candidate(**kw):
    base = dict(name="Health", score=1.0, words=[], topics={}, notes=25, named=False)
    return lexical_filing.Candidate(**{**base, **kw})


def test_a_topic_named_by_its_own_word_is_not_said_twice():
    why = _candidate(topics={"Cooking": ["cooking"]}).why
    assert why == "It mentions “cooking”, like the 25 notes in Health."


def test_a_topic_that_adds_a_name_still_shows_it():
    why = _candidate(name="Gym", notes=3, topics={"Fitness": ["squat", "deadlift"]}).why
    assert "(Fitness)" in why


def test_filler_words_never_file_a_note():
    for word in ("note", "notes", "one", "two", "three"):
        assert word in plain_words.PLAIN
        assert word in lexical_filing._STOP
        assert word in notebook_stats._PLAIN
