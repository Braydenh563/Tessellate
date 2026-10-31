"""WORLD_CLASS_PLAN section 17, the original vision's open rows (section 8,
row 11): the review queue, the filing style, explain this note, most opened
this month, tidy proposals and charts from questions."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]


def _note(client, text, **extra):
    return client.post("/entries", json={"content": text, **extra}).json()


# --- 1. the review queue ------------------------------------------------------------


def test_the_review_queue_holds_unsure_and_uncategorised_filings(client, session):
    from tessellate.core.database import Entry

    unsure = _note(client, "Maybe a recipe, maybe a plan")
    settled = _note(client, "Filed by hand", category="Plans")
    sure = _note(client, "Atlas was sure")
    row = session.get(Entry, unsure["id"])
    row.ai_confidence = 40
    row.user_filed = False
    session.get(Entry, sure["id"]).ai_confidence = 90
    session.commit()
    queue = client.get("/review-queue").json()
    assert unsure["id"] in queue["ids"]
    assert settled["id"] not in queue["ids"]
    assert queue["count"] == len(queue["ids"])

    accepted = client.post(f"/review-queue/{unsure['id']}/accept")
    assert accepted.status_code == 200
    assert unsure["id"] not in client.get("/review-queue").json()["ids"]


def test_notes_filter_and_dashboard_offer_the_queue():
    app = app_js_text()
    assert 'flag === "review"' in app
    assert "/review-queue" in app


# --- 3. the filing style ------------------------------------------------------------------


def test_the_filing_style_reaches_the_filing_prompt(client, session):
    from tessellate.ai import librarian
    from tessellate.core import deps

    plain = librarian.filing_prompt(session, "a note", ["Work"])
    assert "File by" not in plain
    reply_1 = client.put("/preferences", json={"filing_style": "project"})
    assert reply_1.status_code == 200
    assert deps.get_config().get_preference("filing_style") == "project"
    styled = librarian.filing_prompt(session, "a note", ["Work"])
    assert "File by project" in styled
    reply_2 = client.put("/preferences", json={"filing_style": "nonsense"})
    assert reply_2.status_code == 422


# --- 5. most opened this month ---------------------------------------------------------------


def test_most_opened_counts_this_month_only(client, session):
    from tessellate.core.database import EntryOpen, utcnow

    a = _note(client, "Opened twice")
    b = _note(client, "Opened once")
    old = _note(client, "Opened long ago, often")
    client.get(f"/entries/{a['id']}?open=1")
    client.get(f"/entries/{a['id']}?open=1")
    client.get(f"/entries/{b['id']}?open=1")
    session.add(EntryOpen(entry_id=old["id"], day=(utcnow().date() - timedelta(days=60)).isoformat(), count=50))
    session.commit()
    top = client.get("/most-opened").json()
    assert [row["id"] for row in top] == [a["id"], b["id"]]
    assert top[0]["opened"] == 2


# --- 2. tidy proposals --------------------------------------------------------------------


def test_tidy_proposes_near_names_and_old_empty_categories(client, session):
    from tessellate.core.database import Category, utcnow

    _note(client, "one", category="Recipes")
    _note(client, "two", category="Recipes")
    _note(client, "three", category="Recipe")
    session.add(Category(name="Old empty", created_at=utcnow() - timedelta(days=45)))
    session.add(Category(name="New empty"))
    session.commit()
    body = client.get("/tidy-proposals").json()
    pairs = [(m["keep"]["name"], m["merge"]["name"]) for m in body["merges"]]
    assert ("Recipes", "Recipe") in pairs
    assert [e["name"] for e in body["empty"]] == ["Old empty"]

    client.post("/tidy-proposals/dismiss", json={"a": "Recipe", "b": "Recipes"})
    again = client.get("/tidy-proposals").json()
    assert not [m for m in again["merges"] if {m["keep"]["name"], m["merge"]["name"]} == {"Recipe", "Recipes"}]


# --- 4. charts from questions --------------------------------------------------------------------


def test_a_counting_question_is_read_without_a_model():
    from tessellate.api.routes_vision import parse_chart_question

    today = date(2026, 10, 15)
    asked = parse_chart_question("How many notes per category this month?", today)
    assert asked["by"] == "category" and asked["since"] == date(2026, 10, 1)
    assert parse_chart_question("notes per week in 2026", today)["by"] == "week"
    assert parse_chart_question("how many notes did I write last month", today)["by"] == "day"
    assert parse_chart_question("what did I write about Kyoto?", today) is None


def test_the_chart_route_counts_the_records(client):
    _note(client, "a", category="Travel")
    _note(client, "b", category="Travel")
    _note(client, "c", category="Work")
    chart = client.post("/charts/question", json={"question": "how many notes per category this month"}).json()["chart"]
    assert chart["kind"] == "bar"
    assert {r["label"]: r["value"] for r in chart["rows"]} == {"Travel": 2, "Work": 1}
    line = client.post("/charts/question", json={"question": "notes per day this week"}).json()["chart"]
    assert line["kind"] == "line" and sum(r["value"] for r in line["rows"]) == 3
    assert client.post("/charts/question", json={"question": "who is Ada?"}).json() == {"chart": None}


def test_the_ask_box_draws_the_chart_with_its_table_and_png():
    chart_js = (ROOT / "frontend" / "js" / "ask-chart.js").read_text(encoding="utf-8")
    assert "function renderAskChart(" in chart_js
    assert "<table" not in chart_js and 'createElement("table")' in chart_js
    assert "toBlob" in chart_js
    assert "#" not in "".join(line for line in chart_js.splitlines() if "fill" in line and "var(" not in line and "//" not in line)
    design = (ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8")
    assert "renderAskChart" in design


# --- 6. explain this note --------------------------------------------------------------------------


def test_a_note_menu_offers_explain_this_note():
    app = app_js_text()
    assert "Explain this note" in app
    assert "explainNote(" in app


def test_a_dismissed_merge_proposal_comes_back_on_undo(client):
    """INBOX 898: "Not these" has an inverse, so Undo can offer the pair again."""
    _note(client, "one", category="Recipes")
    _note(client, "two", category="Recipes")
    _note(client, "three", category="Recipe")

    def proposed():
        merges = client.get("/tidy-proposals").json()["merges"]
        return [m for m in merges if {m["keep"]["name"], m["merge"]["name"]} == {"Recipe", "Recipes"}]

    assert proposed()
    client.post("/tidy-proposals/dismiss", json={"a": "Recipe", "b": "Recipes"})
    assert not proposed()
    reply_3 = client.post("/tidy-proposals/undismiss", json={"a": "Recipes", "b": "Recipe"})
    assert reply_3.status_code == 200
    assert proposed()
