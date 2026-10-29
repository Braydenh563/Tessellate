"""The composed answer from the notes (INBOX 688, `ai/composer.py`).

The rule under test, the brief's own words: every factual clause in a composed
answer is either the person's own words (a quoted or lightly trimmed sentence
from a note, cited) or a number or date the app measured; only connective
tissue comes from templates. `assert_traceable` checks that of every answer
these tests produce, part by part, against the notes the answer was given.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

import pytest

from tessellate.ai import composer
from tests import _composer_eval as ev

TODAY = date(2026, 10, 6)
#: Spelled by its code point: the lint reads this file too.
EM_DASH = chr(0x2014)


def _note(note_id: int, content: str, days_ago: int, **extra) -> dict:
    return {
        "id": note_id,
        "content": content,
        "created_at": (TODAY - timedelta(days=days_ago)).isoformat(),
        **extra,
    }


NOTES = [
    _note(1, "# Harbor launch plan\n\nShip the mobile app to the public on the 14th of next month. "
          "Three gates before then: beta feedback closed, the onboarding rewrite merged, and the "
          "pricing page signed off.\n\n- [x] Beta invite list\n- [x] Crash reporting\n- [ ] Store listing copy", 30),
    _note(2, "# Beta feedback, week 2\n\n41 testers active. The top complaint is the sign-up flow "
          "(nine fields). So, offline mode is hard to find.", 20),
    _note(3, "# Public API, maybe\n\nThree people in the beta asked for one. Not before launch.", 12),
    _note(4, "# Dentist\n\nCheck-up booked for the 21st. Ask about the night guard.", 9),
    _note(5, "# Reading list\n\n- Designing Data-Intensive Applications\n- The Mom Test\n- A Pattern Language", 40),
    _note(6, "# Lisbon, where to stay\n\nAlfama has the walk-everywhere feel, but the hills are steep. "
          "Príncipe Real is quieter and close to the metro.", 25),
    _note(7, "# Porto, three days\n\nRibeira at sunset, and a port lodge tour across the bridge in Gaia.", 24),
    _note(8, "# Why the list felt slow\n\nIt was not the database. Every row re-measured its own height on "
          "scroll. Caching the height per row took a long list from 40ms a frame to 6.", 15),
    _note(9, "# Sync rewrite, first notes\n\nThe conflict rule is last-writer-wins today, which silently "
          "drops edits. Proposal: keep both versions and ask.", 50),
    _note(10, "# Sync rewrite, week 3\n\nThe sync rewrite now keeps both versions and asks. Merged behind a flag.", 3),
    _note(11, "# Offline as the headline\n\nBeta testers did not know Harbor works offline.", 10),
    _note(12, "# Standup\n\nThe launch date is the 14th of next month.", 5),
    _note(13, "# Standup again\n\nThe launch date is the 21st of next month, moved a week.", 1),
    _note(14, "Note with no heading about the garden shed roof. It leaks in the north corner.", 2),
]


def assert_traceable(result: dict, question: str, notes: list[dict], asked_from: str = "") -> None:
    """Every part of the answer is a template, a quote of the note it names, a
    note's name, a measured value or a word of the question; and the parts are
    the whole text, so nothing can sit between them unchecked. The check is
    the eval's (`tests/_composer_eval.py`), so the gate and the measure are
    one definition. The suggested next questions are held to it too."""
    failures = ev.trace_failures(result, question, notes, TODAY, asked_from)
    for parts in result.get("next_parts") or []:
        failures += ev.trace_failures(
            {"parts": parts, "text": "".join(p[1] for p in parts), "grounding": []}, question, notes, TODAY, asked_from
        )
    assert failures == [], failures


def ask(question: str, notes=NOTES, **kwargs) -> dict:
    result = composer.compose(question, notes, today=TODAY, **kwargs)
    assert_traceable(result, question, notes)
    return result


# --- the question --------------------------------------------------------------


@pytest.mark.parametrize(
    ("question", "shape"),
    [
        ("What is the Harbor launch plan?", "what"),
        ("When is the dentist check-up?", "when"),
        ("Who asked for a public API?", "who"),
        ("How many beta testers are active?", "count"),
        ("Which books are on my reading list?", "list"),
        ("Compare Lisbon and Porto", "compare"),
        ("Lisbon vs Porto", "compare"),
        ("Why did the list feel slow?", "explain"),
        ("How do I make pizza?", "explain"),
        ("What is the latest on the sync rewrite?", "status"),
        ("Does Harbor work offline?", "yesno"),
        ("tell me about the garden", "what"),
    ],
)
def test_the_shape_is_read_from_the_wording(question, shape):
    assert composer.classify(question) == shape


def test_the_subject_drops_the_asking_words():
    assert composer.subject_terms("What is the latest on the sync rewrite?") == ["sync", "rewrite"]
    assert "feel" not in composer.subject_terms("Why did the list feel slow?")


def test_compare_finds_both_sides():
    assert composer.compare_sides("Compare Lisbon and Porto") == ("Lisbon", "Porto")
    assert composer.compare_sides("What is the difference between Lisbon and Porto?") == ("Lisbon", "Porto")
    assert composer.compare_sides("Lisbon vs Porto") == ("Lisbon", "Porto")


# --- the notes, as sentences ----------------------------------------------------


def test_a_note_reads_as_sentences_and_items_with_offsets():
    view = composer.read_note(NOTES[0], 0)
    assert view.title == "Harbor launch plan"
    texts = [s.text for s in view.sentences]
    assert texts[0] == "Ship the mobile app to the public on the 14th of next month."
    assert texts[1].startswith("Three gates before then")
    tasks = [s for s in view.sentences if s.kind == "task"]
    assert [(s.text, s.done) for s in tasks] == [
        ("Beta invite list", True),
        ("Crash reporting", True),
        ("Store listing copy", False),
    ]
    for s in view.sentences:
        assert NOTES[0]["content"][s.start:s.end] == s.text


def test_a_leading_discourse_word_is_trimmed_and_the_offsets_follow():
    view = composer.read_note(NOTES[1], 0)
    last = view.sentences[-1]
    assert last.text == "Offline mode is hard to find."
    assert NOTES[1]["content"][last.start:last.end] == "offline mode is hard to find."


def test_a_note_without_a_heading_is_named_by_its_first_words():
    view = composer.read_note(NOTES[13], 0)
    #: Cut at a word, and never on a dangling "the" (audit 1029 C9): the
    #: intent, a name from the first words, is unchanged.
    assert view.title == "Note with no heading about…"
    #: Its first sentence is still quotable: the name is not the body.
    assert view.sentences[0].text.startswith("Note with no heading")


def test_a_long_sentence_is_cut_at_a_word_and_says_so():
    long = "This sentence goes on " + "and on " * 80 + "until it ends."
    view = composer.read_note(_note(99, f"# Long\n\n{long}", 1), 0)
    text = view.sentences[0].text
    assert text.endswith("…") and len(text) <= composer.MAX_QUOTE_CHARS + 1


# --- composition, one test per shape ----------------------------------------------


def _first_line(result: dict) -> str:
    return result["text"].split("\n", 1)[0]


def test_what_leads_with_the_note_named_by_the_question_and_shows_its_checklist():
    result = ask("What is the Harbor launch plan?")
    text = result["text"]
    first = _first_line(result)
    assert "**Harbor launch plan**" in first
    #: INBOX 725: the first line is the answer, the note's sentence on it.
    assert "Ship the mobile app to the public on the 14th of next month." in first
    assert "Its checklist has two of three done:\n\n- [x] Beta invite list\n- [x] Crash reporting\n- [ ] Store listing copy" in text
    assert result["support"]["ratio"] == 1.0 and not result["support"]["low"]


def test_when_leads_with_the_dated_sentence():
    first = _first_line(ask("When is the dentist check-up?"))
    #: INBOX 741: the sentence first, the note named once after it.
    assert first == "Check-up booked for the 21st. [**Dentist**]" or first.endswith(": Check-up booked for the 21st. [**Dentist**]")


def test_when_without_a_date_in_the_sentence_says_the_day_it_was_written():
    notes = [_note(1, "# Flights\n\nBooked, seats 14A and 14B on the evening plane.", 4)]
    result = ask("When did I book the flights?", notes)
    assert _first_line(result) == (
        "On 2 October you wrote: Booked, seats 14A and 14B on the evening plane. [**Flights**]"
    )


def test_when_lists_the_other_notes_in_the_order_they_were_written():
    notes = [
        _note(1, "# Boiler\n\nThe boiler service is booked for 3 March.", 30),
        _note(2, "# Engineer\n\nThe boiler service engineer is coming on Tuesday.", 2),
        _note(3, "# Boiler history\n\nThe last boiler service, in 2023, replaced the valve.", 60),
    ]
    result = ask("When is the boiler service?", notes)
    text = result["text"]
    heading = next(w for w in composer.phrase_options("timeline") if w in text)
    timeline = text.split(heading, 1)[1]
    days = re.findall(r"^- (\d+ \w+): ", timeline, re.M)
    parsed = [date(2026, composer._MONTH_INDEX[d.split()[1].lower()], int(d.split()[0])) for d in days]
    assert len(parsed) == 2 and parsed == sorted(parsed)


def test_who_quotes_the_sentence_that_names_who():
    assert "Three people in the beta asked for one." in _first_line(ask("Who asked for a public API?"))


def test_count_leads_with_the_figure():
    first = _first_line(ask("How many beta testers are active?"))
    assert "**Beta feedback, week 2**" in first
    assert ": 41 testers active." in first


def test_list_answers_with_the_persons_own_list():
    result = ask("Which books are on my reading list?")
    #: Short entries read as one sentence, the person's words, counted.
    assert result["text"].startswith(
        "Your note **Reading list** lists three: Designing Data-Intensive Applications, The Mom Test and A Pattern Language."
    )


def test_a_list_of_sentences_stays_a_list():
    notes = [_note(1, "# Launch risks\n\n1. The store review takes longer than a week.\n2. Sync conflicts surface "
                      "under real load.\n3. The pricing page is not signed off in time.", 2)]
    result = ask("What are the launch risks?", notes)
    assert result["text"].startswith("Your note **Launch risks** lists three:\n\n- The store review")


def test_a_list_of_plain_phrases_reads_in_sentence_case():
    notes = [_note(1, "# Packing list\n\n- Walking shoes with grip\n- A light jacket\n- Plug adapter", 2)]
    result = ask("What should I pack?", notes)
    assert "lists three: walking shoes with grip, a light jacket and plug adapter." in result["text"]
    assert {row["sentence"] for row in result["grounding"]} == {"walking shoes with grip", "a light jacket", "plug adapter"}


def test_compare_draws_two_sides_with_measured_counts():
    result = ask("Compare Lisbon and Porto")
    text = result["text"]
    assert text.startswith(
        tuple(
            f"{lead}one mentions Lisbon and one mentions Porto.\n\n**Lisbon**\n"
            for lead in composer.phrase_options("of_found") + composer.phrase_options("across_found")
        )
    ), text
    #: The lead names only what follows (probe P15, ledger row 443): no
    #: sentence promising the sides before the sides, under 14 words.
    assert len(text.split("\n", 1)[0].split()) <= 14, text
    #: Each side's count is said once, by the lead (decision 52), not again
    #: beside its heading.
    assert "**Lisbon**\n" in text and "**Porto**\n" in text and "(one note)" not in text
    lisbon, porto = text.split("**Porto**", 1)
    assert "Alfama" in lisbon and "Ribeira" in porto


def test_explain_keeps_the_notes_sentences_in_their_own_order():
    first = _first_line(ask("Why did the list feel slow?"))
    assert first.endswith(
        "It was not the database. Every row re-measured its own height on scroll. "
        "Caching the height per row took a long list from 40ms a frame to 6. [**Why the list felt slow**]"
    )


def test_status_leads_with_the_newest_and_walks_back_through_the_earlier():
    result = ask("What is the latest on the sync rewrite?")
    text = result["text"]
    first = _first_line(result)
    assert "**Sync rewrite, week 3**" in first and "3 October" in first
    assert "the sync rewrite now keeps both versions and asks." in first.lower()
    #: Any of the "before that" variants: the order is the point, not the wording.
    assert any(f"\n\n{w}17 August, the conflict rule" in text for w in composer.phrase_options("before_that"))
    assert "[**Sync rewrite, first notes**]" in text


def test_yes_no_never_answers_yes_or_no():
    result = ask("Does Harbor work offline?")
    first = _first_line(result)
    #: INBOX 741: a sentence holding every word asked is said as the notes'
    #: answer ("Going by your notes, ..."), never as a yes or a no.
    assert first.startswith(
        tuple(text for key in ("closest_a", "closest_b", "going_by", "notes_have") for text in composer.phrase_options(key))
    )
    assert "Beta testers did not know Harbor works offline." in first
    assert not re.search(r"\b(yes|no)\b[,.]", result["text"].split("\n\n", 1)[0], re.I)


def test_two_notes_that_may_disagree_are_said_as_a_but():
    result = ask("What is the launch date?")
    text = result["text"]
    assert "**Standup**" in _first_line(result)
    assert any(f"\n\n{w}, the launch date is the 21st" in text for w in composer.phrase_options("but_newer"))
    assert "[**Standup again**]" in text
    assert any(wording in text for wording in composer.phrase_options("disagree_check"))
    #: Each side said once.
    assert text.lower().count("the launch date is the 21st") == 1 and text.lower().count("the launch date is the 14th") == 1


def test_two_other_notes_that_may_disagree_are_named_older_first():
    notes = [
        _note(1, "# House\n\nThe boiler pressure is what the engineer checks first.", 9),
        _note(2, "# Monday\n\nThe boiler pressure was at 1.5 bar this morning.", 6),
        _note(3, "# Friday\n\nThe boiler pressure was at 0.8 bar this morning.", 2),
    ]
    text = ask("What about the boiler pressure?", notes)["text"]
    lead = next(w for w in composer.phrase_options("disagree_lead") if w in text)
    pair = text.split(lead, 1)[1]
    but = next(w for w in composer.phrase_options("but_newer") if w in pair)
    assert pair.index("**Monday**") < pair.index(but) < pair.index("**Friday**")


def test_words_no_note_found_holds_are_named_in_the_closing_line():
    result = ask("What hotel is near the Porto lodge?")
    assert result["text"].endswith(tuple(f"{w}“hotel”." for w in composer.phrase_options("missing")))


def test_the_closing_line_is_left_out_when_nothing_matched_at_all():
    result = ask("What is the capital of Peru?")
    #: Engine probe P1: the no-answer names the words no note found holds.
    #: One of eight leads and eight questions back (the owner: "can it have more varied responses??").
    lead = next(w for w in composer.phrase_options("none_found") if result["text"].startswith(w))
    assert result["text"][len(lead):].startswith("“capital” or “Peru”. ")
    assert result["text"].endswith(tuple(composer.phrase_options("nothing_ask")))
    assert result["grounding"] == [] and result["next"] == []


def test_the_newest_notes_for_a_question_with_no_subject():
    newest = sorted(NOTES, key=lambda n: n["created_at"], reverse=True)
    result = ask("what did I write recently", newest, recent=True)
    assert result["shape"] == "recent"
    assert result["text"].startswith("Your five newest notes, from 27 September to yesterday:")
    assert result["text"].count("\n- ") == 5


def test_near_duplicates_are_dropped():
    notes = [
        _note(1, "# A\n\nThe boiler pressure keeps dropping to 0.8 bar.", 3),
        _note(2, "# B\n\nThe boiler pressure keeps dropping to 0.8 bar again.", 2),
    ]
    result = ask("What about the boiler pressure?", notes)
    assert result["text"].count("keeps dropping") == 1


def test_a_connected_note_ranks_below_a_matching_one():
    notes = [
        _note(1, "# Linked\n\nThe boiler pressure was fine in May.", 3, connected=True),
        _note(2, "# Boiler\n\nThe boiler pressure keeps dropping.", 2),
    ]
    result = ask("What about the boiler pressure?", notes)
    assert "**Boiler**" in result["text"].split("\n", 1)[0]


# --- the grounding --------------------------------------------------------------


def test_every_quote_is_cited_once_with_its_exact_span():
    result = ask("What is the Harbor launch plan?")
    sentences = [row["sentence"] for row in result["grounding"]]
    assert len(sentences) == len(set(sentences))
    assert all(row["verdict"] == "supported" for row in result["grounding"])
    assert all(row["note_id"] in {n["id"] for n in NOTES} for row in result["grounding"])


def test_support_counts_the_quotes_not_the_connective_words():
    result = ask("Why did the list feel slow?")
    #: Three quotes; the first ("It was not the database.") is under
    #: `grounding.MIN_SENTENCE_WORDS` and is counted in neither half, as for
    #: any answer.
    assert len(result["grounding"]) == 3
    assert result["support"]["supported"] == result["support"]["sentences"] == 2
    assert result["support"]["unsupported"] == []


# --- fluency without invention -------------------------------------------------------


def test_the_same_question_composes_the_same_answer():
    assert ask("What is the Harbor launch plan?")["text"] == ask("What is the Harbor launch plan?")["text"]


def test_openings_vary_across_questions():
    openings = {
        ask(q)["text"].split("**", 1)[0]
        for q in (
            "What is the Harbor launch plan?",
            "What about the public API?",
            "Tell me about the dentist",
            "What about Lisbon?",
            "What did the beta feedback say?",
            "What about the reading list?",
        )
    }
    assert len(openings) >= 2


@pytest.mark.parametrize("phrase", list(composer.PHRASES.values()))
def test_every_phrase_follows_the_copy_rules(phrase):
    assert EM_DASH not in phrase and "!" not in phrase
    assert "Oops" not in phrase
    letters = phrase.strip(" -*>“”():,.\n")
    if letters and letters[0].isalpha() and phrase[0].isalpha():
        #: The phrases that only ever follow other words: "or", "one of
        #: your notes" and "your note" inside a citation's brackets.
        #: And a source's kind, said inside a citation's bracket before its
        #: name ("[board **Harbor board**]", CHAT_PLAN decision 37).
        assert letters[0].isupper() or phrase.startswith(("a ", "one", "or", "your note", "board ", "map ", "document ", "file ", "page ")), phrase


def test_the_rule_holds_over_a_sweep_of_questions():
    """Every answer to a spread of questions passes the traceability check
    (`ask` runs it), whatever shape the question takes."""
    for question in (
        "what about offline",
        "how much did the API cost",
        "who is on the beta",
        "which tasks are done for the launch",
        "is the sync rewrite merged",
        "how do I fix the slow list",
        "what is the status of the dentist",
        "when are the gates",
        "garden shed roof",
        "difference between Alfama and Príncipe Real",
    ):
        ask(question)


def test_a_notes_tags_say_what_it_is_about_without_being_quoted():
    """"Reading list", tagged books, answers "which books am I reading" though
    no line of it says "book"; the tag picks the note and is never quoted."""
    notes = [
        _note(1, "# Reading list\n\n- Designing Data-Intensive Applications\n- The Mom Test", 5, tags=["books"]),
        _note(2, "# Teach what I just learned\n\nWrite a short post after each book I am reading.", 3),
    ]
    result = ask("Which books am I reading?", notes)
    assert result["text"].startswith("Your note **Reading list** lists two:")
    assert "books" not in result["text"].split("\n", 1)[1].lower().replace("**", "")


def test_the_word_list_is_a_subject_unless_it_opens_the_question():
    assert composer.subject_terms("Why did the list feel slow?") == ["list", "slow"]
    assert composer.subject_terms("List my books") == ["books"]


def test_a_sentence_that_leans_back_brings_the_one_it_leans_on():
    notes = [
        _note(1, "# Main\n\nThe beta testers are the subject here, all of them active.", 4),
        _note(2, "# Teach\n\nWrite a short post after each book. It keeps the beta testers reading.", 3),
    ]
    result = ask("What about the beta testers?", notes)
    #: After a joiner its first letter may be lowered ("Elsewhere, write ...").
    assert "rite a short post after each book. It keeps the beta testers reading." in result["text"]


def test_closest_match_wording_is_kept_for_the_first_result() -> None:
    """INBOX 724: the lead said "The closest match is your note" about the
    third note found. INBOX 741 took every "Your note ... says" opening out,
    so no phrase calls any note the closest match."""
    assert not any("closest match" in value for value in composer.PHRASES.values())


def test_an_answer_no_model_wrote_says_so_in_its_support_notice() -> None:
    """INBOX 724: "this message needs to be altered as a model wasnt used"."""
    from pathlib import Path

    routes = Path("src/tessellate/api/routes_chat.py").read_text(encoding="utf-8")
    assert routes.count('"by_model": False') >= 1
    js = Path("frontend/js/capture-ask.js").read_text(encoding="utf-8")
    body = js[js.index("function renderAnswerSupport") :]
    body = body[: body.index("\n}\n")]
    assert "support.by_model === false" in body and "no model wrote any of it" in body


def test_a_grounding_row_carries_the_title_the_answer_cites() -> None:
    """2026-10-10 triage, decision 5: the page makes "[**Dentist**]" open the
    note, matching the name exactly from the row rather than from its label."""
    result = ask("When is the dentist check-up?")
    assert "[**Dentist**]" in result["text"]
    assert {row["title"] for row in result["grounding"]} >= {"Dentist"}
    untitled = ask("What about the hotel?", [_note(1, "the hotel is booked for May, near the river.", 2)])
    assert all(row["title"] == "" for row in untitled["grounding"])


def test_a_cited_name_opens_its_note_and_never_the_sources_panel() -> None:
    from pathlib import Path

    js = Path("frontend/js/ask-compose.js").read_text(encoding="utf-8")
    body = js[js.index("function linkCitedTitles") :]
    body = body[: body.index("\n}\n")]
    assert "flashEntry(g.note_id)" in body and "scheduleCitationPeek(" in body
    assert "source" not in body.lower().replace("citationsource", "")
    caller = Path("frontend/js/capture-ask.js").read_text(encoding="utf-8")
    assert "linkCitedTitles(targets, sentences, byId, numberFor);" in caller
    assert caller.index('ensureModule("askCompose").then(() => {') < caller.index("linkCitedTitles(targets, sentences, byId, numberFor);")
