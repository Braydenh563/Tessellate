"""A question an answer suggests is also a one-click chip (INBOX 1497)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from tessellate.ai import ask_chips, help_chat

SRC = Path(__file__).resolve().parent.parent / "src" / "tessellate" / "ai"


@pytest.mark.parametrize(("text", "chips"), [
    ("If it helps, ask me “how do I attach a note to a chat” and I will show you.", ["How do I attach a note to a chat?"]),
    ("A good next question here: “how do I tag a note”.", ["How do I tag a note?"]),
    ("To get going, ask me “what is left in Packing”.", ["What is left in Packing?"]),
    ("Try asking “show my pinned notes”.", ["Show my pinned notes"]),
    ("Ask me “when is the dentist” or “who is Tom”.", ["When is the dentist?", "Who is Tom?"]),
    ("You could say “list my open tasks” next.", ["List my open tasks"]),
    ("Ask me “how do I tag a note”, then ask me “how do I tag a note” again.", ["How do I tag a note?"]),
    ("Nothing suggested here.", []),
    ("He said “hello there” to me.", []),
    ("Ask me about “Packing”.", []),
    ("", []),
])
def test_a_quoted_suggestion_is_lifted_as_the_question_to_ask(text, chips):
    assert ask_chips.lift(text) == chips


def _templates():
    """Every plain string in the composer's and the Guide's wording that names a
    thing with a placeholder and suggests asking."""
    for name in ("composer_lines.py", "composer_aware.py", "composer.py", "help_chat.py", "help_topics_more.py", "guide_intent.py"):
        tree = ast.parse((SRC / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and "{" in node.value:
                if re.search(r"\b[Aa]sk(?:ing)?\b(?! (?:for|about|if|when you))", node.value) and re.search(r"\bask(?: me)?\b\s+[“\"a-z]", node.value, re.I):
                    yield name, node.value


def test_every_template_that_suggests_an_ask_lifts_to_a_chip():
    seen = 0
    bad = []
    for name, text in _templates():
        try:
            filled = text.format(t="Packing", title="Packing", topic="Lisbon", subject="Lisbon", howto="how do I tag a note", name="Packing", n=3)
        except (KeyError, IndexError, ValueError):
            continue
        seen += 1
        if not ask_chips.lift(filled):
            bad.append(f"{name}: {text!r}")
    assert not bad, "suggest a question a person would have to retype:\n" + "\n".join(bad)
    assert seen >= 8


def test_a_guide_reply_carries_its_suggestion_as_a_chip_to_the_guide():
    reply = help_chat.with_asks({"content": "Skills are saved prompts. If it helps, ask me “how do I attach a note to a chat” and I will show you."})
    assert reply["asks"] == ["How do I attach a note to a chat?"] and reply["asks_to"] == "guide"


def test_a_reply_with_its_own_asks_is_left_alone():
    own = {"content": "ask me “how do I tag a note”", "asks": ["Put this in Chat"], "asks_to": "chat"}
    assert help_chat.with_asks(own) == own


def test_the_guide_answer_with_a_screen_ends_in_a_chip():
    reply = help_chat._aware(  # noqa: SLF001
        {"content": "Skills are saved prompts you run from Chat.", "badges": [], "sources": []},
        "what are skills", "chat", ["Opened the Chat tab"],
    )
    if "ask me" in reply["content"].lower() or "next question" in reply["content"].lower():
        assert reply.get("asks"), reply


# The Guide leads with the sentence that names the act asked (coordinator, 2026-10-31).

ACT_QUESTIONS = [
    "how do I export documents?", "how do I export a document", "how can I export my notes", "how do I export my data",
    "can I export to Word", "how to export", "how do I import notes", "how do I import a PDF", "how do I import markdown files",
    "how do I print a document", "how do I print a note", "how do I save as PDF", "how do I share a note", "how do I share a document",
    "how do I delete a note", "how do I delete a document", "how do I restore a deleted note", "how do I restore a backup",
    "how do I move a card on the board", "how do I rename a tag", "how do I attach a file to a note", "how do I pin a note",
    "how do I pin a document",
]


@pytest.mark.parametrize("question", ACT_QUESTIONS)
def test_a_question_that_names_an_act_is_led_by_the_sentence_naming_it(question):
    from tessellate.ai import composer

    reply = help_chat.offline_answer(question, "notes")
    lead = reply["content"].split("\n\n")[0]
    act = composer._help_act(question)  # noqa: SLF001
    said = {composer._stem(w) for w in re.findall(r"[a-z]+", lead.lower())}  # noqa: SLF001
    assert act and composer._HELP_ACT_STEMS[act] & said, (question, lead)  # noqa: SLF001


def test_exporting_documents_is_not_led_by_the_editors_views():
    reply = help_chat.offline_answer("how do I export documents?", "documents")["content"]
    assert reply.startswith("Export your data as"), reply
    assert "four views" not in reply.split("\n\n")[0] and "mermaid" not in reply.lower().split("\n\n")[0]
    assert "Documents" in reply, "the E2E spec reads the reply for Documents"


def test_a_question_with_no_act_keeps_its_usual_lead():
    reply = help_chat.offline_answer("what are the document views", "documents")["content"]
    assert "four views" in reply.split("\n\n")[0], reply
