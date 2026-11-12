"""Draft with Atlas in Settings, Templates (INBOX 430: "AI templates
(generate, edit, regenerate)")."""

from pathlib import Path
from tests._js_scope import unwrapped


def test_a_template_is_drafted_from_its_name(ai_client, fake_ollama):
    fake_ollama.librarian_reply = "# Book notes\n\nTitle:\nAuthor:\nStarted: {date}\n"
    body = ai_client.post("/templates/draft", json={"name": "Book notes", "description": "what I read"}).json()
    assert body["content"].startswith("# Book notes")
    assert body["reason"] == ""


def test_a_fenced_answer_loses_its_fence(ai_client, fake_ollama):
    fake_ollama.librarian_reply = "```markdown\n## Meeting\n\nAgenda:\n```"
    body = ai_client.post("/templates/draft", json={"name": "Meeting"}).json()
    assert body["content"] == "## Meeting\n\nAgenda:"


def test_no_model_is_a_reason_not_an_error(client):
    response = client.post("/templates/draft", json={"name": "Journal"})
    assert response.status_code == 200
    assert response.json()["content"] == "" and response.json()["reason"]


def test_the_button_is_wired():
    root = Path(__file__).resolve().parent.parent / "frontend"
    assert 'id="template-draft"' in (root / "index.html").read_text(encoding="utf-8")
    assert '$("template-draft")?.addEventListener("click"' in unwrapped((root / "js" / "settings-controls.js").read_text(encoding="utf-8"))
