"""W7 (2026-11-10): which note leads and what it is called. One test per audit row, probed first and
fixed as a class (B9 one-note notebook and time travel here; B1 to B8 and B10 below). Clock fixed."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager

NOW = datetime(2026, 10, 30, 2, 50)


def _stream(client, body: dict) -> str:
    out = ""
    with client.stream("POST", "/chat/stream", json=body) as response:
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                if event.get("type") == "answer":
                    out += event["delta"]
    return out


@pytest.fixture
def one_note(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    entry = manager.create_entry(session, "# Lisbon trip\nFlying 14 November. Descale the kettle on Sunday.", category_name="Uncategorised")
    entry.created_at = entry.updated_at = datetime(2026, 10, 30, 1, 0)
    session.commit()
    return lambda q, **extra: _stream(client, {"question": q, "use_tools": False, **extra})


# --- B9 one-note notebook and time travel (R3-31, R3-32) --------------------------------

@pytest.mark.parametrize("question", ["what do I know about Lisbon", "what is in the Lisbon trip note", "tell me about Lisbon"])
def test_a_one_note_notebook_does_not_promise_other_notes(one_note, question):
    text = one_note(question)
    assert "Lisbon" in text and "search by meaning" not in text, text


@pytest.mark.parametrize("question", ["what is in my notebook", "what's in my notebook", "what did I write"])
def test_as_of_gives_the_notebook_as_it_stood(one_note, question):
    text = one_note(question, as_of="2026-10-31")
    assert text.startswith("On 31 October 2026 you had 1 note"), text
    assert "I found no mention" not in text


def test_as_of_before_any_note_says_none(one_note):
    assert "no notes from on or before 1 October 2026" in one_note("what is in my notebook", as_of="2026-10-01")


# --- B2 a number or property question is answered with the number, or says none (D7, R3-28, C21) ------------

import tests._seed_1031c as seed_c  # noqa: E402


@pytest.fixture
def chat31(client, session, monkeypatch):
    seed_c.seed(session)
    return seed_c.asker(client, monkeypatch, chat=True)


@pytest.mark.parametrize("question", ["what is my squat", "what did I squat", "how heavy is my squat", "how much do I squat"])
def test_a_lift_is_answered_with_its_weight(chat31, question):
    assert "80 kg" in chat31(question)[0], question


@pytest.mark.parametrize("question", ["what is my passport number", "passport number", "the passport number", "my passport number?", "what's my visa number"])
def test_a_number_no_note_holds_is_said_to_be_missing(chat31, question):
    text = chat31(question)[0]
    assert text.startswith("None of your notes give a "), text
    assert "expires" not in text and "Not sure" not in text


def test_a_note_that_holds_the_number_leads_with_it(client, session, monkeypatch):
    seed_c.seed(session)
    manager.create_entry(session, "# Passport details\n\nPassport number 530123456. Issued in London.", category_name="Uncategorised")
    session.commit()
    text = seed_c.asker(client, monkeypatch, chat=True)("what is my passport number")[0]
    assert "530123456" in text, text


# --- B1 the defining note leads (D1, R3-20, C19, C1) ---------------------------------------------------

import tests._r5_1108 as r5  # noqa: E402


@pytest.fixture
def ask5(client, session, monkeypatch):
    go = r5.driver(client, session, monkeypatch)
    return lambda q: go(q)["text"]


@pytest.mark.parametrize("question", ["tl;dr Lisbon", "summarise Lisbon", "summarize my notes on Lisbon", "give me a summary of Lisbon"])
def test_the_fuller_titled_note_leads_a_summary(ask5, question):
    text = ask5(question)
    assert text.index("Lisbon trip") < text.index("Lisbon dinner") if "Lisbon dinner" in text else "Lisbon trip" in text, text


def test_a_list_of_notes_leads_with_the_fuller_titled_note(ask5):
    text = ask5("show me notes about Lisbon")
    assert text.index("Lisbon trip") < text.index("Lisbon dinner"), text


def test_a_latest_ask_still_leads_with_the_newest(ask5):
    text = ask5("what is the latest on Lisbon")
    assert "Lisbon offsite" in text, text
