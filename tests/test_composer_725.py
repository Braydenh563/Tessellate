"""The composed answer, as close to a chat bot as the rule allows (INBOX 725).

The owner, 2026-10-06: "make them something the world hasnt seen before like
stringing sentences together based off meaning, similarity etc." Each test is
one of the brief's ideas, kept because the eval measured it earning its place
(`tests/test_composer_eval_725.py`), and every answer here passes the same
traceability check as INBOX 688's (`assert_traceable`).
"""

from __future__ import annotations

import re

import pytest

from tessellate.ai import composer, composer_tables
from tessellate.ai import composer_dialogue
from tessellate.ai import composer_read
from tessellate.ai import composer_select
from tests.test_composer_688 import NOTES, TODAY, _note, assert_traceable
from tests._app_js import with_pieces


def ask(question: str, notes=NOTES, **kwargs) -> dict:
    result = composer.compose(question, notes, today=TODAY, **kwargs)
    assert_traceable(result, question, notes)
    return result


# --- lead-ins and stems ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("sentence", "kept"),
    [
        ("So basically, the API is slow.", "The API is slow."),
        ("Ok so basically, it works offline.", "It works offline."),
        ("Basically the hills are steep.", "The hills are steep."),
        ("Note to self: buy the adapter.", "Buy the adapter."),
        ("Honestly, the green wins.", "The green wins."),
        ("To be honest the green wins.", "The green wins."),
        #: A contrast or a time word with no comma is part of the claim.
        ("But the API is slow.", "But the API is slow."),
        ("Now the list scrolls smoothly.", "Now the list scrolls smoothly."),
        #: A bare lead-in before a name is left: it may be the name's sentence.
        ("Basically Lisbon wins on food.", "Basically Lisbon wins on food."),
    ],
)
def test_lead_ins_come_off_a_quote_from_the_tested_list(sentence, kept):
    content = f"# Note\n\n{sentence}"
    view = composer.read_note(_note(1, content, 1), 0)
    unit = view.sentences[0]
    assert unit.text == kept
    #: The offsets follow the trim: the row still points at the note's words.
    assert content[unit.start:unit.end].lower() == kept.lower()


def test_every_listed_lead_in_is_trimmed_with_its_comma():
    for lead in composer_read.LEAD_INS:
        view = composer.read_note(_note(1, f"# N\n\n{lead.capitalize()}, the boiler pressure dropped.", 1), 0)
        assert view.sentences[0].text == "The boiler pressure dropped.", lead


@pytest.mark.parametrize(
    ("a", "b"),
    [("running", "run"), ("runs", "run"), ("hiring", "hire"), ("stopped", "stop"), ("making", "make"), ("sketches", "sketch")],
)
def test_word_forms_meet(a, b):
    assert composer._stem(a) == composer._stem(b)


def test_a_note_is_never_a_negation():
    assert composer._stem("note") != composer._stem("not")
    assert composer._stem("notes") != composer._stem("not")


@pytest.mark.parametrize(
    ("a", "b"),
    [("business", "busy"), ("university", "universe"), ("general", "generous"), ("organ", "organisation")],
)
def test_unrelated_words_do_not_meet(a, b):
    """The stemmer's rule (`_stem`: "a stemmer that turned news into new
    would match the wrong notes"), held for the collisions a full Porter
    stemmer makes:
    "business" and "busy" are both "busi" to it, and "university" and
    "universe" both "univers" (2026-10-10 triage, decision 3: the vendored
    Porter stemmer measured no gain on the eval and fails this)."""
    assert composer._stem(a) != composer._stem(b)


# --- redundancy ---------------------------------------------------------------------


def test_a_sentence_several_notes_repeat_is_said_once_and_counted():
    notes = [
        _note(1, "# Standup\n\nThe launch date is the 14th of next month.", 5),
        _note(2, "# Planning\n\nThe launch date is the 14th of next month, as agreed.", 4),
        _note(3, "# Email\n\nThe launch date is the 14th of next month, the email says.", 3),
    ]
    result = ask("What is the launch date?", notes)
    text = result["text"]
    assert text.count("The launch date is the 14th") == 1
    assert "(Your notes say this three times.)" in text


# --- meaning ------------------------------------------------------------------------


def _fake_embed(texts: list[str]) -> list[list[float]]:
    """A deterministic stand-in for the embedder: a sentence about the boiler
    points one way, anything else another, so cosine says what a model would
    about these four sentences."""
    vectors = []
    for text in texts:
        boiler = 1.0 if "boiler" in text.lower() or "pressure" in text.lower() else 0.0
        vectors.append([boiler, 1.0 - boiler, len(text) % 3 * 0.01])
    return vectors


def test_meaning_from_the_embedder_finds_a_paraphrase_shared_words_miss():
    notes = [
        _note(1, "# Boiler\n\nThe boiler pressure keeps dropping to 0.8 bar.", 3),
        _note(2, "# Heating\n\nPressure in the heating loop falls every week.", 2),
    ]
    lexical = composer._Meaning(composer.read_note(notes[0], 0).sentences + composer.read_note(notes[1], 1).sentences, None)
    meant = composer._Meaning(composer.read_note(notes[0], 0).sentences + composer.read_note(notes[1], 1).sentences, _fake_embed)
    a, b = composer.read_note(notes[0], 0).sentences[0], composer.read_note(notes[1], 1).sentences[0]
    assert meant.same_topic(a, b) and not lexical.same_topic(a, b)


def test_an_embedder_that_fails_falls_back_to_words():
    def broken(texts):
        raise RuntimeError("no backend")

    result = ask("What about the boiler pressure?", [_note(1, "# Boiler\n\nThe boiler pressure keeps dropping.", 3)], embed=broken)
    assert "The boiler pressure keeps dropping." in result["text"]


def test_the_embedder_changes_nothing_the_rule_holds():
    for question in ("What is the Harbor launch plan?", "What is the launch date?", "Does Harbor work offline?"):
        ask(question, embed=_fake_embed)


def test_textrank_prefers_the_sentence_the_others_lean_towards():
    notes = [
        _note(1, "# A\n\nSourdough needs a strong starter and a long cold proof.", 3),
        _note(2, "# B\n\nA long cold proof gives sourdough its open crumb.", 2),
        _note(3, "# C\n\nThe starter lives in the fridge on weekdays.", 1),
    ]
    views = [composer.read_note(n, i) for i, n in enumerate(notes)]
    pool = [v.sentences[0] for v in views]
    for s in pool:
        s.score = 1.0
    rank = composer_select.centrality(pool, composer._Meaning(pool, None, {"sourdough"}))
    assert max(pool, key=lambda s: rank[s.key]).note_id == 1


# --- joining by relation ---------------------------------------------------------------


def test_a_second_note_on_the_subject_is_said_with_no_also():
    notes = [
        _note(1, "# Week 2\n\n41 beta testers active this week.", 20),
        _note(2, "# Offline\n\nBeta testers active in the forum did not know the app works offline.", 10),
        _note(3, "# Store\n\nFive screenshots for the store page, dark and light.", 9),
    ]
    text = ask("How many beta testers are active?", notes)["text"]
    second = text.split("\n\n")[1]
    #: INBOX 741: the sentence itself, its note named after it, never
    #: "**Offline** also says:".
    assert "Beta testers active in the forum did not know the app works offline. From your **Offline** note." in second
    assert not second.startswith("**Offline**") and "says" not in second


def test_the_same_joining_words_never_come_twice_in_one_answer():
    joiners = {composer.PHRASES[k] for k in ("and_join", "on_top", "separately", "elsewhere", "another_note", "later_on", "then_on")}
    for question in ("Which books am I reading?", "What is the Harbor launch plan?", "What do my notes say about the beta?"):
        parts = [p[1] for p in ask(question)["parts"] if p[0] == "template"]
        joins = [p for p in parts if p in joiners]
        assert len(joins) == len(set(joins)), joins


# --- question-shaped openings ---------------------------------------------------------


def test_a_broad_question_opens_with_how_many_notes_mention_it():
    notes = [
        _note(1, "# Sourdough log\n\nLoaf 6 had the best crumb yet.", 30, tags=["sourdough"]),
        _note(2, "# Pizza night\n\nThe sourdough discard makes a good thin base.", 3),
        _note(3, "# Starter feeding\n\nFeed it at night, ready by morning.", 33, tags=["sourdough"]),
    ]
    result = ask("What do I know about sourdough?", notes)
    first = result["text"].split("\n", 1)[0]
    #: The lead and its middle are a pair with variants (decision 51's floor).
    leads = composer_tables.VOICE_VARIANTS["natural"]["mention_lead"]
    mids = composer_tables.VOICE_VARIANTS["natural"]["mention_mid"]
    said = tuple(f"{composer.PHRASES[a]}three{composer.PHRASES[b]}“sourdough”, from 3 September to 3 October." for a, b in zip(leads, mids))
    assert first.startswith(said), first
    #: The note named for the subject leads, and every note counted is quoted.
    assert "**Sourdough log**" in first
    assert {row["note_id"] for row in result["grounding"]} == {1, 2, 3}


def test_a_connected_note_is_not_counted_as_mentioning_it():
    notes = [
        _note(1, "# Sourdough log\n\nLoaf 6 had the best crumb.", 30, tags=["sourdough"]),
        _note(2, "# Pizza\n\nThe sourdough discard makes a base.", 3, connected=True),
    ]
    assert "At least" not in ask("What do I know about sourdough?", notes)["text"]


# --- pictures ------------------------------------------------------------------------


PICTURE_NOTE = _note(
    1,
    "# Sketches\n\n![](/media/abc.png)\n\n[Pictures in this note, as this app read them:\n"
    "- bean.png: shows a blue bean drawn in pen; text in it: \"bean v2\"]",
    3,
)


def test_a_pictures_reading_is_introduced_as_the_picture():
    view = composer.read_note(PICTURE_NOTE, 0)
    kinds = [(s.kind, s.text) for s in view.sentences]
    assert ("picture", "a blue bean drawn in pen") in kinds and ("picture_text", "bean v2") in kinds
    assert not any(s.text.startswith("[Pictures") for s in view.sentences)
    result = ask("What does the bean sketch show?", [PICTURE_NOTE])
    #: Its words are said with it, never as a second sentence naming the
    #: picture again (INBOX 787).
    assert "The picture in **Sketches** shows a blue bean drawn in pen, which reads “bean v2”." in result["text"]
    row = next(r for r in result["grounding"] if r["sentence"] == "a blue bean drawn in pen")
    assert PICTURE_NOTE["content"][row["start"]:row["end"]] == "a blue bean drawn in pen"


# --- what to ask next -----------------------------------------------------------------


def test_next_questions_come_from_what_the_answer_found_and_did_not_say():
    notes = [
        _note(1, "# Beta feedback\n\n41 beta testers active this week.", 20, tags=["harbor", "beta"]),
        _note(2, "# Offline headline\n\nBeta testers did not know Harbor works offline.", 10, tags=["harbor"]),
        _note(3, "# Launch plan\n\nThe beta closes before the launch, testers thanked by email.", 12, tags=["harbor"]),
    ]
    result = ask("How many beta testers are active?", notes, )
    assert 1 <= len(result["next"]) <= 3
    assert "What else do my notes say about harbor?" in result["next"]
    for question in result["next"]:
        assert question.endswith("?") and len(question) <= composer_dialogue.NEXT_MAX_CHARS


def test_no_next_question_offers_what_was_asked():
    result = ask("What is the Harbor launch plan?")
    assert not any("Harbor launch plan”" in q for q in result["next"])


# --- conversation memory ---------------------------------------------------------------


def test_tell_me_more_is_the_last_question_again_with_what_it_said_left_out():
    first = ask("What is the Harbor launch plan?")
    follow = composer.follow_on("tell me more", [{"question": "What is the Harbor launch plan?", "answer": first["text"]}])
    assert follow.kind == "more" and follow.question == "What is the Harbor launch plan?"
    more = composer.compose(follow.question, NOTES, today=TODAY, said=follow.said)
    assert_traceable(more, follow.question, NOTES)
    said = {row["sentence"] for row in first["grounding"]}
    assert said and not said & {row["sentence"] for row in more["grounding"]}


def test_the_second_one_is_the_second_note_the_last_answer_named():
    history = [{"question": "Compare Lisbon and Porto", "answer": ask("Compare Lisbon and Porto")["text"]}]
    follow = composer.follow_on("what about the second one?", history)
    assert follow.kind == "ordinal"
    assert follow.question == "what about “Lisbon, where to stay”?"


def test_it_takes_the_last_questions_subject():
    history = [{"question": "When is the dentist check-up?", "answer": "..."}]
    follow = composer.follow_on("when was that written?", history)
    assert follow.kind == "pronoun" and follow.question == "when was dentist check-up written?"


@pytest.mark.parametrize("question", ["What is the Harbor launch plan?", "Which books are on my reading list?"])
def test_a_question_that_stands_alone_is_left_alone(question):
    assert composer.follow_on(question, [{"question": "When is the dentist check-up?", "answer": "x"}]) is None
    assert composer.follow_on("tell me more", []) is None


# --- the chips, in Ask and in Chat -----------------------------------------------------


def test_a_composed_answers_next_questions_are_drawn_as_its_chips():
    """The composed answer's `next` rides on its grounding event and is drawn
    by the next-step strips that already exist, in Ask and in Chat, with no
    model call for them."""
    from pathlib import Path

    ask_js = with_pieces("capture-ask.js")
    assert "composedNext = Array.isArray(event.next) ? event.next : [];" in ask_js
    assert "renderAskFollowups(question, answerRaw, answerMeta?.composed ? composedNext : null);" in ask_js
    chat_js = with_pieces("chat-attach.js")
    assert "composedNext = Array.isArray(event.next) ? event.next : [];" in chat_js
    assert "offerFollowups(bubble, question, answerRaw, t.meta?.composed ? t.composedNext : null);" in chat_js
    routes = Path("src/tessellate/api/routes_chat.py").read_text(encoding="utf-8")
    assert '"next": result["next"],' in routes


# --- Chat with no model -----------------------------------------------------------------


def test_with_no_model_chat_stays_open_and_agent_mode_says_what_it_needs(client):
    """INBOX 725, the owner: "if the composer can respond in the chat, should
    the chat input bar be enabled?? maybe agent mode should be disabled
    though unless needle is used to call tools without an ai"."""
    from pathlib import Path

    markup = Path("frontend/index.html").read_text(encoding="utf-8")
    assert '<textarea id="chat-input"' in markup and '<button id="chat-send">' in markup
    status_js = Path("frontend/js/status.js").read_text(encoding="utf-8")
    #: The gate is one helper since the 2026-10-10 chat list: no model and no Needle.
    assert "return modelStatus?.model_ready === true || !!modelStatus?.tools_engine;" in status_js and "const gated = !agentModeAvailable();" in status_js
    assert "Chat answers from your notes" in status_js and "Chat cannot answer yet" not in status_js
    status = client.get("/models/status").json()
    assert status["ollama_running"] is False and "tools_engine" in status


# Next-question chips and day counts over the notes (ledger rows 410, 441, 444).


@pytest.mark.parametrize("question", ["what are my notes about sourdough", "show me notes on sourdough", "wat r my notes abt sourdough"])
def test_a_next_question_chip_names_the_subject_not_the_word_notes(question):
    """Row 410: "some next-question chips repeat the subject": "What is the
    latest on notes about sourdough?" was offered."""
    import json
    from datetime import date
    from pathlib import Path

    notes = json.loads((Path(__file__).parent / "fixtures" / "composer" / "showcase_725.json").read_text(encoding="utf-8"))["notes"]
    chips = composer.compose(question, notes, today=date(2026, 10, 1))["next"]
    assert chips, question
    assert not [c for c in chips if re.search(r"\bnotes? (?:about|on|abt)\b", c)], chips


_DATED = [
    {"id": 1, "content": "# Dentist\n\nCheck-up booked for 21 October. Ask about the night guard.", "tags": ["health"], "category": "Admin", "created_at": "2026-10-01T10:00:00"},
    {"id": 2, "content": "# Harbor launch\n\nShip the app on the 14th of November.\n\n- [x] Beta feedback\n- [ ] Store listing\n- [ ] Press kit", "tags": ["harbor"], "category": "Work", "created_at": "2026-10-02T10:00:00"},
    {"id": 5, "content": "# Mum birthday\n\nMum turns 60 on 3 December.", "tags": ["family"], "category": "Personal", "created_at": "2025-09-06T10:00:00"},
]


@pytest.mark.parametrize(
    ("question", "lead"),
    [
        ("how many days until the dentist", "Ten days from today, on 21 October"),
        ("hw many days til the dentst", "Ten days from today, on 21 October"),
        ("how many days till my dentist appointment", "Ten days from today, on 21 October"),
        ("how long until the harbor launch", "34 days from today, on 14 November"),
        ("how many dayz until mums bday", "53 days from today, on 3 December"),
    ],
)
def test_days_until_a_day_a_note_names(question, lead):
    """Row 441 (P10): "how many days until the dentist" counts to the day
    the dentist note names, and quotes the sentence that names it. Found
    writing it: "booked for 21 October" read as last year's (the booking is
    past, the day is not), and "on the 14th of November" as the 14th of
    this month."""
    from datetime import date

    said = composer.compose(question, _DATED, today=date(2026, 10, 11))
    assert lead in said["text"], said["text"]
    assert said["grounding"] and "From your **" in said["text"], said["text"]


def test_days_until_something_no_note_dates_is_not_counted():
    from datetime import date

    said = composer.compose("how many days until the standup", _DATED, today=date(2026, 10, 11))
    assert "days from today" not in said["text"], said["text"]


@pytest.mark.parametrize(
    "question",
    ["what is still open on the harbor launch", "whats left to do for harbor", "wat's stil open on the harbor launch", "what do i still need to do for the harbor launch"],
)
def test_what_is_still_open_lists_the_unticked_items(question):
    """Row 444 (P16): "what is still open on X" quoted the whole checklist
    and ended "None of these notes say anything about “open”"; it says how
    many are open and lists only those."""
    from datetime import date

    said = composer.compose(question, _DATED, today=date(2026, 10, 11))["text"]
    assert "Two of three items are still open on **Harbor launch**:" in said, said
    assert "- [ ] Store listing" in said and "- [ ] Press kit" in said and "Beta feedback" not in said, said
    assert "anything about" not in said, said
