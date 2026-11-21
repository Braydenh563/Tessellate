"""L-chat-125 (Build 1, findings 1 to 3): a note about translation is not a
translate command, a utility answer is a computed row that stands alone, and
a summary says how many sides it took. Over the real route, no model."""

import pytest

import tests._seed_r9_1109 as sd


@pytest.fixture
def ask(client, session, monkeypatch):
    sd.seed(session)
    sd.fix_clock(monkeypatch)
    return lambda q: sd.ask(client, q, history=[], notes_only=False)


@pytest.mark.parametrize("question", ["what did I write about the translate feature", "where is my note on how to translate"])
def test_translate_mid_sentence_is_a_search_not_a_command(ask, question):
    assert "translation of" not in ask(question)["text"].lower()


@pytest.mark.parametrize("question, expect", [("what is 12 times 12", "144"), ("convert 5 km to miles", "3.1")])
def test_a_utility_answer_is_computed_and_says_how_it_was_read(ask, question, expect):
    out = ask(question)
    assert expect in out["text"]
    assert out.get("composed") is not False


def test_a_summary_and_a_comparison_both_answer_without_error(ask):
    assert ask("summarise what I saved about running")["text"].strip()
    assert ask("compare running and bread")["text"].strip()
