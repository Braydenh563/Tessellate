"""Q34, WORLD_CLASS row 35: the studio's script is the person's own words and a fixed frame.

No model and no voice are involved: `ai/studio.script` is plain text in, sentences out.
"""

from __future__ import annotations

from tessellate.ai import studio

NOTES = [
    {"text": "# Garden plan\nPlant the beans in May. The soil needs compost first. Water twice a week."},
    {"text": "---\ntags: [x]\n---\n## Call the plumber\nThe tap in the kitchen drips. Ask about the quote."},
    {"text": "Buy paint\nTwo tins of white."},
]


def test_every_note_is_told_by_its_name_then_its_own_sentences():
    lines = studio.script(NOTES, topic="the house")
    assert lines[0] == "Here is an overview of your notes about the house."
    assert "First, Garden plan." in lines and "Plant the beans in May." in lines
    assert "Next, Call the plumber." in lines and "Last, Buy paint." in lines
    assert lines[-1] == "That was 3 notes."


def test_a_brief_has_no_closing_count_and_names_its_topic():
    lines = studio.script(NOTES, topic="Monday with Sam", brief=True)
    assert lines[0] == "Here is a brief about Monday with Sam, from your own notes."
    assert not any(line.startswith("That was") for line in lines)


def test_nothing_is_added_that_the_notes_did_not_say():
    said = " ".join(n["text"] for n in NOTES).lower()
    for line in studio.script(NOTES)[1:-1]:
        body = line.split(", ", 1)[1] if line.startswith(("First,", "Next,", "Last,")) else line
        assert body.rstrip(".").lower() in said, line


def test_a_long_sentence_is_said_by_its_gist_and_the_length_asked_for_limits_the_notes():
    long = "word " * 80 + "end."
    notes = [{"text": f"Note {i}\n{long}"} for i in range(12)]
    short = studio.script(notes, minutes=1)
    longer = studio.script(notes, minutes=5)
    assert len(short) < len(longer)
    assert sum(len(line.split()) for line in short) <= studio.WORDS_PER_MINUTE + 40
    assert all(len(line.split()) <= studio.SENTENCE_WORDS + 3 for line in longer)


def test_notes_with_no_text_make_no_script():
    assert studio.script([{"text": ""}, {"text": "  \n "}]) == []
    assert studio.script([]) == []


def test_a_lone_note_has_no_closing_count():
    assert studio.script(NOTES[:1])[-1] != "That was 1 notes."
