"""Five classes the fourth composer agent left open (composer5-1031, the
owner's standing order: fix the class, test it over many phrasings).

1. A comparison ranks every side it names (two to six), not the first two.
2. A format wish ("in a table", "as a list", "side by side", "please") is no
   part of a side's name.
3. "Show me my X notes" is one rule whether or not a tag of that name exists.
4. "What's the latest on X" answers with the newest matching note.
5. A timed question's day lead says how far away the day is, then the day.

Fixed clock: Friday 30 October 2026 (`tests/_seed_1030.py`).
"""

from __future__ import annotations

import contextvars
import re
from datetime import date

import pytest

import tests._seed_1030 as seed_1030
from tessellate.ai import composer, composer_digest, note_recency
from tessellate.entry import manager
from tests.test_composer_class_1031 import uni  # noqa: F401  (a fixture)


@pytest.fixture
def ask(client, session, monkeypatch):
    seed_1030.seed(session)
    entry = manager.create_entry(session, "# Porto trip\nWeekend in Porto in January 2027. Budget $900 all in.", tags=["travel"])
    entry.created_at = entry.updated_at = seed_1030.NOW.replace(hour=10, minute=0)
    session.commit()
    go = seed_1030.asker(client, monkeypatch)
    return lambda q: go(q)[0]


def _lead(said: str) -> str:
    return said.split("\n")[0]


# 1. Every named side is ranked and headed.

@pytest.mark.parametrize("question, sides", [
    ("which is the soonest, the dentist, the Lisbon trip or the Tokyo trip", ("the dentist", "the Lisbon trip", "the Tokyo trip")),
    ("which comes first, the dentist, the Lisbon trip or the Tokyo trip", ("the dentist", "the Lisbon trip", "the Tokyo trip")),
    ("which is sooner, the dentist, the Lisbon trip, the Porto trip or the Tokyo trip", ("the dentist", "the Lisbon trip", "the Porto trip", "the Tokyo trip")),
    ("the dentist, the Lisbon trip or the Tokyo trip, which is the soonest", ("the dentist", "the Lisbon trip", "the Tokyo trip")),
    ("which is the cheapest, Lisbon, Tokyo or Porto", ("Lisbon", "Tokyo", "Porto")),
    ("which is the cheapest, Lisbon or Tokyo or Porto", ("Lisbon", "Tokyo", "Porto")),
    ("compare Lisbon, Tokyo and Porto", ("Lisbon", "Tokyo", "Porto")),
    ("compare Lisbon, Tokyo, and Porto", ("Lisbon", "Tokyo", "Porto")),
    ("compare Lisbon and Tokyo and Porto", ("Lisbon", "Tokyo", "Porto")),
    ("Lisbon vs Tokyo vs Porto", ("Lisbon", "Tokyo", "Porto")),
    ("what are the differences between Lisbon, Tokyo and Porto", ("Lisbon", "Tokyo", "Porto")),
    ("compare the Lisbon, Tokyo and Porto notes", ("Lisbon", "Tokyo", "Porto")),
    ("compare Trip to Lisbon and Trip to Porto and Trip to Tokyo", ("Trip to Lisbon", "Trip to Porto", "Trip to Tokyo")),
    ("which is cheaper, Trip to Lisbon or Trip to Tokyo", ("Trip to Lisbon", "Trip to Tokyo")),
    ("which is cheaper, bread and butter or jam", ("bread and butter", "jam")),
    ("compare A1 trip, B2 trip, C3 trip, D4 trip, E5 trip, F6 trip and G7 trip", ("A1 trip", "B2 trip", "C3 trip", "D4 trip", "E5 trip", "F6 trip")),
])
def test_a_comparison_names_every_side(question, sides):
    assert composer.compare_sides(question) == sides


@pytest.mark.parametrize("question", [
    "which is the soonest, the dentist, the Lisbon trip or the Tokyo trip",
    "which comes first, the dentist, the Lisbon trip or the Tokyo trip",
    "the dentist, the Lisbon trip or the Tokyo trip, which is the soonest",
    "which is sooner, the dentist, the Lisbon trip or the Tokyo trip",
])
def test_the_soonest_of_three_is_ranked_with_all_three_days(ask, question):
    said = ask(question)
    lead = _lead(said)
    assert re.match(r"\*\*Dentist\*\* comes first: 4 November against 14 November for \*\*Lisbon trip\*\* and April 2027 for \*\*Tokyo trip\*\*\.", lead), lead
    assert said.count("**Tokyo trip**") >= 2 and "**Lisbon trip**" in said, said


def test_four_sides_are_all_ranked(ask):
    lead = _lead(ask("which is sooner, the dentist, the Lisbon trip, the Porto trip or the Tokyo trip"))
    assert lead.index("Dentist") < lead.index("Lisbon trip") < lead.index("Porto trip") < lead.index("Tokyo trip"), lead
    assert "January 2027" in lead and "April 2027" in lead, lead


@pytest.mark.parametrize("question", [
    "which is the cheapest, Lisbon, Tokyo or Porto", "which is the cheapest, Lisbon or Tokyo or Porto",
    "Lisbon, Tokyo or Porto, which is the cheapest", "which is cheapest, Lisbon, Porto or Tokyo",
])
def test_the_cheapest_of_three_names_three_figures(ask, question):
    lead = _lead(ask(question))
    assert lead.count("$") == 3 and "$420" in lead and "$900" in lead and "$3,000" in lead, lead
    assert "is the cheapest" in lead and lead.index("Lisbon") < lead.index("Tokyo"), lead


@pytest.mark.parametrize("question", [
    "compare Lisbon, Tokyo and Porto", "compare the Lisbon trip, the Tokyo trip and the Porto trip",
    "what are the differences between Lisbon, Tokyo and Porto", "Lisbon vs Tokyo vs Porto",
])
def test_a_plain_comparison_of_three_heads_each_side(ask, question):
    said = ask(question)
    heads = re.findall(r"^\*\*([^*\n]+)\*\*$", said, re.M)
    assert len(heads) >= 3, said
    assert {"lisbon", "tokyo", "porto"} <= {h.lower().replace(" trip", "") for h in heads}, said
    assert re.search(r"one mentions .+ and one mentions .+ and one mentions", _lead(said)), said


# 2. A format wish is not part of a name.

TAILS = ["in a table", "as a table", "in table form", "as a list", "in a list", "side by side", "for me", "please",
         "in bullet points", "as bullets", "in a chart", "in a table, please", "side by side please", "briefly"]


@pytest.mark.parametrize("tail", TAILS)
@pytest.mark.parametrize("head", ["compare the dentist with the Lisbon trip", "compare the dentist and the Lisbon trip",
                                  "the dentist vs the Lisbon trip", "what are the differences between the dentist and the Lisbon trip"])
def test_a_format_tail_is_not_part_of_the_last_side(head, tail):
    assert composer.compare_sides(f"{head} {tail}") == ("the dentist", "the Lisbon trip")


@pytest.mark.parametrize("question", [
    "compare the dentist in a table with the Lisbon trip", "compare the dentist side by side with the Lisbon trip",
    "compare in a table the dentist with the Lisbon trip", "compare the dentist as a list and the Lisbon trip as a list",
])
def test_a_format_wish_in_the_middle_or_front_is_dropped_too(question):
    assert composer.compare_sides(question) == ("the dentist", "the Lisbon trip")


@pytest.mark.parametrize("question, sides", [
    ("which is the soonest, the dentist, the Lisbon trip or the Tokyo trip in a table", ("the dentist", "the Lisbon trip", "the Tokyo trip")),
    ("compare Lisbon, Tokyo and Porto as a list", ("Lisbon", "Tokyo", "Porto")),
    ("compare Lisbon, Tokyo and Porto side by side please", ("Lisbon", "Tokyo", "Porto")),
    ("which is cheaper, Lisbon or Tokyo, for me", ("Lisbon", "Tokyo")),
])
def test_format_tails_and_lists_meet(question, sides):
    assert composer.compare_sides(question) == sides


@pytest.mark.parametrize("question", [
    "compare the dentist with the Lisbon trip in a table", "compare the dentist and the Lisbon trip as a list",
    "compare the dentist with the Lisbon trip side by side", "compare the dentist with the Lisbon trip for me",
])
def test_the_answer_never_says_the_format_as_part_of_a_side(ask, question):
    said = ask(question)
    assert re.search(r"(?i)table|as a list|side by side|for me", said) is None, said
    assert "**Lisbon trip**" in said and "**dentist**" in said, said


@pytest.mark.parametrize("name", ["Table tennis", "List of lists", "The summary page", "Chart of accounts"])
def test_a_name_that_holds_a_format_word_keeps_it(name):
    assert composer.compare_sides(f"compare {name} with Porto") == (name, "Porto")


# 4. "What's the latest on X" takes the newest note that matches.

@pytest.mark.parametrize("question, subject", [
    ("what's the latest on uni", "uni"), ("what is the latest on university", "university"),
    ("what's the latest news on the Atlas project", "atlas project"), ("the newest about my flat", "flat"),
    ("what's the most recent update on the sync rewrite", "sync rewrite"), ("whats the latest on baking", "baking"),
    ("what is the newest with my cloud computing", "cloud computing"), ("tell me the latest about Priya", "priya"),
    ("what's the latest regarding the passport", "passport"),
])
def test_a_latest_ask_names_its_subject(question, subject):
    assert note_recency.status_subject(question) == subject


@pytest.mark.parametrize("question", [
    "what did I write last week", "what's the latest note", "what's the latest", "my latest notes about running",
    "what is the latest on last week", "what's the latest on today", "what is new", "the new flat is on Main street",
    "what's the latest on", "when is the latest",
])
def test_other_asks_name_no_latest_subject(question):
    assert note_recency.status_subject(question) == ""


@pytest.mark.parametrize("question", [
    "what's the latest on uni", "what is the latest on uni", "what's the latest on university", "what is the latest on university",
    "what's the newest on university", "what's the most recent update on uni", "latest on university", "what's the latest about uni",
])
def test_the_latest_on_uni_is_the_newest_note_not_the_first_found(uni, question):  # noqa: F811
    said = uni(question)
    assert "8 October" in _lead(said) and "missed the bus" in _lead(said), said
    assert "July" not in _lead(said), said


@pytest.mark.parametrize("question", [
    "what's the latest on baking", "what is the latest on baking", "what's the newest on baking", "what's the most recent update on baking",
    "what's the latest about baking", "what is the latest on my baking",
])
def test_the_latest_on_baking_is_the_loaf_not_the_starter(ask, question):
    lead = _lead(ask(question))
    assert "Sourdough loaf" in lead and "Banana" not in lead and "starter" not in lead.lower(), lead


@pytest.mark.parametrize("question", ["what's the latest on running", "what is the newest on running", "what's the most recent update on running"])
def test_the_latest_on_running_is_the_newest_run(ask, question):
    assert "Felt really good" in _lead(ask(question)), question


@pytest.mark.parametrize("question", ["what's the latest on Priya", "what is the newest on Priya", "what's the latest about Priya"])
def test_the_latest_on_a_person_is_the_newest_note_naming_them(ask, question):
    lead = _lead(ask(question))
    assert "Meeting with Priya" in lead or "Atlas scope" in lead, lead


# 3. One rule for "show me my X notes": the verb decides, not whether a tag has the name.

SHOWN = ["show me my {} notes", "show my {} notes", "show me all my {} notes", "show me all of my {} notes", "pull up my {} notes",
         "bring up my {} notes", "get my {} notes", "find my {} notes", "please show me my {} notes", "my {} notes"]
LISTED = ["list my {} notes", "list all my {} notes", "list the {} notes", "notes tagged {}", "show me notes tagged {}", "list my notes in {}"]


@pytest.mark.parametrize("subject", ["baking", "travel", "running", "health"])
@pytest.mark.parametrize("form", SHOWN)
def test_a_show_ask_is_the_overview_where_a_tag_has_the_name(ask, form, subject):
    said = ask(form.format(subject))
    assert re.match(rf"You have \w+ notes about {subject}", said), said
    assert "Here are your" not in said, said


@pytest.mark.parametrize("subject", ["baking", "travel", "running"])
@pytest.mark.parametrize("form", LISTED)
def test_a_list_ask_is_the_listing(ask, form, subject):
    assert re.match(rf"Here are your \w+ notes tagged #{subject}", ask(form.format(subject))), form


@pytest.mark.parametrize("form", SHOWN)
def test_the_same_rule_in_a_notebook_filed_under_university(uni, form):  # noqa: F811
    said = uni(form.format("university"))
    assert re.match(r"You have ten notes about (?:uni|university)", said), said
    assert "tagged #university" not in said, said


@pytest.mark.parametrize("form", LISTED)
def test_the_listing_in_a_notebook_filed_under_university(uni, form):  # noqa: F811
    assert re.match(r"Here are your \w+ notes tagged #university", uni(form.format("university"))), form


@pytest.mark.parametrize("text, lot", [
    ("show me my university notes", True), ("pull up my uni notes", True), ("my uni notes", True), ("get the study notes", True),
    ("list my university notes", False), ("notes tagged university", False), ("show me my pinned notes", False),
    ("show me my recent notes", False), ("show me my latest notes", False), ("my untagged notes", False),
    ("show me all my notes", False), ("what is in my notes", False),
])
def test_the_one_reader_of_a_show_ask(text, lot):
    from tessellate.ai import composer_digest, filed_name

    assert filed_name.shows_the_lot(text) is lot
    assert composer_digest.shows_the_lot(text) is lot


# 5. A timed answer's day lead says how far away the day is, then the day.

TODAY = date(2026, 10, 30)


def _said(days_ago: int, question: str = "what did I do") -> str:
    def run() -> str:
        composer_digest._set_timing(question)  # noqa: SLF001
        return composer_digest._said_day(date(2026, 10, 30).fromordinal(TODAY.toordinal() - days_ago), TODAY)  # noqa: SLF001

    return contextvars.copy_context().run(run)


@pytest.mark.parametrize("days_ago, said", [
    (0, "today"), (1, "yesterday"), (3, "on Tuesday"), (5, "last Sunday"), (8, "a week ago, on 22 October"),
    (14, "two weeks ago, on 16 October"), (22, "three weeks ago, on 8 October"), (40, "back in September"),
    (120, "back in July"), (200, "back in April"), (400, "back in September 2025"),
])
def test_a_day_is_said_by_how_far_back_it_is_then_its_date(days_ago, said):
    assert _said(days_ago) == said


@pytest.mark.parametrize("days_ago, said", [
    (0, "today"), (1, "yesterday"), (22, "on 8 October, about three weeks ago"), (120, "on 2 July, about four months ago"),
])
def test_when_did_i_keeps_the_date_first_and_still_says_how_far(days_ago, said):
    assert _said(days_ago, "when did I do it") == said


def test_a_day_not_yet_gone_stays_a_plain_date():
    def run() -> str:
        composer_digest._set_timing("what did I do")  # noqa: SLF001
        return composer_digest._said_day(date(2026, 11, 4), TODAY)  # noqa: SLF001

    assert contextvars.copy_context().run(run) == "on 4 November"


GYM = [
    {"id": 1, "content": "# Gym\nSquat 80kg for 5, bench 60kg for 5. Gym on Monday, Wednesday and Friday.", "created_at": "2026-09-08T10:00:00", "category": "Fitness", "tags": ["gym"]},
    {"id": 2, "content": "# Gym\nSquat up to 90kg for 5. Knee felt fine.", "created_at": "2026-10-02T10:00:00", "category": "Fitness", "tags": ["gym"]},
]


@pytest.mark.parametrize("question", ["how's the gym going?", "how is my gym going", "how is the gym going", "how's my gym going"])
def test_a_digest_line_never_leads_with_a_bare_date(question):
    text = composer_digest.answer(question, GYM, today=TODAY)["text"]
    assert not re.search(r"(?:^|\n)On \d{1,2} [A-Z][a-z]+,", text), text
    assert re.search(r"(?:Back in September|Seven weeks ago|Six weeks ago|Eight weeks ago)", text) or "ago, on" in text, text


def _who_lines(question: str) -> str:
    notes = [
        {"id": i, "content": f"# T{i}\n\nPriya moved to Leeds in spring.", "tags": [], "category": "x", "created_at": f"2026-09-0{i}T10:00:00"}
        for i in (1, 2, 3)
    ]

    def run() -> str:
        composer_digest._set_timing(question)  # noqa: SLF001
        out = composer_digest._Out()  # noqa: SLF001
        views = [composer.read_note(n, 0) for n in notes]
        assert composer_digest._who(out, "priya", views, set(), TODAY)  # noqa: SLF001
        return "\n".join(out.lines)

    return contextvars.copy_context().run(run)


@pytest.mark.parametrize("question, first", [
    ("when did Priya come up?", "On 1 September, about two months ago, Priya moved to Leeds in spring."),
    ("what date did Priya come up", "On 1 September, about two months ago, Priya moved to Leeds in spring."),
    ("how long ago did Priya come up", "A month ago, on 1 September, Priya moved to Leeds in spring."),
])
def test_a_who_line_says_how_far_back_not_a_bare_date(question, first):
    text = _who_lines(question)
    assert first in text, text
    assert not re.search(r"(?:^|\n)On \d{1,2} [A-Z][a-z]+, Priya", text), text


@pytest.mark.parametrize("question, said", [
    ("what's the latest on baking", "written two weeks ago, on 12 October"),
    ("what's the latest on the Atlas project", "written three weeks ago, on 9 October"),
    ("what's the latest on Atlas", "written today"),
    ("what is the newest on running", "written last Sunday"),
])
def test_a_source_line_says_how_long_ago_it_was_written(ask, question, said):
    text = ask(question)
    assert said in _lead(text), text
    assert not re.search(r"written on \d", text), text


@pytest.mark.parametrize("question, line", [
    ("how many days since the meeting with Priya", "The meeting with Priya was two days ago, on 28 October."),
    ("how many days since the sourdough loaf", "The sourdough loaf was 18 days ago, on 12 October."),
    ("how many days has it been since the meeting with Priya", "The meeting with Priya was two days ago, on 28 October."),
])
def test_a_days_since_answer_says_the_count_then_the_day(ask, question, line):
    said = _lead(ask(question))
    assert said.startswith(line), said
