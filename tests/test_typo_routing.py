"""One slip in any word of a registered phrase routes as the clean phrase
does (BACKLOG "Type tolerance everywhere": "every registered command phrase
with one keyboard-neighbour slip, one swap, one dropped and one doubled
letter must route as the clean phrase does"). Measured 2026-10-17 before the
router-guided repair (`question_noise.guided`): 283 of 339; after: 339."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.ai import act_registry, commands, intent, question_noise, reading, utilities
from tessellate.entry import manager

READER = reading.__name__
NOW = datetime(2026, 10, 17, 12)
_ROWS = ("qwertyuiop", "asdfghjkl", "zxcvbnm")
_NEAR = {c: (r[i - 1] if i else "") + (r[i + 1] if i + 1 < len(r) else "") for r in _ROWS for i, c in enumerate(r)}

PHRASES = [a.example for a in act_registry.ACTS.values()] + [
    "what did I write this week", "what is due soon", "how many notes do I have", "search the web for sandwiches",
    "summarise my recent notes", "what time is it in japan", "convert 5 miles to km", "what have I saved recently",
    "remind me to water the plants every sunday", "what do my notes cover",
]


def slips(word: str) -> set[str]:
    """One dropped, one doubled, one swapped and one keyboard-neighbour
    letter, in the middle of the word."""
    if len(word) < 4 or not word.isalpha():
        return set()
    i = len(word) // 2
    out = {word[:i] + word[i + 1:], word[:i] + word[i] + word[i:], word[:i - 1] + word[i] + word[i - 1] + word[i + 1:]}
    if _NEAR.get(word[i].lower()):
        out.add(word[:i] + _NEAR[word[i].lower()][0] + word[i + 1:])
    return out - {word}


def _route(text: str) -> tuple:
    return intent.classify(text), (commands.read_typed(text, NOW) or {}).get("intent")


@pytest.mark.parametrize("phrase", PHRASES)
def test_a_slip_in_any_word_routes_as_the_clean_phrase(phrase):
    clean = _route(phrase)
    words = phrase.split()
    wrong = []
    for i, word in enumerate(words):
        for slip in slips(word):
            typed = " ".join([*words[:i], slip, *words[i + 1:]])
            if _route(typed) != clean:
                wrong.append((typed, _route(typed)))
    assert not wrong, (clean, wrong)


@pytest.mark.parametrize(
    "text",
    ["home", "Tom", "the", "what tie should I wear to the wedding", "a form about taxes", "my concert in Tokyo",
     "remind me to watter the plants every sunday"],
)
def test_a_real_sentence_is_not_bent_into_a_command_or_a_utility(text):
    """The router decides, and only a router word: a real word becomes a
    content word only where a utility's anchored pattern then takes it."""
    assert utilities.kind_of(text) in (None, "until_note") or text.startswith("remind"), (text, utilities.kind_of(text))
    if not text.startswith("remind"):
        assert commands.read_typed(text, NOW) is None, text
    assert intent.classify("remind me to watter the plants every sunday") == "act"


def test_the_fixture_strings_are_not_read_by_the_guided_repair():
    """Every question string in the composer fixtures that neither parse
    nor plain repair made a command stays as it is (0 of 5,953, measured)."""
    from pathlib import Path

    seen: set[str] = set()

    def walk(obj):  # noqa: ANN001, ANN202
        if isinstance(obj, str) and 3 <= len(obj) <= 140:
            seen.add(obj)
        elif isinstance(obj, dict):
            for key, value in obj.items():
                if key in ("question", "typed", "text", "ask", "message") or isinstance(value, (dict, list)):
                    walk(value)
        elif isinstance(obj, list):
            for value in obj:
                walk(value)

    for path in (Path(__file__).parent / "fixtures" / "composer").glob("*.json"):
        walk(json.loads(path.read_text(encoding="utf-8")))
    bent = []
    for text in sorted(seen):
        tidy = question_noise.tidy(text)
        if commands.read(question_noise.repair(tidy), NOW) is None and commands.read(tidy, NOW) is None:
            if commands.read_typed(text, NOW) is not None:
                bent.append(text)
    assert not bent, bent[:10]


def test_a_slipped_act_runs_through_chat_with_no_model(client, session):
    entry = manager.create_entry(session, "Dentist appointment on Tuesday at 3pm")
    session.commit()
    events = []
    with client.stream("POST", "/chat/stream", json={"question": "pin the dentist noe", "use_tools": True}) as response:
        for line in response.iter_lines():
            if line.strip():
                events.append(json.loads(line))
    session.expire_all()
    from tessellate.core.database import Entry

    assert session.get(Entry, entry.id).pinned, events[-3:]
