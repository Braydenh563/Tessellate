"""The composer's voice and understanding (INBOX 741, the owner: "better to
understand ... more social, more engaging, better at responding and answering
questions correctly").

Each test pins one reading or one wording rule, and every answer here passes
INBOX 688's traceability check: facts stay the notes' own words.
"""

from __future__ import annotations

import pytest

from tessellate.ai import composer
from tessellate.ai import composer_ask
from tessellate.ai import composer_phrases
from tests.test_composer_688 import NOTES, TODAY, _note, assert_traceable


def ask(question: str, notes=NOTES, **kwargs) -> dict:
    result = composer.compose(question, notes, today=TODAY, **kwargs)
    assert_traceable(result, question, notes)
    return result


# --- casual and indirect questions ------------------------------------------


@pytest.mark.parametrize(
    ("question", "shape", "terms"),
    [
        ("can you remind me when the dentist is", "when", ["dentist"]),
        ("hey, quick question: where did I put the spare key?", "where", ["spare", "key"]),
        ("any idea how many beta testers we have", "count", ["beta", "testers"]),
        ("hows the sync rewrite going", "status", ["sync", "rewrite"]),
        ("any news on the sync rewrite?", "status", ["sync", "rewrite"]),
        ("any idea if the hotel deposit is paid", "yesno", ["hotel", "deposit", "paid"]),
        ("i forgot what hotel i booked", "what", ["hotel", "booked"]),
        ("how come the list is slow", "explain", ["list", "slow"]),
        ("what time is the dentist", "when", ["dentist"]),
        ("do you know who asked for an api", "who", ["asked", "api"]),
        ("is there anything about the boiler", "what", ["boiler"]),
        ("how many notes mention sourdough", "what", ["sourdough"]),
        ("whats the deal with the pricing page", "what", ["pricing", "page"]),
        ("Could you please tell me when the boiler is due, thanks", "when", ["boiler", "due"]),
    ],
)
def test_a_casual_wrapper_comes_off_before_the_question_is_read(question, shape, terms):
    assert composer.classify(question) == shape
    assert composer.subject_terms(question) == terms


def test_rephrase_never_adds_a_word_the_person_did_not_write():
    assert composer.rephrase("Hey, can you remind me when the dentist is please?") == "when the dentist is?"
    assert composer.rephrase("What is the launch date?") == "What is the launch date?"


def test_a_casual_question_gets_the_same_answer_as_the_plain_one():
    plain = ask("When is the dentist check-up?")
    casual = ask("hey can you remind me when the dentist check-up is?")
    assert plain["grounding"][0]["sentence"] == casual["grounding"][0]["sentence"]


# --- synonyms ---------------------------------------------------------------


def test_a_synonym_finds_the_note_and_is_not_reported_missing():
    notes = [
        _note(1, "# Trip budget\n\nRoughly 1,900 for two, flights included.", 5),
        _note(2, "# Packing\n\nA light jacket for the evenings.", 3),
    ]
    result = ask("How much will the trip cost?", notes)
    assert "1,900" in result["text"].split("\n", 1)[0]
    assert "mention “cost”" not in result["text"]


def test_synonym_groups_are_symmetric_and_never_hold_a_word_twice():
    seen: set[str] = set()
    for group in composer_ask.SYNONYM_GROUPS:
        assert len(group) == len(set(group))
        assert not (set(group) & seen), group
        seen |= set(group)
    synonyms = composer_ask._build_synonyms()
    for stem, others in synonyms.items():
        for other in others:
            assert stem in synonyms[other]


# --- new question kinds -----------------------------------------------------


def test_a_where_question_leads_with_the_sentence_that_names_a_place():
    notes = [
        _note(1, "# Keys\n\nThe spare key is in the kitchen drawer under the tea towels. Keys are a pain.", 5),
        _note(2, "# House\n\nThe key thing this month is the boiler.", 3),
    ]
    first = ask("Where is the spare key?", notes)["text"].split("\n", 1)[0]
    assert "kitchen drawer" in first


def test_a_yes_no_answered_in_the_notes_words_never_says_yes_or_no():
    notes = [_note(1, "# Lisbon\n\nThe hotel deposit is paid, the rest is due on arrival.", 5)]
    text = ask("Is the hotel deposit paid?", notes)["text"]
    assert text.startswith(
        tuple(f"{w}, the hotel deposit is paid" for w in composer_phrases.phrase_options("going_by")) + composer_phrases.phrase_options("notes_have")
    )
    assert not text.lower().startswith(("yes", "no"))


def test_how_many_notes_is_answered_with_the_measured_count():
    text = ask("how many notes mention the beta?")["text"]
    assert text.startswith("At least ")


# --- two questions in one, and one that could mean two notes ----------------


def test_two_questions_in_one_message_are_each_answered_under_their_own_words():
    result = ask("When is the dentist check-up and why did the list feel slow?")
    text = result["text"]
    assert result["shape"] == "multi"
    assert text.startswith("**When is the dentist check-up?** ")
    assert "\n\n**Why did the list feel slow?** " in text
    assert "Check-up booked for the 21st." in text and "It was not the database." in text


def test_a_comparison_is_one_question_whatever_its_ands():
    assert composer.split_parts("Compare Lisbon and Porto") == ["Compare Lisbon and Porto"]
    assert composer.split_parts("When is the dentist and how?") == ["When is the dentist and how?"]


def test_a_short_question_two_notes_answer_differently_asks_which_was_meant():
    notes = [
        _note(1, "# Boiler service\n\nThe boiler service is due in March.", 5),
        _note(2, "# Boiler pressure\n\nThe boiler pressure was low this morning.", 3),
    ]
    text = ask("What about the boiler?", notes)["text"]
    assert text.rstrip().endswith("Did you mean **Boiler service** or **Boiler pressure**?") or text.rstrip().endswith(
        "Did you mean **Boiler pressure** or **Boiler service**?"
    )
    #: The likelier is answered first: the question is never the whole reply.
    assert not text.startswith("Did you mean")


def test_a_question_its_note_is_named_for_is_not_asked_back():
    notes = [
        _note(1, "# Boiler service\n\nThe boiler service is due in March.", 5),
        _note(2, "# House\n\nThe boiler is in the loft, the service hatch is stiff.", 3),
    ]
    assert "Did you mean" not in ask("When is the boiler service?", notes)["text"]
