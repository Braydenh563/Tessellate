"""L-chat-116 (C14) and L-chat-117, L-chat-127 (C15, Build 3): with no model,
each thing the app cannot do says so with the step that fixes it, and every
composed bubble carries one meta event with no model named, which the page
draws as the badge (`replyBylineFacts`, tests/test_reply_cards.py)."""

import pytest

import tests._seed_r9_1109 as sd


@pytest.fixture
def ask(client, session, monkeypatch):
    sd.seed(session)
    sd.fix_clock(monkeypatch)
    return lambda q: sd.ask(client, q, notes_only=False)


@pytest.mark.parametrize(
    ("question", "line"),
    [
        ("search the web for kettles", "Web search is off"),
        ("write me a poem", "needs a model: connect one in Settings, Models"),
        ("translate hello to french", "Translating needs a model"),
        ("what is the weather", "nothing leaves this computer"),
    ],
)
def test_each_limit_is_named_with_its_step(ask, question, line):
    assert line in ask(question)["text"]


@pytest.mark.parametrize("question", ["hello", "what is 2+2", "tell me a joke", "what did I write yesterday", "call me Sam", "write me a poem", "thanks"])
def test_every_composed_bubble_has_a_meta_event_and_no_model_name(ask, question):
    metas = [e for e in ask(question)["events"] if e.get("type") == "meta"]
    assert len(metas) == 1 and not metas[0].get("answered_by"), metas
