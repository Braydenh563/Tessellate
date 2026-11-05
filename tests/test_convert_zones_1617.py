"""The Convert widget and the Units tab's time zones (INBOX 1617, the owner:
"widgets for the conversion etc"). The widget is the Calculator's own Units pane
drawn with no strip (`openCalculator.inline(body, "convert", { only: true })`);
a time-zone kind joins the unit kinds. Zones are read from the machine's zone
database, so it works offline; currency rates were already set by hand, so it is
offered too. Fixed clock throughout."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from tessellate.ai import utilities

ROOT = Path(__file__).resolve().parents[1]
KIT = (ROOT / "frontend/js/reply-kit.js").read_text(encoding="utf-8")
DASH = (ROOT / "frontend/js/dashboard.js").read_text(encoding="utf-8")
PANES = (ROOT / "frontend/js/settings-panes.js").read_text(encoding="utf-8")

NOON = datetime(2026, 11, 4, 12, 0)


def test_every_offered_place_converts_to_london_and_back():
    assert len(utilities.CONVERT_PLACES) == len(set(utilities.CONVERT_PLACES))
    for place in utilities.CONVERT_PLACES:
        got = utilities.answer(f"09:00 {place} to London", now=NOON)
        assert got and re.search(r"09:00 in .+ is \d\d:\d\d", got[0][1]), place
        back = utilities.answer(f"09:00 London to {place}", now=NOON)
        assert back and re.search(r"09:00 in London is \d\d:\d\d", back[0][1]), place


def test_a_known_pair_is_right_on_the_fixed_date():
    # 4 November 2026: London is on GMT, Tokyo is nine hours ahead all year.
    assert utilities.answer("09:00 London to Tokyo", now=NOON)[0][1] == "09:00 in London is 18:00 in Tokyo."
    # New York is on EST by then, five hours behind London.
    assert utilities.answer("09:00 New York to London", now=NOON)[0][1] == "09:00 in New York is 14:00 in London."
    # Across midnight it says which day.
    assert "the day before" in utilities.answer("09:00 Sydney to London", now=NOON)[0][1]


def test_the_units_route_offers_time_zones_beside_currency(ai_client):
    units = ai_client.get("/utilities/units").json()
    assert units["timezone"] == list(utilities.CONVERT_PLACES)
    assert "USD" in units["currency"] and units["rates_date"]
    got = ai_client.get("/utilities/work", params={"q": "09:00 London to Tokyo"}).json()
    assert got["answer"] == "09:00 in London is 18:00 in Tokyo." or got["answer"].startswith("09:00 in London is ")


def test_convert_is_a_widget_drawn_from_the_calculators_own_units_pane():
    table = DASH.split("const POPUP_WIDGETS = {", 1)[1].split("\n  };", 1)[0]
    assert 'openCalculator.inline(body, "convert", { only: true })' in table
    assert re.search(r'^\s+convert: \{ title: "ph:ruler Convert", description: "[^"]{20,}"', table, re.M)
    block = PANES.split('id: "convert"', 1)[1].split("\n  },", 1)[0]
    assert 'widget: "convert"' in block
    # One build for the dialog and the widget; the strip is left out for `only`.
    assert KIT.count("function replyCalcBuild(") == 1
    assert "openCalculator.inline = (host, mode = \"work\", { only = false } = {}) =>" in KIT
    assert "card.append(...(only ? [] : [modes]), wrap, actions.el);" in KIT


def test_the_units_pane_switches_its_amount_to_a_time_for_a_zone():
    pane = KIT.split("function replyCalcConvertPane(", 1)[1].split("\n}\n", 1)[0]
    assert 'kind.value === "timezone"' in pane and 'amount.type = zone ? "time" : "number"' in pane
    assert "REPLY_CALC_PAIRS" in KIT and 'timezone: ["London", "Tokyo"]' in KIT
