"""A document's history in a few sentences (L-documents-5):
`POST /documents/{id}/revisions/summary` walks the newest saved versions pair by
pair and reports what was added and removed and in which sections. A model (a
fake transport here) is shown only the budgeted changed lines and writes the
account; with no model, or one that fails or answers nothing, the account is
built from the same counts in plain words. Nothing is written.
"""

from __future__ import annotations

from datetime import timedelta

from tessellate.api import routes_document_story, routes_documents
from tessellate.core.database import DocumentRevision, utcnow

V0 = "# Plan\n\nAlpha stays.\n\n## Costs\n\nOld budget line.\n"
V1 = "# Plan\n\nAlpha stays.\n\n## Costs\n\nNew budget line.\nSecond new line.\n"
V2 = V1 + "\n## Risks\n\nWeather may turn.\n"


def _history(client, versions):
    doc = client.post("/documents", json={"title": "Doc", "content": versions[0]}).json()
    for n, text in enumerate(versions[1:], 1):
        client.put(f"/documents/{doc['id']}", json={"content": text})
        with routes_documents.deps.get_db().session() as session:
            # Age every revision past the quiet window so each edit is its own entry.
            for k, row in enumerate(session.query(DocumentRevision).order_by(DocumentRevision.id)):
                row.created_at = utcnow() - timedelta(seconds=routes_documents.REVISION_QUIET_SECONDS * (9 - k) + 60)
            session.commit()
    return doc["id"]


def test_with_no_model_the_account_is_built_from_the_counts(client):
    doc = _history(client, [V0, V1, V2])
    got = client.post(f"/documents/{doc}/revisions/summary").json()
    assert got["source"] == "words" and got["reason"] == "offline"
    assert (got["steps"], got["added"], got["removed"]) == (2, 4, 1)
    first = got["summary"].splitlines()[0]
    assert first.startswith("Over the last 2 versions: 4 lines added, 1 removed, across 2 sections (Costs, Risks)")
    assert len(got["summary"].splitlines()) == 3, "one line per step after the total"


def test_a_document_with_no_history_says_so_and_asks_no_model(ai_client, fake_ollama):
    doc = ai_client.post("/documents", json={"title": "Doc", "content": V0}).json()
    got = ai_client.post(f"/documents/{doc['id']}/revisions/summary").json()
    assert got["summary"] == "Nothing has changed in this document yet." and got["steps"] == 0
    assert fake_ollama.chat_calls == []


def test_the_model_is_shown_the_changed_lines_only_and_its_words_are_the_account(ai_client, fake_ollama):
    doc = _history(ai_client, [V0, V1, V2])
    fake_ollama.librarian_reply = "The budget was reworded and a risks section arrived."
    got = ai_client.post(f"/documents/{doc}/revisions/summary").json()
    assert got["source"] == "model" and got["summary"] == "The budget was reworded and a risks section arrived."
    sent = fake_ollama.chat_calls[-1][-1]["content"]
    assert "+ New budget line." in sent and "- Old budget line." in sent and "+ Weather may turn." in sent
    assert "Alpha stays" not in sent, "unchanged text never reaches the model"
    assert sent.index("Step 1") < sent.index("Step 2")


def test_the_prompt_is_budgeted(ai_client, fake_ollama):
    big = "# H\n\n" + "\n".join(f"line {n} " + "x" * 300 for n in range(200))
    doc = _history(ai_client, ["# H\n\nstart\n", big])
    ai_client.post(f"/documents/{doc}/revisions/summary")
    sent = fake_ollama.chat_calls[-1][-1]["content"]
    assert len(sent) < routes_document_story.BUDGET_CHARS + 600
    assert sent.count("\n  + ") <= routes_document_story.STEP_LINES


def test_an_empty_or_failing_model_falls_back_to_the_counts(ai_client, fake_ollama):
    doc = _history(ai_client, [V0, V1])
    fake_ollama.librarian_reply = "   "
    got = ai_client.post(f"/documents/{doc}/revisions/summary").json()
    assert (got["source"], got["reason"]) == ("words", "unusable") and "lines added" in got["summary"]


def test_nothing_is_written(client):
    doc = _history(client, [V0, V1])
    before = client.get(f"/documents/{doc}/revisions").json()
    client.post(f"/documents/{doc}/revisions/summary")
    assert client.get(f"/documents/{doc}/revisions").json() == before
    assert client.get(f"/documents/{doc}").json()["content"] == V1


def test_the_history_dialog_has_the_action_and_it_asks_the_summary_route():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    html = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    dlg = html[html.index('id="doc-history-dialog"') :]
    dlg = dlg[: dlg.index("</dialog>")]
    assert 'id="doc-history-story-btn"' in dlg and 'id="doc-history-story"' in dlg
    js = (root / "frontend" / "js" / "documents-history.js").read_text(encoding="utf-8")
    assert "/revisions/summary" in js and "readOnly: true" in js


# --- the real model, by hand (CLAUDE.md section 4) ----------------------------

import os  # noqa: E402

import pytest  # noqa: E402

EVALS_URL = os.environ.get("TESSELLATE_EVALS_URL", "").strip()
EVALS_MODEL = os.environ.get("TESSELLATE_EVALS_MODEL", "").strip()


@pytest.mark.evals
@pytest.mark.skipif(not (EVALS_URL and EVALS_MODEL), reason="no real model: export TESSELLATE_EVALS_URL and TESSELLATE_EVALS_MODEL")
def test_a_real_model_writes_an_account_of_a_known_history(app_state, fake_embeddings, capsys):
    from fastapi.testclient import TestClient

    from tessellate.ai.openai_client import OpenAICompatClient
    from tessellate.api.app import create_app
    from tessellate.core import deps

    deps.override_ai(ollama=OpenAICompatClient(base_url=EVALS_URL))
    config = deps.get_config()
    config.set_preference("llm_provider", "openai")
    config.set_preference("llm_base_url", EVALS_URL)
    config.set_preference("chat_model", EVALS_MODEL)
    client = TestClient(create_app())
    doc = _history(client, [V0, V1, V2])
    got = client.post(f"/documents/{doc}/revisions/summary").json()
    with capsys.disabled():
        print("\nREAL MODEL ACCOUNT:", got["source"], got["reason"], repr(got["summary"]))
    assert got["source"] == "model" and got["summary"]
