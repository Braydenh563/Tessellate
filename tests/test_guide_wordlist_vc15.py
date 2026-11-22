"""The Guide reads a word the English list does not hold as the topics' nearest word (CHAT_PLAN VC15).

Thirty bank questions with a keyword spelt wrong by two edits or by a swap
(the mutation table below, deterministic): 25 reached the right topic first
before the word list was read, 28 after.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from tessellate.ai import help_chat, help_words, variants

BANK = json.loads((Path(__file__).parent / "fixtures" / "help_questions.json").read_text())
TOPICS = {t["id"]: t for t in help_chat.HELP_TOPICS}


def _first(question: str) -> str | None:
    return next((t["id"] for t in help_chat._matching_topics(question)), None)


def _mutate(word: str, i: int) -> str:
    m = len(word) // 2
    return [
        word[: m - 1] + word[m] + word[m - 1] + word[m + 1 :],
        word[:m] + word[m + 1 :],
        word[:m] + word[m] + word[m:],
        word[:m] + "x" + word[m + 1 :],
        word[: m - 1] + word[m] + word[m - 1] + word[m + 2 :],
    ][i % 5]


def _misspelt(count: int = 30) -> list[tuple[str, str]]:
    made: list[tuple[str, str]] = []
    for question, expected in BANK:
        if _first(question) != expected:
            continue
        own = {w for k in TOPICS[expected]["keywords"] for w in k.split() if len(w) >= 6}
        hit = [w for w in re.findall(r"[a-z']+", question.lower()) if w in own]
        if not hit:
            continue
        word = max(hit, key=len)
        made.append((re.sub(rf"\b{word}\b", _mutate(word, len(made)), question.lower(), count=1), expected))
        if len(made) == count:
            break
    return made


def test_misspelt_guide_questions_reach_the_right_topic():
    cases = _misspelt()
    assert len(cases) == 30
    right = sum(_first(q) == e for q, e in cases)
    assert right >= 28, [(q, e, _first(q)) for q, e in cases if _first(q) != e]


def test_a_word_the_list_holds_is_left_alone():
    english = variants.english()
    assert help_words.forgive(["thoughts", "pictures", "settings"], help_chat._KEYWORD_WORDS, english) == {}


def test_a_swapped_word_is_read_as_the_topics_word():
    fixes = help_words.forgive(["thuoght", "qwertyuiop"], help_chat._KEYWORD_WORDS, variants.english())
    assert fixes == {"thuoght": "thought"}


def test_a_short_word_is_not_guessed_at_two_edits():
    assert help_words.forgive(["abcde"], {"abxyz"}, frozenset()) == {}
