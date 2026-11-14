"""L-chat-254: a find ask matches on its words, not on a lone year or number: "find my tax return 2019" must not
list the cat note that only holds "2019" (the Todo note holds "tax"; it is the one honest partial)."""

from __future__ import annotations

import tests._seed_r9_1109 as sd


def test_a_year_alone_is_no_match(client, session, monkeypatch):
    sd.seed(session)
    text = sd.asker(client, monkeypatch, chat=True)("find my tax return 2019")[0]
    assert "Pickle" not in text, text


def test_a_number_asked_alone_still_finds(client, session, monkeypatch):
    sd.seed(session)
    text = sd.asker(client, monkeypatch, chat=True)("find notes about 2019")[0]
    assert "Pickle" in text, text
