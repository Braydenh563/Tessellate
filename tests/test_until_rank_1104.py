"""The count-down shapes order candidate notes with the shared ranker
(audit 1029 rank 18): a note that defines the subject beats a diary whose
title merely holds it. Fixed clock: Thursday 29 October 2026, 10:00."""

from __future__ import annotations

import datetime as dt

import pytest

from tessellate.ai import note_rank
from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = dt.datetime(2026, 10, 29, 10, 0, 0)
D = dt.datetime
SUBJECTS = ["chess", "violin", "orchids", "kayaking"]


def test_lead_by_returns_items_in_note_rank_order():
    notes = [{"content": "# Shopping\n\nask about chess"}, {"content": "# Chess diary\n\nplayed chess"}, {"content": "# Chess\n\nplan"}]
    wrapped = [{"note": n} for n in notes]
    got = note_rank.lead_by(wrapped, "chess", lambda w: w["note"])
    assert [w["note"]["content"][:8] for w in got] == ["# Chess\n", "# Chess ", "# Shoppi"]


@pytest.mark.parametrize("subject", SUBJECTS)
@pytest.mark.parametrize("phrasing", ["how many days until the {s} meetup", "how long until the {s} meetup"])
def test_until_prefers_the_defining_note_over_a_diary(client, session, monkeypatch, subject, phrasing):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    cap = subject.capitalize()
    for text, when in [
        (f"# {cap} diary\n\nWe booked the {subject} meetup for 5 November.", D(2026, 10, 20, 9)),
        (f"# Hobby basics\n\nThe {subject} meetup is a monthly club night, next on 20 November.", D(2026, 7, 4, 9)),
    ]:
        entry = manager.create_entry(session, text, "Personal")
        entry.created_at = entry.updated_at = when
    session.commit()
    said = _ask(client, phrasing.format(s=subject), notes_only=True, answer_from="notes")["text"]
    assert "Hobby basics" in said, said
    assert "22 days" in said or "three weeks" in said, said
