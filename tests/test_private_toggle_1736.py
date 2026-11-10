"""INBOX 1736: the graph's New note popover creates a private note when its Private toggle is on.

The recipe lints (pressed state, head) are `test_a_lock_toggle_*` in test_ui_recipes.py.
"""

from __future__ import annotations


def test_a_note_created_with_private_true_is_stored_private(client, session):
    """The graph popover posts `private: true` to /entries, as Capture does."""
    from tessellate.core import vault

    vault.close()
    vault.create(session, "test-passphrase")
    session.commit()
    try:
        response = client.post("/entries", json={"content": "grown on the map", "defer_filing": True, "inline_tags": True, "private": True})
        assert response.status_code == 201
        assert response.json()["is_private"] is True
        listed = client.get(f"/entries/{response.json()['id']}")
        assert listed.status_code == 200
        assert listed.json()["is_private"] is True
        plain = client.post("/entries", json={"content": "a plain note", "defer_filing": True})
        assert plain.json()["is_private"] is False
    finally:
        vault.close()
