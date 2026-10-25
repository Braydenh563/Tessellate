"""The composer is aware of the screen and the last actions (owner, 2026-10-25).

Local only, private notes never named, wording varied by seed and the same for
one seed. The unit half holds `ai/composer_aware.py`; the route half sends a
real request with a `screen`."""

from __future__ import annotations

import json

import pytest

from tessellate.ai import composer_aware as aware
from tessellate.entry import manager

ACTIONS = ["Added a mark", "Cleared a box", "Moved a note to the bin", "Renamed a speaker"]


def test_actions_are_the_last_three_newest_first():
    assert aware.clean_actions(ACTIONS) == ("Renamed a speaker", "Moved a note to the bin", "Cleared a box")


@pytest.mark.parametrize("label", ['Deleted "Tax return"', "Deleted ‘Tax’", "x" * 61, "", "   "])
def test_a_label_that_names_something_or_is_long_is_dropped(label):
    assert aware.clean_actions([label]) == ()


def test_unknown_tab_is_not_named():
    assert aware.tab_name("../etc") == "" and aware.tab_name("graph") == "the Graph"


def test_nothing_known_says_nothing():
    a = aware.build()
    assert not a.known
    assert aware.opening(a, "s") == "" and aware.closing(a, "s") == "" and aware.model_context(a) == ""


def test_opening_names_the_tab_and_the_open_title():
    a = aware.build(tab="notes", open_title="Harbor launch plan")
    line = aware.opening(a, "s")
    assert "Notes" in line and "“Harbor launch plan”" in line


def test_opening_falls_back_to_the_last_action():
    line = aware.opening(aware.build(actions=["Cleared a box"]), "s")
    assert "cleared a box" in line


def test_closing_picks_up_the_open_note():
    line = aware.closing(aware.build(tab="notes", open_title="Dentist"), "s")
    assert "“Dentist”" in line


def test_closing_picks_up_the_last_action_and_offers_a_howto():
    line = aware.closing(aware.build(tab="graph", actions=["Cleared a box"]), "s")
    assert "cleared a box" in line and "how do I link two notes" in line


def test_closing_uses_the_chat_topic_without_an_action():
    assert "golf" in aware.closing(aware.build(topic="golf"), "s")


@pytest.mark.parametrize("seed", [f"seed{n}" for n in range(10)])
def test_the_wording_house_style(seed):
    a = aware.build(tab="notes", open_title="Dentist", actions=["Cleared a box"], topic="golf")
    for text in (aware.opening(a, seed), aware.closing(a, seed), aware.model_context(a)):
        assert text and "!" not in text and chr(0x2014) not in text


def test_the_wording_varies_with_the_seed_and_holds_for_one():
    a = aware.build(tab="notes", open_title="Dentist")
    assert len({aware.opening(a, f"s{n}") for n in range(16)}) >= 3
    assert len({aware.closing(a, f"s{n}") for n in range(16)}) >= 2
    assert aware.opening(a, "same") == aware.opening(a, "same")


def test_the_model_gets_a_labelled_block():
    block = aware.model_context(aware.build(tab="chat", open_title="Dentist", actions=["Cleared a box"]))
    assert block.startswith("[On screen now") and block.endswith("]")
    assert "Dentist" in block and "Cleared a box" in block


def _ask(client, question: str, **body) -> str:
    text = ""
    with client.stream("POST", "/chat/stream", json={"question": question, **body}) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                if event["type"] == "answer":
                    text += event["delta"]
    return text


def _seed(session):
    plain = manager.create_entry(session, "# Dentist\n\nCheck-up booked for the 21st. Ask about the night guard.")
    secret = manager.create_entry(session, "# Divorce lawyer\n\nMeeting on the 3rd about the settlement.")
    session.commit()
    return plain.id, secret.id


def test_a_composed_answer_picks_up_the_open_note(client, session):
    plain, _ = _seed(session)
    text = _ask(client, "when is the check-up", open_note_id=plain, screen={"tab": "notes", "actions": ["Cleared a box"]})
    assert "Check-up booked for the 21st" in text
    assert "“Dentist”" in text.splitlines()[-1]


def test_a_hello_says_what_the_app_can_see(client, session):
    _seed(session)
    text = _ask(client, "hello", screen={"tab": "graph", "actions": ["Cleared a box"]})
    assert "the Graph" in text


def test_a_private_note_is_never_named(client, session):
    _, secret = _seed(session)
    entry = session.get(manager.Entry, secret)
    entry.is_private = True
    session.commit()
    text = _ask(client, "hello", open_note_id=secret, screen={"tab": "notes"})
    assert "Divorce" not in text and "lawyer" not in text


def test_without_a_screen_nothing_changes(client, session):
    _seed(session)
    text = _ask(client, "hello")
    assert "I can see" not in text and "Looks like" not in text


def test_the_guide_picks_up_the_last_action_without_a_model(client):
    reply = client.post("/help/ask", json={"question": "how do I tag a note", "tab": "notes", "actions": ["Cleared a box"]}).json()
    assert reply["composed"] and "cleared a box" in reply["content"]
    plain = client.post("/help/ask", json={"question": "how do I tag a note", "tab": "notes"}).json()
    assert "cleared a box" not in plain["content"]


def test_the_client_sends_the_screen_with_ask_and_the_guide():
    from pathlib import Path

    js = Path(__file__).resolve().parents[1] / "frontend" / "js"
    ask = (js / "capture-ask.js").read_text(encoding="utf-8")
    assert 'body.screen = await screenContext(notesOnly ? "ask" : "")' in ask
    lazy = (js / "screen-context.js").read_text(encoding="utf-8")
    assert "function screenContext(" in lazy and "undoStack.slice(-3)" in lazy
    entries = (js / "lazy-entries.js").read_text(encoding="utf-8")
    assert 'screenContext: ["/js/screen-context.js"]' in entries and 'screenContext: ["screenContext"]' in entries
    assert "actions: (await screenContext()).actions" in (js / "help-chat.js").read_text(encoding="utf-8")
