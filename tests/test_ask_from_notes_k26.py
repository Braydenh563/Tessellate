"""K26: both answers visible in the Ask box.

A model answer can be set beside the composed one on a press (`peek`, saved to
nothing), and what the composer says before a model on the composed path (the
personal digest, a place in the app) reaches the model path as a `pre_answer`
card above the AI text, never in place of it.
"""

from __future__ import annotations

import json

from tessellate.entry import manager


def _ask(client, question: str, **body) -> dict:
    events: dict[str, list] = {}
    with client.stream("POST", "/chat/stream", json={"question": question, **body}) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                events.setdefault(event["type"], []).append(event)
    events["text"] = "".join(e["delta"] for e in events.get("answer", []))
    return events


def _seed(session) -> None:
    manager.create_entry(session, "# About me\n\nI live in Perth and I work part time at the cafe.")
    manager.create_entry(session, "# Dentist\n\nCheck-up booked for the 21st. Ask about the night guard.")
    session.commit()


def test_a_peek_is_composed_and_not_saved(ai_client, fake_ollama, session):
    _seed(session)
    out = _ask(ai_client, "When is the dentist check-up?", notes_only=True, use_tools=False, peek=True)
    assert out["meta"][0]["composed"] is True
    assert out["text"].startswith("Check-up booked for the 21st")
    assert ai_client.get("/ask-history").json()["turns"] == []


def test_the_same_question_without_peek_is_saved(ai_client, fake_ollama, session):
    _seed(session)
    _ask(ai_client, "When is the dentist check-up?", notes_only=True, use_tools=False, answer_from="notes")
    assert len(ai_client.get("/ask-history").json()["turns"]) == 1


def test_a_personal_digest_leads_the_model_answer_as_a_card(ai_client, fake_ollama, session):
    _seed(session)
    out = _ask(ai_client, "where do i live", notes_only=True, use_tools=False, answer_from="ai")
    assert out["meta"][0]["composed"] is False
    assert fake_ollama.librarian_reply in out["text"]
    card = next(e for e in out["panel"] if e["panel"] == "pre_answer")
    assert card["text"].startswith("You live in Perth")
    assert card["text"] not in out["text"]


def test_no_card_when_the_composer_has_no_special(ai_client, fake_ollama, session):
    _seed(session)
    out = _ask(ai_client, "When is the dentist check-up?", notes_only=True, use_tools=False, answer_from="ai")
    assert not [e for e in out.get("panel", []) if e["panel"] == "pre_answer"]
    assert fake_ollama.librarian_reply in out["text"]


def test_no_card_on_the_composed_path(ai_client, session):
    _seed(session)
    out = _ask(ai_client, "where do i live", notes_only=True, use_tools=False, answer_from="notes")
    assert not [e for e in out.get("panel", []) if e["panel"] == "pre_answer"]
    assert out["text"].startswith("You live in Perth")


def test_the_page_wires_both_answers():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "frontend"
    ask = (root / "js" / "capture-ask.js").read_text(encoding="utf-8")
    compose = (root / "js" / "ask-compose.js").read_text(encoding="utf-8")
    assert "peek, answer_from" in ask
    assert "renderAskBoth(" in ask
    #: Drawn only beside a model's answer, fetched once on the first open.
    assert "meta.composed || !meta.answered_by" in compose and "fetched" in compose
    html = (root / "index.html").read_text(encoding="utf-8")
    assert 'id="ask-pre"' in html and 'id="ask-notes"' in html
