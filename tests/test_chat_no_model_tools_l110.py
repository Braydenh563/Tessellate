"""L110: with no model, Chat answers "what contradicts" and "what is in the bin" itself; a model turn
sends the composer's own next-question chips with its preview (`test_composer_chips_1110.py`)."""

import pytest

from tests import _seed_1031c as seed_c


@pytest.fixture
def chat(client, session, monkeypatch):
    seed_c.seed(session, filler=10)
    return seed_c.asker(client, monkeypatch, chat=True)


def test_contradictions_are_listed_without_a_model(chat):
    said, _ = chat("do any of my notes contradict each other")
    assert said.startswith("Each change of mind in your dated notes")


@pytest.mark.parametrize("question", ["what is in my bin", "show me the deleted notes"])
def test_the_bin_is_listed_without_a_model(chat, question):
    assert chat(question)[0] == "The bin is empty."
