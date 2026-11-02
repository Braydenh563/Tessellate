"""A web search that failed because SearXNG is down offers the way to start it
(INBOX 1556, the owner: "no button to start up searxng").

The backend says so with a reason a program reads (`WebSearchError.reason`,
`code` in the 502 body, `reason` on a tool event); nothing in the app matches
the message text. The start flow is one helper (`startSearxng`, chat.js) and
every surface that shows the failure draws the same row (`searxngDownRow`)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tessellate.ai import tools
from tessellate.search import websearch

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _read(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def test_an_unanswering_searxng_carries_a_reason_and_other_failures_do_not(monkeypatch):
    import requests

    class Boom:
        def post(self, *a, **k):  # noqa: ANN002, ANN003
            raise requests.ConnectionError("refused")

        def close(self):
            pass

    monkeypatch.setattr(websearch, "_private_session", lambda: Boom())
    monkeypatch.setattr(websearch, "_searxng_target", lambda url: ("http://127.0.0.1:1/search", {}))
    with pytest.raises(websearch.WebSearchError) as down:
        websearch.search_web("kettles", searxng_url="http://127.0.0.1:8888", provider="searxng")
    assert down.value.reason == websearch.REASON_SEARXNG_DOWN

    with pytest.raises(websearch.WebSearchError) as unset:
        websearch.search_web("kettles", searxng_url=None, provider="searxng")
    assert unset.value.reason == websearch.REASON_SEARXNG_DOWN

    assert websearch.WebSearchError("plain").reason is None


def test_the_route_sends_the_reason_as_a_code_and_keeps_the_words(client, monkeypatch):
    client.put("/preferences", json={"web_search_enabled": True})

    def down(*a, **k):  # noqa: ANN002, ANN003
        raise websearch.WebSearchError("The SearXNG search failed. Check that SearXNG is running, then try again.", reason=websearch.REASON_SEARXNG_DOWN)

    monkeypatch.setattr(websearch, "search_web", down)
    response = client.get("/websearch?q=kettles")
    assert response.status_code == 502
    body = response.json()
    assert body["code"] == "searxng_down" and body["detail"].startswith("The SearXNG search failed")

    def other(*a, **k):  # noqa: ANN002, ANN003
        raise websearch.WebSearchError("Web search failed. Check your internet connection and try again.")

    monkeypatch.setattr(websearch, "search_web", other)
    assert client.get("/websearch?q=kettles").json()["code"] != "searxng_down"


def test_a_tool_failure_carries_the_reason_to_the_chip(client, session, monkeypatch):
    from tessellate.ai.agent_turn import _tool_event
    from tessellate.core import deps

    deps.get_config().set_preference("web_search_enabled", True)

    def down(*a, **k):  # noqa: ANN002, ANN003
        raise websearch.WebSearchError("down", reason=websearch.REASON_SEARXNG_DOWN)

    monkeypatch.setattr(websearch, "search_web", down)
    result = tools.execute_tool(session, "web_search", {"query": "kettles"})
    assert result.get("reason") == "searxng_down", result
    assert _tool_event("web_search", {"query": "kettles"}, result)["reason"] == "searxng_down"
    ok = _tool_event("web_search", {}, {"results": []})
    assert "reason" not in ok or not ok["reason"]


def test_no_script_matches_the_failure_by_its_words():
    for path in JS.glob("*.js"):
        text = path.read_text(encoding="utf-8")
        assert "Check that SearXNG is running" not in text and "search failed. Check" not in text, path.name


def test_the_start_flow_is_one_helper_with_one_call_site():
    sites = [p.name for p in JS.glob("*.js") if re.search(r"/websearch/searxng/start", p.read_text(encoding="utf-8"))]
    assert sites == ["web-results.js"], sites
    chat = _read("web-results.js")
    assert "async function startSearxng(" in chat
    for name in ("ask-compose.js", "settings-controls.js"):
        assert "startSearxng(" in _read(name), name


def test_the_panel_and_the_tool_chip_draw_the_same_row():
    web = _read("web-results.js")
    assert "async function searxngDownRow(" in web
    assert 'error.body?.code === "searxng_down"' in web and "searxngDownRow(" in web.split("async function runWebSearch")[1]
    kit = _read("answer-kit.js")
    assert 'reason === "searxng_down"' in kit and "searxngDownRow(" in kit


def test_the_row_says_why_it_cannot_start_and_offers_the_settings():
    web = _read("web-results.js")
    row = web.split("async function searxngDownRow(")[1].split("\nasync function ")[0].split("\nfunction ")[0]
    assert "onOtherDevice()" in row and "THIS_COMPUTER_ONLY" in row
    assert "info.backend" in row and "Web search settings" in row
    assert "Install SearXNG" in row and "Start SearXNG" in row
    assert chr(0x2014) not in row and "!" not in re.sub(r"!==|!=|!\w|!\(|!info", "", row)
