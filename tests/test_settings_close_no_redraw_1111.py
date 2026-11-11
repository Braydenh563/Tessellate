"""Closing Settings does not open the tab under it again (owner-asks-audit 1620 lag).

The backdrop, the X and Escape all step the browser back off Settings' entry;
`popstate` walks to the entry underneath and `openHistoryEntry` used to run
`switchTab` on it, which redrew the Dashboard under a closing window (a 580 ms
frame at 4x with 223 ms in `onpopstate`; numbers in
docs/roadmap/agent-remaining/w34-def1-1111.md). The function is run in node
here with its collaborators stubbed.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
NAV = (ROOT / "frontend" / "js" / "navigation.js").read_text(encoding="utf-8")

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _run(entry: dict, from_entry: dict | None, active: str, modal_open: bool = False) -> dict:
    fn = re.search(r"^async function openHistoryEntry\(.*?^\}", NAV, re.S | re.M)
    assert fn, "openHistoryEntry is gone from navigation.js"
    script = f"""
const calls = [];
const window = {{}};
const prefs = {{ get: () => {json.dumps(active)} }};
let tabSwitchDeclined = false;
let modalOpen = {json.dumps(modal_open)};
const settingsModalOpen = () => modalOpen;
const closeSettingsModal = () => {{ modalOpen = false; calls.push("close"); }};
const openSettingsModal = async () => calls.push("openSettings");
const paintTabHistory = () => {{}};
const switchTab = async (name) => calls.push("switchTab:" + name);
{fn.group(0)}
openHistoryEntry({json.dumps(entry)}, {json.dumps({"from": from_entry}) if from_entry else "undefined"})
  .then(() => process.stdout.write(JSON.stringify(calls)));
"""
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return {"calls": json.loads(out)}


def test_closing_settings_onto_the_tab_under_it_opens_nothing() -> None:
    result = _run({"tab": "dashboard", "section": None}, {"tab": "settings", "section": "models"}, "dashboard")
    assert result["calls"] == []


def test_back_with_the_window_still_open_closes_it_but_does_not_redraw() -> None:
    result = _run({"tab": "dashboard", "section": None}, {"tab": "settings", "section": "models"}, "dashboard", modal_open=True)
    assert result["calls"] == ["close"]


def test_a_walk_to_another_tab_still_opens_it() -> None:
    # Settings was opened over Notes and Back went two steps, to the Dashboard.
    result = _run({"tab": "dashboard", "section": None}, {"tab": "settings", "section": "models"}, "notes")
    assert result["calls"] == ["switchTab:dashboard"]


def test_a_walk_that_does_not_start_in_settings_still_opens_the_tab() -> None:
    result = _run({"tab": "dashboard", "section": None}, {"tab": "notes", "section": None}, "dashboard")
    assert result["calls"] == ["switchTab:dashboard"]
    assert _run({"tab": "dashboard", "section": None}, None, "dashboard")["calls"] == ["switchTab:dashboard"]


def test_the_walk_hands_the_entry_it_leaves_to_the_opener() -> None:
    assert "openHistoryEntry(entry, { from: tabHistory.stack[from] })" in NAV
