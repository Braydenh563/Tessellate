"""Auto-update asks once (the owner's decision, 2026-10-05).

WORLD_CLASS_PLAN 12, "Decisions made": the first launch asks, in the terminal
or the app, whether to check for updates automatically, and remembers the
answer; until it is answered nothing about updating touches the network;
Settings keeps a "Check for updates" button and the switch. INBOX 221 had
made `auto_update_enabled` default on for a source checkout, so every clone
ran `git pull` on every launch unasked.

The launcher half (start.sh's plan and its terminal question) is tested in
`tests/test_launcher_update_settings.py` and `tests/test_launcher_scripts.py`.
"""

from __future__ import annotations

import pytest

from tessellate.api import routes_update


@pytest.fixture(autouse=True)
def _clean_update_state():
    routes_update.reset_for_tests()
    yield
    routes_update.reset_for_tests()


def test_a_fresh_notebook_has_not_answered_and_checks_nothing(tmp_path):
    from tessellate.core.config import ConfigManager

    config = ConfigManager(tmp_path / "fresh")
    assert config.get_preference("update_choice_made") is False
    # Off for every install now, a source checkout included.
    assert config.get_preference("auto_update_enabled") is False
    assert config.get_preference("update_check_enabled") is False


def test_settings_reports_whether_the_question_was_answered(client):
    body = client.get("/preferences").json()
    assert body["update_choice_made"] is False


def test_yes_turns_checking_on_and_remembers(client, app_state):
    response = client.post("/update/choice", json={"check": True})
    assert response.status_code == 200
    assert app_state.get_preference("update_choice_made") is True
    assert app_state.get_preference("update_check_enabled") is True
    # INBOX 1440: yes is "tell me"; the launcher's pull stays its own switch.
    assert app_state.get_preference("auto_update_enabled") is False


def test_yes_in_the_packaged_app_does_not_also_install_unasked(client, app_state, monkeypatch):
    """Installing is its own switch in the packaged app: yes is "tell me"."""
    monkeypatch.setattr(routes_update.sys, "frozen", True, raising=False)
    assert client.post("/update/choice", json={"check": True}).status_code == 200
    assert app_state.get_preference("update_check_enabled") is True
    assert app_state.get_preference("auto_update_enabled") is False
    assert app_state.get_preference("update_choice_made") is True


def test_no_turns_both_off_and_remembers(client, app_state):
    app_state.set_preference("auto_update_enabled", True)
    assert client.post("/update/choice", json={"check": False}).status_code == 200
    assert app_state.get_preference("update_choice_made") is True
    assert app_state.get_preference("update_check_enabled") is False
    assert app_state.get_preference("auto_update_enabled") is False


def test_turning_a_switch_in_settings_is_an_answer(client, app_state):
    assert client.put("/preferences", json={"update_check_enabled": False}).status_code == 200
    assert app_state.get_preference("update_choice_made") is True


def test_the_launchers_answer_is_kept_by_the_app(app_state, monkeypatch):
    """start.sh asks in the terminal before there is a Python to write the
    file, so it hands the answer over in `MM_UPDATE_CHOICE`."""
    monkeypatch.setenv("MM_UPDATE_CHOICE", "no")
    routes_update.apply_launcher_choice(app_state)
    assert app_state.get_preference("update_choice_made") is True
    assert app_state.get_preference("auto_update_enabled") is False


def test_the_launchers_answer_never_overrides_a_later_one(app_state, monkeypatch):
    app_state.set_preference("update_choice_made", True)
    app_state.set_preference("update_check_enabled", True)
    monkeypatch.setenv("MM_UPDATE_CHOICE", "no")
    routes_update.apply_launcher_choice(app_state)
    assert app_state.get_preference("update_check_enabled") is True


@pytest.mark.parametrize("value", ["", "maybe", "YES please"])
def test_anything_but_yes_or_no_is_no_answer(app_state, monkeypatch, value):
    monkeypatch.setenv("MM_UPDATE_CHOICE", value)
    routes_update.apply_launcher_choice(app_state)
    assert app_state.get_preference("update_choice_made") is False


def test_the_check_button_works_with_the_switch_off(client, app_state, monkeypatch):
    """Settings keeps a "Check for updates" button: a click is the person
    asking for that one request, so it is not refused by the switch."""
    calls = []

    class _Response:
        status_code = 404

    def fake_get(url, **kwargs):
        calls.append(url)
        return _Response()

    monkeypatch.setattr(routes_update.requests, "get", fake_get)
    app_state.set_preference("update_channel", "stable")
    # The automatic check (no click) still does nothing.
    assert client.get("/update/check").json()["reason"] == "disabled"
    assert calls == []
    body = client.get("/update/check?manual=1").json()
    assert body["reason"] == "no_releases"
    assert len(calls) == 1
