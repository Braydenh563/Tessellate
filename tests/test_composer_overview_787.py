"""The composed answer to a topic asked about as a whole (INBOX 787).

The owner: "the composer is still pretty barebone, has no life to it and I
may as well just ignore it and use the matching records". Asked "games notes"
it quoted two sentences and a picture's caption as "shows The image shows
...". The overview answers in its first sentence (how many notes, over which
days, the thread most share), groups the notes by that thread with a day and
a short line each, says a picture as what it shows and one line of its
words, names what links the notes, and offers what to ask next; every
clause is still a quote, a measured value, a word of the question or a word
of the notes (`tests/_composer_eval.trace_failures`).
"""

from __future__ import annotations

import json
from datetime import date, datetime

import pytest

from tessellate.ai import composer, composer_overview
from tests._composer_eval import trace_failures

TODAY = date(2026, 10, 10)


def _pictures(name: str, caption: str, text: str) -> str:
    return f'\n\n[Pictures in this note, as this app read them:\n- {name}: shows {caption}; text in it: "{text}"]'


NOTES = [
    (1, "2026-07-12", ["ideas"], "Project ideas\n\n- A habit tracker that syncs with my calendar\n- A Discord bot for our League team that posts match stats\n- A recipe app that plans meals from what is in the fridge\n- Portfolio site with my uni projects"),
    (2, "2026-08-03", ["ideas"], "App idea: study planner\n\nI want to build a study planner that splits each subject into weekly goals. It should remind me before quizzes."),
    (3, "2026-08-31", ["ideas"], "Feature list\n\n![features.png](/media/feat1.png)" + _pictures(
        "features.png", "The image contains a text excerpt discussing features for a note-taking app.",
        "Features / 1. Offline search / 2. Tags and categories / 3. Graph view of linked notes")),
    (4, "2026-07-17", ["games"], "League of Legends\n\nI hit Gold 2 this season. Playing mostly jungle with Vi and Lee Sin."),
    (5, "2026-08-02", ["games"], "League notes\n\nTilted after three losses in a row. Rule: stop after two losses."),
    (6, "2026-08-24", ["games"], "Minecraft server with Jake and Sam. We are building a castle on the north island."),
    (7, "2026-09-05", ["games"], "League stats\n\n![stats.png](/media/stats1.png)" + _pictures(
        "stats.png", "The image shows a screenshot of a game statistics screen with a win rate graph.",
        "Ranked Solo/Duo / Gold II / Win rate 54%")),
    (8, "2026-09-09", ["games"], "Games to try: Hollow Knight, Hades, Celeste. Hades is on sale until Friday."),
    (9, "2026-09-14", ["ideas"], "Side project ideas from the hackathon\n\nJake suggested a campus map app. I think a lecture recording summariser could win."),
    (10, "2026-09-29", [], "Jake's birthday is 12 October. He wants the new Zelda game."),
    (11, "2026-09-28", ["projects"], "Working on: the Tessellate clone for my portfolio. Today I got the search working with SQLite FTS."),
    (12, "2026-09-30", [], "This week I am working on the study planner backend and the COMP1511 assignment."),
    (13, "2026-09-22", ["uni"], "Lecture slide\n\n![slide.png](/media/slide1.png)" + _pictures(
        "slide.png", "The image contains a lecture slide about binary search trees with a diagram.",
        "Binary Search Trees / insert O(log n) average, O(n) worst case")),
]


def _notes() -> list[dict]:
    return [{"id": i, "created_at": f"{day}T10:00:00", "tags": tags, "content": content} for i, day, tags, content in NOTES]


def ask(question: str, notes: list[dict] | None = None, **kwargs) -> dict:
    return composer.compose(question, notes if notes is not None else _notes(), today=TODAY, **kwargs)


@pytest.mark.parametrize(
    ("question", "subject"),
    [
        ("games notes", "games"),
        ("ideas for projects", "ideas for projects"),
        ("what did I write about uni", "uni"),
        ("summarise my uni notes", "uni"),
        ("what do I know about League of Legends?", "League of Legends"),
        ("who is Jake", "Jake"),
        ("what did Priya say", "Priya"),
        ("how many notes about games", "games"),
        ("what am I working on", composer_overview.DOING),
        ("what are my app ideas", "app ideas"),
        ("what is there about games", "games"),
        ("whats there on uni?", "uni"),
    ],
)
def test_the_frames_that_ask_about_a_topic_as_a_whole(question, subject):
    assert composer_overview.topic(question) == subject


@pytest.mark.parametrize("question", ["when is my assignment due", "what is 12 * 7", "what did I write last week", "my notes", "hey"])
def test_a_question_about_one_thing_is_no_overview(question):
    assert composer_overview.topic(question) is None


def test_games_notes_answers_in_its_first_sentence_and_groups_by_the_thread():
    result = ask("games notes")
    first = result["text"].split("\n", 1)[0]
    assert result["shape"] == "overview"
    #: How many and the thread most of them share; the days only when the
    #: question is about time (INBOX 1441, the owner, 2026-10-29).
    assert "five notes" in first and "games" in first and "24 August" not in first
    assert "July" not in first and "League" in first
    assert "**League**" in result["text"]
    assert not trace_failures(result, "games notes", _notes(), TODAY)
    #: Decision 52's maxims hold: no day said twice, no capital after a comma.
    from tessellate.ai import validate

    assert not validate.report(result, "games notes")["findings"]


def test_a_picture_is_said_as_what_it_shows_and_one_line_of_its_words():
    text = ask("games notes")["text"]
    assert "The image" not in text and "shows The" not in text
    assert "a screenshot of a game statistics screen" in text
    assert "“Ranked Solo/Duo”" in text and "Win rate 54%" not in text


def test_no_citation_markers_in_an_overview():
    assert "[your note," not in ask("what did I write about ideas")["text"]


def test_a_person_is_answered_by_where_they_come_up():
    result = ask("who is Jake")
    assert result["text"].startswith("Jake")
    assert "three" in result["text"].split("\n", 1)[0]
    assert not trace_failures(result, "who is Jake", _notes(), TODAY)


def test_a_list_note_is_said_as_one_sentence():
    text = ask("ideas for projects")["text"]
    assert "a list: A habit tracker that syncs with your calendar; A Discord bot" in text


def test_what_links_the_notes_and_what_to_ask_next():
    result = ask("games notes")
    assert any("League" in chip for chip in result["next"])
    assert all(len(chip) <= composer.NEXT_MAX_CHARS for chip in result["next"])


def test_one_note_holding_the_whole_subject_is_the_answer_not_an_overview():
    result = ask("what did I note about binary search trees")
    assert result["shape"] != "overview"
    assert "a lecture slide about binary search trees" in result["text"]


def test_the_lead_varies_by_question_and_turn():
    leads = {ask("games notes", salt=f"chat{n}", turn=n)["text"].split(" ", 2)[1] for n in range(1, 13)}
    assert len(leads) >= 3, leads


def test_a_heading_line_with_no_stop_does_not_run_into_the_next_quote():
    notes = [_notes()[8]]
    text = ask("what did Jake suggest", notes)["text"]
    assert "hackathon Jake" not in text


def test_a_picture_caption_loses_its_frame_and_its_text_is_a_line_each():
    view = composer.read_note(_notes()[2], 0)
    shows = [s.text for s in view.sentences if s.kind == "picture"]
    reads = [s.text for s in view.sentences if s.kind == "picture_text"]
    assert shows == ["a text excerpt discussing features for a note-taking app."]
    assert reads == ["Offline search", "Tags and categories", "Graph view of linked notes"]
    content = _notes()[2]["content"]
    for s in view.sentences:
        assert content[s.start:s.end] == s.text


def test_a_picture_with_several_lines_is_said_once_not_a_sentence_a_line():
    text = ask("what is on my feature list", [_notes()[2]])["text"]
    assert text.count("The picture in") == 1
    assert "“Offline search”, “Tags and categories” and “Graph view of linked notes”" in text


def test_the_notice_under_a_composed_answer_shows_only_when_pictures_carry_it():
    from tessellate.api.routes_chat import _composed_support

    quoted = {"grounding": [{"said": "quoted"}, {"said": "picture"}], "support": {"low": True}}
    pictured = {"grounding": [{"said": "picture"}, {"said": "picture"}, {"said": "quoted"}], "support": {"low": False}}
    assert _composed_support(quoted)["low"] is False
    assert _composed_support(pictured)["low"] is True and _composed_support(pictured)["by_model"] is False


def test_the_route_reads_every_note_of_the_topic_and_joins_a_pictures_lines(client, session):
    from tessellate.core.database import Entry, MediaUpload

    session.add(MediaUpload(filename="s1.png", original_name="stats.png", caption="The image shows a game screen.",
                            vision_ocr_text="Ranked Solo/Duo\nGold II"))
    session.commit()
    bodies = [
        ("League notes\n\nRule: stop after two losses.", ["games"]),
        ("League stats\n\n![stats.png](/media/s1.png)", ["games"]),
        ("Minecraft server with Jake and Sam.", ["games"]),
        ("Games to try: Hollow Knight, Hades, Celeste.", ["games"]),
        ("Hollow Knight is hard but fair.", ["games"]),
        ("Bought a new keyboard for gaming.", ["games"]),
        ("Dentist on Friday.", []),
    ]
    for n, (content, tags) in enumerate(bodies):
        made = client.post("/entries", json={"content": content, "tags": tags}).json()
        entry = session.get(Entry, made["id"])
        entry.created_at = datetime(2026, 8, 1 + n, 10)
        session.commit()
    with client.stream("POST", "/chat/stream", json={"question": "games notes"}) as r:
        events = [json.loads(line) for line in r.iter_lines() if line.strip()]
    text = "".join(e.get("delta", "") for e in events if e.get("type") == "answer")
    assert text.startswith(("You have six", "I found six", "There are six", "Your notebook holds six")), text
    assert "“Ranked Solo/Duo”" in text and "Gold II" not in text.split("“Ranked Solo/Duo”")[0]


def test_a_conversation_varies_the_lead_and_never_mismatches_its_halves():
    """Decision 25 (no joining words twice in a conversation) with the pairs
    of decision 34: whichever half a turn has used, the two halves read."""
    dialogue = composer.Dialogue.from_history([])
    leads = []
    for _ in range(8):
        first = ask("games notes", dialogue=dialogue)["text"].split("\n", 1)[0]
        assert " and September" not in first and "from July and" not in first, first
        leads.append(first.split(" five ")[0])
    assert len(set(leads)) >= 3, leads


def test_a_count_and_a_day_are_two_values_and_a_day_said_twice_is_one():
    from tessellate.ai import validate

    def parts(*measures):
        out = []
        for m in measures:
            out += [("measure", m), ("template", ". ")]
        return {"parts": out}

    assert not [f for f in validate.maxims(parts("five", "5 September")) if f.rule == "measured value said twice"]
    assert [f for f in validate.maxims(parts("5 September", "5 September")) if f.rule == "measured value said twice"]


def test_what_is_there_about_a_topic_is_the_overview_not_one_quote():
    """OPEN 806 (decision 64): "what is there about X" with no model is the
    overview shape, as "what do I know about X" is."""
    assert ask("what is there about games")["shape"] == "overview"
