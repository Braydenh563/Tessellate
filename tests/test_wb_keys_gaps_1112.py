"""The draw.io keys the board lacked (WHITEBOARD_PLAN section 11, 2026-11-12).

Behaviour is measured by `scratchpad/ui-sweeps/wbkeys2.js`; these hold the wiring: each key sits on its
command (so the palette, the help sheet and the key reader read one chord), no two board commands share a
chord, and every chord an app shortcut also owns is one the board is meant to take while it has the keys.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
COMMANDS = (JS / "whiteboard-commands.js").read_text(encoding="utf-8")
KEYS = (JS / "whiteboard-keys.js").read_text(encoding="utf-8")
BOARD = (JS / "whiteboard.js").read_text(encoding="utf-8")
WIRING = (JS / "settings-wiring.js").read_text(encoding="utf-8")

NEW_KEYS = {
    "edit-data": "Ctrl+M",
    "select-shapes": "Ctrl+Shift+I",
    "turn-90": "Ctrl+R",
    "copy-image": "Ctrl+Alt+X",
    "copy-svg": "Ctrl+Alt+Shift+X",
    "copy-size": "Alt+Shift+F",
    "paste-size": "Alt+Shift+V",
    "copy-data": "Alt+Shift+B",
    "paste-data": "Alt+Shift+E",
    "clear-waypoints": "Alt+Shift+R",
    "enter-group": "Ctrl+Shift+End",
    "font-bigger": "Ctrl+Shift+Plus",
    "font-smaller": "Ctrl+Shift+Minus",
}


def _rows() -> dict[str, dict[str, str]]:
    block = COMMANDS[COMMANDS.index("const WB_COMMANDS = [") :]
    block = block[: block.index("\n];\n")]
    rows = {}
    for line in block.splitlines():
        found = re.search(r'\{ id: "([\w-]+)".*?keys: "([^"]*)", surface: "(\w+)"', line)
        if found:
            rows[found.group(1)] = {"keys": found.group(2), "surface": found.group(3)}
    return rows


def test_every_new_key_sits_on_its_command() -> None:
    rows = _rows()
    for command, keys in NEW_KEYS.items():
        assert rows[command]["keys"] == keys, command


def test_the_key_reader_binds_each_of_them() -> None:
    bound = re.search(r"const BOUND = \[(.*?)\];", KEYS, re.S).group(1)
    for command in NEW_KEYS:
        assert f'"{command}"' in bound, command
    assert 'ungroup: "Ctrl+Shift+U"' in KEYS and '"leave-group": "Ctrl+Shift+Home"' in KEYS
    assert 'addEventListener("keydown", onKey, true)' in KEYS


def test_no_two_board_commands_share_a_chord() -> None:
    seen: dict[tuple[str, str], str] = {}
    for command, row in _rows().items():
        if not row["keys"] or row["surface"] == "map":
            continue
        for surface in ("board",) if row["surface"] == "board" else ("board",):
            clash = seen.get((surface, row["keys"]))
            assert clash is None, f"{command} and {clash} both take {row['keys']}"
            seen[(surface, row["keys"])] = command
    assert ("board", "Ctrl+Shift+U") not in seen and ("board", "Ctrl+Shift+Home") not in seen


def test_no_new_board_key_takes_an_app_shortcut() -> None:
    app = set(re.findall(r'\{ keys: "([^"]+)"', WIRING))
    mine = set(NEW_KEYS.values()) | {"Ctrl+Shift+U", "Ctrl+Shift+Home", "F2"}
    shared = app & mine
    #: Changed 2026-11-12 (orchestrator review): the board first took Ctrl+Shift+A, E, R and Y from Atlas,
    #: selection actions, record and the companion; those stay the app's, so no new board key is an app key.
    assert shared == set(), shared
    # Taken in the capture phase, ahead of the app's document listener, and only while a board has the keys.
    assert "wbBoardHasFocus()" in KEYS and "e.stopImmediatePropagation()" in KEYS


def test_a_key_with_a_browser_meaning_goes_on_unless_the_command_applies() -> None:
    idle = re.search(r"const PASS_WHEN_IDLE = new Set\(\[(.*?)\]\)", KEYS, re.S).group(1)
    for command in ("turn-90", "font-bigger", "font-smaller"):
        assert f'"{command}"' in idle, command


def test_f2_writes_like_enter_and_slash_goes_to_the_library() -> None:
    assert '(e.key === "Enter" || e.key === "F2")' in BOARD
    assert re.search(r'e\.key === "/"[^}]*?wbOpenSidebar\("library"\)', BOARD, re.S)


def test_ctrl_arrow_resizes_by_one_and_a_burst_is_one_undo_step() -> None:
    assert "e.shiftKey ? (wbSnapOn() ? WB_GRID_SPACING : 10) : 1" in BOARD
    body = BOARD[BOARD.index("wbBoardState.resizeOnce = async function") :]
    body = body[: body.index("// Extract notes")]
    assert "wbBoardState.resizeBurst" in body and "WB_NUDGE_BURST_MS" in body
    assert 'kind: "scale"' in body, "Repeat last takes the resize as the nudge is taken"


def test_the_data_clip_is_one_undo_step_through_the_format_apply() -> None:
    fmt = (JS / "whiteboard-format.js").read_text(encoding="utf-8")
    block = fmt[fmt.index("wbFmtState.dataKeys = (() => {") :]
    block = block[: block.index("})();")]
    assert 'wbFmtApply("props"' in block


def test_the_help_sheet_lists_each_new_key() -> None:
    for command in NEW_KEYS:
        assert f'{{ cmd: "{command}"' in COMMANDS, command
    assert '{ cmd: "text", also: ["F2"] }' in COMMANDS
    assert '{ cmd: "ungroup", also: ["Ctrl+Shift+U"] }' in COMMANDS
    assert '{ cmd: "leave-group", also: ["Ctrl+Shift+Home"] }' in COMMANDS


def test_the_app_slash_steps_aside_on_a_board() -> None:
    body = BOARD[BOARD.index("function wbOwnsChord(") :]
    body = body[: body.index("async function wbFlushNudge")]
    assert 'e.key === "/" && !e.ctrlKey && !e.metaKey && !e.altKey && !e.shiftKey) return true' in body


def test_the_apps_own_chords_stay_the_apps() -> None:
    """Ctrl+Shift+A (Atlas from anywhere), E (selection actions), R (record) and Y (the companion) are the
    app's keys in the settings registry; draw.io's select none, select connectors, clear default style and
    autosize keep no key on a board rather than take them (2026-11-12, orchestrator review)."""
    for command in ("select-none", "select-connectors", "clear-default-style", "auto-size"):
        assert _rows()[command]["keys"] == "", command
    bound = re.search(r"const BOUND = \[(.*?)\];", KEYS, re.S).group(1)
    for command in ("select-none", "select-connectors", "clear-default-style", "auto-size"):
        assert f'"{command}"' not in bound, command


def test_enter_on_a_focused_button_is_the_buttons_own() -> None:
    """Review 5883430964: with a shape selected, Enter on a Format panel button (Add point) opened the shape's label
    instead of pressing the button, so the keyboard path never ran (sweep wbports-offsets.js)."""
    assert "&& !(e.key === \"Enter\" && document.activeElement?.closest(\"button, [role='button'], a[href], summary\"))" in BOARD
