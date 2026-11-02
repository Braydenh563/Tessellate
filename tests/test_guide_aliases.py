"""The Guide answers the topic a realistic question is about (audit 1028
E31), for the class of phrasing, not the eight questions that were measured.
Each group is one intent in several phrasings, including ones the alias table
was not written from."""

from __future__ import annotations

import pytest

from tessellate.ai import guide_aliases, help_chat


def _first(question: str, tab: str | None = None) -> str:
    topics = help_chat.topics_for(question, tab)
    return topics[0]["id"] if topics else ""


def _ids(question: str) -> list[str]:
    return [t["id"] for t in help_chat.topics_for(question)]


CASES = {
    "documents": [
        "how do I export to PDF", "can I save a document as a pdf", "how do i turn a note into a pdf",
        "how to print to pdf", "download my document as pdf",
    ],
    "chat-controls": [
        "how do I edit my question", "can I change the message I sent", "how do I fix a typo in my question",
        "how do I edit my last message", "reword my question",
        "how do I attach a file to chat", "can I upload a document to the chat", "how do I add a picture to my message",
        "where is the paperclip", "how do i send an image to the ai in chat",
        "how do I stop the AI", "how do I cancel the answer", "can I interrupt the reply", "make it stop generating",
        "how do I stop it talking",
    ],
    "delete-data": [
        "how do I delete all my data", "how can I wipe everything", "erase all my notes", "how to remove everything i have saved",
        "can i start over from scratch", "how do I delete my whole notebook",
    ],
    "performance": [
        "why is the AI slow", "why are the answers so slow", "the chat takes forever to reply", "how can I speed up the AI",
        "how much RAM do I need", "how much memory does it use", "what are the system requirements", "does it need a lot of ram",
        "why is the app laggy", "the page is so slow",
    ],
    "model-downloads": [
        "which model for my laptop", "what model should I use on my old computer", "best model for a cheap pc",
        "which model will run on my machine", "recommend a model for my hardware", "what model fits my mac",
    ],
}


@pytest.mark.parametrize(("topic", "question"), [(t, q) for t, qs in CASES.items() for q in qs])
def test_a_realistic_question_reaches_its_topic(topic, question):
    ids = _ids(question)
    assert topic in ids[:2], (question, ids)


@pytest.mark.parametrize("question", [q for qs in CASES.values() for q in qs])
def test_the_same_question_in_any_case_or_with_a_typo_still_lands(question):
    assert _ids(question.upper()) == _ids(question)


@pytest.mark.parametrize(
    ("question", "not_first"),
    [
        ("how do I read text from a scanned pdf", "documents"),
        ("how do I import a pdf", "documents"),
        ("scan a pdf with ocr", "documents"),
    ],
)
def test_scanned_pdf_questions_keep_their_own_topic(question, not_first):
    assert _first(question) != not_first, _ids(question)


@pytest.mark.parametrize(
    ("question", "topic"),
    [
        ("how do I change the theme", "appearance"),
        ("how do i set a reminder for friday", "reminders"),
        ("how do I link two notes", "links"),
        ("how do I tag a note", "tags-categories"),
        ("how do I back up my notes", "import-export"),
        ("how do I reset my password", "security"),
    ],
)
def test_ordinary_questions_are_not_disturbed(question, topic):
    assert topic in _ids(question)[:3], (question, _ids(question))


def test_every_alias_names_real_topics():
    real = {t["id"] for t in help_chat.HELP_TOPICS}
    for name, _rx, ids in guide_aliases._ROWS:
        assert set(ids) <= real, (name, set(ids) - real)
    assert len(guide_aliases._ROWS) >= 40


def test_an_unplaced_question_offers_the_nearest_topics():
    said = help_chat.offline_answer("tell me about the mouse")["content"]
    assert "Did you mean:" in said, said


def test_a_question_sharing_no_word_gets_the_plain_line():
    said = help_chat.offline_answer("qzxv wplk")["content"]
    assert "Did you mean" not in said and said.startswith("The local model is not running"), said


def test_the_offline_answer_for_stop_the_ai_leads_with_the_chat_keys():
    said = help_chat.offline_answer("how do I stop the AI")["content"]
    assert "Escape" in said or "Ctrl+." in said, said


@pytest.mark.parametrize(
    ("question", "topic"),
    [
        ("I forgot the passcode", "lock"),
        ("can I use it from my iphone", "phone"),
        ("is my stuff safe", "privacy"),
        ("I want to switch to dark theme", "appearance"),
        ("is there a way to bring in my word files", "import-export"),
    ],
)
def test_a_soft_row_fills_in_when_the_keywords_reach_nothing(question, topic):
    assert topic in _ids(question)[:3], (question, _ids(question))
