"""A web reply is not from the notes (INBOX 1550).

The owner's screenshot: "the search service at 127.0.0.1 is not answering ...
Your notes did not hold an answer either", badged "From your notes" with
"Sources: 10 notes". The turn's first meta was the notes search's; a web reply,
answered or down, now sends a second one that the client takes in its place:
not composed, no notes."""

from __future__ import annotations

import pytest

from tessellate.core import deps
from tessellate.entry import manager
from tessellate.search import websearch
from tests.test_composer_route_688 import _ask


@pytest.fixture()
def down(monkeypatch):
    deps.get_config().set_preference("web_search_enabled", True)

    def search(*a, **k):  # noqa: ANN002, ANN003
        raise websearch.WebSearchError("Connection refused")

    monkeypatch.setattr(websearch, "search_web", search)


def test_a_failed_web_search_is_not_badged_from_the_notes(client, session, down):
    for n in range(4):
        manager.create_entry(session, f"# Soup {n}\n\nA pot of lentil soup for the week.")
    out = _ask(client, "what is the capital of France", use_tools=True)
    assert "is not answering" in out["text"], out["text"]
    assert len(out["meta"]) == 2, "the notes search's meta, then the web reply's"
    last = out["meta"][-1]
    assert last["composed"] is False and last["raw_results"] == [] and last["web"] is True
