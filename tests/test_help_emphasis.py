"""Help text carries emphasis: hotkeys, places and control names (INBOX 520).

The owner: "key characters or hotkeys or item/location names should be in like
inline codeblocks or bolded/italicised in the help text". The topics are the
model's only source of facts, so they stay plain text and the page decorates
its own copy at draw time (`helpEmphasis` in settings-find.js): a hotkey is a
`kbd`, a place a `strong`, a control name a `code` chip. The tokenizer is pure,
so it runs here in node; `scratchpad/ui-sweeps/helpsearch.js` measures the DOM.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from tests._js_scope import unwrapped_copy

ROOT = Path(__file__).resolve().parents[1]
JS_PATH = unwrapped_copy(ROOT / "frontend" / "js" / "settings-find.js")
JS = JS_PATH.read_text(encoding="utf-8")

HARNESS = """
const vm = require("vm"), fs = require("fs");
const ctx = vm.createContext({ document: { addEventListener() {} }, window: {} });
vm.runInContext(fs.readFileSync(process.argv[1], "utf8"), ctx);
console.log(JSON.stringify(vm.runInContext(process.argv[2], ctx)));
"""

PLACES = '["Appearance", "Search and index", "Import & export", "What it learned", "Models"]'
TABS = '["Notes", "Library", "Chat"]'


def _emph(text: str):
    expr = f"helpEmphasis({json.dumps(text)}, {PLACES}, {TABS})"
    out = subprocess.run(["node", "-e", HARNESS, str(JS_PATH), expr], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_hotkeys_become_kbd_and_plain_words_stay_plain() -> None:
    assert _emph("Press Ctrl+Shift+A, then Esc.") == [
        ["", "Press "],
        ["kbd", "Ctrl+Shift+A"],
        ["", ", then "],
        ["kbd", "Esc"],
        ["", "."],
    ]
    assert _emph("Ctrl/Cmd+Shift+A and Ctrl+, and Ctrl+Alt+[")[0] == ["kbd", "Ctrl/Cmd+Shift+A"]
    parts = {text: kind for kind, text in _emph("Press Ctrl+Z, Ctrl+, or Alt+Enter; F2 renames; Tab walks.")}
    for key in ("Ctrl+Z", "Ctrl+,", "Alt+Enter", "F2", "Tab"):
        assert parts[key] == "kbd", key
    #: A modifier on its own, or the word inside another word, is not a key.
    assert _emph("Control the Tabs and Entering") == [["", "Control the Tabs and Entering"]]


def test_the_m_chord_is_two_keys() -> None:
    assert _emph("Press m then r to jump.") == [
        ["", "Press "],
        ["kbd", "m"],
        ["", " then "],
        ["kbd", "r"],
        ["", " to jump."],
    ]


def test_press_m_then_a_letter_marks_only_the_m() -> None:
    assert _emph("Press m then a letter to jump.") == [
        ["", "Press "],
        ["kbd", "m"],
        ["", " then a letter to jump."],
    ]


def test_locations_are_strong_and_control_names_are_code() -> None:
    parts = _emph('Open Settings, Import & export and press Clear app cache: the "Capture a thought" box.')
    assert ["strong", "Settings, Import & export"] in parts
    assert ["code", "Clear app cache"] in parts
    assert ["code", "Capture a thought"] in parts, "the quotes drop and the chip stays"
    assert ["strong", "Settings -> Models"] in _emph("Use Settings -> Models for that.")
    assert ["strong", "Library tab, Images and Files"] in _emph("See the Library tab, Images and Files.")
    #: A bare tab name in prose, or an unknown settings name, is not a place.
    assert _emph("The Library is everything.") == [["", "The Library is everything."]]
    assert _emph("Settings, Unknown thing") == [["", "Settings, Unknown thing"]]


def test_emphasis_is_added_at_draw_time_never_stored_in_the_text_the_model_reads() -> None:
    from tessellate.ai.help_chat import HELP_TOPICS

    for topic in HELP_TOPICS:
        body = topic["body"]
        assert "**" not in body and "`" not in body, topic["id"]
        assert "<kbd>" not in body and "<strong>" not in body and "<code>" not in body, topic["id"]
    code = re.sub(r"//.*", "", JS)
    assert "innerHTML" not in code and "insertAdjacentHTML" not in code
