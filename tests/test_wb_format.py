"""The board's Format panel (WHITEBOARD_PLAN decision 19; the features audit 9.2 item 3).

The context bar keeps its seven controls per kind; the long tail (numbers for
place and size, angle, flip, opacity, shadow, a shape's text, a connector's
line shape, ends and label place) goes to one docked panel with three tabs,
hidden until asked for. What the source promises, tested here; the browser
half is `scratchpad/ui-sweeps/wb1005-format.js`.
"""

from tests._app_js import frontend_text
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
FORMAT = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")
BOARD = frontend_text("whiteboard.js")
COMMANDS = (ROOT / "frontend" / "js" / "whiteboard-commands.js").read_text(encoding="utf-8")
APP = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")


def _panel() -> str:
    start = INDEX.index('<aside id="wb-format"')
    return INDEX[start : INDEX.index("</aside>", start)]


def test_four_tabs_on_a_tabs_line_and_one_tabpanel() -> None:
    #: Data, the fourth, is Edit data (canvasdepth2, `tests/test_wb_edit_data.py`).
    panel = _panel()
    strip = re.search(r'<div class="tabs-line wb-format-tabs" id="wb-format-tabs" role="tablist"[^>]*>(.*?)</div>', panel, re.S)
    assert strip, "the tabs are a .tabs-line (DESIGN.md: a second-level strip)"
    assert re.findall(r'data-format-tab="(\w+)"', strip.group(1)) == ["style", "text", "arrange", "data"]
    assert "<i " not in strip.group(1), "second-level tabs are words only"
    assert 'role="tabpanel"' in panel
    assert re.findall(r'data-format-panel="(\w+)"', panel) == ["style", "text", "arrange", "data"]


def test_every_control_is_named() -> None:
    panel = _panel()
    for tag in re.findall(r"<(?:input|select|button)\b[^>]*>", panel):
        assert "aria-label=" in tag or 'role="tab"' in tag, tag


def test_every_row_names_a_field_the_kinds_know() -> None:
    fields = set(re.findall(r'data-fmt="([\w-]+)"', _panel()))
    table = FORMAT[FORMAT.index("const WB_FMT_FIELDS") : FORMAT.index("};", FORMAT.index("const WB_FMT_FIELDS"))]
    known = set(re.findall(r'"([\w-]+)"', table))
    assert fields <= known, fields - known
    #: Every field a kind takes has a row to show.
    assert known - {"shape", "line", "link", "text", "image", "frame", "note"} <= fields


def test_one_change_is_one_undo_step() -> None:
    apply = FORMAT[FORMAT.index("async function wbFmtApply") :]
    apply = apply[: apply.index("\n}\n")]
    assert "wbRecordGesture(" in apply
    for name in ("wbFmtGeometry", "wbFmtFlip"):
        body = FORMAT[FORMAT.index(f"async function {name}") :]
        assert "wbRecordGesture(" in body[: body.index("\n}\n")], name


def test_ctrl_shift_p_is_the_boards_on_a_board() -> None:
    owns = BOARD[BOARD.index("function wbOwnsChord") :]
    owns = owns[: owns.index("\n}\n")]
    assert '["g", "p"]' in owns
    assert 'wbRunCommand("format-panel")' in BOARD
    assert re.search(r'id: "format-panel"[^}]*keys: "Ctrl\+Shift\+P"', COMMANDS)


def test_the_panel_opens_from_the_bar_and_the_view_menu() -> None:
    more = INDEX[INDEX.index('id="wb-context-menu"') :]
    assert 'data-wb-cmd="format-panel"' in more[: more.index("</div>")]
    view = INDEX[INDEX.index('id="wb-view-menu"') :]
    assert 'data-wb-cmd="format-panel"' in view[: 3000]


def test_the_arrange_buttons_come_from_the_command_table() -> None:
    buttons = FORMAT[FORMAT.index("function wbFormatCommandButtons") :]
    buttons = buttons[: buttons.index("\n}\n")]
    assert "WB_COMMAND_BY_ID.get(id)" in buttons
    for command in ("order-front", "order-forward", "order-backward", "order-back", "group", "lock", "distribute-h"):
        assert f'"{command}"' in buttons


def test_the_bundle_loads_the_panel_after_the_table() -> None:
    #: The `boards` bundle (lazy-entries.js) since D22, 2026-11-11; the whiteboard files were `library`'s in app.js.
    entries = (ROOT / "frontend" / "js" / "lazy-entries.js").read_text(encoding="utf-8")
    library = entries[entries.index("  boards: [") : entries.index("],", entries.index("  boards: ["))]
    assert library.index("/js/whiteboard-commands.js") < library.index("/js/whiteboard-format.js")


def test_opacity_and_shadow_are_kept_by_the_server(ai_client):
    board = ai_client.post("/whiteboard/boards", json={"name": "Format", "type": "board"}).json()
    made = ai_client.post("/whiteboard/objects", json={
        "kind": "text", "data": {"content": "Hi", "alpha": 0.5, "shadow": True, "bold": True},
        "board_id": board["id"], "x": 0, "y": 0, "width": 100, "height": 40,
    })
    assert made.status_code in (200, 201), made.text
    data = made.json()["data"]
    assert data["alpha"] == 0.5 and data["shadow"] is True and data["bold"] is True
    bad = ai_client.post("/whiteboard/objects", json={
        "kind": "text", "data": {"content": "Hi", "alpha": 0}, "board_id": board["id"], "x": 0, "y": 0, "width": 100, "height": 40,
    })
    assert bad.status_code == 422


def test_a_shapes_text_takes_size_weight_and_alignment() -> None:
    paint = BOARD[BOARD.index("function wbPaintShapeLabel") :]
    paint = paint[: paint.index("\n}\n")]
    for field in ("label_size", "label_bold", "label_italic", "label_align", "label_color"):
        assert f"parsed.{field}" in paint, field


def test_a_multi_selection_shows_what_it_shares_and_says_mixed() -> None:
    """The owner, 2026-10-11: "if I highlight and select multiple objects, cna
    I cnahge the properties they share which are available in the properties
    side panel??" The rows are the fields every selected kind takes (not the
    union, which showed a fill for a shape and a line together), and a value
    the items differ on reads Mixed instead of the first item's value. The
    browser half (one edit, one Undo, across the selection) is
    `scratchpad/ui-sweeps/wbcolour-mixed.js`."""
    sync = FORMAT[FORMAT.index("function wbFormatSync(") :]
    sync = sync[: sync.index("\n}\n")]
    assert "fieldSets.every((s) => s.has(f))" in sync
    assert "for (const k of kinds) for (const f of WB_FMT_FIELDS[k]" not in sync
    shown = FORMAT[FORMAT.index("function wbFmtShowMixed(") :]
    shown = shown[: shown.index("\n}\n")]
    for part in ('"wb-mixed"', 'option.hidden = true', '"Mixed"', 'el.placeholder'):
        assert part in shown, part
    assert "indeterminate = mixed(" in sync
    assert '"mixed"' in sync and '? "Mixed"' in sync
    # Every edit still goes through the one-gesture writer. The window grew from 400 when INBOX 1685 put a
    # comment and the one-at-a-time wrapper ahead of it; the call is unchanged.
    assert "await wbRecordGesture(async () => {" in FORMAT[FORMAT.index("async function wbFmtApply(") :][:700]


# Small whiteboard rows: reset style (INBOX 747) and a panel frame's hint line (INBOX 740).
WB = BOARD


def _css(name: str) -> str:
    return (ROOT / "frontend" / "css" / name).read_text(encoding="utf-8")


def _fn(name: str) -> str:
    start = WB.index(f"function {name}(")
    return WB[start : WB.index("\n}\n", start) + 3]


def test_reset_style_takes_the_look_off_and_keeps_what_it_says():
    """INBOX 747 (OPEN row 887), the owner: "there's no way to reset a object
    back to default style". Run in node: a text box loses every look field and
    keeps its words; a sticky goes back to the first paper; a map topic is
    left to its map; a link loses its colour and width but keeps its ends."""
    import json
    import shutil
    import subprocess

    import pytest

    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    start = WB.index("const WB_SKETCH_RESET_KEYS")
    consts = WB[start : WB.index("function wbSketchStyleReset(", start)]
    script = (
        "const WB_MAP_KINDS = new Set(['topic']); const WB_STICKY_PAPERS = [{ value: '#fff3a0' }];"
        "function wbIsSticky(o) { return Boolean(o.data.sticky); } function wbSketchTakesCaps() { return false; }"
        + consts + _fn("wbSketchStyleReset") + _fn("wbObjectStyleReset")
        + "const text = wbObjectStyleReset({ kind: 'text', data: { content: 'Hi', color: '#f00', bg: '#000', font_size: 30, bold: true, alpha: 0.5, x: 1 } });"
        + "const sticky = wbObjectStyleReset({ kind: 'text', data: { content: 'S', sticky: true, bg: '#f9c', color: '#123', font_size: 40, fold: false } });"
        + "const topic = wbObjectStyleReset({ kind: 'topic', data: { color: '#f00' } });"
        + "const link = JSON.parse(JSON.stringify(Object.assign({ type: 'link-straight', sourceId: 1, targetId: 2, endCap: 'arrow', color: '#f00', width: 8, dash: 'dashed', route: 'elbow' }, wbSketchStyleReset({ type: 'link-straight' }))));"
        + "const marker = wbSketchStyleReset({ d: 'M 0 0 L 9 9', shape: 'highlighter' });"
        + "console.log(JSON.stringify({ text, sticky, topic, link, marker }));"
    )
    out = json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout)
    assert out["text"] == {"content": "Hi", "x": 1}
    assert out["sticky"] == {"content": "S", "sticky": True, "bg": "#fff3a0", "color": "#2a2a1f", "font_size": 16}
    assert out["topic"] is None and out["marker"] is None
    assert out["link"] == {"type": "link-straight", "sourceId": 1, "targetId": 2, "endCap": "arrow", "route": "elbow"}
    fn = _fn("wbResetSelectedStyle")
    assert "wbRecordGesture" in fn and "WB_MAP_STYLE_KEYS" in fn and "wbIsLocked" in fn
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'data-wb-cmd="reset-style"' in index and 'id="wb-reset-style"' in index
    commands = (ROOT / "frontend" / "js" / "whiteboard-commands.js").read_text(encoding="utf-8")
    #: In the command table (palette and menu); not on the keys sheet, which
    #: lists what has a key, and Reset style has none (cfc684238).
    assert 'id: "reset-style"' in commands and 'keys: "", surface: "both", needs: "selection", run: () => wbResetSelectedStyle()' in commands
    from tessellate.ai import help_chat

    assert any("Reset style" in t["body"] for t in help_chat.HELP_TOPICS)


def test_a_panel_frame_s_hint_line_edits_in_place():
    """INBOX 740 (OPEN row 802), the owner: "I cant edit the text under the
    titles in these objects?" The hint takes a double-click as the title does,
    and an emptied hint is taken away rather than refused."""
    build = _fn("wbBuildFrame")
    assert 'wbEditFrameTitle(this, d, "hint")' in build and 'aria-hidden' not in build
    edit = _fn("wbEditFrameTitle")
    assert 'const isHint = field === "hint";' in edit and "(!name && !isHint)" in edit and "delete frame.data.hint" in edit
    rule = re.search(r"\.wb-frame-panel \.wb-frame-hint:not\(\[hidden\]\)\s*\{([^}]*)\}", _css("library-lazy.css")).group(1)
    assert "pointer-events: none" not in rule
