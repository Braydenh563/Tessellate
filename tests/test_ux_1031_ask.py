"""Audit 1031 rows 10 and 14 and 15 (N43, N35, N36, C45): what Ask says with no model.

N43: a Japanese word that no note holds answers with the miss sentence, as the
English form does, a Japanese word that a note holds finds it, and a word in
another script is never keys pressed at random (the "no vowel at all" test read
Latin letters only, so every sentence in kana, Han, Hangul or Cyrillic was
"I couldn't make that out")."""

from __future__ import annotations

import pytest

from tests import _seed_1031c as seed_c


def _go(client, monkeypatch):
    return seed_c.asker(client, monkeypatch)


@pytest.mark.parametrize("question", ["what did I write about golf", "what did I write about ゴルフ", "what did I write about 골프", "what did I write about 計画"])
def test_a_miss_in_any_script_says_nothing_matched(client, session, monkeypatch, question):
    from tessellate.core.database import Entry

    session.add(Entry(content="Called the plumber about the boiler", created_at=seed_c.NOW))
    session.commit()
    said, events = _go(client, monkeypatch)(question)
    assert said.strip(), events[-3:]
    assert "nothing" in said.lower() or "couldn't find" in said.lower() or "no mention" in said.lower() or "don't mention" in said.lower(), said


@pytest.mark.parametrize("question", ["golf", "ゴルフ", "골프", "гольф", "ゴルフについて何を書いた", "골프에 대해 뭐라고 썼어", "仕事の計画"])
def test_a_word_or_sentence_in_any_script_is_asked_back_never_called_stray_keys(client, session, monkeypatch, question):
    said, _ = _go(client, monkeypatch)(question)
    assert said.strip()
    assert "couldn't make that out" not in said and "stray keys" not in said.lower() and "keyboard" not in said.lower(), said


def test_a_japanese_word_a_note_holds_is_found(client, session, monkeypatch):
    from tessellate.core.database import Entry

    session.add(Entry(content="考え：仕事を済ませてから、練習としてゴルフを数球打った（笑）", created_at=seed_c.NOW))
    session.add(Entry(content="Called the plumber about the boiler", created_at=seed_c.NOW))
    session.commit()
    said, _ = _go(client, monkeypatch)("what did I write about ゴルフ")
    assert said.strip()
    assert "plumber" not in said.lower(), said


@pytest.mark.parametrize("text", ["ゴルフについて何を書いた", "仕事の計画", "привет мир", "здравствуйте", "αβγδε", "골프에 대해 뭐라고 썼어"])
def test_words_in_another_script_are_never_keys_pressed_at_random(text):
    from tessellate.ai import intent

    assert not intent.is_mash(text)


@pytest.mark.parametrize("text", ["asdfgh", "kjhgf lkjh", "jkjkjkjk", "qwertyui"])
def test_keys_pressed_at_random_still_are(text):
    from tessellate.ai import intent

    assert intent.is_mash(text)


def test_a_subject_no_note_holds_whole_is_led_by_the_words_that_are_held(client, session, monkeypatch):
    """N36: "plumber 9988" with no note holding "9988" said the notes "bear on plumber 9988", then,
    at the close, that they "do not talk about 9988"."""
    from tessellate.core.database import Entry

    for i in range(6):
        session.add(Entry(content=f"Called the plumber about the sink, visit {i}", created_at=seed_c.NOW))
    session.commit()
    said, _ = _go(client, monkeypatch)("what did I write about plumber 9988")
    lead = said.split("\n", 1)[0]
    assert "9988" not in lead and "plumber" in lead, lead
    assert said.count("9988") == 1, said


def test_a_vague_pick_is_one_note_and_filler_is_never_a_subject(client, session, monkeypatch):
    """N35: "errm a random ahh note" answered "Random ahh sketch." then "Also: ..." with chips about
    "random ahh". Now one note, picked, and the count is of the notes the notebook holds."""
    from tessellate.core.database import Entry

    session.add(Entry(content="A random ahh sketch\n\nA picture of a photo of a grassy hill", created_at=seed_c.NOW))
    session.add(Entry(content="Called the plumber", created_at=seed_c.NOW))
    session.commit()
    said, events = _go(client, monkeypatch)("errm a random ahh note")
    assert said.startswith("Here is one of your 2 notes, picked at random"), said
    assert "Also:" not in said
    chips = [chip for event in events for key in ("chips", "suggestions", "followups") for chip in event.get(key, [])]
    assert not any("random ahh" in str(chip).lower() for chip in chips), chips


@pytest.mark.parametrize(
    "question",
    [
        "when is the budget", "when is the Lisbon trip", "when is the gym log", "when did I write about sourdough",
        "when is the cloud note", "when did I write the passport note", "when was the dentist note written",
    ],
)
def test_a_when_question_says_the_date_then_the_distance_never_the_other_way(client, session, monkeypatch, question):
    """C45: one order for "when", the date and then how far back (the day is said in the question's
    register, `_SAY_WHEN`); "what's the latest on" and "how long ago" keep their own."""
    import re

    seed_c.seed(session, filler=0)
    said, _ = _go(client, monkeypatch)(question)
    assert not re.search(r"\b(?:ago|yesterday), on \d", said), said
    flipped = re.search(r"written (?:a|an|two|three|four|five|six|seven|eight|\w+) (?:weeks?|months?|days?|years?) ago", said)
    assert not flipped, said
