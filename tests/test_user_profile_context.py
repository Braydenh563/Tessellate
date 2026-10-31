"""The local profile (Settings, Your profile), as the AI reads it.

The profile is three things: a display name, a short "About me" and an avatar
drawn from the name. The first two reach the model through one function,
`librarian.profile_context`, and only while the profile switch is on. The
about text is capped, because the system prompt it lands in is resent on every
round of every turn and nothing downstream trims it for the persona's sake.
"""

from __future__ import annotations

from tessellate.ai import agent, librarian


def _save(client, content):
    response = client.post("/entries", json={"content": content})
    assert response.status_code == 201


def _ask(client, question):
    response = client.post("/chat", json={"question": question})
    assert response.status_code == 200
    return response.json()


def test_the_name_and_the_about_text_both_reach_the_context():
    text = librarian.profile_context("Brayden", "I run track and collect dad jokes.")
    assert "Brayden" in text
    assert "I run track and collect dad jokes." in text


def test_an_empty_profile_says_nothing():
    assert librarian.profile_context("", "") == ""
    assert librarian.profile_context("   ", "\n\n") == ""


def test_the_about_text_is_capped():
    long_about = "word " * 400  # 2,000 characters, the API's own ceiling
    text = librarian.profile_context("Brayden", long_about)
    assert len(text) <= librarian.PROFILE_CONTEXT_MAX_CHARS
    assert librarian.PROFILE_ABOUT_CAP_CHARS == 600


def test_the_cap_is_a_small_share_of_the_prose_budget():
    """The profile sits in the same system message as the persona and the
    tools guide. Its worst case is stated here so a later raise of the cap is
    a decision rather than a drift."""
    assert librarian.PROFILE_CONTEXT_MAX_CHARS * 4 <= agent.PROSE_BUDGET_CHARS


def test_the_name_is_collapsed_and_capped():
    text = librarian.profile_context("A" * 200 + "\n\nB", "")
    assert "\n" not in text
    assert len(text) <= librarian.PROFILE_CONTEXT_MAX_CHARS


def test_chat_sends_the_name_only_while_the_profile_is_on(ai_client, fake_ollama):
    _save(ai_client, "a funny scarecrow joke")
    ai_client.put(
        "/preferences",
        json={"display_name": "Brayden", "user_profile": "", "profile_enabled": False},
    )
    _ask(ai_client, "any funny jokes?")
    assert "Brayden" not in fake_ollama.chat_calls[-1][0]["content"]

    ai_client.put("/preferences", json={"profile_enabled": True})
    _ask(ai_client, "any funny jokes?")
    assert "Brayden" in fake_ollama.chat_calls[-1][0]["content"]


def test_chat_caps_a_long_about_text(ai_client, fake_ollama):
    _save(ai_client, "a funny scarecrow joke")
    about = "start " + "x" * 1500 + " tailmarker"
    ai_client.put("/preferences", json={"user_profile": about, "profile_enabled": True})
    _ask(ai_client, "any funny jokes?")
    system = fake_ollama.chat_calls[-1][0]["content"]
    assert "start x" in system
    assert "tailmarker" not in system


def test_the_profile_fields_round_trip(client):
    client.put(
        "/preferences",
        json={"display_name": "Brayden", "user_profile": "About me", "profile_enabled": True},
    )
    prefs = client.get("/preferences").json()
    assert prefs["display_name"] == "Brayden"
    assert prefs["user_profile"] == "About me"
    assert prefs["profile_enabled"] is True
