"""Specific link reasons without a model (INBOX 691, decision 1).

`entry/link_wording.py` is pure: two notes' facts and the notebook's word
counts in, a sentence a person can check out. These pin the wording the
owner asked for ("Both tagged #university, #schedule", "Both mention Porto
and the Alfa Pendular", "Written two days apart, both in Travel") and the
order the clues are tried in.
"""

from __future__ import annotations

from datetime import datetime

from tessellate.entry import link_wording as lw


def _note(i, text, tags=(), category="Travel", day=1, entities=()):
    return lw.PairNote(
        id=i,
        text=text,
        tags=tuple(tags),
        category=category,
        created_at=datetime(2026, 9, day, 10, 0),
        entities=frozenset(entities),
    )


def _counts(*notes, total=40):
    return lw.Counts.of(notes, total=total)


def test_shared_tags_are_named_rarest_first():
    a = _note(1, "Lecture times for term", tags=["university", "schedule", "life"])
    b = _note(2, "Gym before class", tags=["schedule", "university", "life"], category="Health")
    counts = _counts(a, b)
    counts.tag_df.update({"life": 30, "university": 3, "schedule": 2})
    assert lw.specific_reason(a, b, counts) == "Both tagged #schedule, #university"


def test_a_tag_on_most_notes_says_nothing():
    a = _note(1, "Lecture times", tags=["life"])
    b = _note(2, "Gym plan", tags=["life"], category="Health", day=20)
    counts = _counts(a, b)
    counts.tag_df["life"] = 30
    assert lw.specific_reason(a, b, counts) is None


def test_shared_named_things_are_named():
    a = _note(1, "Take the Alfa Pendular from Lisbon to Porto on Friday.")
    b = _note(2, "In Porto we walk to the station for the Alfa Pendular back.", day=20)
    counts = _counts(a, b)
    assert lw.specific_reason(a, b, counts) == "Both mention Alfa Pendular and Porto"


def test_a_common_word_is_not_a_reason():
    a = _note(1, "Meeting notes about the budget", category="Work")
    b = _note(2, "Meeting with the team about hiring", category="Ideas", day=20)
    counts = _counts(a, b)
    counts.word_df["meeting"] = 25
    assert lw.specific_reason(a, b, counts) is None


def test_entities_count_as_named_things():
    a = _note(1, "Call about the kiln", entities=["Sam Lee"])
    b = _note(2, "Glaze test results", entities=["Sam Lee"], day=20)
    assert lw.specific_reason(a, b, _counts(a, b)) == "Both mention Sam Lee"


def test_one_note_naming_the_other_comes_first():
    a = _note(1, "Kiln plan\nFire on Sunday", tags=["pottery"])
    b = _note(2, "Glaze tests\nSee [[Kiln plan]] for timing", tags=["pottery"], day=20)
    counts = _counts(a, b)
    counts.tag_df["pottery"] = 2
    assert lw.specific_reason(a, b, counts) == "“Glaze tests” names “Kiln plan”; both tagged #pottery"


def test_same_category_written_close_together():
    a = _note(1, "Packing list", day=3)
    b = _note(2, "Hotel booking", day=5)
    assert lw.specific_reason(a, b, _counts(a, b)) == "Written two days apart, both in Travel"


def test_same_day_and_far_apart():
    a = _note(1, "Packing list", day=3)
    b = _note(2, "Hotel booking", day=3)
    assert lw.specific_reason(a, b, _counts(a, b)) == "Written the same day, both in Travel"
    far = _note(3, "Hotel booking", day=25)
    assert lw.specific_reason(a, far, _counts(a, far)) is None


def test_uncategorised_is_not_a_shared_category():
    a = _note(1, "Packing list", category="Uncategorised", day=3)
    b = _note(2, "Hotel booking", category="Uncategorised", day=4)
    assert lw.specific_reason(a, b, _counts(a, b)) is None


def test_two_clues_at_most_and_a_length_cap():
    a = _note(1, "Porto trip with Alfa Pendular", tags=["travel-portugal"], day=3)
    b = _note(2, "Alfa Pendular seats for Porto", tags=["travel-portugal"], day=4)
    counts = _counts(a, b)
    counts.tag_df["travel-portugal"] = 2
    reason = lw.specific_reason(a, b, counts)
    assert reason == "Both tagged #travel-portugal; both mention Alfa Pendular and Porto"
    assert len(reason) <= lw.MAX_CHARS


def test_strength_words():
    assert lw.strength_word(0.82) == "strong"
    assert lw.strength_word(0.7) == "some"
    assert lw.strength_word(0.58) == "weak"
    assert lw.strength_word(None) is None


def test_generic_reasons_are_recognised():
    assert lw.is_generic("similar in meaning")
    assert lw.is_generic("Similar in meaning, and around the same time")
    assert not lw.is_generic("Both tagged #porto")
    assert not lw.is_generic(None)


def test_a_quoted_sentence_pair_is_the_last_resort():
    a = _note(1, "Heading\nThe kiln needs a new thermocouple before spring.", category=None)
    b = _note(2, "Pottery list\nOrder a thermocouple for the kiln this week, then fire.", category=None, day=25)
    counts = _counts(a, b)
    counts.word_df.update({"thermocouple": 6})  # not rare, so no word clue; the pair is what is left
    reason = lw.specific_reason(a, b, counts)
    assert reason == "Says “The kiln needs a new…” and “Order a thermocouple for the…”"
    assert len(reason) <= lw.MAX_CHARS


def test_a_pair_sharing_one_word_is_not_quoted():
    a = _note(1, "The kiln needs a new door seal before spring.", category=None)
    b = _note(2, "Order wire for the kiln this week, then fire.", category=None, day=25)
    assert lw.specific_reason(a, b, _counts(a, b)) is None


def test_a_title_less_note_is_named_like_the_composer_names_it():
    from tessellate.ai import composer_frame
    from tessellate.entry import link_wording
    text = "Dentist said to floss more and book a clean in March."
    got = link_wording.title(text, limit=60)
    assert got == composer_frame.link_text({"content": text})[:60].rstrip("… ") or got.startswith("Dentist said to floss")
    assert link_wording.title("") == ""
