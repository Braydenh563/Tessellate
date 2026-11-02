"""INBOX 1459 (was 1453; the owner, 2026-10-31, Chat, no model), fixed by class (1357).

1. "yooooo" was read as stray keys: a stretched word is read as its word
   before small talk and intent are matched ("heyyy", "hiii", "thxxx").
2. "fuck" got "Quite something" and an offer of more on "yooooo": a swear or
   a frustrated short line gets a calm, short line that offers help, and a
   follow-on offer only ever names a subject that matched notes.
3. "I can tell you're in Chat." said nothing: the surface the chat is typed
   in is not news, and what the app can see is said after a hello only.
4. "right, I need to do my tax return, should probs set a reminder" was
   searched for: a reminder wished for in passing is read as one, with the
   task the sentence names, and asks when.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.ai import commands, composer, intent, question_noise
from tessellate.ai import composer_aware as aware
from tests.test_composer_route_688 import _ask, _seed

NOW = datetime(2026, 10, 31, 7, 50)

# --- 1. a stretched word is read as its word ---------------------------------


@pytest.mark.parametrize(
    ("typed", "word"),
    [("yooooo", "yo"), ("heyyy", "hey"), ("hiii", "hi"), ("thxxx", "thx"), ("sooo good", "so good"),
     ("yesss", "yes"), ("pleaseeee", "please"), ("noooo", "no"), ("okkk", "ok"), ("Yooo!", "Yo!")],
)
def test_a_stretched_word_reads_as_its_word(typed, word):
    assert question_noise.destretch(typed) == word


@pytest.mark.parametrize("word", ["good", "coffee", "bookkeeper", "hmm", "zzz", "asdfgh", "Harbor", "jkjkjkjk"])
def test_a_word_that_is_not_stretched_is_left_alone(word):
    assert question_noise.destretch(word) == word


@pytest.mark.parametrize("typed", ["yooooo", "yooo", "heyyy", "heyyyyy", "hiii", "hiiiiii"])
def test_a_stretched_greeting_is_a_greeting(typed):
    assert not intent.is_mash(typed)
    assert intent.classify(typed) == intent.SMALLTALK
    assert composer.social_kind(typed) == "greeting"


@pytest.mark.parametrize("typed", ["thxxx", "thanksss", "tyyy", "cheersss"])
def test_stretched_thanks_is_thanks(typed):
    assert composer.social_kind(typed) == "thanks"


@pytest.mark.parametrize("typed", ["sooo good", "okkk", "yesss", "coool", "niceee"])
def test_a_stretched_reaction_is_small_talk_not_stray_keys(typed):
    assert intent.classify(typed) == intent.SMALLTALK
    assert composer.social_kind(typed) not in ("unclear", "test")


def test_real_stray_keys_are_still_stray_keys():
    for typed in ("asdfgh", "jkjkjkjk", "kjhgf lkjh"):
        assert composer.social_kind(typed) == "unclear"


# --- 2. a swear or a frustrated line -------------------------------------------

FRUSTRATED = ["fuck", "ugh", "wtf", "this is useless", "ffs", "for fucks sake", "argh", "fucking hell", "this sucks"]


@pytest.mark.parametrize("typed", FRUSTRATED)
def test_a_frustrated_line_is_its_own_kind(typed):
    assert intent.classify(typed) == intent.SMALLTALK
    assert composer.social_kind(typed) == "frustrated"


@pytest.mark.parametrize("voice", ["natural", "professional"])
@pytest.mark.parametrize("seed", [f"s{n}" for n in range(8)])
def test_a_frustrated_line_gets_a_calm_short_offer_of_help(voice, seed):
    for typed in FRUSTRATED:
        said = composer.social(typed, "smalltalk", previous="I couldn't make that out.", last_question="yooooo", voice=voice, seed=seed)
        assert "Quite something" not in said and "yooooo" not in said
        assert len(said) <= 110 and "!" not in said and chr(0x2014) not in said
        assert said.endswith("?") or any(w in said.lower() for w in ("tell me", "say", "you need"))


def test_both_voices_have_eight_frustrated_lines():
    assert len(composer.SOCIAL["frustrated"]) >= 8
    assert len(composer.SOCIAL_PROFESSIONAL["frustrated"]) >= 8


@pytest.mark.parametrize("before", ["yooooo", "asdfgh", "fuck", "test", "hiii", "lol"])
@pytest.mark.parametrize("now", ["ok", "lol", "wow", "thanks", "nice"])
def test_a_follow_on_never_names_a_turn_that_was_not_about_notes(before, now):
    said = composer.social(now, "smalltalk", previous="Hmm.", last_question=before, seed="x")
    assert f"“{before}”" not in said


def test_a_follow_on_still_names_a_subject_that_matched_notes():
    said = composer.social("thanks", "smalltalk", previous="Ship it on 14 November.", last_question="when is the harbor launch", seed="x")
    assert "harbor launch" in said.lower()


def test_through_the_route_fuck_after_yooooo(client, session):
    _seed(session)
    first = _ask(client, "yooooo", use_tools=False, screen={"tab": "chat"})
    hist = [{"question": "yooooo", "answer": first["text"]}]
    out = _ask(client, "fuck", use_tools=False, history=hist, screen={"tab": "chat"})
    assert "Quite something" not in out["text"] and "yooooo" not in out["text"]
    assert "you're in Chat" not in first["text"] + out["text"]
    assert "stray keys" not in first["text"] and "make that out" not in first["text"]


@pytest.mark.parametrize("typed", ["yooooo", "thxxx", "heyyy", "hiiii"])
def test_through_the_route_a_stretched_word_is_never_a_nickname_or_stray_keys(client, session, typed):
    _seed(session)
    out = _ask(client, typed, use_tools=False)
    low = out["text"].lower()
    assert typed not in low and "stray keys" not in low and "make that out" not in low and "you called" not in low, out["text"]


def test_through_the_route_a_follow_on_needs_the_notes_named(client, session):
    _seed(session)
    hist = [{"question": "what is the weather like", "answer": "None of your notes mention “weather”. Could you put it another way?"}]
    out = _ask(client, "ok", use_tools=False, history=hist)
    assert "weather" not in out["text"]


# --- 3. the surface the chat is typed in is not news ----------------------------


@pytest.mark.parametrize("tab", ["chat", "ask"])
def test_the_chat_tab_alone_says_nothing(tab):
    for seed in ("a", "b", "c", "d", "e"):
        assert aware.opening(aware.build(tab=tab), seed) == ""


def test_another_tab_or_an_open_note_is_still_said():
    assert "Notes" in aware.opening(aware.build(tab="notes"), "a")
    assert "“Dentist”" in aware.opening(aware.build(tab="chat", open_title="Dentist"), "a")


def test_only_a_hello_says_what_the_app_can_see(client, session):
    _seed(session)
    for typed in ("ok", "lol", "fuck", "asdfgh"):
        out = _ask(client, typed, use_tools=False, screen={"tab": "notes"})
        assert "you're in Notes" not in out["text"], typed


# --- 4. a reminder wished for in passing ------------------------------------------

PASSING = [
    ("right, I need to do my tax return, should probs set a reminder", "do my tax return"),
    ("I need to call the bank, remind me", "call the bank"),
    ("I should set a reminder to renew my passport", "renew my passport"),
    ("gotta remember to pay rent", "pay rent"),
    ("don't let me forget to water the plants", "water the plants"),
    ("prolly should set a reminder to email Sam", "email Sam"),
    ("ok so I have to book the vet, can you remind me", "book the vet"),
    ("need to remember to bring the charger", "bring the charger"),
]


@pytest.mark.parametrize(("typed", "task"), PASSING)
def test_a_reminder_wished_for_in_passing_is_read_with_its_task(typed, task):
    found = commands.read_typed(typed, NOW)
    assert found and found["intent"] == "reminder", typed
    assert found["said"].lower() == task.lower()
    assert not found["time_given"]


def test_a_time_in_the_sentence_is_kept():
    found = commands.read_typed("I need to do my tax return on Friday, should probs set a reminder", NOW)
    assert found["intent"] == "reminder" and found["time_given"] and found["said"].lower() == "do my tax return"
    found = commands.read_typed("I need to do my tax return, should probs set a reminder for friday at 9", NOW)
    assert found["intent"] == "reminder" and found["time_given"] and found["said"].lower() == "do my tax return"


@pytest.mark.parametrize(
    "typed",
    [
        "I set a reminder to call mum yesterday",
        "did I set a reminder for the dentist?",
        "I don't need a reminder for that",
        "that reminds me, what did I write about golf",
        "I remember to water the plants every day",
        "I should probably set a reminder",
        "no need to set a reminder",
    ],
)
def test_what_is_not_a_reminder_wish_is_not_read_as_one(typed):
    found = commands.read_typed(typed, NOW)
    assert not found or found["intent"] != "reminder", typed


def test_a_noun_task_is_asked_about_not_to(app_state):
    line = commands.ask_when("the bins")
    assert "to the bins" not in line and "about the bins" in line


@pytest.mark.parametrize(("typed", "task"), PASSING[:4])
def test_through_the_route_it_asks_when_with_no_model(client, session, typed, task):
    _seed(session)
    out = _ask(client, typed, use_tools=False)
    #: Said back in the second person: "do my tax return" is "do your tax return".
    said = task.lower().replace(" my ", " your ")
    assert said in out["text"].lower() and out["text"].rstrip().endswith("?"), out["text"]
    assert "notes mention" not in out["text"]


def test_through_the_route_it_asks_when_with_a_model_up(ai_client, session):
    #: CHAT_PLAN decision 75: model on and off, the reminder is the act's.
    _seed(session)
    out = _ask(ai_client, PASSING[0][0], use_tools=False)
    assert "do your tax return" in out["text"].lower() and out["text"].rstrip().endswith("?"), out["text"]


def test_the_time_said_next_sets_it(client, session):
    _seed(session)
    typed = PASSING[0][0]
    first = _ask(client, typed, use_tools=False)
    out = _ask(client, "friday at 9", use_tools=False, history=[{"question": typed, "answer": first["text"]}])
    reminders = client.get("/reminders").json()
    items = reminders.get("reminders", reminders) if isinstance(reminders, dict) else reminders
    assert any("tax return" in str(r.get("text", "")).lower() for r in items), (out["text"], reminders)
