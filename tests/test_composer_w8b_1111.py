"""W8B (2026-11-11): the four composer date rows W8 left open (docs/roadmap/agent-remaining/w8-1110.md, "Found, not fixed").
Each is fixed as a class and has sibling phrasings. Clocks fixed: the bt seed is Monday 9 November 2026, the r5 seed
Saturday 7 November 2026, the calls notebook Thursday 29 October 2026."""

from __future__ import annotations

import datetime as dt
from datetime import date

import pytest

import tests._seed_bt_1109 as bt
from tessellate.ai import composer_ahead
from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests._r5_1108 import driver
from tests.test_composer_route_688 import _ask


@pytest.fixture
def btask(client, session, monkeypatch):
    bt.seed(session)
    bt.fix_clock(monkeypatch)
    return lambda q: bt.ask(client, q, notes_only=True)["text"]


@pytest.fixture
def r5(client, session, monkeypatch):
    return driver(client, session, monkeypatch)


# --- 4. getting in touch is one act said five ways ----------------------------------------------------

NOW = dt.datetime(2026, 10, 29, 10, 0, 0)


@pytest.fixture
def calls(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)

    def build(verb: str):
        for text, when in ((f"# Calls\n\n{verb} mum on 26 October. Long chat about the garden.", dt.datetime(2026, 10, 26, 9)),
                           ("# Todo\n\n- [ ] Call dad", dt.datetime(2026, 10, 27, 9))):
            entry = manager.create_entry(session, text, "Personal")
            entry.created_at = entry.updated_at = when
        session.commit()
        return lambda q: _ask(client, q, notes_only=True, answer_from="notes")["text"]

    return build


ASKS = ["when did I call mum", "when did I phone mum", "when did I ring mum", "when did I text mum", "when did I message mum",
        "when did I last phone mum"]


@pytest.mark.parametrize("verb", ["Called", "Phoned", "Rang", "Texted", "Messaged"])
def test_when_did_i_phone_is_the_day_with_the_notes_own_verb(calls, verb):
    go = calls(verb)
    for question in ASKS:
        assert go(question) == f"On Monday 26 October, you {verb.lower()} mum.", (question, go(question))


def test_a_phone_the_object_is_not_a_call(calls):
    said = calls("Called")("when did I buy my phone")
    assert "you called mum" not in said, said


def test_the_contact_verbs_are_one_synonym_group():
    from tessellate.ai import composer_ask

    for word in ("phone", "ring", "rang", "rung", "text", "message"):
        assert "call" in composer_ask._build_synonyms()[word]  # noqa: SLF001


def test_long_form_still_reads_a_plain_fact():
    assert composer_ahead.long_form("Thu 12 Nov 9:30", date(2026, 11, 9)) == "Thursday 12 November, 9:30"
