"""Decision 45: with a model running, the model picks among the engine's numbered readings.

A scripted transport stands in for the model (every provider test runs against
a fake; real inference is unverified). The model only ever returns a number.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from tessellate.ai import composer
from tessellate.api import chat_pick

SEED = json.loads((Path(__file__).parent / "fixtures" / "composer" / "phase6_seed.json").read_text(encoding="utf-8"))
TODAY = date.fromisoformat(SEED["today"])
MEETINGS = [n for n in SEED["notes"] if "meeting" in n["content"].lower()]


class Scripted:
    """A model that answers each chat with the next canned string."""

    def __init__(self, *replies: str, running: bool = True) -> None:
        self.replies, self.running, self.calls = list(replies), running, []

    def is_running(self) -> bool:
        return self.running

    def chat(self, model: str, messages: list[dict], mode: str | None = None) -> dict:
        self.calls.append(messages)
        if self.replies and self.replies[0] == "boom":
            raise RuntimeError("model down")
        return {"content": self.replies.pop(0) if self.replies else ""}

    def served_chat_model(self, provider) -> str:  # noqa: ANN001
        return "fake"


def _settle(model: Scripted) -> tuple[dict, dict]:
    def compose(pool: list) -> dict:
        return composer.compose("the meeting", pool, today=TODAY)

    first = compose(MEETINGS)
    req = SimpleNamespace(ollama=model, model_manager=model, question="the meeting")
    return first, chat_pick.settle(req, first, MEETINGS, compose)


def test_the_engine_lists_two_readings_to_pick_from():
    first, _ = _settle(Scripted("none"))
    assert [r["n"] for r in first["readings"]] == [1, 2]


@pytest.mark.parametrize("which", [0, 1])
def test_the_chosen_reading_is_answered_over_that_one_note(which):
    first = composer.compose("the meeting", MEETINGS, today=TODAY)
    chosen = first["readings"][which]
    _, settled = _settle(Scripted(f"{chosen['n']}"))
    assert not settled.get("readings"), settled.get("text")
    assert {row["note_id"] for row in settled["grounding"]} == {chosen["note_id"]}


def test_the_model_is_asked_for_a_number_and_sees_only_the_readings():
    model = Scripted("1")
    first, _ = _settle(model)
    system, user = model.calls[0]
    assert "number" in system["content"] and "none" in system["content"]
    assert all(r["label"] in user["content"] for r in first["readings"])
    assert MEETINGS[0]["content"] not in user["content"]


@pytest.mark.parametrize("reply", ["none", "I think it is the second one", "7", "", "boom"])
def test_none_garbage_or_a_failure_leaves_the_engines_own_question(reply):
    first, settled = _settle(Scripted(reply))
    assert settled is first


def test_without_a_running_model_the_person_is_asked():
    first, settled = _settle(Scripted("1", running=False))
    assert settled is first


def test_the_answer_never_carries_the_models_words():
    _, settled = _settle(Scripted("2, because the second one is obviously the right meeting"))
    assert "obviously" not in json.dumps(settled)
