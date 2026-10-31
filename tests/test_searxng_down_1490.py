"""A web search that was asked for and cannot run offers buttons, not a pasted
docker command (INBOX 1490, the owner, 2026-10-31): Start SearXNG when the app
can launch it, Set it up (Settings, Web search), Open the web panel, Use
another provider."""

from __future__ import annotations

import pytest

from tessellate.ai import composer_web
from tests._app_js import app_js_text
from tests.test_composer_route_688 import _ask

LABELS = ("Start SearXNG", "Set it up in Settings", "Open the web panel", "Use another provider")


def _buttons(offer: dict) -> list[dict]:
    return [{k: v for k, v in offer.items() if k != "also"}, *offer.get("also", [])]


@pytest.mark.parametrize(("url", "provider"), [("http://127.0.0.1:8888", "auto"), ("", "searxng"), ("http://localhost:8888", "searxng"), ("", "auto")])
def test_a_down_service_the_app_can_start_offers_four_buttons_and_no_command(url, provider):
    out = composer_web.search_down("connection refused", url, provider, can_start=True)
    assert "docker" not in out["text"].lower() and "```" not in out["text"], out["text"]
    buttons = _buttons(out["offer"])
    assert [b["label"] for b in buttons] == list(LABELS), buttons
    assert buttons[0]["kind"] == "searxng-start"
    assert [b["surface"] for b in buttons[1:]] == ["settings:websearch", "web-panel", "settings:websearch"]
    paragraphs = [p.strip() for p in out["text"].split("\n\n")]
    assert all(label in paragraphs for label in LABELS), out["text"]


def test_a_service_the_app_cannot_start_offers_the_other_three():
    out = composer_web.search_down("connection refused", "http://192.168.1.20:8888", "searxng", can_start=False)
    buttons = _buttons(out["offer"])
    assert [b["label"] for b in buttons] == list(LABELS[1:]) and all(b["kind"] == "open" for b in buttons)
    assert "Start SearXNG" not in out["text"] and "192.168.1.20" in out["text"]


def test_never_set_up_says_so_without_a_command():
    out = composer_web.search_down("no address", "", "searxng", can_start=True)
    assert "not set up" in out["text"] and "not answering" not in out["text"] and "docker" not in out["text"].lower()


def test_the_words_are_sentence_case_with_no_dash_and_no_exclamation():
    for can in (True, False):
        text = composer_web.search_down("refused", "http://127.0.0.1:8888", "auto", can_start=can)["text"]
        assert "!" not in text and chr(0x2014) not in text and "the assistant" not in text.lower()


@pytest.fixture()
def down(monkeypatch):
    from tessellate.core import deps
    from tessellate.search import websearch

    deps.get_config().set_preference("web_search_enabled", True)

    def search(*a, **k):  # noqa: ANN002, ANN003
        raise websearch.WebSearchError("Connection refused")

    monkeypatch.setattr(websearch, "search_web", search)


@pytest.mark.parametrize("said", ["search the web for the best kettle", "what is the capital of France", "look it up online: spring tides", "weather in Brisbane"])
def test_a_web_search_that_was_asked_for_and_failed_carries_the_buttons(client, session, down, said):
    out = _ask(client, said, use_tools=True)
    assert "docker" not in out["text"].lower(), out["text"]
    offers = [e["offer"] for e in out["offer"] if e["offer"].get("kind") != "ask"]
    assert len(offers) == 1
    assert [b["label"] for b in _buttons(offers[0])] == list(LABELS), offers


def test_with_a_remote_address_or_duckduckgo_only_there_is_no_start_button(client, session, down):
    from tessellate.core import deps

    for url, provider in (("http://10.0.0.5:8888", "searxng"), ("", "duckduckgo")):
        deps.get_config().set_preference("searxng_url", url)
        deps.get_config().set_preference("search_provider", provider)
        out = _ask(client, "search the web for kettles", use_tools=True)
        offers = [e["offer"] for e in out["offer"] if e["offer"].get("kind") != "ask"]
        assert [b["label"] for b in _buttons(offers[0])] == list(LABELS[1:]), (url, provider)


def test_the_button_starts_searxng_through_the_settings_door_and_the_web_panel_opens():
    js = app_js_text()
    assert 'offer.kind === "searxng-start"' in js and "/websearch/searxng/start" in js
    assert 'offer.surface === "web-panel"' in js and "toggleWebPanel(true)" in js
