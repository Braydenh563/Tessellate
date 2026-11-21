"""L519, decision 43: the dated currency table is edited in Settings, Search
and index, and currency answers use what was saved, with its date."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from tessellate.ai import utilities

pytestmark = pytest.mark.usefixtures("app_state")

ROOT = Path(__file__).resolve().parents[1]


def test_saved_rates_lay_over_the_built_in_table():
    rates, when = utilities.saved_rates({"date": "2026-10-01", "rates": {"EUR": 0.5, "USD": 9, "XXX": 3, "GBP": -1}})
    assert when == date(2026, 10, 1)
    assert rates["EUR"] == 0.5 and rates["USD"] == 1.0 and "XXX" not in rates
    assert rates["GBP"] == utilities.RATES["GBP"]
    assert utilities.saved_rates(None) == (utilities.RATES, utilities.RATES_DATE)
    assert utilities.saved_rates({"date": "soon"}) == (utilities.RATES, utilities.RATES_DATE)


def test_the_route_saves_answers_with_and_resets_the_table(client):
    first = client.get("/utilities/rates").json()
    assert first["built_in"] is True
    saved = client.put("/utilities/rates", json={"date": "2026-10-01", "rates": {"EUR": 0.5}}).json()
    assert saved["built_in"] is False and saved["rates"]["EUR"] == 0.5 and saved["date"] == "2026-10-01"
    said = " ".join(text for _kind, text in utilities.answer("10 dollars to euros"))
    assert "5" in said and "October 2026" in said
    units = client.get("/utilities/units").json()
    assert units["rates_date"] == "2026-10-01"
    unknown = client.put("/utilities/rates", json={"date": "2026-10-01", "rates": {"ZZZ": 1}})
    zero = client.put("/utilities/rates", json={"date": "2026-10-01", "rates": {"EUR": 0}})
    assert unknown.status_code == 422 and zero.status_code == 422
    reset = client.delete("/utilities/rates").json()
    assert reset["built_in"] is True
    said = " ".join(text for _kind, text in utilities.answer("10 dollars to euros"))
    assert "8.8" in said


def test_settings_has_the_editor_and_says_where_it_is():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    section = html[html.index('id="settings-searchindex"') :]
    section = section[: section.index("</section>")]
    for needed in ('id="currency-rates-date"', 'id="currency-rates-text"', 'id="currency-rates-save"', 'data-help-for="currency-rates-help"'):
        assert needed in section
    js = (ROOT / "frontend" / "js" / "settings.js").read_text(encoding="utf-8")
    assert "showSettingsSection.loadCurrencyRates();" in js and 'apiJson("/utilities/rates", { method: "PUT"' in js
    assert "offerUndo(" in js[js.index("async function saveCurrencyRates") :]
    topics = (ROOT / "src" / "tessellate" / "ai" / "help_topics_more.py").read_text(encoding="utf-8")
    assert "currency rates are dated, set in Settings, Search and index." in topics
