"""The owner's own typos are composer fixtures (INBOX 837, Brief 90).

The owner: "make sure that for all future conversations, all my spelling
mistakes and grammar issues in all these and future prompts in these sessions
are checked against the composer to see if it can properly understand them".
`fixtures/owner_typos.json` holds their real misspellings and run-ons, each with
the reading it should get; a session appends the new ones it was typed (the
standing order is in HANDOVER). Each entry is tested at the level it should be
understood: the repaired text, the Guide topic, the routed intent. A miss is
fixed in `question_noise`, never by special-casing the string.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tessellate.ai import help_chat, intent, question_noise

BANK = json.loads((Path(__file__).parent / "fixtures" / "owner_typos.json").read_text(encoding="utf-8"))
IDS = [entry["typed"] for entry in BANK]


@pytest.mark.parametrize("entry", BANK, ids=IDS)
def test_the_typed_text_is_repaired_to_the_reading(entry):
    assert question_noise.repair(question_noise.tidy(entry["typed"])) == entry["repaired"]


@pytest.mark.parametrize("entry", [e for e in BANK if "topic" in e], ids=lambda e: e["typed"])
def test_the_guide_finds_the_topic(entry):
    assert help_chat.topics_for(entry["typed"])[0]["id"] == entry["topic"]


@pytest.mark.parametrize("entry", [e for e in BANK if "intent" in e], ids=lambda e: e["typed"])
def test_the_message_is_routed_to_its_intent(entry):
    assert intent.classify(entry["typed"]) == entry["intent"]


def test_a_word_near_two_words_offers_the_other_reading():
    unsure: list[dict] = []
    assert question_noise.repair("what is the tiem", unsure) == "what is the time"
    assert [(u["typed"], u["chosen"], u["alternative"]) for u in unsure] == [("tiem", "time", "item")]


@pytest.mark.parametrize("entry", BANK, ids=IDS)
def test_a_repaired_reading_is_stable(entry):
    assert question_noise.repair(entry["repaired"]) == entry["repaired"]


#: Correct text, names and rare words the notebook is full of: repair must
#: leave them as typed (the cost of a general speller is a wrongly "fixed" word).
LEFT_ALONE = [
    "what did Sarah say about kombucha",
    "when is the dentist",
    "how many times did I go to the gym",
    "notes about the mantis shrimp",
    "what is on the wifi router in Zoe's flat",
    "tailscale and kubernetes setup",
    "who is Brayden and what did he write about sourdough",
    "show my notes tagged #ideas from last week",
    "the zhuzh upgrade for the hallway",
    "what did Nguyen say about the Fremantle trip",
    "how do I use the whiteboard and the mind map",
    "summarise my meeting with Priya",
    "what is a tooltip",
    "compare the hiking notes with the camping notes",
    "stop generating features and keep the proper hierarchy",
    "the instant highlights on the pancakes recipe page",
    "they stopped planning the corner shop and the hallway",
    "everything everywhere in the statistical timezones panel",
    "a thorough perceive of what receives the notifications",
    "my wifi password and the sourdough starter notes",
    "when is the next whiteboard session with Priya",
    "the ocr workspace shows the mind map and the timeline",
    "which notes mention the beta and the deposit that was paid",
    "advise the kindly neighbour about the hallway light",
    "it was a really nice weekend at the lake house",
]


@pytest.mark.parametrize("text", LEFT_ALONE)
def test_correct_text_and_names_are_left_alone(text):
    assert question_noise.repair(text) == text


# --- the speller's guards ----------------------------------------------------


def test_a_word_the_notes_hold_is_never_changed():
    assert question_noise.repair("what is the suer", known=frozenset({"suer"})) == "what is the suer"


@pytest.mark.parametrize(
    ("typed", "meant"),
    [
        ("pasta and tacos", "pasta and tacos"),
        ("the pasta recipe", "the pasta recipe"),
        ("a nd b", "and b"),
        ("the dsiplay", "the display"),
        ("shouldn follow", "should not follow"),
        ("the Westen office", "the Westen office"),
        ("NASA launch", "NASA launch"),
        ("v2 notes in notes.txt", "v2 notes in notes.txt"),
    ],
)
def test_the_speller_changes_only_what_it_is_sure_of(typed, meant):
    assert question_noise.repair(typed) == meant


def test_a_split_word_is_joined_and_a_run_on_pair_is_recut_only_into_words():
    from tessellate.ai import spelling

    assert spelling.rejoin(["thes", "ebuttons"]) == ["these", "buttons"]
    assert spelling.rejoin(["kombucha", "scoby"]) == ["kombucha", "scoby"]
    assert spelling.rejoin(["Brayden", "Hoyle"]) == ["Brayden", "Hoyle"]


# --- the acknowledgement varies (decision d) ---------------------------------

NOTES = [{"id": 1, "title": "Gym", "content": "I went to the gym on Monday and ran five kilometres.", "created_at": "2026-10-05T09:00:00"}]
TYPED = [
    "wehn did i go to the gym",
    "hwo far did i run",
    "whn did i run five kilometres",
    "wher did i go on monday",
    "wehn was the gym",
    "hwo far was the run",
    "whn was monday",
    "wher is the gym",
]


def _ack(text: str) -> str:
    return text.split("\n\n", 1)[0] if "“" in text.split("\n\n", 1)[0] else ""


def test_a_repaired_question_is_answered_with_how_it_was_read():
    from tessellate.ai import composer

    result = composer.compose("wehn did i go to the gym", NOTES)
    assert result["text"].startswith(_ack(result["text"])) and "when did i go to the gym" in _ack(result["text"])


def test_a_question_that_needed_no_repair_is_not_acknowledged():
    from tessellate.ai import composer

    assert "“" not in composer.compose("when did i go to the gym", NOTES)["text"].split("\n\n", 1)[0]


@pytest.mark.parametrize("voice", ["natural", "professional"])
def test_the_acknowledgement_is_never_the_same_words_twice_in_a_row(voice):
    from tessellate.ai import composer

    dialogue = composer.Dialogue.from_history([])
    opened = []
    for question in TYPED * 2:
        result = composer.compose(question, NOTES, dialogue=dialogue, voice=voice)
        opened.append(_ack(result["text"]).split("“")[0])
    assert all(opened), opened
    assert all(a != b for a, b in zip(opened, opened[1:])), opened
    assert len(set(opened)) >= 4


def test_the_acknowledgement_skips_the_last_one_used_even_across_a_plain_turn():
    from tessellate.ai import composer

    dialogue = composer.Dialogue.from_history([])
    first = _ack(composer.compose("wehn did i go to the gym", NOTES, dialogue=dialogue)["text"]).split("“")[0]
    composer.compose("when did i go to the gym", NOTES, dialogue=dialogue)
    for question in TYPED[1:]:
        second = _ack(composer.compose(question, NOTES, dialogue=dialogue)["text"]).split("“")[0]
        assert second != first
        first = second


@pytest.mark.parametrize("typo", ["redeisgn", "knoe", "thier", "suer", "noficiations", "proffesionalising", "westen", "wierd", "ahve", "hwo", "liks", "odf", "mut", "everythign", "becaus", "ehte", "compoiser", "ot", "eb", "coule", "speach", "everythinf", "liek", "ther", "ist", "bototm", "restert", "typeos", "linal", "capble", "tis", "abutton", "loit", "cor"])
def test_the_owners_misspellings_are_not_in_the_word_list(typo):
    from tessellate.ai import spelling

    assert not spelling.is_word(typo)


def test_a_misspelt_word_is_read_towards_the_notes_own_word():
    known = frozenset({"hotel", "lisbon", "balcony"})
    assert question_noise.repair("when did i book the hotle in lisbn", known=known) == "when did i book the hotel in lisbon"


# Reading a word the notes hold despite a past form or a typo, and the
# plain-language lines under an answer (owner, 2026-10-12): asked "when did I
# buy that gamin mouse earlier this year??", the answer quoted "I just bought a
# new gaming mouse" and then said "I couldn't find any reference to buy or
# gamin". A past form and a typo of a word the note has are not missing.

def _found_stems(*words):
    from tessellate.ai import composer

    return {composer._stem(w) for w in words}


def test_a_past_form_counts_as_the_word():
    from tessellate.ai import composer

    assert composer._seen("buy", _found_stems("I", "just", "bought", "mouse"))


def test_a_dropped_g_counts_as_the_word():
    from tessellate.ai import composer

    assert composer._seen("gamin", _found_stems("gaming", "mouse"))


def test_one_letter_off_counts_as_the_word():
    from tessellate.ai import composer

    assert composer._seen("mouce", _found_stems("mouse"))


def test_a_word_no_note_has_is_still_missing():
    from tessellate.ai import composer

    assert not composer._seen("hotel", _found_stems("gaming", "mouse"))


def test_a_sentence_heading_is_not_wrapped_in_your_note():
    """"Your the split follows this structure note has" (owner, 2026-10-12)."""
    from datetime import date
    from types import SimpleNamespace
    from tessellate.ai import composer_digest as d
    held = [SimpleNamespace(view=SimpleNamespace(written=date(2026, 7, 27)))]
    line = d._prose("The split follows this structure", held, ["has Pull, Push and Legs"], 0, date(2026, 10, 12))
    assert "Your the" not in line and "structure note" not in line, line


def test_a_cold_process_routes_an_act_without_anything_else_imported():
    """`intent.classify` alone in a fresh interpreter reads "pin the dentist
    noe" as an act: the typed reader is registered by `commands`, which the
    classifier itself must bring in (it used to depend on what ran before)."""
    import subprocess
    import sys

    src = Path(__file__).resolve().parents[1] / "src"
    code = (
        "from tessellate.ai import intent;"
        "print(intent.classify('pin the dentist noe'), intent.classify('unlnk the gym note from the running note'))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True, env={"PYTHONPATH": str(src), "PATH": ""}
    ).stdout.split()
    assert out == ["act", "act"]
