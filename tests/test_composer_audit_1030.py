"""Composer deep audit 2026-10-30 (docs/roadmap/agent-remaining/audit-1030-composer.md)."""

from __future__ import annotations

from tessellate.ai import composer, spelling


def test_z65_a_typo_is_spell_checked_once_per_question(monkeypatch):
    """"recepie for banan bread" took 10 s: `compare_sides` re-read the
    question for each of its patterns, and every reading spell-checked each
    unknown word against the whole list, uncached."""
    calls = []
    real = composer.rephrase
    monkeypatch.setattr(composer, "rephrase", lambda q: calls.append(q) or real(q))
    composer.compare_sides("recepie for banan bread")
    assert len(calls) == 1
    assert hasattr(spelling._candidates, "cache_info")  # noqa: SLF001
    spelling._candidates.cache_clear()  # noqa: SLF001
    real("recepie for banan bread")
    real("recepie for banan bread")
    assert spelling._candidates.cache_info().hits > 0  # noqa: SLF001


import datetime as dt  # noqa: E402

import pytest  # noqa: E402

from tessellate.ai import composer_digest  # noqa: E402

_N = dt.datetime(2026, 10, 29, 10)
_DID_NOTES = [
    {"id": i, "content": c, "created_at": _N, "updated_at": _N, "category": "Personal"}
    for i, c in enumerate([
        "# Reminders\n\nRemember to pay rent on the 1st. Need to call the bank about the card.",
        "# Conference\n\nThe conference in June was great; met Tom there.",
        "# Bills\n\nPaid the phone bill on 2 October.",
    ], 1)
]


@pytest.mark.parametrize(("question", "lead"), [
    # Z19: a plan is not the doing.
    ("did I pay rent", "Not yet, as far as your notes go. Your note of 29 October only plans it: Remember to pay rent"),
    ("did I call the bank", "Not yet, as far as your notes go."),
    # Z18: writing verbs need only the thing; an irregular past meets its verb.
    ("did I write about the conference", "Yes, your note of 29 October mentions the conference:"),
    ("did I mention Tom", "Yes, your note of 29 October mentions Tom:"),
    ("did I pay the phone bill", "Yes, your note of 29 October says so: Paid the phone bill"),
    # Z18: the no form is a sentence, not the question echoed back.
    ("have I written anything about meditation", "I found nothing in your notes about meditation."),
    ("did I go to the gym", "I found nothing in your notes about the gym."),
])
def test_z18_z19_did_i_answers(question, lead):
    said = composer_digest.answer(question, _DID_NOTES, today=_N.date())["text"]
    assert said.startswith(lead), said
    assert "says you" not in said, said


def test_z60_a_tick_that_ran_says_so_and_asks_no_confirm(client, session):
    """"Tick off the sunscreen" ticked the line, then said "I will mark it
    done" over a card that read "Nothing changes until you confirm"."""
    import json

    from tessellate.entry import manager

    entry = manager.create_entry(session, "# Lisbon packing list\n\n- [x] Passport\n- [ ] Sunscreen\n- [ ] Charger")
    session.commit()
    events = []
    body = {"question": "tick off the sunscreen", "use_tools": True}
    with client.stream("POST", "/chat/stream", json=body) as response:
        events = [json.loads(line) for line in response.iter_lines() if line.strip()]
    acts = [e for e in events if e.get("type") == "act"]
    said = "".join(e["delta"] for e in events if e["type"] == "answer")
    assert acts and acts[-1]["done"] is True, events
    assert not acts[-1]["notice"], acts[-1]
    assert "ticked off “Sunscreen”" in said.replace("“sunscreen”", "“Sunscreen”"), said
    assert " will " not in f" {said} ", said
    session.refresh(entry)
    assert "- [x] Sunscreen" in entry.content


@pytest.mark.parametrize(("question", "framed"), [
    ("how do I turn the oven on", {"turn"}),
    ("how hot is the oven", {"hot"}),
    ("have I seen Arrival", {"seen"}),
    ("what should I mark as done", {"mark"}),
    ("what is the total of my budget", {"total"}),
])
def test_z16_a_questions_frame_words_are_never_called_missing(question, framed):
    """"These notes do not mention “turn”" sat under answers that answered:
    the words that shape a question are not its topic."""
    stems = composer._frame_stems(question)  # noqa: SLF001
    assert {composer._stem(w) for w in framed} <= stems, stems  # noqa: SLF001
    #: The thing asked for after "what" is the topic, and stays checkable.
    assert composer._stem("hotel") not in composer._frame_stems("What hotel is near the Porto lodge?")  # noqa: SLF001


_PEOPLE = [
    {"id": i, "content": c, "created_at": _N - dt.timedelta(days=i), "updated_at": _N - dt.timedelta(days=i), "category": "Personal"}
    for i, c in enumerate([
        "# Tom\n\nMet Tom at the conference in June. He works on the data team at Atlas. Likes climbing.",
        "# Priya\n\nOn 28 October we talked about the Atlas scope. Priya is the product lead for Atlas.",
        "# Goals\n\nQ1: run a 10k, read 12 books. Q2: learn Spanish basics.",
    ], 1)
]


@pytest.mark.parametrize(("question", "lead", "absent"), [
    # Z12: the sentence that says the work leads.
    ("what does Priya do", "Priya is the product lead for Atlas", None),
    ("what is Tom's job", "He works on the data team at Atlas", None),
    ("where does Tom work", "He works on the data team at Atlas", None),
    # A labelled list keeps every item, and a named label keeps to itself.
    ("what are my goals for Q1", "From your Goals note: run a 10k, read 12 books.", "Spanish"),
    ("what are my Q2 goals", "From your Goals note: learn Spanish basics.", "10k"),
])
def test_z12_the_asked_property_or_label_leads(question, lead, absent):
    said = composer_digest.answer(question, _PEOPLE, today=_N.date())["text"]
    assert said.startswith(lead), said
    assert absent is None or absent not in said, said


def test_to_dos_written_as_sentences_answer_what_is_left():
    """2026-10-30 probe: "what do I need to do for the trip" said no checklist
    had anything left, beside "Book the train to Leeds and then draft the
    itinerary"."""
    notes = [{"id": 1, "content": "# Trip plan\n\nBook the train to Leeds and then draft the itinerary for Sam.",
              "created_at": _N, "updated_at": _N, "category": "Personal"}]
    said = composer_digest.answer("what do I need to do for the trip", notes, today=_N.date())["text"]
    assert said.startswith("There is no checklist for it, but Trip plan has this to do:"), said
    assert "Book the train to Leeds" in said, said
