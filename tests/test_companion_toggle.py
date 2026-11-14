"""Showing and hiding the companion from anywhere says what it will do.

INBOX 430, the owner: "a show/hide hotkey and palette action". The chord
(`toggleCompanion` in the shortcut registry, rebindable like the rest), the
palette row and Find anything's row were already there and all go through
`nameMarkBuddyHide`, the one hide path that sweeps every copy
(`scratchpad/ui-sweeps/companiontoggle.js`). What was left: the row read
"Show or hide the companion" whichever it would do, and the toast after a
hide named Ctrl+Shift+Y even when the chord had been rebound.
"""

from __future__ import annotations

import json
import shutil
import subprocess

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
#: The companion's code: avatars.js and the lazy files its settings and throw moved to (audit AI23).
AV = "\n".join((ROOT / "frontend" / "js" / n).read_text(encoding="utf-8") for n in ("avatars.js", "companion-settings.js"))
PANES = (ROOT / "frontend" / "js" / "settings-panes.js").read_text(encoding="utf-8") + (ROOT / "frontend" / "js" / "app-features.js").read_text(encoding="utf-8")
WIRING = (ROOT / "frontend" / "js" / "settings-wiring.js").read_text(encoding="utf-8")


def _fn(name: str, src: str = AV) -> str:
    start = src.index(f"function {name}(")
    return src[start : src.index("\n}\n", start) + 2]


def test_the_palette_row_names_what_it_will_do() -> None:
    row = 'label: nameMarkBuddyShowing() ? "ph:eye-slash Hide companion" : "ph:person-simple Show companion", chord: "toggleCompanion", act: () => nameMarkBuddyToggle()'
    assert row in PANES
    # Out or not is decided once, the way the toggle itself decides it.
    assert "if (nameMarkBuddyShowing()) {" in _fn("nameMarkBuddyToggle")


def test_the_chord_is_in_the_registry_and_rebindable() -> None:
    assert 'toggleCompanion: { keys: "Ctrl+Shift+Y", label: "Show or hide the companion" },' in WIRING
    assert "toggleCompanion: () => {" in WIRING and "nameMarkBuddyToggle();" in WIRING
    # A locked notebook answers no chord: the dispatcher returns first.
    keydown = WIRING[WIRING.index('document.addEventListener("keydown", (e) => {') :]
    assert keydown.index("if (notebookLocked()) return;") < keydown.index("for (const [id, def] of Object.entries(shortcuts))")


def _hide_toast(shortcuts: str) -> str:
    script = (
        """
const said = [];
const store = { "avatar-buddy": "atlas" };
global.localStorage = { getItem: (k) => store[k] ?? null, setItem: (k, v) => { store[k] = String(v); } };
global.window = global;
"""
        + (ROOT / "frontend" / "js" / "prefs.js").read_text(encoding="utf-8")
        + """
global.document = { getElementById: () => null, querySelectorAll: () => [] };
global.toast = (m) => said.push(m);
global.toastAction = (m, label) => said.push(`${m} [${label}]`);
global.nameMarkBuddyLeave = (b, then) => then();
global.nameMarkBuddyGone = () => {};
global.dropAnimations = () => {};
"""
        + shortcuts
        + "\n"
        + _fn("nameMarkBuddyHide")
        + """
nameMarkBuddyHide(null);
console.log(JSON.stringify({ said, store }));
"""
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_hide_toast_names_the_chord_as_it_is_bound() -> None:
    got = _hide_toast('var shortcuts = { toggleCompanion: { keys: "Alt+Shift+C" } };')
    assert got["store"]["avatar-buddy"] == "off" and got["store"]["nm-buddy-last"] == "atlas"
    assert len(got["said"]) == 1
    assert "Alt+Shift+C" in got["said"][0] and "Ctrl+Shift+Y" not in got["said"][0]
    # No registry loaded (a page without settings-wiring.js): no chord named.
    bare = _hide_toast("")
    #: INBOX 743: the way back is the toast's button, not a Settings path in
    #: prose ("the show companion notification button was poorly shown").
    assert "Ctrl+" not in bare["said"][0] and bare["said"][0].endswith("[Show it]")


def test_the_toggle_mounts_the_companion_without_the_settings_listener() -> None:
    # The Appearance select's change listener is wired only when Settings
    # opens (settings-controls.js); the select can exist before that, so a
    # dispatched change mounted nothing (E2E shell.spec.js, Ctrl+Shift+Y).
    toggle = _fn("nameMarkBuddyToggle")
    assert "dispatchEvent" not in toggle
    assert "syncNameMarkBuddy();" in toggle and "mountBuddyCustom();" in toggle
