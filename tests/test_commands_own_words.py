"""A command keeps the person's own words (audit 1028 E9).

"uni" is slang for "university" to the speller, but in "delete notes about
uni" it is the person's category Uni; and "all my uni notes" names the uni
notes, not notes about "all my uni".
"""

from datetime import datetime

from tessellate.ai import commands, question_noise

NOW = datetime(2026, 10, 28, 10)


def test_slang_alone_does_not_rewrite_the_target():
    assert commands.read_typed("delete notes about uni", NOW)["about"] == "uni"


def test_a_quantifier_is_not_part_of_the_target():
    found = commands.read_typed("move all my uni notes to Archive", NOW)
    assert found["about"] == "uni" and found["category"] == "Archive"


def test_a_misspelt_verb_is_still_put_right():
    assert commands.read_typed("delte my old wifi note", NOW) == {"intent": "delete", "about": "old wifi", "single": True}


def test_a_known_word_is_never_spelled_out():
    assert question_noise.repair("what is due for uni", known=frozenset({"uni"})) == "what is due for uni"
    assert "university" in question_noise.repair("what is due for uni")
