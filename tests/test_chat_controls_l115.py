"""L-chat-115 (C13): the conversation controls over real turns, no model: "say
that again", "shorter", "longer", "back", "start over", "stop"."""

import pytest

import tests._seed_r9_1109 as sd


@pytest.fixture
def chat(client, session, monkeypatch):
    sd.seed(session)
    sd.fix_clock(monkeypatch)
    history: list[dict] = []

    def say(question):
        text = sd.ask(client, question, history=history, notes_only=False)["text"]
        history.append({"question": question, "answer": text})
        return text

    return say


def test_shorter_then_longer_change_the_length_of_the_last_answer(chat):
    full = chat("what have I saved about running?")
    short = chat("shorter")
    long = chat("longer")
    assert len(short) < len(full) and "in detail" in long and long != full


def test_say_that_again_repeats_the_last_answer(chat):
    first = chat("what have I saved about bread?")
    assert first in chat("say that again")


@pytest.mark.parametrize("said", ["back", "go back", "go back to the previous answer"])
def test_back_restores_the_answer_before_the_last(chat, said):
    first = chat("what have I saved about running?")
    chat("and bread?")
    assert first in chat(said)


def test_back_with_nothing_earlier_says_so(chat):
    chat("what have I saved about running?")
    assert "nothing earlier" in chat("back")


@pytest.mark.parametrize("said", ["start over", "stop", "never mind"])
def test_start_over_and_stop_end_the_thread(chat, said):
    chat("what have I saved about running?")
    assert "running" not in chat(said).lower()
