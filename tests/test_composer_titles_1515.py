"""INBOX 1515: one title reader for every answer shape, and a quote is always
the note's own words (the class behind four wrongs left after 1512)."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from datetime import datetime

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager

NOW = datetime(2026, 11, 1, 12, 0)

#: Four note shapes the answer must name the same way in every frame.
CLIMB = "Climbing gym membership renewed for a year"
POTTERY = "Pottery class on Thursday at 6pm"
LEGS = "Legs day\n\nWarm up: five minutes on the bike and leg swings\n\nSquats 4x8, Romanian deadlifts 3x10 and lunges 3x12"
BREAD = "Bake at 230C\n\nRest the dough for an hour, then shape the loaf"


@pytest.fixture
def make(session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)

    def build(notes, category="Hobbies"):
        made = []
        for n, (content, tags) in enumerate(notes):
            entry = manager.create_entry(session, content, category, tags)
            entry.created_at = datetime(2026, 10, 1 + n, 18, 0)
            made.append(entry)
        session.commit()
        return made

    return build


def ask(client, question: str) -> str:
    body = {"question": question, "answer_from": "notes", "notes_only": True, "use_tools": False}
    text = []
    with client.stream("POST", "/chat/stream", json=body) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                if event["type"] == "answer":
                    text.append(event["delta"])
    return "".join(text)


#: Each title shape, with the question that reads it and a word the answer holds.
TITLE_SHAPES = [
    ("Legs day\n\nWarm up: five minutes on the bike\n\nSquats 4x8 and lunges 3x12", "Legs day"),
    ("Pottery plan\n\nGlaze: celadon\n\nFiring: Friday", "Pottery plan"),
    ("Chess openings\n\nStudy: the Italian game\n\nPractice: five minutes a day", "Chess openings"),
    ("# Trains\n\nFirst line: the Overland\n\nSecond line: the Ghan", "Trains"),
]


@pytest.mark.parametrize(("content", "title"), TITLE_SHAPES)
def test_a_plain_first_line_over_a_blank_line_names_the_note_everywhere(client, make, content, title):
    """The frame and the sections read one title (1515): never "your warm up note"."""
    make([(content, ["x"]), ("Some other note about something else entirely", ["y"])])
    for question in ("Summarise my notes in Hobbies.", f"What did I write about {title.lower()}?"):
        text = ask(client, question)
        assert not re.search(r"\b[Yy]our (?:warm up|glaze|study|first line) note\b|[Ff]rom your (?:warm up|glaze|study) note", text), text


def test_the_reader_agrees_with_the_frame_on_every_shape():
    from tessellate.ai import composer_frame, composer_read

    for content, title in TITLE_SHAPES:
        view = composer_read.read_note({"id": 1, "content": content}, 0)
        assert view.titled
        assert view.title == title == composer_frame.title_line(content)
    for sentence in ("Went to the gym today\n\nDid legs", "Had a long day at work\n\nTired", "Buy milk and eggs\n\nAlso bread", "I think the plan is fine\n\nMore"):
        assert composer_frame.title_line(sentence) == "", sentence
        assert not composer_read.read_note({"id": 1, "content": sentence}, 0).titled, sentence


@pytest.mark.parametrize("line", ["Pottery class on Thursday at 6pm", "Dentist at 3pm", "Yoga every Monday", "Rent due by 5 November", "Coffee with Sam on Friday"])
def test_a_line_with_a_time_in_it_is_said_not_named(client, make, line):
    """"You started your Pottery class on Thursday at 6pm note" (1515)."""
    make([(line, ["x"])])
    text = ask(client, "Summarise my notes in Hobbies.") + ask(client, "What do I have in Hobbies?")
    assert f"your {line} note" not in text and f"{line} note" not in text, text


@pytest.mark.parametrize("line", [CLIMB, "Renewed my passport at the post office", "Lisbon trip booked for the spring with Sara"])
def test_a_note_quoted_in_its_group_line_is_not_quoted_again(client, make, line):
    """A group names a one-line note by its words or by its day, never both lines quoting it (1515)."""
    make([(line, ["gym"]), (LEGS, ["gym"])])
    text = ask(client, "Summarise my notes in Hobbies.")
    quote = f"“{line}”"
    assert text.count(quote) <= 1, text


@pytest.mark.parametrize(
    "content",
    [
        "Bake at 230C for forty minutes. Rested the dough overnight. Scored the top.",
        "Bake at 230C. Rested the dough overnight.",
        "Bake at 230C for forty minutes. Fed the starter twice.",
    ],
)
def test_a_quote_is_the_notes_own_words(client, make, content):
    """The composer's re-voicing ("You rested the dough") never rides inside a quote (1515)."""
    make([(content, ["bread"]), ("Sourdough starter\n\nFed it twice", ["bread"])])
    for question in ("Summarise my notes in Hobbies.", "What did I write about bread?"):
        #: A quoted word the question asked for is the question's; a quote of three words is a note's.
        for quoted in (q for q in re.findall(r"“([^”]*)”", ask(client, question)) if len(q.split()) >= 3):
            assert re.sub(r"[.\s]+$", "", quoted) in content or quoted in content, quoted


def test_own_words_mends_a_reworded_sentence_and_leaves_the_rest():
    from tessellate.ai import composer_threads

    notes = ["Bake at 230C for forty minutes. Rested the dough overnight.", "they are both sketches"]
    assert composer_threads.own_words("You wrote “Bake at 230C for forty minutes. You rested the dough overnight”.", notes) == "You wrote “Bake at 230C for forty minutes. Rested the dough overnight”."
    assert composer_threads.own_words("You wrote “Bake at 230C for forty minutes”.", notes) == "You wrote “Bake at 230C for forty minutes”."
    assert composer_threads.own_words("A link: “they are both sketches”.", notes) == "A link: “they are both sketches”."
    #: A quote that matches no sentence is the app's own and stays.
    assert composer_threads.own_words("It has no “other word here”.", notes) == "It has no “other word here”."


@pytest.mark.skipif(not os.environ.get("COMPOSER_1515_DUMP"), reason="dump, run by hand")
def test_dump(client, make):
    spec = json.loads(Path(os.environ["COMPOSER_1515_DUMP"]).read_text(encoding="utf-8"))
    make([(c, t) for c, t in spec["notes"]])
    for q in spec["questions"]:
        print("\n## " + q + "\n" + ask(client, q))


def test_a_note_in_an_unsegmented_script_counts_by_character():
    """INBOX 1518, audit 1031 N15: one word counter, not whitespace splits."""
    from tessellate.ai import composer_frame

    assert composer_frame.note_words("今日は雨が降っていたので、家にいました") > 10
    assert composer_frame.note_words("ゴルフ") == 3
    assert composer_frame.note_words("# Title line\n\nthree plain words") == 3


@pytest.mark.parametrize("flight", ["Flight on 20 October to Lisbon", "Lisbon flight is 20 October", "Lisbon flight: 20 October, gate 14"])
@pytest.mark.parametrize("question", ["how many days since my Lisbon flight?", "how long ago was my Lisbon flight?"])
def test_a_day_with_no_year_is_the_nearer_one_to_when_it_was_written(client, make, flight, question):
    """INBOX 1518: a note written 2 October that names "20 October" means the
    one 18 days on, so on 1 November it is 12 days ago, never 377."""
    make([("Some other note about something else entirely", ["y"]), (flight, ["x"])])
    text = ask(client, question)
    assert "2025" not in text and "377" not in text, text
    if "since" in question:
        assert re.search(r"\b12 days|twelve days", text), text
