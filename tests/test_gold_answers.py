"""The answer judged against gold answers (CHAT_PLAN decision 70, INBOX 812).

The owner: "you keep saying youve improved it but i still cant see much".
Every earlier round passed its own rule counts; this one is held to answers
written by hand for the owner's questions (`tests/fixtures/gold_answers.json`)
and scored by `tests/_gold.py`. The floor is a ratchet: raise it as the
answers improve, never lower it. The app itself is measured by
`scratchpad/ui-sweeps/gold.js` (the same questions through the route).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from tests import _gold
from tessellate.ai import composer, composer_digest

FIXTURE = _gold.load()
TODAY = date.fromisoformat(FIXTURE["today"])
NOTES = [
    {"id": i + 1, "content": n["content"], "created_at": f"{n['date']}T10:00:00", "category": n["category"], "tags": n["tags"]}
    for i, n in enumerate(FIXTURE["notes"])
]
KEYS = {n["key"]: i + 1 for i, n in enumerate(FIXTURE["notes"])}
NOTE_ANSWERS = [a for a in FIXTURE["answers"] if a["kind"] == "notes"]
#: Measured 2026-10-11: before the digest the note answers scored 49 on
#: average through the app; after, 80; with B1, B3, B4 and B12 (the "so
#: what" line, pinned times, one offer a kind), 88. The floor sits under it.
NOTES_FLOOR = 85


def _notebook(item: dict) -> list[dict]:
    """The shared notebook, or the answer's own when the owner's question
    came with its note (n 21: one note, which the shared one would muddle)."""
    own = item.get("notes")
    if not own:
        return NOTES
    return [
        {"id": 100 + i, "content": n["content"], "created_at": f"{n['date']}T10:00:00", "category": n["category"], "tags": n["tags"]}
        for i, n in enumerate(own)
    ]


def _answer(item: dict) -> dict:
    notes = _notebook(item)
    return composer_digest.answer(item["question"], notes, today=TODAY) or composer.compose(item["question"], notes, today=TODAY)


def test_the_fixture_is_twenty_answers_across_the_kinds_decision_71_names():
    kinds = {a["type"] for a in FIXTURE["answers"]}
    #: Twenty, the owner's gaming mouse question (2026-10-11) as typed, and
    #: the owner's social connections notebook (INBOX 1301 D5).
    assert len(FIXTURE["answers"]) == 22
    assert {"fact", "overview", "compare", "count", "who", "left"} <= kinds


def test_the_note_answers_read_like_the_gold_on_average():
    scores = [_gold.score(_answer(a)["text"], a)["total"] for a in NOTE_ANSWERS]
    assert sum(scores) / len(scores) >= NOTES_FLOOR, scores


@pytest.mark.parametrize("item", NOTE_ANSWERS, ids=lambda a: str(a["n"]))
def test_no_note_answer_quotes_brackets_or_repeats_the_sources(item):
    """INBOX 812: quoted fragments under a bar, "[your note, 27 July]" on
    every line, then "Grounded in" chips and "4 of 4" under it."""
    failed = _gold.score(_answer(item)["text"], item)["failed"]
    assert not {"no_brackets", "no_quoting", "never"} & set(failed), failed


def test_the_owners_question_opens_with_the_count():
    result = composer_digest.answer("What have I saved about courses & study?", NOTES, today=TODAY)
    lines = result["text"].split("\n\n")
    #: The count without the span: the question is not about time (INBOX 1441).
    assert lines[0] == "You have four notes about uni."
    #: The first note told as what happened (the owner, 2026-10-11), its
    #: "next week" said from today; the narration tests further down have the rest.
    assert lines[1].startswith("You went back to uni the week of 20 July") and "classes on Tuesdays and Thursdays" in lines[1]
    assert "Nothing yet on assessments or due dates." in lines
    #: The note's Thursday (6 August) has gone by: the offer drops the day
    #: and says what to ask, from the line beside it (the owner, 2026-10-11).
    assert lines[-1] == "Remind you to ask the tutor about big O?"
    assert result["offer"] == {"kind": "reminder", "label": lines[-1], "text": "Ask the tutor about big O"}


def test_the_joke_is_never_a_fact_about_the_person():
    """Decision 67: the homework joke is filed under Courses & Study and
    tagged joke; it is not one of "your four notes about uni"."""
    result = composer_digest.answer("What have I saved about courses & study?", NOTES, today=TODAY)
    assert "homework" not in result["text"]
    assert KEYS["joke1"] not in {row["note_id"] for row in result["grounding"]}
    asked = composer_digest.answer("what jokes have I saved?", NOTES, today=TODAY)
    assert "homework" in asked["text"]


def test_one_citation_row_a_line_and_each_names_its_note():
    result = composer_digest.answer("What have I saved about courses & study?", NOTES, today=TODAY)
    #: Every paragraph that tells a note, labelled or prose (the owner,
    #: 2026-10-11), has its one row, in order.
    labelled = [line for line in result["text"].split("\n\n")[1:] if any(r["sentence"] in line for r in result["grounding"])]
    assert len(result["grounding"]) == len(labelled) == 4
    for row, line in zip(result["grounding"], labelled):
        assert row["sentence"] in line
        assert row["note_id"] in {KEYS[k] for k in ("uni1", "uni2", "uni3", "uni4")}
    assert result["support"]["digest"] is True


@pytest.mark.parametrize(
    ("typed", "clean"),
    [
        ("what is there about a gaming mouse?\\", "what is there about a gaming mouse?"),
        ("'what is there about a gaming mouse?\\\\'", "what is there about a gaming mouse?"),
        ("  notebook   stats ", "notebook stats"),
    ],
)
def test_the_question_is_cleaned_before_it_is_read(typed, clean):
    """INBOX 808: the backslash was kept in the query and the search."""
    assert composer_digest.clean(typed) == clean


def test_a_question_the_digest_does_not_fit_falls_to_the_composer():
    assert composer_digest.answer("what is the weather on mars", NOTES, today=TODAY) is None
    assert composer_digest.answer("", NOTES, today=TODAY) is None
    assert composer_digest.answer("what have I saved about uni?", [], today=TODAY) is None


def test_progress_is_said_as_the_change():
    result = composer_digest.answer("how's the gym going?", NOTES, today=TODAY)
    assert result["text"].startswith("Going up: your squats went from 80 kg to 90 kg, 8 September to 2 October.")


def test_a_comparison_names_the_one_the_notes_lean_to():
    result = composer_digest.answer("Logitech or Razer?", NOTES, today=TODAY)
    assert result["text"].startswith("The Logitech, by your notes: you're leaning towards it")
    assert "| Price | about $230 | $200 |" in result["text"]


def test_a_comparison_is_a_table_of_the_two():
    """Decision 71: a comparison is a table, one column a thing, a row a
    point the notes make, an empty cell said rather than left blank."""
    result = composer_digest.answer("Logitech or Razer?", NOTES, today=TODAY)
    rows = [line for line in result["text"].splitlines() if line.startswith("|")]
    assert rows[0] == "| | Logitech G Pro X Superlight | Razer Viper V3 |"
    assert rows[1] == "| --- | --- | --- |"
    assert [r.split("|")[1].strip() for r in rows[2:]] == ["Price", "What you found"]
    assert all(cell.strip() for r in rows[2:] for cell in r.strip("|").split("|")), rows
    assert result["support"]["shape"] == "compare"


def test_what_is_left_is_a_checklist():
    result = composer_digest.answer("what do I need to buy?", NOTES, today=TODAY)
    lines = result["text"].splitlines()
    assert lines[0] == "Five groceries, from your list of 5 October:"
    assert lines[1:6] == ["- [ ] oat milk", "- [ ] eggs", "- [ ] spinach", "- [ ] rice", "- [ ] chicken thighs"]
    assert result["support"]["shape"] == "left"
    assert result["support"]["offer"]["label"] == "Save it as a checklist note?"


@pytest.mark.parametrize(("question", "shape"), [
    ("how much did I spend on groceries?", "count"),
    ("who is Sam?", "who"),
    ("Logitech or Razer?", "compare"),
    ("what do I need to buy?", "left"),
])
def test_the_answer_names_its_shape_for_the_page(question, shape):
    """`support.shape` is what `digestShape` lifts: the count's figure, the
    who card. A count still opens with its figure, a who with the name."""
    result = composer_digest.answer(question, NOTES, today=TODAY)
    assert result["support"]["shape"] == shape
    if shape == "count":
        assert result["text"].startswith("You spent $84 ")
    if shape == "who":
        assert result["text"].startswith("Sam ")


@pytest.mark.parametrize(("text", "said"), [
    ("Gym three times this week", "Gym three times the week of 13 July"),
    ("Uni starts back next week", "Uni starts back the week of 20 July"),
    ("Cleaned the garage last weekend", "Cleaned the garage the weekend of 11 July"),
    ("Ship it on the 14th of next month", "Ship it on 14 August"),
    ("Spent more this month", "Spent more in July"),
    ("Pay it before next week", "Pay it before 20 July"),
])
def test_a_relative_time_is_pinned_to_the_day_it_meant(text, said):
    """CHAT_PLAN B3: "this week" written 17 July becomes "the week of 13 July",
    its Monday, as the Mentions chip's resolver (`when.span`) has it; "before
    next week" is before that Monday, a day (the owner, 2026-10-11)."""

    assert composer_digest._tidy(text, date(2026, 7, 17)) == said


@pytest.mark.parametrize(("question", "kind", "label", "text"), [
    ("what did I think of Dune?", "note", "Start a list of films to watch next?", "Films to watch next\n\n- [ ] "),
    ("how much did I spend on groceries?", "reminder", "Remind you each week to log your spending?", "Log your spending every Sunday"),
    ("Logitech or Razer?", "note", "Note the Logitech as your pick?", "My pick: the Logitech G Pro X Superlight"),
    ("do I like golf?", "reminder", "Remind you to go to the driving range again?", "Go to the driving range"),
    ("what hobbies do I want to try?", "reminder", "Remind you to try bouldering?", "Try bouldering"),
])
def test_every_kind_ends_with_one_offer_the_app_can_do(question, kind, label, text):
    """CHAT_PLAN B12: one acting offer, the answer's last line, done in one
    press (a reminder or a note); never two."""
    result = composer_digest.answer(question, NOTES, today=TODAY)
    assert result["offer"] == {"kind": kind, "label": label, "text": text}
    assert result["text"].split("\n\n")[-1] == label
    assert result["text"].count("?") == 1


def test_how_its_going_says_the_change_what_went_quiet_and_offers_a_table():
    """B1 and B4: the change, then what an earlier note had that the latest
    does not, then the lifts as a table note."""
    result = composer_digest.answer("how's the gym going?", NOTES, today=TODAY)
    lines = result["text"].split("\n\n")
    assert lines[0] == "Going up: your squats went from 80 kg to 90 kg, 8 September to 2 October."
    assert "Nothing on bench since September." in lines
    assert result["offer"]["label"] == "Track your lifts in a table?"
    assert "| 8 September | 80 kg | 60 kg |" in result["offer"]["text"]


@pytest.mark.parametrize(("question", "closing"), [
    ("what hobbies do I want to try?", "None of them has a note of its own yet."),
    ("how much did I spend on groceries?", "It's the only week you've written down."),
    ("who is Sam?", "It's the only note that names Sam."),
])
def test_the_so_what_line_says_how_alone_the_facts_are(question, closing):
    assert closing in composer_digest.answer(question, NOTES, today=TODAY)["text"].split("\n\n")


POTTERY = [
    "Pottery class: centring the clay is the hard part.", "Pottery: trimmed my first bowl today.",
    "Glaze test came out blue-green, not the blue I wanted.", "Kiln firing is on Saturday at 10am.",
    "Bought a set of pottery tools for $45.", "Wheel speed: slower when pulling walls.",
    "Teacher said wedge the clay longer before throwing.", "Pottery: my mug handle cracked in the kiln.",
    "Signed up for the advanced pottery term in November.", "Studio is open Thursdays until 9pm.",
]


def _pottery() -> list[dict]:
    return [
        {"id": i + 1, "content": f"{c} #pottery", "created_at": f"2026-09-{i + 1:02d}T10:00:00", "category": "Hobbies", "tags": ["pottery"]}
        for i, c in enumerate(POTTERY)
    ]


def test_a_long_overview_is_short_with_the_rest_behind_more():
    """B5: five lines show; the rest are sent cited and named by their
    labels, so the page folds them behind one "Show five more"."""
    result = composer_digest.answer("what have I saved about pottery?", _pottery(), today=TODAY)
    more = result["support"]["more"]
    #: Found by the words each opens with: a day's line is prose now (the
    #: owner, 2026-10-11), a labelled one keeps its label too.
    assert more["label"] == "Show five more" and len(more["starts"]) == 5
    for start in more["starts"]:
        assert start in result["text"].replace("**", "")
    for label in more["labels"]:
        assert f"**{label}:**" in result["text"]
    assert len(result["grounding"]) == 10, "every line, shown or folded, keeps its mark"
    assert "more on the right" not in result["text"]


def test_a_short_answer_has_no_more():
    assert composer_digest.answer("what have I saved about uni?", NOTES, today=TODAY)["support"]["more"] is None


def test_hashtags_and_today_are_tidied():
    text = composer_digest.answer("what have I saved about pottery?", _pottery(), today=TODAY)["text"]
    assert "#" not in text
    #: A note's own "today" is said against the day it was written, as the
    #: date and how far back (INBOX 1461, newer than 1441's undated line);
    #: since INBOX 1483 a day five weeks back is said by its month, never
    #: "2 September (a month ago)".
    assert "today" not in text and "Back in September, you trimmed your first bowl." in text, text


@pytest.mark.parametrize(("question", "subject"), [
    ("What have I saved about courses & study?", "courses & study"),
    ("what have i got on pottery", "pottery"),
    ("tell me about pottery", "pottery"),
    ("what is there about the gaming mouse?", "gaming mouse"),
])
def test_the_owners_question_counts_every_note_on_the_topic(question, subject):
    """"What have I saved about X" is a topic asked about as a whole: the
    route widens it to every note on X, so the count is not capped at the
    five a search ranked."""
    from tessellate.ai import composer_overview

    assert composer_overview.topic(question) == subject


def test_the_owners_when_question_leads_with_the_day():
    """The owner, 2026-10-11: "when did I buy that gaming mouse??" over "You
    just bought a new gaming mouse discounted from $150 to $68 haha" was
    answered with the note as written, then its day."""
    item = next(a for a in FIXTURE["answers"] if a["n"] == 21)
    result = _answer(item)
    #: The date first, then how far back in words (INBOX 1483).
    assert result["text"] == "On 17 July, about three months ago, you bought a gaming mouse, discounted from $150 to $68."
    row = result["grounding"][0]
    #: The mark sits after the day: "On 17 July[1] you bought ...".
    assert row["anchor"] == "On 17 July" and row["source"].startswith("You just bought")


@pytest.mark.parametrize(
    ("question", "note", "said"),
    [
        #: "On 17 July, about three months ago, you ...": INBOX 1483 moved
        #: the bare date to the date and how far back, as a person says it.
        ("when did I buy the kindle", "I just bought a new Kindle yesterday lol \U0001F602", "On 16 July, about three months ago, you bought a Kindle."),
        ("when did I run the 5k", "Finally finished the 5k run today!!", "On 17 July, about three months ago, you finally finished the 5k run."),
        ("when did i see Sam", "Saw Sam at the cafe \U0001F642", "On 17 July, about three months ago, you saw Sam at the cafe."),
        ("when did I book flights", "I've just booked flights to Lisbon haha", "On 17 July, about three months ago, you booked flights to Lisbon."),
        ("when did I get my phone??", "Got a new iPhone lmao", "On 17 July, about three months ago, you got an iPhone."),
    ],
)
def test_a_when_question_says_the_day_then_what_happened_without_the_asides(question, note, said):
    notes = [{"id": 1, "content": note, "created_at": "2026-07-17T10:00:00", "category": "", "tags": []}]
    assert composer_digest.answer(question, notes, today=TODAY)["text"] == said


def test_just_meaning_only_stays():
    assert composer_digest._unfilled("just two tickets left haha") == "just two tickets left"


# A note told as what happened (the owner, 2026-10-11): its relative time
# resolved against the day it was written and said again from today, its
# connected facts in one flowing sentence with a reporting verb rather than
# label lines, its citation kept and covering every sentence it tells.

NARRATE_FIXTURE = json.loads((Path(__file__).parent / "fixtures/gold_narrated.json").read_text(encoding="utf-8"))
NARRATE_ONE = [n for n in NOTES if n["id"] == KEYS[NARRATE_FIXTURE["note"]]]


@pytest.mark.parametrize("variant", NARRATE_FIXTURE["variants"], ids=lambda v: v["name"])
def test_the_note_is_told_from_today(variant):
    result = composer_digest.answer(NARRATE_FIXTURE["question"], NARRATE_ONE, today=date.fromisoformat(variant["today"]))
    text = result["text"]
    for words in variant["says"]:
        assert words in text, (words, text)
    for words in variant["never"]:
        assert words not in text, (words, text)
    #: The first paragraph against the gold, measured 2026-10-11
    #: (scratchpad/atlas-narr-measure.py): same week 0.31 before, 0.68 now
    #: (against the owner's own words); months later 0.59 before, 1.0 now.
    assert _gold.similarity(text.split("\n\n")[0], variant["gold"]) >= {"same week": 0.6, "months later": 0.9}[variant["name"]]
    row = result["grounding"][0]
    assert row["note_id"] == KEYS[NARRATE_FIXTURE["note"]] and len(row["parts"]) == 3


@pytest.mark.parametrize(("today", "said", "ahead"), [
    (date(2026, 7, 17), "next week", True),
    (date(2026, 7, 21), "this week", True),
    (date(2026, 7, 29), "the week of 20 July", False),
])
def test_next_week_is_said_from_today(today, said, ahead):
    assert composer_digest._when_now("next week", date(2026, 7, 17), today) == (said, ahead)


def test_in_the_whole_notebook_the_note_is_one_flowing_line():
    text = composer_digest.answer(NARRATE_FIXTURE["question"], NOTES, today=TODAY)["text"]
    assert "You went back to uni the week of 20 July, and you" in text
    assert "**This semester:**" not in text and "**Your week:** classes" not in text


NARRATE_ALL = composer_digest.answer(NARRATE_FIXTURE["question"], NOTES, today=TODAY)


@pytest.mark.parametrize("para", NARRATE_FIXTURE["paragraphs"], ids=lambda p: p["note"])
def test_every_paragraph_is_prose_that_understands_its_note(para):
    """The owner, 2026-10-11: "it didnt do the understanding and rewrite for
    the rest of the response, only the first paragraph and note"."""
    text = NARRATE_ALL["text"]
    line = next((p for p in text.split("\n\n") if para["says"][0] in p), "")
    assert line, (para["says"][0], text)
    for words in para["says"]:
        assert words in line, (words, line)
    for words in para["never"]:
        assert words not in line, (words, line)
    assert _gold.similarity(line, para["gold"]) >= 0.8, line
    #: Its mark still covers the note it tells.
    assert any(r["note_id"] == KEYS[para["note"]] for r in NARRATE_ALL["grounding"])


def test_no_heading_label_lines_and_varied_openings():
    paragraphs = NARRATE_ALL["text"].split("\n\n")[1:]
    assert not [p for p in paragraphs if p.startswith("**")], paragraphs
    openings = [" ".join(p.split()[:2]) for p in paragraphs]
    assert len(openings) == len(set(openings)), openings


def test_the_open_plan_is_said_once_in_prose():
    text = NARRATE_ALL["text"]
    for words in NARRATE_FIXTURE["said_once"]:
        assert text.count(words) == 1, (words, text)
    drift = [i for i in NARRATE_ALL["insights"] if i["rule"] == "drift"]
    assert drift and drift[0]["in_answer"] is True
    assert "It may be still open" not in text


@pytest.mark.parametrize(("body", "said"), [
    ("Lisbon trip planned for May", "you planned the Lisbon trip for May"),
    ("squats 80 kg for 5, bench 60 kg for 5", "you squatted 80 kg for 5 and benched 60 kg for 5"),
    ("squats up to 90 kg for 5", "your squat was up to 90 kg for 5"),
    ("knee felt fine", "your knee felt fine"),
    ("going Monday, Wednesday and Friday", "you were going on Mondays, Wednesdays and Fridays"),
    ("tram 28, pasteis de Belem", None),
])
def test_a_days_shorthand_is_said_as_the_persons_own_clause(body, said):
    assert composer_digest._day_clause(body) == said


def test_a_day_line_is_prose_not_a_date_label():
    """The owner, 2026-10-11: "it didnt do the understanding and rewrite for
    the rest of the response". The gym log and the Lisbon plan were left as
    "**8 September:** squats 80 kg for 5 ..." and "**30 August:** Lisbon
    trip planned for May"."""
    import re

    for question in ("how's the gym going?", "what's the plan for Lisbon?"):
        text = composer_digest.answer(question, NOTES, today=TODAY)["text"]
        assert not re.search(r"^\*\*\d{1,2} [A-Z][a-z]+:\*\*", text, re.M), text
    gym = composer_digest.answer("how's the gym going?", NOTES, today=TODAY)["text"]
    assert "On 8 September, you squatted 80 kg for 5 and benched 60 kg for 5, going on Mondays, Wednesdays and Fridays." in gym
    assert "by 2 October, your squat was up to 90 kg for 5, and your knee felt fine." in gym or "on 2 October, your squat" in gym
