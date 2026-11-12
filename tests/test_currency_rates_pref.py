"""The currency table is a dated preference (CHAT_PLAN decision 43).

Rates are the person's to edit in Settings, Search and index; the answer says
the date they carry, and a saved table never reaches past what was entered.
"""

from __future__ import annotations

from datetime import date

import pytest

from tessellate.ai import utilities


@pytest.fixture(autouse=True)
def _built_in_after():
    yield
    utilities.configure_rates(None)


def _said(question: str) -> str:
    return " ".join(text for _, text in utilities.answer(question))


def test_the_built_in_table_is_dated_and_said():
    assert "1 June 2025" in _said("100 usd in eur")


def test_a_saved_table_changes_the_answer_and_its_date():
    utilities.configure_rates({"date": "2026-10-01", "rates": {"EUR": 0.5}})
    said = _said("100 usd in eur")
    assert "about 50 EUR" in said and "1 October 2026" in said, said


def test_a_saved_table_keeps_the_codes_it_does_not_name():
    utilities.configure_rates({"date": "2026-10-01", "rates": {"EUR": 0.5}})
    assert utilities.current_rates()[0]["GBP"] == utilities.RATES["GBP"]


def test_nothing_saved_is_the_built_in_table():
    utilities.configure_rates({"date": "2026-10-01", "rates": {"EUR": 0.5}})
    utilities.configure_rates(None)
    assert utilities.current_rates() == (utilities.RATES, utilities.RATES_DATE)


def test_the_preference_round_trips_and_applies(client):
    body = {"currency_rates": {"date": "2026-10-01", "rates": {"eur": "0.5", "x": 3, "ABC": 2, "GBP": -1, "JPY": "abc"}}}
    got = client.put("/preferences", json=body).json()["currency_rates"]
    assert got == {"date": "2026-10-01", "rates": {"EUR": 0.5}}
    assert utilities.current_rates()[1] == date(2026, 10, 1)
    assert "1 October 2026" in _said("100 usd in eur")
    units = client.get("/utilities/units").json()
    assert units["rates_date"] == "2026-10-01"


def test_a_bad_date_is_refused_by_falling_back_to_the_built_in_date(client):
    got = client.put("/preferences", json={"currency_rates": {"date": "soon", "rates": {"EUR": 0.5}}}).json()
    assert got["currency_rates"] == {}


def test_reset_puts_the_built_in_table_back(client):
    client.put("/preferences", json={"currency_rates": {"date": "2026-10-01", "rates": {"EUR": 0.5}}})
    client.put("/preferences", json={"unset": ["currency_rates"]})
    assert client.get("/preferences").json()["currency_rates"] == {}
    assert utilities.current_rates()[1] == utilities.RATES_DATE


def test_the_rates_come_back_in_the_editor_text(client):
    client.put("/preferences", json={"currency_rates": {"date": "2026-10-01", "rates": {"EUR": 0.5}}})
    shown = client.get("/utilities/units").json()
    assert shown["rates"]["EUR"] == 0.5 and shown["rates"]["USD"] == 1.0
