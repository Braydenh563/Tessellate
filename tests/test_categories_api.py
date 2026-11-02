"""Category management: rename (merging on collision) and delete.

The rule that matters throughout: neither operation may ever lose a note.
"""

from __future__ import annotations


def _make(client, content, category):
    """Create an entry and force it into a known category."""
    entry = client.post("/entries", json={"content": content}).json()
    client.put(f"/entries/{entry['id']}", json={"category": category})
    return entry


def _categories(client):
    return {c["name"]: c for c in client.get("/categories").json()}


def test_list_categories_counts_live_notes(client):
    _make(client, "first work note", "Work")
    _make(client, "second work note", "Work")
    _make(client, "a recipe", "Cooking")
    cats = _categories(client)
    assert cats["Work"]["count"] == 2
    assert cats["Cooking"]["count"] == 1


def test_binned_notes_are_not_counted(client):
    a = _make(client, "kept", "Work")
    b = _make(client, "binned", "Work")
    client.delete(f"/entries/{b['id']}")
    assert _categories(client)["Work"]["count"] == 1
    survivor = client.get(f"/entries/{a['id']}")
    assert survivor.status_code == 200


def test_count_matches_the_notes_list_under_the_category(client):
    """Archived notes and drafts are not in the Notes list, so not in the count.

    Measured 2026-10-03: Health read 4 in the sidebar and 5 in the panel with
    one archived note; Work 5 and 6 with one draft. The sidebar counts what
    `GET /entries` returns, less drafts; the panel's number came from
    `GET /categories`.
    """
    _make(client, "kept", "Health")
    archived = _make(client, "archived", "Health")
    client.post(f"/entries/{archived['id']}/archive")
    draft = client.post("/entries", json={"content": "a draft", "category": "Health", "is_draft": True}).json()
    assert draft["is_draft"] is True

    listed = [e for e in client.get("/entries").json() if e["category"] == "Health" and not e["is_draft"]]
    assert _categories(client)["Health"]["count"] == len(listed) == 1


def test_rename_category(client):
    _make(client, "a note", "Wrok")
    cats = _categories(client)
    result = client.put(f"/categories/{cats['Wrok']['id']}", json={"name": "Work"}).json()
    assert result["renamed"] is True and result["merged"] is False

    cats = _categories(client)
    assert "Wrok" not in cats
    assert cats["Work"]["count"] == 1


def test_renaming_onto_an_existing_category_merges_them(client):
    """A misspelt category merging into the right one is what rename is for. The
    case-only pair no longer exists to merge (audit 1031 N6: the note routes
    now reuse "Work" for "work"), so the test uses a typo."""
    _make(client, "note one", "wrok")
    _make(client, "note two", "Work")
    _make(client, "note three", "Work")

    cats = _categories(client)
    result = client.put(f"/categories/{cats['wrok']['id']}", json={"name": "Work"}).json()
    assert result["merged"] is True
    assert result["moved"] == 1

    cats = _categories(client)
    assert "wrok" not in cats
    assert cats["Work"]["count"] == 3  # nothing was lost in the merge


def test_delete_category_keeps_its_notes(client):
    """Deleting a category is an organising action, never a destructive one."""
    kept = _make(client, "still here afterwards", "Temporary")
    cats = _categories(client)
    result = client.delete(f"/categories/{cats['Temporary']['id']}").json()
    assert result["deleted"] is True and result["moved"] == 1

    assert "Temporary" not in _categories(client)
    survivor = client.get(f"/entries/{kept['id']}").json()
    assert survivor["content"] == "still here afterwards"
    assert survivor["category"] == "Uncategorised"


def test_uncategorised_cannot_be_deleted(client):
    """It's the fallback every orphaned note lands in."""
    _make(client, "a note", "Uncategorised")
    cats = _categories(client)
    response = client.delete(f"/categories/{cats['Uncategorised']['id']}")
    assert response.status_code == 400
    assert "can't be removed" in response.json()["detail"]


def test_rename_rejects_a_blank_name(client):
    _make(client, "a note", "Work")
    cats = _categories(client)
    # The request is made outside the assert so it still runs under `python -O`.
    response = client.put(f"/categories/{cats['Work']['id']}", json={"name": "   "})
    assert response.status_code == 400


def test_operations_on_a_missing_category_are_400(client):
    renamed = client.put("/categories/9999", json={"name": "Nope"})
    assert renamed.status_code == 400
    deleted = client.delete("/categories/9999")
    assert deleted.status_code == 400
