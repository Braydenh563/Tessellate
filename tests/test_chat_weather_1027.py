"""The weather with a model up or Web on (the owner, 2026-10-27, a follow-up
"What's the weather like today?" answered by the composer's "not something
this app knows" while a model ran and Web was on), and the web query a local
question is searched with."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from tessellate.ai import composer_digest, utilities
from tessellate.api import routes_chat


@pytest.mark.parametrize(
    ("asked", "place", "query"),
    [
        ("What's the weather like today?", "Brisbane", "What's the weather like today Brisbane"),
        ("search the web for the forecast this weekend", "Brisbane", "the forecast this weekend Brisbane"),
        ("weather in Perth tomorrow", "Brisbane", "weather in Perth tomorrow"),
        ("pharmacies open now", "Perth", "pharmacies open now Perth"),
        ("train times to Perth", "Brisbane", "train times to Perth"),
        ("What's the weather like today?", "", "What's the weather like today?"),
    ],
)
def test_a_local_question_carries_the_persons_place_and_no_other(asked: str, place: str, query: str) -> None:
    assert composer_digest.web_query(asked, place) == query


@pytest.mark.parametrize(
    ("zone", "place"),
    [("Australia/Brisbane", "Brisbane"), ("America/New_York", "New York"), ("UTC", ""), ("Etc/GMT+10", ""), ("", "")],
)
def test_the_place_is_the_timezones_city(zone: str, place: str) -> None:
    config = SimpleNamespace(get_preference=lambda key, default=None: zone if key == "timezone" else default)
    assert routes_chat._home_place(config) == place


@pytest.mark.parametrize(("running", "web"), [(True, False), (False, True), (True, True)])
def test_the_weather_is_no_worked_answer_with_a_model_or_the_web(monkeypatch, running: bool, web: bool) -> None:
    monkeypatch.setattr(routes_chat.deps, "get_ollama", lambda: SimpleNamespace(is_running=lambda: running))
    monkeypatch.setattr(utilities, "web_on", lambda: web)
    detected, stats = routes_chat._worked_out("What's the weather like today?")
    assert stats is None
    assert detected == routes_chat.intent.NOTES


def test_with_neither_the_composer_says_it_cannot(monkeypatch) -> None:
    monkeypatch.setattr(routes_chat.deps, "get_ollama", lambda: SimpleNamespace(is_running=lambda: False))
    monkeypatch.setattr(utilities, "web_on", lambda: False)
    #: A fixed clock and no config: the composer needs only the day.
    monkeypatch.setattr(routes_chat.deps, "get_config", lambda: None)
    monkeypatch.setattr(routes_chat, "user_now", lambda _config: datetime(2026, 10, 27, 9, 30))
    utilities._kind_of_cached.cache_clear()
    detected, stats = routes_chat._worked_out("What's the weather like today?")
    assert detected == routes_chat.intent.UTILITY
    assert "weather" in stats.text
