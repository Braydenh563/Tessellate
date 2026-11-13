"""Source text: "The first-run queue (welcome, recovery key, updates) costs 3 acts
before the dashboard" (L451).

The update question rides the welcome's preferences card as one more choice,
so a person who finishes the welcome has answered it there, and the separate
dialog (update-dialogs.js, which skips once `update_choice_made` is true) never
opens: two acts, not three. Skipping the welcome before that card leaves it
unanswered, so the dialog still asks.
"""

from __future__ import annotations

from tests._app_js import frontend_text


def _onboarding() -> str:
    return frontend_text("onboarding.js")


def test_the_preferences_card_offers_the_update_choice():
    js = _onboarding()
    assert 'select.id = "onboarding-pref-update";' in js
    assert '["no", "Don\'t check"]' in js and '["yes", "Check each time it starts"]' in js
    assert '"/update/choice"' in js


def test_closing_from_the_preferences_card_records_the_shown_answer():
    js = _onboarding()
    close = js[js.index("function closeOnboarding(") : js.index("function onboardingNext(")]
    assert "onboardingRun.saveUpdateChoice()" in close
    save = js[js.index("onboardingRun.saveUpdateChoice = ") :]
    save = save[: save.index("\n};\n")]
    # Only an unanswered question, and only from the card that showed it.
    assert "update_choice_made !== false" in save
    assert "onboardingRun.updateSelect" in save and "?.prefs" in save


def test_the_dialog_still_skips_an_answered_question():
    assert "prefsCache?.update_choice_made !== false ? Promise.resolve(undefined)" in frontend_text("update-dialogs.js")
