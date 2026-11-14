"""Sub-pages (DOCUMENTS_PLAN D14, L-documents-44): a document may have one
parent, never a cycle, checked here on the server. Binning a parent bins its
subtree and restore brings that subtree back; purging a parent lifts its
children to the top level. The frontend half is read at the bottom."""

from __future__ import annotations

from pathlib import Path

from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]


def read_text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _doc(client, title, parent_id=None):
    body = {"title": title}
    if parent_id is not None:
        body["parent_id"] = parent_id
    response = client.post("/documents", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _tree(client):
    return {d["title"]: d["parent_id"] for d in client.get("/documents").json()}


def test_a_document_is_made_under_a_parent_and_the_summary_says_so(client):
    parent = _doc(client, "Parent")
    child = _doc(client, "Child", parent["id"])
    grandchild = _doc(client, "Grandchild", child["id"])
    assert parent["parent_id"] is None
    assert child["parent_id"] == parent["id"]
    assert _tree(client) == {"Parent": None, "Child": parent["id"], "Grandchild": child["id"]}
    #: The breadcrumb: the open document's parents, root first.
    full = client.get(f"/documents/{grandchild['id']}").json()
    assert [p["title"] for p in full["parents"]] == ["Parent", "Child"]
    top = client.get(f"/documents/{parent['id']}").json()
    assert top["parents"] == []


def test_move_under_and_back_to_the_top_level(client):
    a, b = _doc(client, "A"), _doc(client, "B")
    moved = client.put(f"/documents/{b['id']}", json={"parent_id": a["id"]})
    assert moved.status_code == 200 and moved.json()["parent_id"] == a["id"]
    #: A save that does not name the parent leaves it alone (autosave sends only text).
    client.put(f"/documents/{b['id']}", json={"content": "text"})
    assert _tree(client)["B"] == a["id"]
    lifted = client.put(f"/documents/{b['id']}", json={"parent_id": None})
    assert lifted.json()["parent_id"] is None


def test_a_cycle_is_refused_with_a_readable_message(client):
    a = _doc(client, "A")
    b = _doc(client, "B", a["id"])
    c = _doc(client, "C", b["id"])
    for target, parent in ((a, c), (a, b), (a, a)):
        response = client.put(f"/documents/{target['id']}", json={"parent_id": parent["id"]})
        assert response.status_code == 409
        assert "sub-page" in response.json()["detail"]
    assert _tree(client) == {"A": None, "B": a["id"], "C": b["id"]}


def test_a_missing_or_binned_parent_is_refused(client):
    a = _doc(client, "A")
    missing = client.post("/documents", json={"title": "X", "parent_id": 99999})
    assert missing.status_code == 404
    gone = _doc(client, "Gone")
    client.delete(f"/documents/{gone['id']}")
    binned = client.put(f"/documents/{a['id']}", json={"parent_id": gone["id"]})
    assert binned.status_code == 409


def test_binning_a_parent_bins_its_subtree_and_restore_brings_it_back(client):
    parent = _doc(client, "Parent")
    child = _doc(client, "Child", parent["id"])
    _doc(client, "Grandchild", child["id"])
    #: Binned on its own before the parent: restoring the parent leaves it in the bin.
    alone = _doc(client, "Binned alone", parent["id"])
    client.delete(f"/documents/{alone['id']}")
    client.delete(f"/documents/{parent['id']}")
    live = client.get("/documents").json()
    assert live == []
    client.post(f"/documents/{parent['id']}/restore")
    assert _tree(client) == {"Parent": None, "Child": parent["id"], "Grandchild": child["id"]}


def test_purging_a_parent_lifts_its_children_to_the_top_level(client):
    parent = _doc(client, "Parent")
    child = _doc(client, "Child", parent["id"])
    _doc(client, "Grandchild", child["id"])
    #: The child lives on: moved out, then the parent alone is binned and purged.
    client.put(f"/documents/{child['id']}", json={"parent_id": None})
    client.put(f"/documents/{child['id']}", json={"parent_id": parent["id"]})
    client.delete(f"/documents/{parent['id']}")
    client.post(f"/documents/{child['id']}/restore")
    purged = client.delete(f"/documents/{parent['id']}/purge")
    assert purged.status_code == 200
    assert _tree(client) == {"Child": None, "Grandchild": child["id"]}


def test_export_of_a_parent_stays_the_one_document(client):
    parent = _doc(client, "Parent")
    client.put(f"/documents/{parent['id']}", json={"content": "# Parent\n\nOwn words."})
    child = _doc(client, "Child", parent["id"])
    client.put(f"/documents/{child['id']}", json={"content": "Child words."})
    exported = client.get(f"/documents/{parent['id']}/export.md").text
    assert "Own words." in exported and "Child words." not in exported



def test_the_frontend_draws_the_tree_and_offers_the_two_menu_items():
    code = app_js_text() + read_text("frontend/js/documents-subpages.js")
    library = read_text("frontend/js/library.js")
    assert "New sub-page" in code and "Move under" in code
    assert "doc-tree-toggle" in code and "aria-expanded" in code
    assert "documents-subpages.js" in library
    editor = read_text("frontend/js/editor.js")
    assert 'id: "subpage"' in editor
