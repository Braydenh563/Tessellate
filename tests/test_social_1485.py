"""Social lines are never searched (INBOX 1485, the owner, 2026-10-31).

A ping ("test", "hi test test"), filler before a greeting ("errrmmm. hi"),
a question about who or what it is talking to ("r u an ai??") and a repair
line ("not what I asked") are social turns: answered in a sentence or two,
never a notebook search and never a web search, in Chat and in Agent mode,
with Web on, with a model or without (CHAT_PLAN decision 75). A hello that
names the last note links it, and a note is never a place.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.ai import intent, question_noise
from tessellate.core import deps
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = datetime(2026, 10, 31, 15, 45)

PINGS = ["test", "hi test test", "testing 123", "errrmmm. hi test test", "Test", "test test", "hello test", "umm test", "hey, test", "testing", "test?"]
PINGS_PLAIN = ["is this working", "is this thing on", "hey is this working?"]
IDENTITY = [
    "whoa, stop right there, r u an ai??", "are you a bot", "who are you", "are you real", "what are you",
    "are u an ai??", "r u a bot", "are you human", "am i talking to a bot", "is this an ai", "are you a real person?",
    "wait are you an AI", "are u a robot lol",
]
FILLER_GREETINGS = ["umm hi", "uhh hello", "hmm, hey", "errrmmm. hi", "erm hi there"]
REPAIRS = ["not what I asked", "that's wrong", "no I meant", "you misunderstood", "thats not what i asked", "you got it wrong"]

_NOTES = (
    "# Party Thoughts\n\nA test of the party games before Saturday.",
    "# Test Document\n\nThis is a test of the quiet garden plan.",
    "# Test-driven development\n\nWrite the test first, then the code.",
    "# Dentist\n\nCheck-up booked for the 21st.",
)


@pytest.fixture()
def notebook(session, monkeypatch):
    from tessellate.api import routes_chat
    from tessellate.core import config

    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for text in _NOTES:
        manager.create_entry(session, text)
    session.commit()
    deps.get_config().set_preference("web_search_enabled", True)
    return session


@pytest.fixture()
def no_web(monkeypatch):
    """Records every web search: a social line must never make one."""
    from tessellate.search import websearch

    seen: list[str] = []

    def search(q, *a, **k):  # noqa: ANN001, ANN002, ANN003
        seen.append(q)
        return []

    monkeypatch.setattr(websearch, "search_web", search)
    return seen


def _quoted(text: str) -> bool:
    """Whether a reply quotes a seeded note's body (a search's answer)."""
    return any(body in text for body in ("party games", "quiet garden", "Write the test first", "Check-up booked"))


def _asks(out: dict) -> list[str]:
    return [a for e in out.get("offer", []) if e["offer"].get("kind") == "ask" for a in e["offer"]["asks"]]


# --- the reading ------------------------------------------------------------------


@pytest.mark.parametrize("said", ["hi test test", "hey test", "yo test", "hi there", "sup test"])
def test_a_small_talk_word_is_never_glued_to_its_neighbour(said):
    assert question_noise.repair(said) == said


@pytest.mark.parametrize(("said", "left"), [
    ("errrmmm. hi test test", "hi test test"), ("umm hi", "hi"), ("uhh, hello", "hello"), ("hmm test", "test"),
    ("erm what did I write about golf", "what did I write about golf"), ("hmm", "hmm"), ("umm", "umm"),
    ("summer plans", "summer plans"), ("the hum of the fridge", "the hum of the fridge"),
])
def test_filler_is_dropped_before_reading(said, left):
    assert question_noise.drop_filler(said) == left


@pytest.mark.parametrize("said", PINGS + PINGS_PLAIN)
def test_a_ping_is_a_test(said):
    assert intent.is_test(said), said
    assert intent.classify(said) == intent.SMALLTALK


@pytest.mark.parametrize("said", IDENTITY)
def test_an_identity_question_is_small_talk_about_atlas(said):
    assert question_noise.social_kind(said) == "who", said
    assert intent.classify(said) == intent.SMALLTALK


@pytest.mark.parametrize("said", ["are u ok", "are you good", "are u well?", "are you alright", "how are u"])
def test_are_you_well_is_still_how_are_you(said):
    assert question_noise.social_kind(said) == "how", said


@pytest.mark.parametrize("said", REPAIRS)
def test_a_repair_line_is_social(said):
    assert question_noise.social_kind(said) == "repair", said
    assert intent.classify(said) == intent.SMALLTALK


@pytest.mark.parametrize("said", ["is the test on friday", "what did I write about the test", "test results from the lab", "who are you seeing on friday", "are you able to find my golf notes"])
def test_a_question_with_test_or_you_in_it_is_still_a_question(said):
    assert not intent.is_test(said)
    assert question_noise.social_kind(said) is None, said


# --- through the route, no model ---------------------------------------------------


@pytest.mark.parametrize("tools", [False, True])
def test_a_ping_says_it_works_asks_and_offers_the_matching_notes(client, notebook, no_web, tools):
    for said in PINGS:
        out = _ask(client, said, use_tools=tools)
        text = out["text"]
        assert not out.get("grounding") and not _quoted(text), (said, text)
        assert "notes about" not in text and "hitest" not in text and "errrmmm" not in text, (said, text)
        assert "?" in text and "search" in text.lower(), (said, text)
        assert "Three notes mention “test”" in text or "three notes mention “test”" in text, (said, text)
        assert any("test" in a.lower() for a in _asks(out)), (said, out.get("offer"))
        assert len(text) <= 160 and "!" not in text and chr(0x2014) not in text, (said, text)
    #: The chip is a search of the notes it counted.
    shown = _ask(client, _asks(out)[0], use_tools=tools)
    assert "Test Document" in shown["text"] or shown.get("grounding"), shown["text"]
    assert no_web == []


@pytest.mark.parametrize("tools", [False, True])
def test_is_this_working_says_it_is_and_lists_nothing(client, notebook, no_web, tools):
    for said in PINGS_PLAIN:
        out = _ask(client, said, use_tools=tools)
        assert not out.get("grounding") and not _quoted(out["text"]) and "#/notes/" not in out["text"], (said, out["text"])
    assert no_web == []


@pytest.mark.parametrize("tools", [False, True])
def test_an_identity_question_says_what_it_is_and_never_searches(client, notebook, no_web, tools):
    for said in IDENTITY:
        out = _ask(client, said, use_tools=tools)
        text = out["text"]
        assert "Atlas" in text, (said, text)
        assert not out.get("grounding") and not _quoted(text), (said, text)
        assert "search service" not in text and "web" not in text.lower(), (said, text)
        assert not text.startswith(("Good.", "Fine", "Doing well")), (said, text)
        assert text.count(".") <= 3 and "the ai" not in text.lower(), (said, text)
    assert no_web == []


@pytest.mark.parametrize("tools", [False, True])
def test_filler_and_a_greeting_is_a_greeting(client, notebook, no_web, tools):
    for said in FILLER_GREETINGS:
        out = _ask(client, said, use_tools=tools)
        assert not out["text"].startswith(("Understood", "Got it", "Ok")), (said, out["text"])
        assert not out.get("grounding") and not _quoted(out["text"]), (said, out["text"])
    assert no_web == []


@pytest.mark.parametrize("tools", [False, True])
def test_a_repair_owns_the_miss_and_gives_the_better_reading(client, notebook, no_web, tools):
    history = [{"question": "are u an ai??", "answer": "Good. What can I find for you?"}]
    for said in REPAIRS:
        out = _ask(client, said, use_tools=tools, history=history)
        text = out["text"]
        assert text.startswith("Sorry"), (said, text)
        assert "“are u an ai??”" in text and "small talk" in text, (said, text)
        assert "program" in text and "Atlas" in text, (said, text)
        assert not out.get("grounding") and not _quoted(text) and "latest on" not in str(out.get("offer")), (said, text)
    assert no_web == []


def test_a_repair_with_nothing_better_asks_what_was_meant(client, notebook, no_web):
    history = [{"question": "what about the garden", "answer": "This is a test of the quiet garden plan.", "objects": ["Test Document"]}]
    out = _ask(client, "not what I asked", use_tools=False, history=history)
    assert out["text"].startswith("Sorry") and "“what about the garden”" in out["text"] and "a search of your notes" in out["text"]
    assert out["text"].rstrip().endswith("?") and not out.get("grounding")


# --- the hello -------------------------------------------------------------------


@pytest.mark.parametrize("tools", [False, True])
def test_a_hello_links_the_last_note_and_never_puts_you_in_it(client, session, monkeypatch, tools):
    from tessellate.api import routes_chat
    from tessellate.core import config

    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    entry = manager.create_entry(session, "# 考え：仕事を済ませてから、練習としてゴルフを数球打った（笑）\n\nゴルフ")
    session.commit()
    deps.get_config().set_preference("web_search_enabled", True)
    seen = set()
    for n, said in enumerate(["hellooo", "hi", "hey there", "hello", "good afternoon", "hiya", "heyyy", "yo"] * 3):
        out = _ask(client, said, use_tools=tools, attempt=n)
        text = out["text"]
        assert "you were in" not in text and "left off at" not in text, text
        if "考え" in text:
            assert f"](#/notes/{entry.id})" in text, text
            seen.add(text)
    assert seen, "no hello named the last note"


def test_a_long_title_is_cut_once_in_the_hello(client, session, monkeypatch):
    from tessellate.api import chat_extra

    title = "A very long title about the garden plan and the shed and the fence and the gate we talked about"
    manager.create_entry(session, f"# {title}\n\nBody.")
    session.commit()
    for n in range(12):
        line = chat_extra.welcome_line(session, NOW, question="hello", seed=f"s{n}", link=True)
        if "#/notes/" in line:
            label = line.split("[", 1)[1].split("](", 1)[0]
            assert label.endswith("…") and label.count("…") == 1 and len(label) <= 61, label
            return
    pytest.fail("no welcome named the last note")


def test_a_long_unspaced_title_is_cut_once():
    from tessellate.ai import realise

    cut = realise.cut_title("考" * 90, 60)
    assert cut.endswith("…") and cut.count("…") == 1 and len(cut) <= 61, cut


# --- with a model (decision 75): a social line is not searched either ------------


@pytest.mark.parametrize("tools", [False, True])
def test_with_a_model_a_social_line_is_not_searched(ai_client, fake_ollama, notebook, no_web, tools):
    seen: list[list[dict]] = []
    original = fake_ollama.chat_stream

    def recording(model, messages, mode=None):  # noqa: ANN001
        seen.append(messages)
        return original(model, messages, mode)

    fake_ollama.chat_stream = recording
    for said in ["test", "hi test test", "errrmmm. hi test test", "is this working", "whoa, stop right there, r u an ai??", "are u an ai??", "not what I asked"]:
        seen.clear()
        out = _ask(ai_client, said, use_tools=tools)
        prompt = "\n".join(str(m.get("content")) for msgs in seen for m in msgs)
        assert not out.get("grounding"), said
        assert not _quoted(prompt) and not _quoted(out["text"]), said
        assert "hitest" not in prompt and "errrmmm" not in prompt, said
    assert no_web == []
