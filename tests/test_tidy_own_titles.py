"""Tidy's rename review also reads the person's own note titles (L513)."""

from __future__ import annotations

from tessellate.entry import manager, tidy


def _rows(session):
    return tidy._rows_category_names(session, "standard")


def test_a_word_most_of_a_categorys_titles_share_is_offered_as_its_name(session):
    for text in ("Zephyr plan: alpha", "Zephyr gamma", "Zephyr notes beta", "Gamma delta"):
        manager.create_entry(session, text, category_name="Misc")
    session.commit()
    rows = [r for r in _rows(session) if "Misc" in r["title"]]
    assert rows and rows[0]["change"] in ("Rename to Zephyr",), rows
    assert "note titles say" in rows[0]["detail"]


def test_no_word_is_offered_when_the_titles_do_not_share_one_or_the_name_has_it(session):
    for text in ("Gamma delta", "Omega sigma", "Kappa theta", "Rho lambda"):
        manager.create_entry(session, text, category_name="Misc")
    for text in ("Trip to Rome", "Trip budget", "Trip packing"):
        manager.create_entry(session, text, category_name="Trip")
    session.commit()
    assert not [r for r in _rows(session) if "Misc" in r["title"] or "Rename Trip" in r["title"]], _rows(session)
