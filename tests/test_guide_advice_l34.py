"""L-chat-34: with no model, the Guide answers general and advice questions
(the owner, 2026-11-13: "the guide should be able to respond like a chatbot
with the composer when an ai model isnt there so if I ask general questions or
advice then it can provide"). A direct answer comes first, grounded in the
help topics it links; the badge says it is the app's own help (composed)."""

from __future__ import annotations

import pytest

from tessellate.ai import guide_advice, help_chat

#: Question, then the answer's pinned first sentence start.
PINNED = {
    "what should I use chat for?": "Use Chat to ask about your own notes and to get small jobs done",
    "what is chat good for": "Use Chat to ask about your own notes and to get small jobs done",
    "what is the difference between chat and ask?": "Both answer from your saved notes",
    "how should I organise my notes?": "Let filing do the first pass",
    "should I use categories or tags?": "Let filing do the first pass",
    "what's the best way to use tags?": "Let filing do the first pass",
    "should I keep work and home in separate spaces?": "Let filing do the first pass",
    "any advice on using reminders?": "Put anything with a time in a reminder",
    "is it better to tag notes or put them in categories?": "Let filing do the first pass",
    "how do I stay on top of my tasks?": "Put anything with a time in a reminder",
    "what is a good way to plan my week?": "Ask Chat “what is due this week?”",
    "how often should I back up?": "The app makes a daily backup for you",
    "how do I write better notes?": "Keep one subject per note",
    "how can I remember things better?": "Turn your notes into practice",
    "should I use a mind map or a board?": "A mind map suits one idea broken into branches",
    "why use a mind map?": "A mind map suits one idea broken into branches",
    "can you give me advice on journaling?": "Write one note a day",
    "any tips for finding things?": "Use Find anything (Ctrl+P)",
    "how should I take meeting notes?": "Start it with New meeting",
    "what is the graph good for?": "The Graph shows how your notes connect",
    "what's the quickest way to jot something down?": "Use Quick note (Alt+N)",
}


class _Down:
    def is_running(self):
        return False


class _Manager:
    def utility_model(self):
        return ""


@pytest.mark.parametrize("question", sorted(PINNED))
def test_an_advice_question_gets_a_direct_answer_first(question):
    reply = help_chat.answer(question, _Manager(), _Down())
    assert reply["content"].startswith(PINNED[question]), reply["content"][:160]
    assert reply.get("composed") is True
    #: Help links: every answer names the topics it stands on, as chips that open them.
    assert reply["badges"] and reply["sources"]


def test_there_are_at_least_fifteen_distinct_questions_and_every_entry_is_asked():
    assert len(PINNED) >= 15
    hit = {guide_advice.match(q).id for q in PINNED}
    assert hit == {a.id for a in guide_advice.ADVICE}


def test_every_answer_stands_on_topics_that_exist():
    ids = {t["id"] for t in help_chat.HELP_TOPICS}
    for advice in guide_advice.ADVICE:
        assert advice.topics and set(advice.topics) <= ids, advice.id


@pytest.mark.parametrize("question", [
    "how do I set a reminder?", "where are my backups?", "how do I add a tag?", "what is the graph?",
    "how do I export my notes", "hello", "what is due soon", "how do I make a mind map",
    "whats the whiteboard for", "what should I do first", "where should I start?",
])
def test_a_how_to_or_a_notebook_question_is_not_taken_as_advice(question):
    assert guide_advice.match(question) is None


def test_with_a_model_running_the_model_answers():
    """Decision 75: model up, it leads."""

    class Up:
        def is_running(self):
            return True

        def chat(self, *a, **k):
            return {"content": "From the model."}

    reply = help_chat.answer("what should I use chat for?", _Manager(), Up())
    assert reply["content"] == "From the model."


def test_the_stream_says_the_same():
    done = list(help_chat.answer_stream("how should I organise my notes?", _Manager(), _Down()))[-1]
    assert done["content"].startswith("Let filing do the first pass") and done.get("composed")
