"""Brief 86 (c): every Settings change and clear can be taken back.

The eager half (status.js: `settingsPrefsSeen`, `noteLookChange`,
`noteSettingChange`, `claimSettingUndo`) and the list's half (settings-data.js:
`settingsHistoryAdd`, `settingsHistoryApply`) are run under node with stubs for
the DOM and the API; `scratchpad/ui-sweeps/settingsclear86.js` drives a real
page (a switch, a look setting, each clear, at 1440 and 390).
"""

from __future__ import annotations

from tests._help_text import help_chat_text

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
STATUS = (JS / "status.js").read_text(encoding="utf-8")
DATA = (JS / "settings-data.js").read_text(encoding="utf-8")
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _slice(source: str, start: str, end: str) -> str:
    return source[source.index(start) : source.index(end)]


EAGER = _slice(STATUS, "let settingsPrefsLast = null;", "function jobsRunning() {")
#: The noting half (settings-data.js): the diff, the words, the coalescing, the toast.
NOTING = _slice(DATA, "const SETTINGS_HISTORY_SKIP", "//: Every box's remembered searches")
LISTED = DATA[DATA.index('// --- Settings, Data: "Recent changes"') :]


def _node(script: str) -> str:
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


HARNESS = f"""
const store = new Map();
globalThis.window = {{ localStorage: {{
  get length() {{ return store.size; }}, key: (i) => [...store.keys()][i] ?? null,
  getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k),
}} }};
globalThis.navigator = {{ platform: "Linux" }};
const fs = require("fs");
eval(fs.readFileSync({str(JS / "prefs.js")!r}, "utf8") + "; globalThis.prefs = prefs;");
let open = true;
const toasts = [];
const timers = [];
const removed = [];
globalThis.settingsOpen = () => open;
globalThis.toastAction = (message, label, run, opts) => toasts.push({{ message, label, opts }});
globalThis.toastHost = () => ({{ querySelectorAll: () => [{{ getAnimations: () => [{{ currentTime: 100 }}], remove: () => removed.push(1) }}] }});
globalThis.settingsHistoryUndo = () => {{}};
globalThis.settingsHistoryApply = () => {{}};
globalThis.undoStack = [];
globalThis.pushUndo = (label, undo, redo) => {{ const action = {{ label, undo, redo }}; undoStack.push(action); return action; }};
globalThis.setTimeout = (fn, ms) => {{ timers.push({{ fn, ms }}); return timers.length; }};
globalThis.clearTimeout = (id) => {{ if (timers[id - 1]) timers[id - 1].dead = true; }};
globalThis.LOOK_KEYS = ["density", "radius"];
//: settings.js owns this object (a mix or an import quiets the per-key notes); a look change reads it.
globalThis.settingsLook = {{ quiet: 0, quietWords: "", themePreview: "", logFilterFromRun: false }};
//: The eager half (status.js): `apiJson` wrapped, handing each PUT's before and after to the lazy diff.
const answers = [];
globalThis.apiJson = async (path, options) => answers.shift();
globalThis.ensureModule = () => Promise.resolve(true);
const added = [];
globalThis.settingsHistoryAdd = (change) => added.push(change);
eval({json.dumps(NOTING)} + "; globalThis.settingsPrefsSeen = settingsPrefsSeen; globalThis.noteSettingChange = noteSettingChange;");
eval({json.dumps(EAGER)} + "; globalThis.settingsOpenSwitch = null;");
const flush = () => {{ for (const t of timers.splice(0)) if (!t.dead) t.fn(); }};
//: One /preferences answer, as the app's apiJson returns it, through the wrapper.
const answer = async (method, data) => {{ answers.push(data); return apiJson("/preferences", {{ method }}); }};
"""


def _run(body: str) -> str:
    """The harness, then `body` as an async function: the notes reach the
    list through a promise (`ensureModule(...).then`), so a test awaits a tick."""
    return _node(
        HARNESS
        + "const tick = async () => { for (let i = 0; i < 4; i++) await Promise.resolve(); };\n"
        + "(async () => {\n" + body + "\n})().catch((e) => { console.error(e); process.exit(1); });"
    )


def test_a_put_is_diffed_against_the_last_answer_so_a_form_that_saves_twelve_fields_records_one() -> None:
    out = _run(
        """
await answer("GET", { recycle_bin_days: 30, auto_tag_enabled: true, llm_api_key: "k1", ui_state: { a: "1" }, display_name: "A" });
await answer("PUT", { recycle_bin_days: 14, auto_tag_enabled: true, llm_api_key: "k2", ui_state: { a: "2" }, display_name: "A" });
await answer("PUT", { recycle_bin_days: 14, auto_tag_enabled: false, llm_api_key: "k2", ui_state: { a: "2" }, display_name: "A" });
await tick();
console.log(JSON.stringify({ n: added.length, first: added[0].changes, second: added[1].changes, words: added.map((c) => c.label) }));
"""
    )
    got = json.loads(out)
    assert got["n"] == 2, "the secret and the mirrored copy are not changes the person made"
    assert got["first"] == [{"key": "recycle_bin_days", "old": 30, "new": 14}]
    assert got["second"] == [{"key": "auto_tag_enabled", "old": True, "new": False}]
    assert got["words"] == ["Recycle bin days: 30 to 14", "Auto tag enabled: on to off"]


def test_a_look_key_in_the_mirrored_copy_is_a_change_of_its_own() -> None:
    """A look setting is localStorage; it reaches the notebook as `ui_state`,
    and that copy's look keys are diffed one by one (a counter or a tab is not)."""
    out = _run(
        """
await answer("GET", { ui_state: { density: "comfortable", activeTab: "notes" } });
await answer("PUT", { ui_state: { density: "compact", activeTab: "chat", radius: "9" } });
await tick();
console.log(JSON.stringify({ n: added.length, kind: added[0].kind, changes: added[0].changes, words: added[0].label }));
"""
    )
    got = json.loads(out)
    assert got["n"] == 1 and got["kind"] == "look", "activeTab is not a look setting"
    assert got["changes"] == [
        {"key": "density", "old": "comfortable", "new": "compact"},
        {"key": "radius", "old": None, "new": "9"},
    ]
    assert got["words"] == "Density: comfortable to compact and 1 more"


def test_nothing_is_noted_when_settings_is_closed_or_on_the_first_answer() -> None:
    out = _run(
        """
await answer("PUT", { a: 1 });   // no earlier answer: nothing to diff against
open = false;
await answer("PUT", { a: 2 });   // Settings closed
open = true;
await answer("GET", { a: 3 });   // a read is not a change
await tick();
console.log(added.length);
"""
    )
    assert out == "0"


def test_a_slider_is_one_change_whose_way_back_is_its_first_value() -> None:
    out = _run(
        """
noteSettingChange({ kind: "look", changes: [{ key: "radius", old: "8", new: "9" }] });
noteSettingChange({ kind: "look", changes: [{ key: "radius", old: "9", new: "10" }] });
noteSettingChange({ kind: "look", changes: [{ key: "radius", old: "10", new: "12" }] });
flush();
console.log(JSON.stringify({ last: added[added.length - 1].changes, toasts: toasts.length, label: toasts[0] && toasts[0].message }));
"""
    )
    got = json.loads(out)
    assert got["last"] == [{"key": "radius", "old": "8", "new": "12"}], "undo goes back to where the drag began"
    assert got["toasts"] == 1, "one offer for the whole drag, not one per tick"
    assert got["label"] == "Radius: 8 to 12"


def test_one_notice_with_the_undo_replaces_the_controls_own_toast_and_stays_ten_seconds() -> None:
    out = _run(
        """
noteSettingChange({ kind: "prefs", changes: [{ key: "a_b", old: 1, new: 2 }] });
noteSettingChange({ kind: "recents", changes: [], words: "Cleared recent searches", data: {} }, { quiet: true });
flush();
console.log(JSON.stringify({ removed: removed.length, toasts: toasts.map((t) => [t.message, t.label, t.opts.ms]) }));
"""
    )
    got = json.loads(out)
    assert got["removed"] == 1, "the control's own toast (its enter animation still running) makes way"
    assert got["toasts"] == [["A b: 1 to 2", "Undo", 10000]], "a quiet change (its caller raised an Undo) raises none"


def test_the_list_keeps_twenty_newest_first_and_every_row_can_undo() -> None:
    out = _run(
        f"""
globalThis.settingsModalOpen = () => false;
globalThis.$ = () => null;
eval({json.dumps(LISTED)} + "; globalThis.settingsHistoryAdd = settingsHistoryAdd; globalThis.settingsHistoryLoad = settingsHistoryLoad; globalThis.settingsHistoryBigKept = settingsHistoryBigKept;");
for (let i = 0; i < 25; i++) settingsHistoryAdd({{ kind: "prefs", at: 100000 + i * 10000, sig: "prefs:k" + i, label: "L" + i, changes: [{{ key: "k" + i, old: i, new: i + 1 }}] }});
settingsHistoryAdd({{ kind: "prefs", at: 900000, sig: "prefs:x", label: "unknown", changes: [{{ key: "x", old: undefined, new: 1 }}] }});
settingsHistoryAdd({{ kind: "prefs", at: 910000, sig: "prefs:y", label: "huge", changes: [{{ key: "y", old: "a".repeat(20000), new: "b" }}] }});
const list = settingsHistoryLoad();
console.log(JSON.stringify({{ n: list.length, newest: list[0].label, second: list[1].label, noUndo: list.slice(0, 2).map((e) => Boolean(e.noUndo)), unset: list[1].changes[0].unset === true, big: list[0].big === true, held: settingsHistoryBigKept.has(list[0].id), kept: list[2].label }}));
"""
    )
    got = json.loads(out)
    assert got["n"] == 20
    assert got["newest"] == "huge" and got["second"] == "unknown"
    assert got["noUndo"] == [False, False], "no row is listed without an Undo"
    assert got["unset"], "a setting never set is undone by unsetting it"
    assert got["big"] and got["held"], "a value too big for the browser's store is held in memory"
    assert got["kept"] == "L24"


def test_the_surfaces_are_there_and_help_names_them() -> None:
    assert 'id="recent-changes-list"' in INDEX and 'data-help-for="recent-changes-help"' in INDEX
    assert re.search(r"apiJson = async \(path, options = \{\}\) => \{[\s\S]{0,400}settingsPrefsSeen", STATUS)
    guide = help_chat_text()
    assert "Recent changes" in guide, "the Guide names the list"


def test_a_recent_change_row_is_text_beside_a_quiet_action_that_never_wraps() -> None:
    """INBOX 848: the Undo sat in a bordered tonal box and "Do again" wrapped
    beside two or three lines of text. The row's one action is the row-actions
    recipe (a quiet text button), kept on one line, and the words column takes
    the room and wraps on its own."""
    row = DATA[DATA.index("function settingsHistoryRow") : DATA.index("function renderSettingsHistory")]
    assert "rowActions(" in row, "the action is the row-actions recipe, not a hand-built ghost button"
    assert 'className = "ghost small"' not in row
    css = (ROOT / "frontend" / "css" / "01-forms-settings.css").read_text(encoding="utf-8")
    words = css[css.index(".recent-change-words {") :].split("}")[0]
    assert "flex: 1 1 0" in words and "min-width: 0" in words
    action = css[css.index(".entry-list .recent-change .row-actions {") :].split("}")[0]
    assert "flex: none" in action and "white-space: nowrap" in action
    assert "opacity: 1" in action, "the entry list hides row actions until hover; this one is there at rest"


def test_a_switch_is_a_step_on_the_stack_a_drag_is_one_and_a_quiet_change_adds_none_l694() -> None:
    out = _run(
        """
noteSettingChange({ kind: "prefs", changes: [{ key: "a_b", old: 1, new: 2 }] });
const afterSwitch = undoStack.map((a) => a.label);
noteSettingChange({ kind: "look", changes: [{ key: "radius", old: "8", new: "9" }] });
noteSettingChange({ kind: "look", changes: [{ key: "radius", old: "9", new: "12" }] });
const afterDrag = undoStack.map((a) => a.label);
noteSettingChange({ kind: "recents", changes: [], words: "Cleared", data: {} }, { quiet: true });
console.log(JSON.stringify({ afterSwitch, afterDrag, quiet: undoStack.length, change: undoStack[0].settingChange.changes[0].key }));
"""
    )
    got = json.loads(out)
    assert got["afterSwitch"] == ["A b: 1 to 2"]
    assert got["afterDrag"] == ["A b: 1 to 2", "Radius: 8 to 12"], "the drag leaves one step, back to where it began"
    assert got["quiet"] == 2, "a caller that raised its own Undo adds none here"
    assert got["change"] == "a_b"
