"""L737 (owner, 2026-11-12): Settings, Models picks who answers plain Ask; default the model; the Guide says so."""

from tests._app_js import frontend_text
from tests._help_text import help_more_text


def test_the_select_exists_with_the_model_first():
    html = open("frontend/index.html", encoding="utf-8").read()
    row = html[html.index('id="ask-answerer-select"') :][:400]
    assert row.index('value="ai"') < row.index('value="notes"')
    assert 'data-help-for="ask-answerer-help"' in html


def test_it_shares_the_ask_switchs_stored_value():
    js = frontend_text("settings-models.js")
    assert 'prefs.set("ask-answer-from"' in js
    assert 'prefs.get("ask-answer-from") === "notes" ? "notes" : "ai"' in js


def test_the_guide_names_the_setting():
    assert "Who answers plain Ask" in help_more_text()
