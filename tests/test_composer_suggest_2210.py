"""Open-ended requests with no model (22-10 bug doc, Composer rows).

"do smth cool" got "I couldn't find anything on cool" and "open a note" a
search for the word "a". The app asks what was meant, with choices, and for an
action it does not understand it offers the closest ones it does, by shared
words and, when the embedder runs, by meaning.
"""

from __future__ import annotations

import json

import pytest

from tessellate.ai import composer_suggest
from tessellate.entry import manager

TITLES = ["Harbor launch plan", "Dentist", "Sourdough log", "Garden jobs", "Old idea"]


@pytest.mark.parametrize(
    ("question", "kind"),
    [
        ("do smth cool", "vague"),
        ("do something fun", "vague"),
        ("Surprise me", "vague"),
        ("im bored", "vague"),
        ("show me something interesting", "vague"),
        ("open a note", "open"),
        ("Open note", "open"),
        ("please open a note", "open"),
        ("find a note", "find"),
        ("delete a note", "delete"),
        ("pin a note", "pin"),
        ("open the note about the boiler", ""),
        ("what is the harbor launch plan", ""),
        ("do the dishes note", ""),
    ],
)
def test_open_ended_kind(question, kind):
    assert composer_suggest.open_ended(question) == kind


def test_open_a_note_asks_which_and_offers_the_newest():
    out = composer_suggest.reply("open a note", TITLES)
    assert "?" in out["text"]
    assert out["asks"][:4] == [f"Open the note about {t}" for t in TITLES[:4]]


def test_open_a_note_with_no_notes_says_so():
    out = composer_suggest.reply("open a note", [])
    assert "no notes" in out["text"].lower() or "yet" in out["text"].lower()
    assert any("note" in a.lower() for a in out["asks"])


def test_do_something_cool_asks_what_kind_and_offers_choices():
    out = composer_suggest.reply("do smth cool", TITLES)
    assert "?" in out["text"]
    assert "couldn't find" not in out["text"].lower()
    assert 3 <= len(out["asks"]) <= 5
    assert len(set(out["asks"])) == len(out["asks"])


def test_the_choices_change_with_the_seed():
    seen = {tuple(composer_suggest.reply("do smth cool", TITLES, seed=str(i))["asks"]) for i in range(8)}
    assert len(seen) >= 2


def test_closest_actions_by_shared_words():
    ranked = composer_suggest.closest("get rid of the boiler note")
    assert ranked and ranked[0].intent == "delete"
    ranked = composer_suggest.closest("stick the dentist note on top")
    assert any(o.intent == "pin" for o in ranked[:3])


def test_closest_uses_meaning_when_the_embedder_runs():
    # The stub embedder puts "banana" next to the reminder act only.
    def embed(texts):
        out = []
        for t in texts:
            low = t.lower()
            out.append([1.0, 0.0] if ("banana" in low or "remind" in low) else [0.0, 1.0])
        return out

    ranked = composer_suggest.closest("banana", embed=embed)
    assert ranked[0].intent == "reminder"


def test_a_broken_embedder_falls_back_to_words():
    def embed(texts):
        raise RuntimeError("no backend")

    ranked = composer_suggest.closest("delete the boiler note", embed=embed)
    assert ranked[0].intent == "delete"


def test_an_unknown_action_offers_the_closest_ones():
    out = composer_suggest.unknown_action("get rid of old stuff", TITLES)
    assert out is not None
    assert "?" in out["text"] or "closest" in out["text"].lower()
    assert out["asks"]


def test_a_question_is_not_an_unknown_action():
    assert composer_suggest.unknown_action("what did I write about the dentist", TITLES) is None


# --- through /chat/stream ------------------------------------------------------------


def _ask(client, question: str, **body) -> dict:
    out = {"text": "", "asks": []}
    with client.stream("POST", "/chat/stream", json={"question": question, **body}) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if not line.strip():
                continue
            event = json.loads(line)
            if event["type"] == "answer":
                out["text"] += event["delta"]
            elif event["type"] == "offer" and event["offer"].get("kind") == "ask":
                out["asks"] = event["offer"]["asks"]
    return out


def test_open_a_note_through_the_route(client, session):
    manager.create_entry(session, "# Harbor launch plan\n\nShip the app.")
    manager.create_entry(session, "# Dentist\n\nCheck-up on the 21st.")
    session.commit()
    out = _ask(client, "open a note")
    assert "Which note" in out["text"]
    assert "Open the note about Dentist" in out["asks"]


def test_do_smth_cool_through_the_route(client, session):
    manager.create_entry(session, "# Dentist\n\nCheck-up on the 21st.")
    session.commit()
    out = _ask(client, "do smth cool")
    assert "couldn't find anything" not in out["text"]
    assert out["asks"]


def test_an_unknown_instruction_through_the_route_offers_actions_not_a_search(client, session):
    manager.create_entry(session, "# Dentist\n\nCheck-up on the 21st.")
    session.commit()
    out = _ask(client, "get rid of the old stuff please")
    assert "closest" in out["text"] or "not sure" in out["text"]
    assert "Delete a note" in out["asks"]
    assert "couldn't find" not in out["text"].lower()
