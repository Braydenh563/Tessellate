"""Sizes belong to the device (INBOX 897).

The owner: "the size of things should be proportional and individual to the
device, so if I change the size of say the companion and the zoom on my
computer, it shouldnt affect my phone." Colours, themes, fonts and motion
follow the person (WORLD_CLASS_PLAN 25f); a size or a place on the screen is a
property of the screen it was chosen on. `DEVICE_ONLY_KEYS` (ai-tools.js) is
the list; the mirror to the notebook's `ui_state` never writes it and never
applies it, and a saved look (colours) does not carry it. The mirror's own
functions are run under node; `scratchpad/ui-sweeps/devsize.js` drives two real
browsers (1440 and 390) on one server.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._app_js import index_html_text

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
AI_TOOLS = (JS / "ai-tools.js").read_text(encoding="utf-8")
INDEX = index_html_text()
SETTINGS = (JS / "settings.js").read_text(encoding="utf-8")
ROWS = (JS / "settings-rows.js").read_text(encoding="utf-8")

#: Sizes, scales and screen positions. Every one is meaningless on another screen.
REQUIRED = {
    "zoom", "fontsize", "density", "avatar-buddy-size", "nm-buddy-spots",
    "chat-composer-height", "wb-panel-pos-board", "wb-panel-pos-library",
    "wb-panel-pos-tools", "wb-panel-pos-zoom",
}
#: What still follows the person.
FOLLOWS = {"theme", "palette", "accent", "font", "radius", "motion", "glass", "avatar-buddy", "themePreset", "bgArt"}


def _device_only() -> list[str]:
    body = re.search(r"const DEVICE_ONLY_KEYS = \[(.*?)\];", AI_TOOLS, re.S)
    assert body, "DEVICE_ONLY_KEYS not found in ai-tools.js"
    text = "\n".join(row for row in body.group(1).splitlines() if not row.strip().startswith("//"))
    return re.findall(r'"([^"]+)"', text)


def _node(script: str) -> str:
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


MIRROR = AI_TOOLS[AI_TOOLS.index("const DEVICE_ONLY_KEYS") : AI_TOOLS.index("function applyPalette")]

HARNESS = f"""
const store = new Map();
globalThis.document = {{ addEventListener() {{}}, hidden: false }};
globalThis.window = {{ addEventListener() {{}}, localStorage: {{
  get length() {{ return store.size; }}, key: (i) => [...store.keys()][i] ?? null,
  getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k),
}} }};
globalThis.localStorage = window.localStorage;
const fs = require("fs");
eval(fs.readFileSync({str(JS / "prefs.js")!r}, "utf8") + "; globalThis.prefs = prefs;");
const puts = [];
const timers = [];
globalThis.setTimeout = (fn) => {{ timers.push(fn); return timers.length; }};
globalThis.clearTimeout = () => {{}};
globalThis.authToken = () => "t";
globalThis.apiJson = async (path, options) => {{ puts.push(JSON.parse(options.body).ui_state); return {{}}; }};
eval({json.dumps(MIRROR)} + "; Object.assign(globalThis, {{ mirroredUiKeys, uiStatePayload, seedUiStateFromServer, saveUiState, LOOK_KEYS, DEVICE_ONLY_KEYS, setSeeded: () => {{ uiStateSeeded = true; }} }});");
"""


def _run(body: str) -> dict:
    return json.loads(_node(HARNESS + "\n" + body))


def test_the_device_only_list_names_every_size_and_place():
    assert REQUIRED <= set(_device_only())
    assert not FOLLOWS & set(_device_only()), "a colour, font or motion setting must keep following the person"


def test_the_mirror_never_lists_a_device_key():
    out = _run("console.log(JSON.stringify(mirroredUiKeys()))")
    assert not set(out) & set(_device_only())
    assert FOLLOWS - {"bgArt"} <= set(out) | {"themePreset"}, "the look keys still follow the person"
    assert {"theme", "accent", "themePreset", "bgArt", "font", "radius"} <= set(out)


def test_a_size_set_here_is_never_written_to_the_notebook():
    out = _run(
        """
setSeeded();
for (const k of DEVICE_ONLY_KEYS) localStorage.setItem(k, "9");
localStorage.setItem("accent", "teal");
console.log(JSON.stringify(uiStatePayload()));
"""
    )
    assert out["accent"] == "teal"
    assert not set(out) & set(_device_only())


def test_a_notebook_that_still_holds_old_sizes_does_not_apply_them():
    """Versions before this one mirrored zoom, text size and density; a notebook
    written then must not set them on a phone that opens it now."""
    out = _run(
        """
const legacy = { accent: "teal", zoom: "130", fontsize: "large", density: "spacious", "avatar-buddy-size": "1.6", "nm-buddy-spots": "{}", "chat-composer-height": "400" };
seedUiStateFromServer(legacy);
console.log(JSON.stringify({ accent: localStorage.getItem("accent"), zoom: localStorage.getItem("zoom"), fontsize: localStorage.getItem("fontsize"), density: localStorage.getItem("density"), buddy: localStorage.getItem("avatar-buddy-size"), spots: localStorage.getItem("nm-buddy-spots"), composer: localStorage.getItem("chat-composer-height") }));
"""
    )
    assert out == {"accent": "teal", "zoom": None, "fontsize": None, "density": None, "buddy": None, "spots": None, "composer": None}


def test_a_size_changed_here_leaves_the_next_save_without_it():
    """The save replaces the whole map, so a notebook holding old sizes is
    cleaned by the first save a current build makes."""
    out = _run(
        """
seedUiStateFromServer({ accent: "teal", zoom: "130" });
localStorage.setItem("zoom", "80");
localStorage.setItem("accent", "rose");
setSeeded();
saveUiState();
for (const fn of timers.splice(0)) fn();
await 0;
console.log(JSON.stringify(puts));
""".replace("await 0;", "")
    )
    assert out and out[-1]["accent"] == "rose"
    assert all(not set(put) & set(_device_only()) for put in out)


def test_old_sizes_in_the_notebook_are_cleared_by_the_next_save():
    out = _run(
        """
seedUiStateFromServer({ accent: "teal", zoom: "130", fontsize: "large" });
setSeeded();
for (const fn of timers.splice(0)) fn();
console.log(JSON.stringify(puts));
"""
    )
    assert len(out) == 1 and out[0]["accent"] == "teal" and not set(out[0]) & set(_device_only())


def test_a_saved_look_is_colours_not_sizes():
    """Decision: zoom, text size and density are not part of a saved look (a
    look is how things are coloured, not how big they are on this screen), and
    applying an older look that carries them leaves this device's sizes alone."""
    out = _run("console.log(JSON.stringify(LOOK_KEYS))")
    assert not set(out) & set(_device_only())
    assert {"theme", "accent", "bgArt", "radius"} <= set(out)
    apply = SETTINGS[SETTINGS.index("function applySavedTheme") : SETTINGS.index("function applySavedTheme") + 900]
    assert "DEVICE_ONLY_KEYS.includes(key)" in apply


def test_the_settings_file_does_not_carry_sizes_to_another_screen():
    assert "DEVICE_ONLY_KEYS" in ROWS[ROWS.index("function browserOnlySettings") : ROWS.index("async function settingsFileSnapshot")]
    assert "DEVICE_ONLY_KEYS" in ROWS[ROWS.index("function applyLookSettings") :][:900]


@pytest.mark.parametrize("label", ["Zoom", "Text size", "Density", "Companion size"])
def test_the_size_controls_say_they_are_on_this_device(label):
    chip = f'<span>{label} <span class="chip setting-scope"'
    assert chip in INDEX
    at = INDEX.index(chip)
    assert "On this device" in INDEX[at : at + 300]


def test_the_scope_chip_says_the_same_wherever_it_is_made():
    assert 'chip("On this device", "setting-scope")' in ROWS
    assert "This browser" not in ROWS.replace("// ", "").replace("//:", "").split("function settingScopeChip")[1][:400]


@pytest.mark.parametrize("topic", ["companion", "themes", "settings-reset"])
def test_help_says_sizes_stay_on_the_device(topic):
    from tessellate.ai.help_topics_more import MORE_TOPICS

    body = next(t["body"] for t in MORE_TOPICS if t["id"] == topic)
    assert "On this device" in body
    if topic != "companion":
        assert "zoom" in body.lower()
