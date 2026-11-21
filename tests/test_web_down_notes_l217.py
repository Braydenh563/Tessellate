"""L217: when web search is down the answer offers a chip, "Search my notes
instead", that runs the notes path without the web; an ambiguous question asks
"Did you mean your notes or the web?" before anything fails."""

from __future__ import annotations

import pytest

from tessellate.ai import composer_web
from tessellate.core import deps
from tessellate.entry import manager
from tessellate.search import websearch
from tests.test_composer_route_688 import _ask

CHIP = "Search my notes instead"
QUESTION = "what is the capital of France"


@pytest.fixture()
def down(monkeypatch):
    deps.get_config().set_preference("web_search_enabled", True)
    calls = []

    def search(*a, **k):  # noqa: ANN002, ANN003
        calls.append(a)
        raise websearch.WebSearchError("Connection refused")

    monkeypatch.setattr(websearch, "search_web", search)
    return calls


def _chips(out):
    return [a for e in out.get("offer", []) for o in [e["offer"], *e["offer"].get("also", [])] if o.get("kind") == "ask" for a in o["asks"]]


def test_the_down_reply_offers_the_notes_chip_and_keeps_start_search_service():
    reply = composer_web.search_down("timed out", "http://127.0.0.1:8888", "searxng", can_start=True)
    assert reply["offer"]["kind"] == "searxng-start", "Start SearXNG stays the first button"
    asks = [o["asks"] for o in reply["offer"]["also"] if o.get("kind") == "ask"]
    assert asks == [[CHIP]]
    assert CHIP not in reply["text"], "a chip, not a line of prose"
    assert [ln for ln in reply["text"].split("\n") if ln.strip()].count("") == 0


def test_a_failed_web_search_streams_the_chip(client, session, down):
    for n in range(4):
        manager.create_entry(session, f"# Soup {n}\n\nA pot of lentil soup for the week.")
    out = _ask(client, QUESTION, use_tools=True)
    assert "is not answering" in out["text"]
    assert CHIP in _chips(out)


def test_the_chip_runs_the_notes_path_and_never_the_web(client, session, down):
    manager.create_entry(session, "# Trip\n\nThe capital of France is Paris, said the guidebook.")
    history = [{"question": QUESTION, "answer": "I tried to search the web, but the search service is not answering."}]
    before = len(down)
    out = _ask(client, CHIP, use_tools=True, history=history)
    assert len(down) == before, "the web is not tried again"
    assert "Paris" in out["text"] or any(r["id"] for m in out.get("meta", []) for r in m["raw_results"]), out["text"]
    assert "is not answering" not in out["text"]


def test_the_chip_with_no_earlier_question_is_an_ordinary_message(client, session, down):
    out = _ask(client, CHIP, use_tools=True)
    assert "is not answering" not in out["text"]
