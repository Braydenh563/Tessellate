"""A language named as a property of a note finds notes by script or words
(INBOX 1490, the owner, 2026-10-31: "japanese note", "I have a nore written in
japanese", Web toggle on, a note in Japanese script in the notebook, answered
with the web search failure and a docker command)."""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.ai import note_language
from tessellate.core import deps
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = datetime(2026, 10, 31, 15, 45)

JAPANESE = "考え：仕事を済ませてから、練習としてゴルフを数球打った（笑）"
CHINESE = "今天我去了公园，天气很好，我们在那里吃了午饭。"
KOREAN = "오늘은 공원에 가서 점심을 먹었고 날씨가 좋았다."
RUSSIAN = "Сегодня я ходил в парк и ел обед, погода была хорошая."
ARABIC = "ذهبت اليوم إلى الحديقة وتناولت الغداء وكان الطقس جميلا."
FRENCH = "Aujourd'hui je suis allé au parc avec mes amis et nous avons mangé un sandwich dans le jardin."
SPANISH = "Hoy fui al parque con mis amigos y comimos un bocadillo en el jardín, y el día estuvo muy bien."
GERMAN = "Heute bin ich mit meinen Freunden in den Park gegangen und wir haben ein Brot im Garten gegessen."
ITALIAN = "Oggi sono andato al parco con i miei amici e abbiamo mangiato un panino nel giardino, è stato molto bello."
PORTUGUESE = "Hoje eu fui ao parque com os meus amigos e nós comemos um sanduíche no jardim, foi muito bom."
DUTCH = "Vandaag ben ik met mijn vrienden naar het park gegaan en we hebben een broodje in de tuin gegeten."
ENGLISH = "Today I went to the park with my friends and we ate a sandwich in the garden, and it was very good."

SAMPLES = {"japanese": JAPANESE, "chinese": CHINESE, "korean": KOREAN, "russian": RUSSIAN, "arabic": ARABIC, "french": FRENCH, "spanish": SPANISH,
           "german": GERMAN, "italian": ITALIAN, "portuguese": PORTUGUESE, "dutch": DUTCH}

ASKS = {
    "japanese": ["japanese", "Japanese?", "japanese note", "my japanese notes", "the japanese one", "I have a japanese note", "I have a nore written in japanese",
                 "I have a note written in japanese", "my note in Japanese", "notes written in japanese", "which note is in japanese", "do I have any notes in japanese",
                 "show me my japanese notes", "the note that is in japanese", "Japanese note?", "a note in japanese"],
    "chinese": ["chinese", "chinese note", "the chinese one", "notes written in chinese", "my notes in chinese"],
    "french": ["french", "french notes", "notes in french", "the note written in french", "my french one"],
    "korean": ["korean note", "notes in korean"],
    "russian": ["russian note", "my notes in russian"],
    "german": ["german notes", "notes written in german"],
    "spanish": ["spanish notes", "the spanish one"],
}
NOT_ABOUT_A_NOTE = [
    "how do you say hello in japanese", "translate this to french", "learn japanese", "japanese food recipes", "what is the japanese word for cat",
    "japanese restaurants near me", "who speaks german", "french revolution history", "what does bonjour mean in english", "best japanese anime",
    "japanese grammar", "how to say thanks in korean", "spanish lessons", "my golf notes", "what did I write about japan",
]


@pytest.mark.parametrize(("language", "text"), SAMPLES.items())
def test_a_note_is_found_in_its_own_language_and_no_other(language, text):
    assert note_language.is_in(text, language), language
    for other in SAMPLES:
        if other != language and not (other == "chinese" and language == "japanese"):
            assert not note_language.is_in(text, other), (language, other)


@pytest.mark.parametrize("language", SAMPLES)
def test_english_is_in_no_language(language):
    assert not note_language.is_in(ENGLISH, language)
    assert not note_language.is_in("Dentist check-up booked for the 21st. Ask about the night guard.", language)
    assert not note_language.is_in("", language)


def test_a_japanese_note_with_kanji_is_not_chinese_and_a_chinese_one_is_not_japanese():
    assert not note_language.is_in(JAPANESE, "chinese") and not note_language.is_in(CHINESE, "japanese")


def test_an_english_note_with_one_japanese_word_is_not_a_japanese_note():
    assert not note_language.is_in("Lunch with Sam on Friday, we talked about sushi (寿司) and the new menu, and then went for a long walk by the river.", "japanese")


@pytest.mark.parametrize(("language", "said"), [(lang, s) for lang, group in ASKS.items() for s in group])
def test_a_language_named_as_a_property_of_a_note_is_read(language, said):
    assert note_language.asked(said) == language, said


@pytest.mark.parametrize("said", NOT_ABOUT_A_NOTE)
def test_a_message_about_the_language_itself_is_not_one(said):
    assert note_language.asked(said) == "", said


_NOTES = (
    "# Dentist\n\nCheck-up booked for the 21st.",
    "# Quantum plan\n\nRead one chapter a week.",
    JAPANESE, CHINESE, FRENCH,
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
def web(monkeypatch):
    from tessellate.search import websearch

    seen: list[str] = []

    def search(q, *a, **k):  # noqa: ANN001, ANN002, ANN003
        seen.append(q)
        raise websearch.WebSearchError("Connection refused")

    monkeypatch.setattr(websearch, "search_web", search)
    return seen


def _asks(out: dict) -> list[str]:
    return [a for e in out.get("offer", []) if e["offer"].get("kind") == "ask" for a in e["offer"]["asks"]]


@pytest.mark.parametrize("tools", [False, True])
def test_the_owners_japanese_messages_list_the_japanese_note_and_never_search_the_web(client, notebook, web, tools):
    for said in ASKS["japanese"]:
        text = _ask(client, said, use_tools=tools)["text"]
        assert "考え" in text and "#/notes/3" in text, (said, text)
        assert "Dentist" not in text and "Quantum" not in text and "search service" not in text and "docker" not in text.lower(), (said, text)
        assert "one note" in text.lower(), (said, text)
    assert web == []


@pytest.mark.parametrize("tools", [False, True])
def test_each_language_finds_its_own_note(client, notebook, web, tools):
    for said, mark in (("chinese note", "#/notes/4"), ("notes in french", "#/notes/5"), ("french", "#/notes/5")):
        text = _ask(client, said, use_tools=tools)["text"]
        assert mark in text and text.count("\n- [") == 1, (said, text)
    assert web == []


@pytest.mark.parametrize("tools", [False, True])
def test_a_language_none_of_the_notes_is_in_says_so_and_offers_the_web_only_as_a_chip(client, notebook, web, tools):
    for said, language in (("korean note", "korean"), ("notes in russian", "russian"), ("my arabic notes", "arabic")):
        out = _ask(client, said, use_tools=tools)
        assert "None of your notes look" in out["text"] and "](#/notes/" not in out["text"], (said, out["text"])
        assert _asks(out) == [f"Search the web for {language}"], (said, out)
    assert web == []


def test_with_web_off_no_web_chip(client, notebook, web):
    deps.get_config().set_preference("web_search_enabled", False)
    out = _ask(client, "korean note", use_tools=True)
    assert "None of your notes look Korean" in out["text"] and _asks(out) == []


@pytest.mark.parametrize("tools", [False, True])
def test_an_ask_that_names_notes_goes_to_the_notes_first_with_web_on(client, notebook, web, tools):
    for said in ("my notes on quantum computing", "notes about banana bread", "what do my notes say about cooking", "any notes on trains", "my notes about cats"):
        out = _ask(client, said, use_tools=tools)
        assert "search service" not in out["text"] and "docker" not in out["text"].lower(), (said, out["text"])
    assert web == []


def test_a_notes_ask_with_nothing_found_offers_the_web_as_a_chip(client, notebook, web):
    out = _ask(client, "my notes about banana bread", use_tools=True)
    assert any(a.startswith("Search the web for") and "banana" in a for a in _asks(out)), out
    assert web == []
