"""L-chat-275 (decision 45 stands): the reading pick sees the recent dialogue, and "none" asks the person.
A scripted transport stands in for the model; real inference is unverified."""

from __future__ import annotations

from types import SimpleNamespace

from tessellate.api import chat_pick

READINGS = [
    {"n": 1, "label": "Meeting with Dana", "note_id": 11},
    {"n": 2, "label": "Meeting with the board", "note_id": 12},
]
HISTORY = [
    {"question": "What did Dana say about the budget?", "answer": "Dana wants the budget cut by ten percent."},
    {"question": "And the plan?", "answer": "The plan waits for the budget."},
]


class Scripted:
    def __init__(self, reply: str) -> None:
        self.reply, self.calls = reply, []

    def is_running(self) -> bool:
        return True

    def chat(self, model: str, messages: list[dict], mode: str | None = None) -> dict:
        self.calls.append(messages)
        return {"content": self.reply}

    def served_chat_model(self, provider) -> str:  # noqa: ANN001
        return "fake"


def _req(model: Scripted, history):  # noqa: ANN001
    return SimpleNamespace(ollama=model, model_manager=model, question="the meeting", history=history)


def test_the_history_reaches_the_prompt():
    model = Scripted("1")
    chat_pick.settle(_req(model, HISTORY), {"readings": READINGS}, [], lambda pool: {"recomposed": True})
    user = model.calls[0][1]["content"]
    assert "What did Dana say about the budget?" in user and "The plan waits for the budget." in user
    assert user.index("Dana say") < user.index("Question: the meeting") < user.index("Readings:")
    assert "earlier turns" in model.calls[0][0]["content"]


def test_only_the_last_turns_and_a_cut_answer_are_sent():
    long = [{"question": f"q{i}", "answer": "x" * 1000} for i in range(6)]
    user = chat_pick.messages("the meeting", READINGS, long)[1]["content"]
    assert "q2" not in user and "q3" in user and "q5" in user
    assert "x" * (chat_pick.CUT + 1) not in user


def test_no_history_leaves_the_prompt_as_it_was():
    user = chat_pick.messages("the meeting", READINGS)[1]["content"]
    assert user.startswith("Question: the meeting") and "Conversation so far" not in user


def test_none_after_a_dialogue_asks_the_person():
    model = Scripted("none")
    result = {"readings": READINGS, "text": "Which meeting?"}
    notes = [{"id": 11}, {"id": 12}]
    settled = chat_pick.settle(_req(model, HISTORY), result, notes, lambda pool: {"recomposed": True})
    assert settled is result, "none keeps the engine's own question"
    assert model.calls, "the model was asked"
