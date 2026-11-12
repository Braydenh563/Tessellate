"""L-chat-30: the compose agent's rules-only fixes have a model-on path (CHAT_PLAN decision 75). Fake transport; what
a real model says to them is not checked here."""

from __future__ import annotations

import json

from tessellate.ai import links
from tessellate.core import deps
from tessellate.entry import manager
from tests.test_link_reasons import _linked_pair


def _stream(client, question: str, **body) -> list[dict]:
    with client.stream("POST", "/chat/stream", json={"question": question, **body}) as response:
        assert response.status_code == 200
        return [json.loads(line) for line in response.iter_lines() if line.strip()]


def _prompt_text(fake_ollama) -> str:
    return "\n".join(m["content"] for call in fake_ollama.chat_calls for m in call)


def test_a_list_question_shows_the_draft_and_the_model_reads_the_list(ai_client, fake_ollama, session):
    manager.create_entry(session, "# Todo\n\nThis week\n- [ ] milk\n- [ ] eggs\n- [ ] stamps")
    session.commit()
    events = _stream(ai_client, "what is on my list?", use_tools=False)
    kinds = [e["type"] for e in events]
    assert "composed_preview" in kinds and "answer" in kinds
    assert "stamps" in _prompt_text(fake_ollama)


def test_a_compare_question_shows_the_draft_and_the_model_reads_both_notes(ai_client, fake_ollama, session):
    manager.create_entry(session, "# Gym\n\nSquat 80 kg on Monday.")
    manager.create_entry(session, "# Running\n\nRan 5 km on Tuesday.")
    session.commit()
    events = _stream(ai_client, "compare gym and running", use_tools=False)
    assert "answer" in [e["type"] for e in events]
    prompt = _prompt_text(fake_ollama)
    assert "Squat 80 kg" in prompt and "Ran 5 km" in prompt


def test_a_generic_link_reason_goes_to_the_model_and_a_specific_one_is_left_alone(session, fake_ollama):
    _, _, vague = _linked_pair(session)
    _, _, specific = _linked_pair(session, reason="both mention the movers", reason_confidence=None)
    fake_ollama.librarian_reply = "both about the Denver move"
    assert links.audit_vague_links(session, deps.get_model_manager(), fake_ollama, limit=10) == 1
    session.refresh(vague)
    session.refresh(specific)
    assert vague.reason == "both about the Denver move"
    assert specific.reason == "both mention the movers"


def test_a_note_that_is_a_picture_reaches_the_model_with_its_reading_beside_the_draft(ai_client, fake_ollama, session):
    """The picture-as-file fix: the composer reads the picture's text, and the model is handed the same reading."""
    from tessellate.core.database import MediaUpload

    session.add(MediaUpload(filename="ideas123.png", original_name="image.png", ocr_text="Offline banner in the status bar."))
    session.commit()
    ai_client.post("/entries", json={"content": "Some feature ideas I had:\n\n![image.png](/media/ideas123.png)"})
    events = _stream(ai_client, "what are my feature ideas?", use_tools=False)
    assert "answer" in [e["type"] for e in events]
    assert "Offline banner in the status bar" in _prompt_text(fake_ollama)
