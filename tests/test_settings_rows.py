"""Settings as rows (WORLD_CLASS_PLAN 25f, decision 52).

A setting is a row with a name, its default and a reset; the file Settings
exports reads back into another install. The backend half is checked here
against the real routes; the rows' registry (`settings-rows.js`) is walked
against every preference key, so a new preference is either given a row or
named below with the reason it has none.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from tessellate.api.routes_settings import PreferencesBody
from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parents[1]
ROWS_JS = (ROOT / "frontend" / "js" / "settings-rows.js").read_text(encoding="utf-8")
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def test_defaults_are_what_a_fresh_notebook_reads(client):
    fresh = client.get("/preferences").json()
    defaults = client.get("/preferences/defaults").json()
    assert defaults == fresh
    assert defaults["recycle_bin_days"] == 30
    assert defaults["auto_tag_enabled"] is True


def test_defaults_do_not_move_when_a_setting_changes(client):
    client.put("/preferences", json={"recycle_bin_days": 7})
    assert client.get("/preferences").json()["recycle_bin_days"] == 7
    assert client.get("/preferences/defaults").json()["recycle_bin_days"] == 30


def test_export_names_itself_and_leaves_this_computer_out(client):
    client.put("/preferences", json={"recycle_bin_days": 9, "timezone": "Europe/London"})
    body = client.get("/preferences/export").json()
    assert body["kind"] == "memorymap-settings"
    assert body["version"] == 1
    prefs = body["preferences"]
    assert prefs["recycle_bin_days"] == 9
    for local in ("timezone", "export_save_dir", "backup_copy_dir", "console_view_intro_seen", "tray_hide_explained"):
        assert local not in prefs
    assert set(prefs) <= set(PreferencesBody.model_fields)


def test_export_then_import_into_a_fresh_notebook_is_equal(client):
    client.put(
        "/preferences",
        json={"recycle_bin_days": 12, "communication_style": "concise", "auto_tag_enabled": False},
    )
    exported = client.get("/preferences/export").json()
    # Back to the defaults, as another install would be.
    defaults = client.get("/preferences/defaults").json()
    client.put(
        "/preferences",
        json={k: defaults[k] for k in ("recycle_bin_days", "communication_style", "auto_tag_enabled")},
    )
    result = client.post("/preferences/import", json=exported).json()
    assert set(result["applied"]) == {"recycle_bin_days", "communication_style", "auto_tag_enabled"}
    assert result["skipped"] == []
    after = client.get("/preferences/export").json()["preferences"]
    assert after == exported["preferences"]


def test_import_skips_a_bad_key_and_keeps_the_rest(client):
    exported = client.get("/preferences/export").json()
    exported["preferences"] = {
        "recycle_bin_days": 5000,  # out of range
        "a_setting_from_the_future": True,
        "timezone": "Asia/Tokyo",
        "auto_link_enabled": False,
    }
    result = client.post("/preferences/import", json=exported).json()
    assert result["applied"] == ["auto_link_enabled"]
    reasons = {row["key"]: row["reason"] for row in result["skipped"]}
    assert set(reasons) == {"recycle_bin_days", "a_setting_from_the_future", "timezone"}
    prefs = client.get("/preferences").json()
    assert prefs["auto_link_enabled"] is False
    assert prefs["recycle_bin_days"] == 30
    assert prefs["timezone"] != "Asia/Tokyo"


def test_import_refuses_a_file_that_is_not_settings(client):
    not_settings = client.post("/preferences/import", json={"notes": []})
    assert not_settings.status_code == 422
    newer = {"kind": "memorymap-settings", "version": 99, "preferences": {}}
    response = client.post("/preferences/import", json=newer)
    assert response.status_code == 422
    assert "newer version" in response.json()["detail"]


# --- the rows' registry, walked against every key -------------------------------

#: Preferences with no row of their own, each with why. A key added to
#: PreferencesBody lands in the registry or here; the test below fails otherwise.
NO_ROW = {
    "embedder_idle_unload_minutes": "an advanced key (decision 62), set by hand; 0 keeps the model loaded",
    "week_start_locale": "reported by the browser at startup; the First day of the week row overrides it",
    "semantic_choice_made": "set by the one-time download question; Download search by meaning is the row that changes the answer",
    # Edited as lists or documents in their own panes, not one control.
    "writing_dictionary": "the dictionary editor (Documents)",
    "link_offer_ignored": "the Ignore answer on a link offer, with its count and reset in Settings, Writing",
    "model_context_windows": "one box per model in Models",
    "custom_templates": "the Templates pane's list",
    "personas": "the Personas pane's list",
    "custom_themes": "Appearance's saved looks",
    "skills": "the Skills pane's list",
    "disabled_tools": "one switch per tool in Tools it can use",
    "dashboard_layout": "the dashboard's Customise",
    "dashboard_quick_access": "the dashboard's Quick access manager",
    "dashboard_quick_tints": "the dashboard's Quick access manager",
    "saved_searches": "rows in the sidebar",
    "saved_finds": "rows in Find anything",
    "ui_state": "the appearance keys, each a row of its own (LOOK_ROWS)",
    "avatar_style": "the profile's look picker",
    "status_bar_hidden": "the status bar's own menu",
    # Chosen where the work is, not in Settings.
    "active_persona": "the chat's persona picker",
    "dashboard_persona": "the dashboard's persona picker",
    "response_mode": "the chat's mode picker",
    "spelling_variant": "the document editor's writing panel",
    "grammar_check": "the document editor's writing panel",
    "agent_activity_notices": "the agent activity panel",
    "tools_enabled": "the chat's agent switch",
    "search_provider": "radio rows drawn from the server's engine list",
    # Bookkeeping, never a choice.
    "timezone": "detected from the browser",
    "console_view_intro_seen": "a one-time intro",
    "tray_hide_explained": "a one-time notice",
    "export_save_dir": "a path with its own Reset to default button",
    "backup_copy_dir": "a path on this computer, set beside the backups list",
    "update_choice_made": "the answer to the ask-once update question",
    # The person's own words, not a choice with a default to go back to.
    "display_name": "your name, typed",
    "user_profile": "your profile, typed",
}


def _registry_keys() -> dict[str, str]:
    block = ROWS_JS[ROWS_JS.index("const SETTING_ROWS"):ROWS_JS.index("];", ROWS_JS.index("const SETTING_ROWS"))]
    return dict(re.findall(r'\{\s*key:\s*"(\w+)",\s*id:\s*"([\w-]+)"', block))


def test_every_preference_has_a_row_or_a_reason(client):
    keys = set(client.get("/preferences").json())
    rows = _registry_keys()
    missing = keys - set(rows) - set(NO_ROW)
    assert not missing, f"preferences with no Settings row and no reason in NO_ROW: {sorted(missing)}"
    assert not set(rows) & set(NO_ROW), "a key cannot both have a row and be excused from one"
    assert set(rows) <= keys, f"rows for keys the server does not have: {sorted(set(rows) - keys)}"


def _settings_modal() -> str:
    start = INDEX.index('id="settings-modal"')
    return INDEX[start:]


def test_every_row_names_a_control_inside_settings():
    modal = _settings_modal()
    for key, control in _registry_keys().items():
        assert f'id="{control}"' in modal, f"{key}: #{control} is not in the Settings window"


def test_every_look_row_names_a_control_inside_settings():
    block = ROWS_JS[ROWS_JS.index("const LOOK_ROWS"):ROWS_JS.index("];", ROWS_JS.index("const LOOK_ROWS"))]
    rows = re.findall(r'\{\s*key:\s*"([\w-]+)",\s*id:\s*"([\w-]+)"', block)
    assert len(rows) >= 20
    modal = _settings_modal()
    for key, control in rows:
        assert f'id="{control}"' in modal, f"{key}: #{control} is not in the Settings window"


def test_the_file_is_lazy_and_reached_from_the_settings_bundle():
    assert "settings-rows.js" not in INDEX.split('id="settings-modal"')[0].split("<body")[0]
    find = (ROOT / "frontend" / "js" / "settings-find.js").read_text(encoding="utf-8")
    assert 'lazyScript("/js/settings-rows.js")' in find


def test_registry_is_valid_json_shape():
    # A row is `{ key: "...", id: "..." }` with optional fields; a typo in the
    # shape would drop the row from the walk above without a word.
    block = ROWS_JS[ROWS_JS.index("const SETTING_ROWS"):ROWS_JS.index("];", ROWS_JS.index("const SETTING_ROWS"))]
    assert block.count("key:") == len(_registry_keys())
    json.dumps(_registry_keys())


def test_import_merges_personas_and_templates_by_name(client):
    """OPEN row 558: a settings file replaced each list whole, so importing a
    file with one persona dropped every other persona this notebook had."""
    client.put("/preferences", json={"personas": [
        {"name": "Coach", "prompt": "Be encouraging."},
        {"name": "Editor", "prompt": "Be strict."},
    ]})
    exported = client.get("/preferences/export").json()
    exported["preferences"] = {"personas": [
        {"name": "Editor", "prompt": "Be gentle."},
        {"name": "Poet", "prompt": "Rhyme."},
    ]}
    result = client.post("/preferences/import", json=exported).json()
    assert result["applied"] == ["personas"]
    names = {p["name"]: p["prompt"] for p in client.get("/preferences").json()["personas"]}
    assert names == {"Coach": "Be encouraging.", "Editor": "Be gentle.", "Poet": "Rhyme."}
    # Undo puts the list back whole, which a merge alone could not.
    exported["preferences"] = {"personas": [
        {"name": "Coach", "prompt": "Be encouraging."},
        {"name": "Editor", "prompt": "Be strict."},
    ]}
    exported["replace_lists"] = True
    client.post("/preferences/import", json=exported)
    assert [p["name"] for p in client.get("/preferences").json()["personas"]] == ["Coach", "Editor"]


# A found setting lands on its control (OPEN ledger 1407).

def _fn(text: str, name: str) -> str:
    start = text.index(f"function {name}(")
    return text[start : text.index("\n}\n", start)]


def test_1407_a_found_setting_lands_on_its_control():
    body = _fn(frontend_text("settings-find.js"), "openSettingRow")
    assert 'pick(el.closest(".setting-row"))' in body
    assert '[aria-checked="true"], [aria-pressed="true"], button:not([disabled])' in body
