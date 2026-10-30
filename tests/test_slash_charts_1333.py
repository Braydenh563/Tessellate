"""/categories and /tags draw the bar chart the same question in words draws
(INBOX 1333 b): the slash answer was one prose line with no graphic."""

from __future__ import annotations

from tessellate.entry import manager
from tests.test_composer_route_688 import _ask


def _seed(session):
    for i, (cat, tag) in enumerate([("Work", "a"), ("Work", "a"), ("Uni", "b"), ("Uni", "b"), ("Uni", "c"), ("Health", "c")]):
        manager.create_entry(session, f"# Note {i}\n\nText {i}.", category_name=cat, tags=[tag])
    session.commit()


def test_slash_categories_draws_the_per_category_bar(client, session):
    _seed(session)
    out = _ask(client, "/categories", use_tools=False)
    assert out["text"].startswith("Your notes sit in three categories: Uni (3), Work (2), Health (1).")
    chart = out["chart"][0]["chart"]
    assert chart["title"] == "Notes per category"
    assert chart["rows"] == [{"label": "Uni", "value": 3}, {"label": "Work", "value": 2}, {"label": "Health", "value": 1}]
    worded = _ask(client, "what categories do I have", use_tools=False)["chart"][0]["chart"]
    assert worded["title"] == chart["title"] and sorted(worded["rows"], key=str) == sorted(chart["rows"], key=str)


def test_slash_tags_draws_the_per_tag_bar(client, session):
    _seed(session)
    chart = _ask(client, "/tags", use_tools=False)["chart"][0]["chart"]
    assert chart["title"] == "Notes per tag"


def test_a_slash_command_with_nothing_to_count_draws_nothing(client, session):
    _seed(session)
    assert "chart" not in _ask(client, "/recent", use_tools=False)
