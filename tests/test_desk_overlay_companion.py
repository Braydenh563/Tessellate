"""The right-click "Companion" choice on the overlay (INBOX 1656): the same options the app's
Appearance offers, the current one marked, a choice written to the app's own prefs through its
window (refused while locked) and the figure restarted with the new look. Fake app window."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from tessellate.core import desk_companion as dc
from tests.test_desk_companion import prefs  # noqa: F401
from tests.test_desk_overlay_wiring import FakeRunner, over  # noqa: F401

PRESETS = [
    {"name": "Night Atlas", "who": "atlas", "look": "feminine"},
    {"name": "Me in a hat", "who": "me", "look": ""},
    {"name": "", "who": "atlas", "look": ""},
]


def app(state: dict, seen: list):
    """A fake app window: answers the look, the choices and the writes from `state`."""

    def run(script: str):
        seen.append(script)
        if script == dc.COMPANION_SCRIPT:
            return json.dumps({"locked": state["locked"], "who": state["who"], "look": state["look"], "presets": PRESETS})
        if script == dc.LOOK_SCRIPT:
            return json.dumps({"look": "feminine" if state["look"] == "feminine" else "masculine", "motion": {"mode": "full", "reason": ""}})
        if "avatar-buddy-presets" in script:
            return "gone" if state.get("gone") else "ok"
        if "prefs.set('atlas-look'" in script:
            if state["locked"]:
                return "locked"
            state["who"], state["look"] = "atlas", "feminine" if '"feminine"' in script else "masculine"
            return "ok"
        return None

    return run


def test_every_appearance_choice_is_listed_with_the_current_one_marked() -> None:
    rows = dc.companion_options({"who": "atlas", "look": "feminine", "presets": PRESETS})
    by = {r["key"]: r for r in rows}
    assert [r["label"] for r in rows][:3] == ["Atlas, masculine", "Atlas, feminine", "Atlas, match your faces"]
    assert [k for k, r in by.items() if r["current"]] == ["atlas:feminine"]
    #: Changed on purpose (INBOX 1684): the overlay now draws the person's own companions from the app's figure
    #: (`capture`), so no row is "shows in the app only" any more; every row is choosable.
    for key in ("me", "persona", "custom"):
        assert by[key]["enabled"] is True and by[key]["group"] == "Yours"
    assert by["preset:0"]["enabled"] is True and by["preset:0"]["group"] == "Saved companions"
    assert by["preset:1"]["enabled"] is True and by["preset:1"]["group"] == "Saved companions"
    assert "preset:2" not in by  # a nameless one is not a row
    assert all(r["enabled"] for r in rows) and len(rows) == 3 + 3 + 2


def test_the_name_based_companion_is_marked_when_it_is_the_apps_choice() -> None:
    rows = dc.companion_options({"who": "me", "look": "auto", "presets": []})
    assert [r["key"] for r in rows if r["current"]] == ["me"]
    assert dc.companion_options("nonsense") == [] and dc.companion_options(None) == []


def test_the_panel_asks_the_app_window_and_lists_nothing_when_locked_or_silent(over) -> None:  # noqa: F811
    state = {"locked": False, "who": "atlas", "look": "masculine"}
    over.main_window.evaluate_js = app(state, [])
    got = dc.DeskApi(over).companion_choices()
    assert got["locked"] is False and len(got["options"]) == 3 + 3 + 2
    state["locked"] = True
    assert dc.DeskApi(over).companion_choices() == {"locked": True, "options": []}
    over.main_window.evaluate_js = lambda script: None
    assert dc.DeskApi(over).companion_choices() == {"locked": False, "options": []}


def test_choosing_feminine_atlas_writes_the_apps_prefs_and_restarts_the_figure_where_it_stood(over) -> None:  # noqa: F811
    state, seen = {"locked": False, "who": "atlas", "look": "masculine"}, []
    over.main_window.evaluate_js = app(state, seen)
    over.set_main_hidden(True)
    first = FakeRunner.started[0]
    first.engine = SimpleNamespace(x=640, y=900)
    assert dc.DeskApi(over).choose_companion("atlas:feminine") == "ok"
    write = next(s for s in seen if "prefs.set('atlas-look'" in s)
    assert "prefs.set('avatar-buddy','atlas')" in write and '"feminine"' in write
    second = FakeRunner.started[1]
    assert "stop" in first.calls and second.look == "feminine" and second.home == (640, 900) and second.calls == ["start", "show"]


def test_choosing_the_look_it_already_has_does_not_restart_it(over) -> None:  # noqa: F811
    state = {"locked": False, "who": "atlas", "look": "masculine"}
    over.main_window.evaluate_js = app(state, [])
    over.set_main_hidden(True)
    assert dc.DeskApi(over).choose_companion("atlas:masculine") == "ok"
    assert len(FakeRunner.started) == 1


def test_a_locked_app_refuses_the_choice_and_nothing_restarts(over) -> None:  # noqa: F811
    state = {"locked": True, "who": "atlas", "look": "masculine"}
    over.main_window.evaluate_js = app(state, [])
    over.set_main_hidden(True)
    assert dc.DeskApi(over).choose_companion("atlas:feminine") == "locked"
    assert len(FakeRunner.started) == 1 and state["look"] == "masculine"
    assert "if(lk&&!lk.classList.contains('hidden'))return 'locked'" in dc.COMPANION_ATLAS


def test_only_known_keys_reach_the_app_window(over) -> None:  # noqa: F811
    seen: list[str] = []
    over.main_window.evaluate_js = app({"locked": False, "who": "atlas", "look": "masculine"}, seen)
    api = dc.DeskApi(over)
    #: "me" and "custom" left this list on purpose (INBOX 1684): they are choices the overlay now draws.
    for bad in ("", "me ", "Custom", "atlas:'); alert(1);//", "preset:99999", "preset:x", "atlas:neutral", None, 3):
        assert api.choose_companion(bad) in ("unknown", "gone"), bad
    assert not any("prefs.set" in s for s in seen)


@pytest.mark.parametrize("answer, result", [("ok", "ok"), ("gone", "gone")])
def test_a_saved_atlas_companion_is_applied_by_name_and_place(over, answer, result) -> None:  # noqa: F811
    state, seen = {"locked": False, "who": "atlas", "look": "masculine", "gone": answer == "gone"}, []
    over.main_window.evaluate_js = app(state, seen)
    over.set_main_hidden(True)
    api = dc.DeskApi(over)
    assert api.choose_companion("preset:0") == "gone"  # never listed yet: no name to check against
    api.companion_choices()
    assert api.choose_companion("preset:0") == result
    script = next(s for s in seen if "avatar-buddy-presets" in s and "[0];" in s)
    assert '"Night Atlas"' in script and "nameMarkBuddyApplyPreset" in script


def test_the_page_api_has_the_two_new_calls(over) -> None:  # noqa: F811
    public = {n for n in dir(dc.DeskApi) if not n.startswith("_")}
    assert {"companion_choices", "choose_companion"} <= public


def test_the_panel_page_lists_the_choices_marks_the_current_and_guards_rows_the_host_refuses() -> None:
    from pathlib import Path

    js = (Path(__file__).resolve().parent.parent / "frontend" / "js" / "desk-companion.js").read_text(encoding="utf-8")
    body = js.split("async function openCompanion()", 1)[1].split("//: Run `action` first", 1)[0]
    assert 'ask("companion_choices")' in body and 'ask("choose_companion", option.key)' in body
    assert 'role", "menuitemradio"' in body and "aria-checked" in body and "row.disabled = !option.enabled" in body
    # Intent moved (INBOX 1684, fa7ed5e): the overlay draws every look, so no row
    # carries the "Shows in the app only" title; a disabled row stays disabled.
    assert "Shows in the app only" not in body and 'item("Back"' in body
    assert 'item("Companion", "user-switch", openCompanion)' in js and "if (overlay)" in js.split('item("Companion"', 1)[0].splitlines()[-1]
    assert "[role^=menuitem]:not(:disabled)" in js  # the arrows skip the rows that cannot be chosen
