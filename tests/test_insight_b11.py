"""Volunteered insight (CHAT_PLAN decision 73, row B11): off, one line, or
as found; at most one line at "one", never one the answer already said,
and the bar rises with each Not right."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scratchpad"))
import restate_share  # noqa: E402

from tessellate.ai import composer_digest, insights  # noqa: E402

Q1 = "What have I saved about courses & study?"


def _ask(question: str = Q1, **kw) -> dict:
    return composer_digest.answer(question, restate_share.NOTES, today=restate_share.TODAY, **kw)


def test_one_line_volunteers_the_plan_gone_quiet():
    result = _ask(insight="one")
    #: Said once, in the study plan's own line (the owner, 2026-10-11).
    assert "try 25 minutes on, 5 off, though no later note says how that went" in result["text"]
    assert result["insights"][0]["in_answer"] is True
    assert len(result["insights"]) == 1 and result["insights"][0]["rule"] == "drift"


def test_off_says_nothing_of_its_own():
    result = _ask(insight="off")
    assert "no later note" not in result["text"] and result["insights"] == []


def test_a_count_the_opening_said_is_not_said_again():
    """"You have written about uni 4 times" after "four notes about uni"."""
    assert "times since" not in _ask(insight="all")["text"]


def test_a_dismissed_insight_is_not_said():
    row = _ask(insight="one")["insights"][0]
    known = insights.Memory(dismissed=frozenset({row["key"]}))
    assert "no later note" not in _ask(insight="one", learned=known)["text"]


def test_the_bar_rises_with_each_dismissal():
    assert composer_digest.insight_bar(None) == composer_digest.INSIGHT_BAR
    five = insights.Memory(dismissed=frozenset(f"x:{i}" for i in range(5)))
    assert composer_digest.insight_bar(five) == 1.0


def test_the_setting_saves_and_reads(client):
    before = client.get("/preferences").json()["insight_level"]
    saved = client.put("/preferences", json={"insight_level": "off"})
    after = client.get("/preferences").json()["insight_level"]
    refused = client.put("/preferences", json={"insight_level": "loud"})
    assert (before, saved.status_code, after, refused.status_code) == ("one", 200, "off", 422)


def test_settings_offers_the_three_levels():
    html = (Path(__file__).resolve().parents[1] / "frontend" / "index.html").read_text(encoding="utf-8")
    select = html[html.index('<select id="pref-insight"'):html.index("</select>", html.index('<select id="pref-insight"'))]
    for value in ("off", "one", "all"):
        assert f'value="{value}"' in select
    assert 'data-help-for="composer-insight-help"' in html


def test_through_the_route_the_line_and_its_row_arrive(client, session):
    """The route's notes carry `written`, not `created_at`; the rules read
    the latter, and without the conversion nothing ever fired in the app."""
    import json
    from datetime import datetime

    from tests import _gold
    from tessellate.core.database import Entry
    from tessellate.entry import manager

    for n in _gold.load()["notes"]:
        made = manager.create_entry(session, n["content"], category_name=n["category"], tags=n["tags"])
        session.flush()
        row = session.get(Entry, made.id)
        row.created_at = row.updated_at = datetime.fromisoformat(n["date"] + "T10:00:00")
    session.commit()
    body = {"question": Q1, "history": [], "notes_only": True, "use_tools": False, "answer_from": "notes"}
    with client.stream("POST", "/chat/stream", json=body) as response:
        events = [json.loads(line) for line in response.iter_lines() if line.strip()]
    text = "".join(e.get("delta", "") for e in events if e.get("type") == "answer")
    grounding = next(e for e in events if e.get("type") == "grounding")
    assert "no later note says how that went" in text
    assert [row["rule"] for row in grounding["insights"]] == ["drift"]
