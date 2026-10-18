"""Ask and Chat read a bare day/month in the asker's locale, as quick-add does:
in en-US "what's on 3/4" is 4 March; elsewhere it is 3 April."""

from __future__ import annotations

from tessellate.search import search_manager


def test_whats_on_3_4_reads_by_locale(session, fake_embeddings):
    us = search_manager.retrieve_detailed(session, "what's on 3/4", fake_embeddings, locale="en-US")
    gb = search_manager.retrieve_detailed(session, "what's on 3/4", fake_embeddings, locale="en-GB")
    assert (us.since.month, us.since.day) == (3, 4)
    assert (gb.since.month, gb.since.day) == (4, 3)


def test_chat_request_carries_the_locale():
    from tessellate.api.routes_chat import ChatRequest

    assert ChatRequest(question="x", locale="en-US").locale == "en-US"
    assert ChatRequest(question="x").locale is None
