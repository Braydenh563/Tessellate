"""Audit 1031 N6: one category-name rule for every writer."""

from __future__ import annotations

from sqlalchemy import select

from tessellate.core.database import Category
from tessellate.entry import manager


def test_label_trims_collapses_clips_and_fills_blank():
    assert manager.category_label("  Big   plans ​") == "Big plans"
    assert len(manager.category_label("x" * 300)) == 100
    assert manager.category_label("   ") == manager.UNCATEGORISED
    assert manager.category_label(None) == manager.UNCATEGORISED


def test_case_variants_reuse_the_first_category(session):
    first = manager.get_or_create_category(session, "Work")
    again = manager.get_or_create_category(session, "work ")
    spaced = manager.get_or_create_category(session, "WORK")
    assert first.id == again.id == spaced.id
    names = [c.name for c in session.scalars(select(Category)) if c.name.lower() == "work"]
    assert names == ["Work"]


def test_a_long_name_is_clipped_not_stored_whole(session):
    made = manager.get_or_create_category(session, "<b>Evil</b>" + "z" * 300)
    assert len(made.name) == 100


def test_import_path_stays_relative_and_loses_dot_steps():
    from tessellate.entry.cleantext import import_path

    assert import_path("../../evil.md") == "evil.md"
    assert import_path("vault\\notes/./a.md") == "vault/notes/a.md"
    assert import_path("/abs/b.md") == "abs/b.md"
    assert import_path("..", "document") == "document"
    assert len(import_path("a/" * 400)) <= 500


def test_markdown_upload_keeps_no_dot_steps(client):
    sent = client.post(
        "/import/markdown",
        files=[("files", ("../../evil.md", b"# Evil\n\nbody text here\n", "text/markdown"))],
    ).json()
    note = client.get(f"/entries/{sent['ids'][0]}").json()
    assert note["source_path"] == "evil.md"


def test_note_routes_do_not_store_an_overlong_category(client):
    made = client.post("/entries", json={"content": "a plain note", "category": "q" * 300})
    assert made.status_code in (200, 201)
    assert len(made.json()["category"]) == 100
