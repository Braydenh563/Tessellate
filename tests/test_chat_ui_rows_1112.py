"""The Chat/Ask UI rows closed from a browser drive (chatui, 2026-11-12): each pins what the drive measured."""

from tests._app_js import app_js_text


def test_a_skill_run_result_draws_its_budget_line_l55():
    js = app_js_text()
    assert "function budgetRow(budget)" in js and "const spent = budgetRow(event.budget);" in js
    assert "if (spent) box.appendChild(spent);" in js


def test_the_ask_scope_is_set_and_cleared_in_one_module_l74():
    """The only caller of setAskScope is the Questions view, whose init wires the clear button, so the button
    cannot be shown before its handler exists."""
    js = app_js_text()
    assert js.count("setAskScope(") == 3  # the two calls and the definition, all in questions-view.js
    assert '$("ask-scope-clear")?.addEventListener("click"' in js


def test_the_open_settings_models_line_is_a_toast_button_l61():
    assert '"Open Settings, Models", () => openSettingsModal("models")' in app_js_text()


def test_a_message_without_a_stamp_shows_no_time_l226():
    """A chat saved before stamps existed has no `at` on its messages; the time is dropped, not guessed."""
    js = app_js_text()
    assert "const label = iso ? chatTimeLabel(iso) : null;" in js and "stamp?.remove();" in js
