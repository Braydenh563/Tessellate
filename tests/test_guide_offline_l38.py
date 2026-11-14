"""L-chat-38: with no model the Guide answers any question in a line or two
(the owner, 2026-11-13: "respond like a chatbot with the composer when an ai
model isnt there"). Thirty-six questions with their first sentences pinned,
over half outside the fourteen advice subjects of L-chat-34: small talk, the
notebook hand-over, yes-or-no questions, how-tos and the world's questions.
A question outside the app says so in one line, with no "Did you mean" menu
of unrelated topics; sums are worked out; a how-to about the world ("how do I
cook rice?") is not answered with the open tab's steps."""

from __future__ import annotations

import pytest

from tessellate.ai import guide_advice, help_chat

OUTSIDE = "That is outside the app"

#: Question, then the start of the reply's first sentence.
PINNED = {
    "hi": "Hi, I'm Atlas, the app's guide.",
    "good morning": "Hi, I'm Atlas, the app's guide.",
    "thanks": "You're welcome.",
    "who are you?": "I'm Atlas, the app's guide, named for a book of maps.",
    "what is Atlas?": "I'm Atlas, the app's guide, named for a book of maps.",
    "what can you do?": "I can tell you where a feature lives",
    "are you an AI?": "I'm Atlas, the app's guide, and I'm software, not a person.",
    "are you a real person?": "I'm Atlas, the app's guide, and I'm software, not a person.",
    "is this a bot?": "I'm Atlas, the app's guide, and I'm software, not a person.",
    "what did I write about the boiler?": "That is one for your notebook, not the help",
    "when is my dentist appointment?": "That is one for your notebook, not the help",
    "is my data private?": "Yes. Your notes stay on this computer",
    "does it work offline?": "Yes, it works offline",
    "is it free?": "There is nothing to buy in the app",
    "how much space does it use?": "Settings, About, Health shows the data folder's size",
    "how much disk space do my notes take?": "Settings, About, Health shows the data folder's size",
    "how do I delete a note?": "Choose Delete in the note's own menu: it goes to the bin, not gone for good.",
    "how can I remove a note?": "Choose Delete in the note's own menu: it goes to the bin, not gone for good.",
    "what's the shortcut for search?": "Ctrl+P opens Find anything",
    "what is the keyboard shortcut to find things?": "Ctrl+P opens Find anything",
    "how do I change the theme?": "Settings, Appearance controls theme",
    "can I import from Notion?": "Settings, Import & export, Import from another app",
    "what's the weather like?": f"{OUTSIDE}: I only know Tessellate's own help, so I can't see the weather or the news.",
    "what's the news today?": f"{OUTSIDE}: I only know Tessellate's own help, so I can't see the weather or the news.",
    "tell me a joke": f"{OUTSIDE}: I only know Tessellate's own help, so jokes, poems and stories are beyond me.",
    "write me a poem": f"{OUTSIDE}: I only know Tessellate's own help, so jokes, poems and stories are beyond me.",
    "what is the capital of France": f"{OUTSIDE}: I only know Tessellate's own help.",
    "how tall is mount everest": f"{OUTSIDE}: I only know Tessellate's own help.",
    "how do I cook rice?": f"{OUTSIDE}: I only know Tessellate's own help.",
    "how do I tie a tie?": f"{OUTSIDE}: I only know Tessellate's own help.",
    "what is 2+2": "2 + 2 is 4.",
    "what's 12 x 3?": "12 × 3 is 36.",
    "10/4": "10 ÷ 4 is 2.5.",
    "should I use tags or categories?": "Let filing do the first pass",
    "tips for studying": "Turn your notes into practice",
    "what is chat good for?": "Use Chat to ask about your own notes",
}


class _Down:
    def is_running(self):
        return False


class _Manager:
    def utility_model(self):
        return ""


def _say(question: str, tab: str = "notes", context: str | None = None) -> str:
    return help_chat.offline_answer(question, tab, context)["content"]


def test_the_eval_is_thirty_questions_and_mostly_outside_the_advice_subjects():
    assert len(PINNED) >= 30
    outside = [q for q in PINNED if guide_advice.match(q) is None]
    assert len(outside) * 2 > len(PINNED), len(outside)


@pytest.mark.parametrize("question", sorted(PINNED))
def test_each_question_gets_its_answer_first(question):
    said = _say(question)
    assert said.startswith(PINNED[question]), said[:200]


@pytest.mark.parametrize("question", sorted(PINNED))
def test_the_stream_with_the_model_down_says_the_same(question):
    reply = help_chat.answer(question, _Manager(), _Down())
    assert reply["content"].startswith(PINNED[question]), reply["content"][:200]


@pytest.mark.parametrize("question", ["what's the weather like?", "tell me a joke", "how do I cook rice?", "what is 2+2"])
def test_a_question_outside_the_app_gets_no_menu_and_no_tab_blurb(question):
    reply = help_chat.offline_answer(question, "dashboard", "Dashboard: your day at a glance.")
    assert "Did you mean" not in reply["content"]
    assert "Dashboard: your day" not in reply["content"]
    assert reply["sources"] == [] and reply["badges"] == []


@pytest.mark.parametrize("question", ["how do I see my streak", "how do I set a reminder", "how does this work"])
def test_a_how_to_with_an_app_word_still_finds_its_topic(question):
    assert help_chat.topics_for(question, "dashboard"), question


def test_the_new_answers_stand_on_topics_that_exist():
    ids = {t["id"] for t in help_chat.HELP_TOPICS}
    for fact in guide_advice.FACTS:
        assert fact.topics and set(fact.topics) <= ids, fact.id


@pytest.mark.parametrize("question", ["how much does it cost", "is it free?", "is there a subscription"])
def test_cost_still_answers_cost(question):
    assert _say(question).startswith("There is nothing to buy in the app")


@pytest.mark.parametrize("question", sorted(q for q, said in PINNED.items() if said.startswith(OUTSIDE)))
def test_the_outside_line_never_blames_the_model_and_says_where_to_look(question):
    said = _say(question)
    assert "model" not in said.lower() and "Settings, Help" in said
