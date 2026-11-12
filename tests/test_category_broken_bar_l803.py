"""LEDGER L803, owner 2026-11-12: a category name with a broken bar (¦) where
"&" belongs is mended: when saved or renamed, and once on load for a name
stored before."""

from __future__ import annotations

from tessellate.core.database import Category
from tessellate.core.database_manager import DatabaseManager
from tessellate.entry import manager
from tessellate.entry.manager_categories import mend_broken_bar_names, rename_category


def test_a_name_saved_or_renamed_with_a_broken_bar_reads_and(session):
    assert manager.category_label("Food ¦ drink") == "Food & drink"
    made = manager.get_or_create_category(session, "Food ¦ drink")
    session.commit()
    assert made.name == "Food & drink"
    rename_category(session, made.id, "Arts ¦ crafts")
    session.commit()
    assert session.get(Category, made.id).name == "Arts & crafts"


def test_a_name_stored_before_is_mended_at_start_and_a_clash_merges(tmp_path):
    db = DatabaseManager(tmp_path / "notes.db")
    with db.engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO categories (name, workspace_id, created_at) VALUES "
            "('Food & drink', 'default', '2026-11-01'), ('Food \u00a6 drink', 'default', '2026-11-01'), "
            "('Arts \u00a6 crafts', 'default', '2026-11-01')"
        )
    db.engine.dispose()
    again = DatabaseManager(tmp_path / "notes.db")
    session = again.session()
    try:
        assert mend_broken_bar_names(session) == 2
        assert mend_broken_bar_names(session) == 0
    finally:
        session.close()
    with again.engine.begin() as connection:
        names = sorted(row[0] for row in connection.exec_driver_sql("SELECT name FROM categories"))
    assert "Arts & crafts" in names and names.count("Food & drink") == 1
    assert not any("¦" in n for n in names)


def test_the_mend_is_a_start_up_maintenance_step():
    """At start, off the path to the first byte, not in the storage layer
    (which would import the entry layer and grow the import cycle)."""
    import inspect

    from tessellate.api import app

    assert '"_mend_category_names"' in inspect.getsource(app._startup_maintenance)
    assert "mend_broken_bar_names" in inspect.getsource(app._mend_category_names)
