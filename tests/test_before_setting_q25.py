"""Q25 (owner 2026-11-11): `before:` leaves its day out by default and a
Settings choice (`before_includes_day`) counts it in. Fake date, no clock."""
from datetime import date

import pytest

from tessellate.search import query as search_query
from tessellate.search.query import understand

NOW = date(2026, 11, 11)


@pytest.fixture(autouse=True)
def _reset():
    search_query.configure_before(False)
    yield
    search_query.configure_before(False)


def test_before_leaves_its_day_out_by_default():
    assert understand("notes before:2026-03-10", now=NOW).until == date(2026, 3, 9)


def test_the_setting_counts_the_day_in():
    search_query.configure_before(True)
    assert understand("notes before:2026-03-10", now=NOW).until == date(2026, 3, 10)


def test_a_spoken_day_follows_the_setting_too():
    assert understand("notes before:yesterday", now=NOW).until == date(2026, 11, 9)
    search_query.configure_before(True)
    assert understand("notes before:yesterday", now=NOW).until == date(2026, 11, 10)


def test_until_and_after_do_not_move_with_the_setting():
    search_query.configure_before(True)
    u = understand("notes until:2026-03-10 after:2026-01-01", now=NOW)
    assert (u.since, u.until) == (date(2026, 1, 2), date(2026, 3, 10))


def test_the_preference_is_wired_through_settings_and_start():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    routes = (root / "src/tessellate/api/routes_settings.py").read_text(encoding="utf-8")
    app = (root / "src/tessellate/api/app.py").read_text(encoding="utf-8")
    assert "before_includes_day: bool | None = None" in routes
    assert '"before_includes_day": config.get_preference("before_includes_day", False)' in routes
    assert 'key == "before_includes_day"' in routes
    assert "configure_before(" in app
