"""L161 (c), INBOX 1841: a Settings switch, off by default, that makes every
answer drop persona voice: the persona's prompt is not sent to a model, and a
persona's own words no longer pick the composer's voice."""

from __future__ import annotations

from tessellate.ai import librarian
from tessellate.api import routes_chat
from tessellate.core import deps


def _a_pirate(client) -> None:
    client.put("/preferences", json={
        "personas": [{"name": "Pirate", "prompt": "You are a witty pirate who answers in jokes."}],
        "active_persona": "Pirate",
    })


def test_the_switch_is_a_preference_off_by_default(client) -> None:
    before = client.get("/preferences").json()
    saved = client.put("/preferences", json={"personas_off": True}).json()
    after = client.get("/preferences").json()
    assert before["personas_off"] is False and saved["personas_off"] is True and after["personas_off"] is True


def test_a_persona_reaches_the_prompt_until_the_switch_is_on(client) -> None:
    _a_pirate(client)
    config = deps.get_config()
    assert "pirate" in librarian.resolve_persona_prompt(None, config)
    client.put("/preferences", json={"personas_off": True})
    assert librarian.resolve_persona_prompt(None, config) is None
    assert librarian.resolve_persona_prompt("Pirate", config) is None


def test_the_composer_no_longer_takes_a_voice_from_the_persona(client) -> None:
    _a_pirate(client)
    config = deps.get_config()

    class _Req:
        persona_prompt = librarian.resolve_persona_prompt(None, config)

    assert routes_chat._chat_voice(_Req) == "playful"
    client.put("/preferences", json={"personas_off": True})
    _Req.persona_prompt = librarian.resolve_persona_prompt(None, config)
    assert routes_chat._chat_voice(_Req) == "natural"
