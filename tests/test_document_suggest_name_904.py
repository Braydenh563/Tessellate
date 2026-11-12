"""INBOX 904 B17: "an option in the editor to have the composer and ai if it is
available suggest and rename the document". A document's kebab menu offers
"Suggest a name": the model writes one when it runs, else the document's own
words (`composer_voice.title_for`) are cut to a title, as a note's are
(`/entries/{id}/generate-title`). Nothing is saved by the route; the client
renames through the same undoable path as Rename."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BODY = "Packed the tent and the stove for the coast trip on Friday. We leave at dawn and drive north."


def _doc(client, **fields):
    return client.post("/documents", json={"title": "Untitled", "content": BODY, **fields}).json()


def test_with_no_model_the_name_is_the_documents_own_words_and_nothing_is_saved(client):
    doc = _doc(client)
    out = client.post(f"/documents/{doc['id']}/suggest-title")
    assert out.status_code == 200, out.text
    body = out.json()
    assert body["by"] == "composer"
    assert body["title"] and all(w.lower().strip(",.") in BODY.lower() for w in body["title"].split()), body
    assert client.get(f"/documents/{doc['id']}").json()["title"] == "Untitled"


def test_the_suggest_title_path_is_called_by_a_plain_id(client):
    # The route ratchet (test_routes_named) reads a literal like "/documents/{did}/suggest-title"; the
    # tests above index into the dict inside the f-string, which it cannot read.
    did = _doc(client)["id"]
    assert client.post(f"/documents/{did}/suggest-title").status_code == 200


def test_a_running_model_writes_the_name(ai_client, fake_ollama):
    doc = _doc(ai_client)
    fake_ollama.librarian_reply = "Coast trip packing"
    body = ai_client.post(f"/documents/{doc['id']}/suggest-title").json()
    assert body == {"title": "Coast trip packing", "by": "model"}


def test_an_empty_document_has_nothing_to_name_it_from(client):
    doc = _doc(client, content="")
    out = client.post(f"/documents/{doc['id']}/suggest-title")
    assert out.status_code == 422 and "nothing" in out.json()["detail"].lower()


def test_the_documents_menu_offers_it_and_renames_with_undo():
    js = (ROOT / "frontend" / "js" / "documents.js").read_text(encoding="utf-8")
    item = js[js.index('"ph:sparkle Suggest a name"'):].split("appLinkMenuItem", 1)[0]
    assert "/suggest-title" in item and "renameDocumentWithUndo(doc" in item
