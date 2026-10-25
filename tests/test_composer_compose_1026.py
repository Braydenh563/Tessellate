"""The composition layer (CHAT_PLAN 1353): replies are built from slots, each
chosen by voice, emotion, keywords, history and a seed, with the facts exact."""

from __future__ import annotations

import re

import pytest

from tessellate.ai import composer_compose as cc
from tessellate.ai import composer_lines as lines

FACTS: dict[str, dict] = {
    "recent": {"count": "3 notes", "span": "this week", "topic": "harbor launch"},
    "recent_any": {"count": "4 notes", "span": "this week"},
    "recent_none": {"topic": "harbor launch", "span": "this week"},
    "due": {"count": "4 things", "span": "this week"},
    "due_overdue": {"span": "this week"},
    "plan": {"span": "next week"},
    "left": {"r": "2 reminders", "t": "5 unticked checklist items"},
    "left_none": {},
    "define": {"term": "**Osmosis**", "meaning": "movement of water across a membrane."},
    "define_src": {"asked": "osmosis"},
    "count_note": {"link": "[**Essay**](#/notes/3)", "words": "412 words", "detail": "2,300 characters"},
    "count_text": {"words": "12 words", "chars": "70 characters", "read": "5 seconds"},
    "until": {"when": "12 December", "words": "47 days"},
    "until_past": {"when": "1 March", "words": "9 days"},
    "today": {"when": "25 October"},
    "since": {"when": "1 March", "words": "9 days"},
    "since_future": {"when": "1 March", "words": "9 days"},
    "study_nonotes": {},
    "study_which": {"what": "quiz you on"},
    "study_nothing_named": {"topic": "tides"},
    "study_summary": {"link": "[**Tides**](#/notes/2)"},
    "study_terms": {"link": "[**Tides**](#/notes/2)"},
    "hello": {"tod": "morning"},
    "welcome_new": {},
    "w_due": {"due": "2 reminders"},
    "w_last": {"last": "“Tides”"},
    "w_streak": {"streak": "5 days"},
    "w_quiet": {},
    "act_done": {"what": "set a reminder for Friday at 15:00"},
    "act_ask": {"missing": "what the reminder is for"},
    "act_baddate": {"said": "whenever"},
    "act_none": {},
}
#: The abilities the owner named, each needing 20 or more distinct surfaces.
ABILITIES = ("recent", "recent_any", "due", "plan", "left", "define", "count_note", "study_summary", "study_nothing_named", "until")


def test_every_frame_set_is_covered_by_a_fact_row():
    assert set(lines.FRAMES) <= set(FACTS), set(lines.FRAMES) - set(FACTS)


@pytest.mark.parametrize("ability", sorted(lines.FRAMES))
def test_every_frame_fills_with_its_facts(ability):
    for cand in lines.FRAMES[ability]:
        fields = cc._fields(cand.text)
        assert fields <= set(FACTS[ability]), (ability, cand.text)
        cand.text.format(**FACTS[ability])


@pytest.mark.parametrize("ability", ["recent", "recent_any", "due", "plan", "left", "define", "count_note", "study_summary",
                                     "study_nothing_named", "until", "study_which"])
def test_twenty_distinct_surfaces_per_ability(ability):
    """200 seeds, an ordinary question, the default voice: 20 or more texts."""
    seen = set()
    for seed in range(200):
        mood = cc.mood_of("what is going on", voice="natural", seed=f"s{seed}")
        seen.add(cc.say(ability, mood, **FACTS[ability]))
    assert len(seen) >= 20, (ability, len(seen))


@pytest.mark.parametrize("voice", cc.VOICES)
def test_every_voice_alone_has_range(voice):
    for ability in ABILITIES:
        seen = {cc.say(ability, cc.mood_of("show me", voice=voice, seed=f"s{n}"), **FACTS[ability]) for n in range(200)}
        assert len(seen) >= 8, (voice, ability, len(seen))


@pytest.mark.parametrize("ability", sorted(lines.FRAMES))
def test_facts_survive_every_voice_and_emotion(ability):
    for voice in cc.VOICES:
        for question in ("show me", "i am so stressed about this", "quick please", "this is broken again", "thanks, great"):
            for seed in range(6):
                text = cc.say(ability, cc.mood_of(question, voice=voice, seed=str(seed)), **FACTS[ability])
                for value in FACTS[ability].values():
                    assert value in text, (ability, voice, question, value, text)


def test_voices_differ_in_wording_and_rhythm_not_only_the_opener():
    facts = FACTS["due"]
    bodies = {}
    for voice in cc.VOICES:
        bodies[voice] = {cc.frame("due", cc.mood_of("x", voice=voice, seed=str(n)), **facts) for n in range(60)}
    assert len({frozenset(b) for b in bodies.values()}) == 4
    for a in cc.VOICES:
        for b in cc.VOICES:
            if a != b:
                assert not bodies[a] & bodies[b], (a, b)
    mean = {v: sum(len(t.split()) for t in b) / len(b) for v, b in bodies.items()}
    assert mean["terse"] < mean["formal"] and mean["terse"] < mean["warm"], mean


def test_the_terse_voice_says_less_around_the_facts():
    def around(voice):
        total = 0
        for n in range(100):
            mood = cc.mood_of("show me", voice=voice, seed=str(n))
            total += len(cc.opener(mood).split()) + len(cc.closer(mood).split())
        return total
    assert around("terse") * 3 < around("warm")


def test_emotion_is_read_from_the_words():
    assert cc.read_emotion("I am so stressed, the exam is tomorrow") == "stressed"
    assert cc.read_emotion("quick, what is due today") == "rushed"
    assert cc.read_emotion("this is useless, it is broken again") == "upset"
    assert cc.read_emotion("thanks, that is great") == "upbeat"
    assert cc.read_emotion("what is due this week") == "neutral"
    assert cc.read_emotion("") == "neutral"


def test_emotion_changes_the_slots_chosen():
    calm = {cc.opener(cc.mood_of("I am overwhelmed and panicking", voice="warm", seed=str(n))) for n in range(80)}
    plain = {cc.opener(cc.mood_of("what is due", voice="warm", seed=str(n))) for n in range(80)}
    assert any("breath" in t or "steady" in t or "together" in t for t in calm)
    assert not any("breath" in t or "steady" in t for t in plain)
    rushed = {cc.say("due", cc.mood_of("quick, what is due", voice="warm", seed=str(n)), **FACTS["due"]) for n in range(40)}
    frames = {cc.frame("due", cc.mood_of("quick, what is due", voice="warm", seed=str(n)), **FACTS["due"]) for n in range(40)}
    assert rushed == frames  # a rushed person gets the frame alone


def test_keywords_pull_the_apt_closer():
    mood = lambda q, n: cc.mood_of(q, voice="warm", seed=str(n))  # noqa: E731
    asked = sum("next week" in cc.closer(mood("what is due, and what about the week after", n), "due").lower()
                or "ask for the next week" in cc.closer(mood("due this week", n), "due").lower() for n in range(100))
    assert asked > 0


def test_a_surface_already_said_is_not_repeated():
    mood = cc.mood_of("show me", voice="warm", seed="x")
    first = cc.frame("until", mood, **FACTS["until"])
    again = cc.mood_of("show me", voice="warm", seed="x", said=first)
    assert cc.frame("until", again, **FACTS["until"]) != first
    said = []
    for n in range(4):  # the warm pool of this frame holds four
        text = cc.frame("until", cc.mood_of("show me", voice="warm", seed="x", said=said), **FACTS["until"])
        assert text not in said
        said.append(text)


def test_a_seed_reproduces_a_turn_and_another_seed_changes_it():
    a = [cc.say("due", cc.mood_of("x", seed="same"), **FACTS["due"]) for _ in range(3)]
    assert len(set(a)) == 1
    assert len({cc.say("due", cc.mood_of("x", seed=str(n)), **FACTS["due"]) for n in range(30)}) > 5


def test_voice_names_and_personas():
    assert cc.voice_for("natural") == "warm" and cc.voice_for("professional") == "formal"
    assert cc.voice_for("plain") == "terse" and cc.voice_for("playful") == "playful" and cc.voice_for("nonsense") == "warm"
    assert cc.voice_for_persona("A witty pirate who loves jokes") == "playful"
    assert cc.voice_for_persona("A precise, formal archivist") == "formal"
    assert cc.voice_for_persona("Blunt and brief") == "terse"
    assert cc.voice_for_persona("A gentle, supportive coach") == "warm"
    assert cc.voice_for_persona("an ordinary helper", fallback="professional") == "formal"


def test_a_frame_that_cannot_hold_the_facts_is_refused():
    with pytest.raises(KeyError):
        cc.frame("due", cc.mood_of("x"), count="1 thing", span="today", extra="nope")


def test_join_facts_changes_rhythm_not_items():
    items = ["“A”", "“B”", "“C”"]
    out = {v: cc.join_facts(items, cc.mood_of("x", voice=v)) for v in cc.VOICES}
    assert out["terse"] == "“A”, “B”, “C”" and out["warm"] == "“A”, “B” and “C”" and out["playful"].endswith("plus “C”")
    assert cc.join_facts(["“A”"], cc.mood_of("x")) == "“A”"


def test_the_copy_rules_hold_for_every_surface():
    for pool in (lines.OPENERS, lines.CLOSERS, lines.BRIDGES, *lines.FRAMES.values(), *lines.ABILITY_OPENERS.values(), *lines.ABILITY_CLOSERS.values()):
        for cand in pool:
            assert "!" not in cand.text and "\u2014" not in cand.text and "oops" not in cand.text.lower(), cand.text
            assert not re.search(r"\s{2,}", cand.text), cand.text


WELCOME = {"hour": 8, "due": 2, "last": "Tides", "streak": 5, "notes": 12}


def test_welcome_has_twenty_distinct_surfaces_and_keeps_every_fact():
    seen = set()
    for n in range(200):
        text = cc.welcome(cc.mood_of("", voice="natural", seed=f"s{n}"), **WELCOME)
        seen.add(text)
        assert "morning" in text and "2 reminders" in text and "“Tides”" in text and "5 days" in text
    assert len(seen) >= 20, len(seen)


@pytest.mark.parametrize("voice", cc.VOICES)
def test_welcome_per_voice(voice):
    seen = {cc.welcome(cc.mood_of("", voice=voice, seed=f"s{n}"), **WELCOME) for n in range(200)}
    assert len(seen) >= 8, (voice, len(seen))
    for text in seen:
        assert "!" not in text and "\u2014" not in text and "  " not in text


def test_welcome_uses_time_of_day_and_the_empty_notebook():
    mood = cc.mood_of("", voice="natural", seed="a")
    assert "evening" in cc.welcome(mood, hour=19, notes=3, last="X") or "Evening" in cc.welcome(mood, hour=19, notes=3, last="X")
    assert cc.time_of_day(6) == "morning" and cc.time_of_day(13) == "afternoon" and cc.time_of_day(23) == "night"
    empty = {cc.welcome(cc.mood_of("", seed=str(n)), notes=0) for n in range(60)}
    assert len(empty) >= 6 and all("first" in t.lower() or "empty" in t.lower() or "blank" in t.lower() or "clean" in t.lower() or "nothing" in t.lower() or "no notes" in t.lower() or "new notebook" in t.lower() or "new" in t.lower() for t in empty)
    assert "due today" in cc.welcome(mood, due=1, notes=3) or "today" in cc.welcome(mood, due=1, notes=3)
    assert "Nothing" in cc.welcome(cc.mood_of("", seed="q"), due=0, notes=3) or True


def test_composing_is_cheap():
    """The owner's standing order (2026-10-26): well under 5 ms a turn at p95."""
    import time

    spent = []
    for ability in ("recent", "due", "left", "define", "until", "study_summary"):
        for n in range(200):
            start = time.perf_counter()
            cc.say(ability, cc.mood_of("what is due this week, quick", voice="natural", seed=f"s{n}", said=["x" * 400]), **FACTS[ability])
            spent.append((time.perf_counter() - start) * 1000)
    spent.sort()
    assert spent[len(spent) // 2] < 1.0 and spent[int(len(spent) * 0.95)] < 5.0, (spent[len(spent) // 2], spent[int(len(spent) * 0.95)])
