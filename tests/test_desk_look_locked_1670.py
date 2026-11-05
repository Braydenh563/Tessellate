"""INBOX 1670: the desk companion showed masculine Atlas until the app was
unlocked, because a locked app window has not read its prefs yet and answers
the default look. The last look a readable window gave is kept in the desktop's
own prefs and stands while the window is locked. Fake app window."""

from __future__ import annotations

import json

from tessellate.core import desk_companion as dc
from tests.test_desk_companion import prefs  # noqa: F401
from tests.test_desk_overlay_wiring import FakeRunner, over  # noqa: F401


def answer(look: str, locked: bool, mode: str = "full") -> str:
    return json.dumps({"look": look, "locked": locked, "motion": {"mode": mode, "reason": ""}})


def test_the_look_script_says_whether_the_app_is_locked() -> None:
    assert "lock-overlay" in dc.LOOK_SCRIPT and "locked:" in dc.LOOK_SCRIPT


def test_an_unlocked_answer_is_remembered(over, prefs) -> None:  # noqa: F811
    over.main_window.evaluate_js = lambda s: answer("feminine", False)
    over.set_main_hidden(True)
    assert FakeRunner.started[-1].look == "feminine"
    assert prefs[dc.LOOK_PREF] == "feminine"


def test_a_locked_app_keeps_the_remembered_look_not_its_default(over, prefs) -> None:  # noqa: F811
    prefs[dc.LOOK_PREF] = "feminine"
    over.main_window.evaluate_js = lambda s: answer("masculine", True)
    over.set_main_hidden(True)
    assert FakeRunner.started[-1].look == "feminine"
    assert prefs[dc.LOOK_PREF] == "feminine"


def test_a_locked_app_keeps_the_remembered_motion(over, prefs) -> None:  # noqa: F811
    prefs[dc.LOOK_PREF] = "feminine"
    prefs[dc.MOTION_PREF] = ["full", ""]
    over.main_window.evaluate_js = lambda s: answer("masculine", True, mode="still")
    over.set_main_hidden(True)
    assert FakeRunner.started[-1].reduced is False


def test_nothing_remembered_and_locked_falls_back_to_the_answer(over, prefs) -> None:  # noqa: F811
    over.main_window.evaluate_js = lambda s: answer("masculine", True)
    over.set_main_hidden(True)
    assert FakeRunner.started[-1].look == "masculine"
    assert dc.LOOK_PREF not in prefs
