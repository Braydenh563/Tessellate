"""Check with AI, in place (INBOX 410, the owner 2026-09-24).

"improve how the 'check with ai' feature works in the documents editor." It
used to send the document to the Chat tab with a long prompt, where a skill
suggestion that did not fit popped up over it (INBOX 413). Now it runs where
it was asked: `POST /documents/{id}/ai-check` streams one finding at a time
(the exact wording, a one-line reason, a one-line fix) into the suggestions
panel, on the documents feature's model, and says so plainly when no model is
there. The panel side is measured by `scratchpad/ui-sweeps/aicheck.js`.
"""

from __future__ import annotations

import json
from pathlib import Path

from tessellate.ai import drafter

ROOT = Path(__file__).resolve().parents[1]
DOC = "Its a good plan. The team have agreed to it's terms. We was going to start monday."


def _lines(response) -> list[dict]:
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def _doc(client, content=DOC) -> int:
    return client.post("/documents", json={"title": "Plan", "content": content}).json()["id"]


REPLY = (
    "Its a good plan | missing apostrophe: it is | It's a good plan\n"
    "QUOTE: it's terms | WHY: possessive has no apostrophe | FIX: its terms\n"
    "1. We was going | agreement: we takes were | We were going\n"
    "not in the document | whatever | x\n"
    "no pipes on this line\n"
)


def test_findings_stream_one_item_per_line(ai_client, fake_ollama):
    fake_ollama.librarian_reply = REPLY
    response = ai_client.post(f"/documents/{_doc(ai_client)}/ai-check", json={})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    events = _lines(response)
    items = [e for e in events if e["type"] == "item"]
    assert [i["quote"] for i in items] == ["Its a good plan", "it's terms", "We was going"]
    assert items[0]["reason"] == "missing apostrophe: it is"
    assert items[0]["fix"] == "It's a good plan"
    assert items[1]["reason"] == "possessive has no apostrophe", "the labels are taken off"
    assert events[-1]["type"] == "done" and events[-1]["count"] == 3
    assert events[-1]["ollama_running"] is True


def test_a_quote_the_document_does_not_contain_is_dropped():
    """A small model paraphrases. A finding that cannot be found cannot be
    shown, jumped to or applied, so it is not a finding."""
    items = drafter.parse_review_line("not in the document | why | fix", DOC)
    assert items is None
    assert drafter.parse_review_line("\"its a good plan\" | why | It's a good plan", DOC)["quote"] == "Its a good plan"


def test_a_fix_the_same_as_the_quote_is_not_a_fix():
    item = drafter.parse_review_line("Its a good plan | tone | Its a good plan", DOC)
    assert item is not None and item["fix"] == ""


def test_it_runs_on_the_documents_feature_model(ai_client, fake_ollama, monkeypatch):
    fake_ollama.librarian_reply = REPLY
    seen = []
    real = drafter.review_stream

    def spy(text, model_manager, ollama):
        seen.append(model_manager._feature)
        yield from real(text, model_manager, ollama)

    monkeypatch.setattr(drafter, "review_stream", spy)
    _lines(ai_client.post(f"/documents/{_doc(ai_client)}/ai-check", json={}))
    assert seen == ["documents"]


def test_a_selection_is_what_gets_checked(ai_client, fake_ollama):
    fake_ollama.librarian_reply = "We was going | agreement | We were going\n"
    events = _lines(
        ai_client.post(f"/documents/{_doc(ai_client)}/ai-check", json={"selection": "We was going to start monday."})
    )
    prompt = fake_ollama.chat_calls[-1][-1]["content"]
    assert "We was going to start monday." in prompt and "good plan" not in prompt
    assert [e["quote"] for e in events if e["type"] == "item"] == ["We was going"]


def test_no_model_says_so_and_checks_nothing(ai_client, fake_ollama):
    fake_ollama.running = False
    events = _lines(ai_client.post(f"/documents/{_doc(ai_client)}/ai-check", json={}))
    assert [e["type"] for e in events] == ["done"]
    assert events[0]["ollama_running"] is False and events[0]["count"] == 0
    assert events[0]["message"]


def test_an_empty_document_is_refused(ai_client, fake_ollama):
    response = ai_client.post(f"/documents/{_doc(ai_client, '   ')}/ai-check", json={})
    assert response.status_code == 400


def test_the_panel_no_longer_sends_the_document_to_chat():
    """The check is in place; chat is the secondary "Discuss in chat"."""
    docs = (ROOT / "frontend" / "js" / "documents-suggest.js").read_text(encoding="utf-8")  # the piece; documents.js has a stand-in
    start = docs.index("async function docAiReview(")
    body = docs[start : docs.index("\n  }\n", start)]
    assert "switchTab(" not in body and "/ai-check" in body
    assert "function docAiDiscussInChat(" in docs
