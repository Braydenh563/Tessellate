"""Q25 (owner 2026-11-11): the order a numeric date is read in ("3/4") is a
Settings choice, `date_order`: "auto" follows the browser's language and
region, "day" and "month" override it. Fixed date, no clock."""
from datetime import date
from pathlib import Path

import pytest

from tessellate.ai import recognise

TODAY = date(2026, 11, 11)
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _reset():
    recognise.configure_date_order("auto")
    yield
    recognise.configure_date_order("auto")


def _first_day(locale):
    return recognise._numeric_dates("3/4", TODAY, locale, None)[0][2][0][0]


def test_auto_follows_the_locale():
    assert _first_day("en-US").month == 3
    assert _first_day("en-GB").month == 4


def test_day_first_overrides_a_month_first_locale():
    recognise.configure_date_order("day")
    assert _first_day("en-US").month == 4


def test_month_first_overrides_a_day_first_locale():
    recognise.configure_date_order("month")
    assert _first_day("en-GB").month == 3


def test_an_unknown_value_is_auto():
    recognise.configure_date_order("sideways")
    assert _first_day("en-GB").month == 4


def test_the_preference_is_wired():
    routes = (ROOT / "src/tessellate/api/routes_settings.py").read_text(encoding="utf-8")
    app = (ROOT / "src/tessellate/api/app.py").read_text(encoding="utf-8")
    cfg = (ROOT / "src/tessellate/core/config.py").read_text(encoding="utf-8")
    assert 'date_order: Literal["auto", "day", "month"] | None = None' in routes
    assert 'key == "date_order"' in routes
    assert "configure_date_order(" in app
    assert '"date_order": "auto"' in cfg
