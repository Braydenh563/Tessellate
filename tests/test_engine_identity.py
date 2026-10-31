"""Identity, the help register and the model that stops (CHAT_PLAN Phase 6
step 8, decision 36; the first tests: a model dying mid-answer left only the
error)."""

from __future__ import annotations

import pytest

from tessellate.ai import composer
from tessellate.ai.ollama_client import OllamaError
from tessellate.api import routes_chat
from tessellate.entry import manager
from tests import _composer_eval
from tests.test_composer_route_688 import _ask


@pytest.mark.parametrize("kind", ["who", "about_app"])
@pytest.mark.parametrize("voice", ["natural", "professional"])
def test_every_identity_line_names_atlas(kind, voice):
    lines = composer.SOCIAL_PROFESSIONAL[kind] if voice == "professional" else composer.SOCIAL[kind]
    assert lines and all("Atlas" in line for line in lines)
    assert all("!" not in line and chr(0x2014) not in line for line in lines)


@pytest.mark.parametrize(
    ("question", "topic"),
    [
        ("how do I add a reminder to a note", "reminders"),
        ("how do I change the theme", "appearance"),
        #: The topic named for the act leads (INBOX 1495-1497, `_act_sentence`):
        #: "export" is `import-export`'s own word, so it answers, not `storage`.
        ("where is the export button", "import-export"),
    ],
)
def test_a_how_to_is_answered_by_its_help_topics_own_sentence(question, topic):
    from tessellate.ai import help_chat

    result = composer.compose(question, [], voice="help")
    help_part = result["parts"][0]
    assert result["shape"] == "help" and help_part[0] == "help" and help_part[2] == topic
    body = next(t["body"] for t in help_chat.HELP_TOPICS if t["id"] == topic)
    #: A sentence over the lead budget comes as its best clause with a full stop
    #: added (INBOX 1406), so the words are the topic's and the stop is not.
    assert help_part[1].rstrip(".") in body


def test_a_question_no_help_topic_names_falls_back_to_the_notes():
    notes = [{"id": 1, "content": "# Rice\n\nCook rice: rinse twice, then simmer for 12 minutes.", "created_at": "2026-09-16"}]
    result = composer.compose("how to cook rice", notes, voice="help")
    assert result["shape"] != "help" and result["grounding"]


def test_a_how_to_about_the_app_is_answered_from_help_on_the_route(client, session):
    out = _ask(client, "how do I change the theme", use_tools=False)
    assert out["text"].startswith("Settings, Appearance controls theme")


def _seed(session):
    manager.create_entry(session, "# Harbor launch plan\n\nShip Harbor to the public on the 14th of next month.")
    session.commit()


class _Dies:
    """A provider whose stream dies before its first word."""

    def __init__(self, fake):
        self.fake = fake

    def __getattr__(self, name):
        return getattr(self.fake, name)

    def chat_stream(self, model, messages, mode=None):  # noqa: ANN001, ARG002
        raise OllamaError("connection reset")
        yield  # pragma: no cover


def test_a_model_that_dies_before_its_first_word_leaves_the_composed_answer(ai_client, fake_ollama, session, monkeypatch):
    _seed(session)
    from tessellate.core import deps

    monkeypatch.setattr(deps, "get_ollama", lambda: _Dies(fake_ollama))
    out = _ask(ai_client, "What is the Harbor launch plan?", notes_only=True, use_tools=False, answer_from="ai")
    assert "Ship Harbor to the public on the 14th of next month." in out["text"]
    assert out["text"].endswith(routes_chat.MODEL_STOPPED_NOTE)


def test_the_eval_traces_a_help_answer():
    from datetime import date

    result = composer.compose("how do I change the theme", [], voice="help")
    assert not _composer_eval.trace_failures(result, "how do I change the theme", [], date(2026, 10, 6))
