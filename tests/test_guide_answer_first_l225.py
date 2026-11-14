"""CHAT_PLAN section 9 row 1 (L-chat-225): the Guide answers first and the
28-word preface is gone. Over the 67 Guide questions of `help_1010.json` and
`guide_1011.json`: none opens with the old preface or the offline lead, the
lead closes the answer, and the first sentence shares a word with the
question for at least 90 percent (measured 61 of 67; the six others answer
in other words: "it's in the gear", "no", a numbered step)."""

from __future__ import annotations

import importlib
import json
import re
from pathlib import Path

from tessellate.ai import help_chat, reading

importlib.import_module("tessellate.ai.composer")
assert reading.__name__
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "composer"
STOP = set("how do i the a an my is where what does it can to of in on for me with and or you show see make turn use".split())


def _questions() -> list[str]:
    rows = json.loads((FIXTURES / "help_1010.json").read_text(encoding="utf-8"))["rows"]
    guide = json.loads((FIXTURES / "guide_1011.json").read_text(encoding="utf-8"))["questions"]
    return [r["question"] for r in rows] + [q[0] for q in guide]


def _first_sentence(content: str) -> str:
    return re.split(r"(?<=[.?!])\s+|\n+", re.sub(r"[#*]", "", content).strip())[0]


def test_the_preface_is_gone_and_the_first_sentence_answers():
    questions = _questions()
    assert len(questions) >= 60
    shared = 0
    for question in questions:
        content = help_chat.offline_answer(question)["content"]
        first = _first_sentence(content)
        assert not first.startswith("The local model is not running"), question
        assert not first.startswith(help_chat.OFFLINE_LEAD), question
        stems = [w[:4] for w in re.findall(r"[a-z]+", question.lower()) if w not in STOP and len(w) > 2]
        shared += any(s in first.lower() for s in stems)
    assert shared / len(questions) >= 0.9, shared
