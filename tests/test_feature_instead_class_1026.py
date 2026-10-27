"""A word that only a help line's examples hold is not an app feature (composer9
Remaining, the dialogue turn "what about running?" answered "Running is one of
the app's own tools": the follow-up topic gives "(what about running?, and
Oppenheimer?, ...)" as examples). The class: any short message whose word sits
in a help topic only inside brackets or quotes, said to a notebook that does
not hold it, is a missing word, not a request for the feature."""

from __future__ import annotations

import functools
import re

import pytest

from tessellate.ai import composer, help_chat
from tests import _composer_eval as E

SHOW = E.load()
NOTES = E.notes_for(SHOW["questions"][24], SHOW)
ON = E.today(SHOW)

#: Words that name the example, not the feature.
SAID = [
    "what about running?",
    "what about running",
    "what about swimming",
    "and Oppenheimer?",
    "what about Oppenheimer",
    "python snake",
]

_EXAMPLE = re.compile(r"\([^)]*\)|\"[^\"]*\"|“[^”]*”|‘[^’]*’")


def _example_only_words() -> list[tuple[str, str]]:
    """(topic id, word) for every word of four letters or more that the Guide
    holds only inside bracketed or quoted examples: in no topic's own words,
    keywords or id."""
    outside: set[str] = set()
    inside: dict[str, str] = {}
    for topic in help_chat.HELP_TOPICS:
        body = str(topic.get("body") or "")
        keys = " ".join(topic.get("keywords") or ()) + " " + str(topic.get("id", "")).replace("-", " ")
        outside |= set(re.findall(r"[a-z]{4,}", (_EXAMPLE.sub(" ", body) + " " + keys).lower()))
        for word in re.findall(r"[a-z]{4,}", " ".join(_EXAMPLE.findall(body)).lower()):
            inside.setdefault(word, topic["id"])
    return sorted((topic, word) for word, topic in inside.items() if word not in outside)


def _says_feature(question: str) -> bool:
    text = composer.compose(question, NOTES, today=ON)["text"]
    return "own tools" in text


@pytest.mark.parametrize("question", SAID)
def test_a_word_from_a_help_example_is_a_missing_word(question):
    assert not _says_feature(question), question


def test_the_topics_were_found():
    assert len(_example_only_words()) > 20


@functools.cache
def _derived() -> list[tuple[str, str]]:
    return _example_only_words()


def test_every_example_only_word_in_the_guide_is_a_missing_word():
    """Each topic's own example words, said as "what about <word>":
    the derived half of the class, so a topic added later is covered."""
    said = [f"what about {word}" for _topic, word in _derived()]
    wrong = [q for q in said if _says_feature(q)]
    assert not wrong, wrong[:10]
