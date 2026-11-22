"""L-chat-113 (C10): "tell me a joke" with no joke saved is one from the app's
table of 100, labelled as its own; a saved joke still wins; Neutral and Plain
opt out."""

import pytest

from tessellate.ai import composer_jokebook
from tessellate.core import deps
import tests._seed_r9_1109 as sd


def test_the_table_is_a_hundred_distinct_clean_jokes():
    jokes = composer_jokebook.JOKES
    assert len(jokes) == len(set(jokes)) == 100
    assert all("\u2014" not in j and "!" not in j and len(j) < 140 for j in jokes)


def test_a_pick_is_stable_and_skips_recent():
    first = composer_jokebook.pick("seed")
    assert first == composer_jokebook.pick("seed")
    assert composer_jokebook.pick("seed", (first,)) != first


@pytest.fixture
def go(client, session, monkeypatch):
    sd.seed(session)
    return sd.asker(client, monkeypatch, chat=True)


def test_a_joke_is_told_and_labelled_as_the_apps_own(go):
    said, _ = go("tell me a joke")
    assert said.startswith("Not from your notes, one of mine: ")
    assert said.split(": ", 1)[1] in composer_jokebook.JOKES


def test_the_next_joke_is_not_the_same(go):
    first, _ = go("tell me a joke")
    second, _ = go("tell me a joke", history=[{"question": "tell me a joke", "answer": first}])
    assert first != second and second.startswith("Not from your notes")


def test_plain_answer_style_opts_out(go, monkeypatch):
    monkeypatch.setattr(deps.get_config(), "get_preference", lambda key, default=None: "plain" if key == "composer_voice" else default)
    said, _ = go("tell me a joke")
    assert "one of mine" not in said
