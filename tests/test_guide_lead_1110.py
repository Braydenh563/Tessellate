"""The Guide with no model: the right sentence leads, and a miss never blames
the model (composer audit 2, G5). Each row is a question the audit hand-checked
(15 of 97 led with the wrong sentence, 9 missed). Parity: tests/test_manual_parity.py."""

from __future__ import annotations

import pytest

from tessellate.ai import help_chat

#: A switch topic reads its preference through deps.get_config(); without a
#: temp data dir that config is the repo's own data/ folder (conftest guard).
pytestmark = pytest.mark.usefixtures("app_state")


def say(question: str, tab: str | None = None, history: list[dict] | None = None) -> dict:
    return help_chat.offline_answer(question, tab, None, history=history)


def first_sentence(topic_id: str) -> str:
    topic = next(t for t in help_chat.HELP_TOPICS if t["id"] == topic_id)
    return help_chat.help_sentences(topic["body"])[0]


LEADS = [
    ("what is Tidy", None, "Tidy is the broom in the Notes dock"),
    ("what is a space", None, "A space is a separate notebook"),
    ("what is the companion", None, "The corner companion is a small character"),
    ("what is the timeline", None, "The Timeline tab lists what you wrote"),
    ("what is the daily note", None, "A daily note is an ordinary note whose title is its day"),
    ("what is on this day", None, "On this day shows today's date in earlier months and years"),
    ("how do I scan a page", None, "OCR workspace: open any image or PDF"),
    ("how do I turn off the companion", None, "Choose who it is in Settings, Appearance, Atlas and faces, Corner companion: Off"),
    ("how do I see my week", None, "The Timeline tab lists what you wrote"),
    ("what should I do first", None, "A new notebook's Dashboard shows First steps"),
    ("what's new", None, "What changed in each version is under Settings, About, What's new."),
    ("how do I make a checklist", None, "A task is a reminder or an open checklist line"),
    ("how do I stop the AI changing my tags", None, "Background AI is off now."),
    ("nothing happens when I click save", None, "If Atlas does not answer"),
    ("who made this", None, "Settings, Help, Credits lists the libraries"),
    ("do I need a model", None, "No."),
    ("how much does it cost", None, "There is nothing to buy in the app"),
    ("is there an app for android", None, "There is no separate Android app."),
    ("why is the AI slow", None, "If the AI is slow, the model is the cause"),
]


@pytest.mark.parametrize(("question", "tab", "start"), LEADS)
def test_the_right_sentence_leads(question, tab, start):
    assert say(question, tab)["content"].startswith(start), say(question, tab)["content"][:200]


@pytest.mark.parametrize("tab", ["whiteboard", "settings", "statistics", "library", "notes", "chat"])
@pytest.mark.parametrize("question", ["what does this page do", "what is this page"])
def test_a_tab_question_leads_with_the_tab_topics_first_sentence(question, tab):
    topic_id = help_chat.TAB_TOPICS[tab][0]
    assert say(question, tab)["content"].startswith(first_sentence(topic_id)[:60])


@pytest.mark.parametrize("question", ["how do I make a private note", "weekly review"])
def test_the_recovery_and_template_sentences_no_longer_lead(question):
    content = say(question)["content"]
    for wrong in ("Forgot your password", "A map's twenty-seven", "Kinds chooses"):
        assert wrong not in content[:120]


@pytest.mark.parametrize("question", ["when is my dentist appointment", "how many notes do I have", "weekly review", "daily review", "what did I write on monday"])
def test_a_question_about_the_persons_notes_is_handed_to_chat(question):
    reply = say(question)
    assert reply["content"].startswith("That is one for your notebook")
    assert reply["asks"] == [question] and reply["asks_to"] == "chat"


@pytest.mark.parametrize("question", ["what is my name", "how do I change my name", "how do I set a reminder", "how do I see my notes"])
def test_a_how_to_about_the_app_is_not_handed_over(question):
    assert not say(question)["content"].startswith("That is one for your notebook")


@pytest.mark.parametrize("question", ["what's the weather", "asdfgh", "xyzzy plugh frobnicate"])
def test_a_miss_never_blames_the_model(question):
    content = say(question)["content"]
    assert content.startswith("I don't have help on that.")
    assert "model" not in content.lower().split("did you mean")[0]
    assert "Settings, Help" in content


def test_bare_help_does_not_open_with_a_yes():
    assert not say("help")["content"].startswith("Yes")


@pytest.mark.parametrize("question", ["how do I set a reminder", "how do I make a note"])
def test_a_how_to_is_not_announced_as_n_steps(question):
    content = say(question)["content"]
    assert "It takes" not in content and "1. " in content


def test_related_never_repeats_the_topic_just_given():
    for question in ("how do I set a reminder", "what is a space", "how do I make a note"):
        reply = say(question)["content"]
        if "**Related:**" in reply:
            related = reply.split("**Related:**")[1]
            lead_topic = help_chat.topics_for(question)[0]
            assert help_chat.topic_title(lead_topic) not in related


def test_a_follow_on_that_names_nothing_keeps_the_last_topic():
    history = [
        {"role": "user", "content": "how do I set a reminder"},
        {"role": "assistant", "content": "It takes three steps, from the Reminders tab"},
    ]
    content = say("where do they show up", None, history)["content"]
    assert content.startswith("I don't have help on that") is False
    assert "Reminders" in content


def test_a_follow_on_with_no_history_is_a_miss():
    assert say("where do they show up")["content"].startswith("I don't have help on that.")


def test_the_model_up_path_keeps_greetings_and_hand_overs_composed():
    """Parity: with a model up, a greeting or a question about the notes is still the composed reply, with its chips."""

    class Up:
        def is_running(self):
            return True

        def chat(self, *a, **k):  # pragma: no cover - must not be reached
            raise AssertionError("the model was called")

        chat_stream = chat

    class Manager:
        def utility_model(self):
            return "m"

    hello = help_chat.answer("hello", Manager(), Up())
    assert hello["content"] == help_chat.GREETING_REPLY and hello.get("greeting")
    mine = help_chat.answer("when is my dentist appointment", Manager(), Up())
    assert mine["content"].startswith("That is one for your notebook") and mine["asks_to"] == "chat"
    streamed = list(help_chat.answer_stream("hello", Manager(), Up()))
    assert streamed[-1]["type"] == "done" and streamed[-1]["content"] == help_chat.GREETING_REPLY
