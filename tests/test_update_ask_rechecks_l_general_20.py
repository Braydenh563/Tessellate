"""Source text: the first-run queue is timed in a browser. The update question
waits its turn there, so it must re-read the answer when its turn comes, or a
choice made meanwhile (another tab, Settings, the sweeps' boot) is asked again
over whatever is on screen (L-general-20: it covered the docks sweep's clicks)."""

from tests._app_js import frontend_text


def test_the_update_question_rechecks_when_its_turn_comes():
    js = frontend_text("update-dialogs.js")
    body = js[js.index("async function askUpdateChoiceOnce()"):]
    ask = body[body.index("const ask = () =>"):body.index("confirmDialog(")]
    assert "prefsCache?.update_choice_made !== false" in ask
    assert "Promise.resolve(undefined)" in ask
