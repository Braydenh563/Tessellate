"""Text pasted onto a board becomes items (FEAT-09).

The features audit: a three-line paste onto a board left three items three
(`wb1.js`): the board's Ctrl+V read only its own clipboard and swallowed the
key, so the browser's paste never arrived. `wbPastePlan` is the pure rule: a
link becomes a link box, one line a text box, several lines a grid of
stickies (more than fifty, one text box). The browser half is
`scratchpad/ui-sweeps/wb1005-paste.js`.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
COMMANDS = (ROOT / "frontend" / "js" / "whiteboard-commands.js").read_text(encoding="utf-8")
PROSE = (ROOT / "frontend" / "js" / "documents-prose.js").read_text(encoding="utf-8")
MAP = (ROOT / "frontend" / "js" / "whiteboard-map.js").read_text(encoding="utf-8")


def _between(text: str, start: str, end: str) -> str:
    return text[text.index(start) : text.index(end)]


#: The shared readings and the board's pure half, as one script node can run.
PURE = _between(PROSE, "// PASTE-CORE-START", "// PASTE-CORE-END") + _between(COMMANDS, "// WB-PASTE-PURE-START", "// WB-PASTE-PURE-END")


def _js(expr: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    out = subprocess.run([node, "-e", PURE + f"\nconsole.log(JSON.stringify({expr}));"], capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip())


def _plan(text: str):
    return _js(f"wbPastePlan({json.dumps(text)})")


def test_a_list_becomes_stickies_without_its_marks() -> None:
    assert _plan("- one\n- two\n- three") == {"kind": "stickies", "lines": ["one", "two", "three"]}
    assert _plan("1. alpha\r\n2) beta\n\n") == {"kind": "stickies", "lines": ["alpha", "beta"]}


def test_one_line_is_a_text_box_and_a_url_a_link() -> None:
    assert _plan("  just a thought  ") == {"kind": "text", "text": "just a thought"}
    assert _plan("https://example.com/a") == {"kind": "link", "url": "https://example.com/a"}


def test_nothing_and_a_flood() -> None:
    assert _plan(" \n \n") is None
    many = "\n".join(f"line {i}" for i in range(60))
    assert _plan(many)["kind"] == "text"


def test_the_keys_let_the_browser_paste_through() -> None:
    keys = SOURCE[SOURCE.index('e.key.toLowerCase() === "v") {') :][:600]
    assert "preventDefault" not in keys.split("return;")[0]
    assert 'document.addEventListener("paste"' in SOURCE
    assert "wbPasteText(text" in SOURCE



# --- paste options and Paste special (wbpaste-1026) ---------------------------

LOOK = '{paper: "#fff4a3", root: "#cfe8ff", ink: "#888888"}'


def _build(mode: str, text: str):
    return _js(f"wbPasteBuild({json.dumps(mode)}, {json.dumps(text)}, 500, 400, {LOOK})")


def test_a_spreadsheet_copy_is_a_table_by_default_and_a_csv_is_offered_one():
    plan = _plan("name\tqty\nmilk\t2\neggs\t12")
    assert plan["kind"] == "table" and plan["grid"][2] == ["eggs", "12"]
    assert _plan("a,b\n1,2")["kind"] == "stickies"
    assert _js('wbPasteVariants("a,b\\n1,2")') == ["stickies", "textbox", "bullets", "branch", "table"]


def test_the_chip_offers_the_readings_a_clipboard_has_and_none_for_one_plain_line():
    assert _js('wbPasteVariants("just one thought")') == ["textbox"]
    assert _js('wbPasteVariants("https://example.com/x")') == ["link", "url"]
    assert _js('wbPasteVariants("- a\\n- b\\n- c")')[:4] == ["stickies", "textbox", "bullets", "branch"]
    assert "plain" in _js('wbPasteVariants("- a\\n\\n- b")')
    assert _js('wbPasteVariants("  \\n ")') == []


def test_a_table_is_one_table_object_the_size_of_its_cells():
    items = _build("table", "h1\th2\th3\nx\ty\n1\t2\t3")["items"]
    assert len(items) == 1 and items[0]["payload"]["kind"] == "table"
    data = items[0]["payload"]["data"]
    assert data["cells"] == [["h1", "h2", "h3"], ["x", "y", ""], ["1", "2", "3"]] and data["header"] is True
    assert (items[0]["payload"]["width"], items[0]["payload"]["height"]) == (360, 120)


def test_a_bullet_list_is_one_shape_with_the_lines_in_its_label():
    [item] = _build("bullets", "- one\n- two")["items"]
    data = json.loads(item["payload"]["data"])
    assert item["kind"] == "sketch" and data["shape"] == "rect" and data["label"] == "• one\n• two"
    assert data["d"].startswith("M ") and data["d"].endswith("Z")


def test_a_branch_nests_by_indentation_and_links_each_child_to_its_parent():
    built = _build("branch", "Plan\n  Research\n    Read\n    Ask\n  Build")
    nodes = [i for i in built["items"] if i["kind"] == "object"]
    links = [i for i in built["items"] if i["kind"] == "sketch"]
    assert [n["payload"]["data"]["content"] for n in nodes] == ["Plan", "Research", "Read", "Ask", "Build"]
    assert [(k["src"], k["dst"]) for k in links] == [("n0", "n1"), ("n1", "n2"), ("n1", "n3"), ("n0", "n4")]
    xs = [n["payload"]["x"] for n in nodes]
    assert xs[0] < xs[1] < xs[2] and xs[3] == xs[2] and xs[4] == xs[1]
    assert nodes[1]["payload"]["y"] < nodes[4]["payload"]["y"]


def test_a_flat_list_as_a_branch_takes_the_first_line_as_the_root():
    built = _build("branch", "Root\nA\nB")
    links = [i for i in built["items"] if i["kind"] == "sketch"]
    assert [(k["src"], k["dst"]) for k in links] == [("n0", "n1"), ("n0", "n2")]


def test_stickies_textbox_plain_and_url_readings():
    assert len(_build("stickies", "- a\n- b\n- c")["items"]) == 3
    assert _build("textbox", "- a\n- b")["items"][0]["payload"]["data"]["content"] == "a\nb"
    assert _build("plain", "- a\n\n- b")["items"][0]["payload"]["data"]["content"] == "- a\n\n- b"
    assert _build("url", "https://example.com/x")["items"][0]["payload"]["data"]["content"] == "https://example.com/x"
    link = _build("link", "https://example.com/x/")["items"][0]["payload"]["data"]
    assert link["md"] is True and link["content"] == "[example.com/x](https://example.com/x/)"


def test_a_picture_keeps_its_size_and_is_shrunk_only_to_sit_in_the_view():
    assert _js("wbPasteImageSize(300, 200, 1000, 800)") == {"width": 300, "height": 200}
    assert _js("wbPasteImageSize(2000, 1000, 1000, 800)") == {"width": 900, "height": 450}
    assert _js("wbPasteImageSize(0, 0, 1000, 800)") == {"width": 300, "height": 200}


def test_a_map_paste_reads_as_branches_or_as_one_topic():
    assert _js('wbMapPasteReading("branches", "a\\n  b")') == "a\n  b"
    assert _js('wbMapPasteReading("oneTopic", "- a\\n- b")') == "a b"


def test_the_wiring_commands_chip_and_copies_without_comments():
    for cid in ("paste-special", "paste-into-shape", "paste-no-comments"):
        assert f'id: "{cid}"' in COMMANDS
    assert "wbPasteChipOffer(" in COMMANDS and "wbRecordGesture(async () => {\n    created = await wbCreateCopies(items, 0, 0);" in COMMANDS
    assert "noComments" in SOURCE and "wbWithoutComments(body)" in SOURCE
    assert "wbMapPasteWithChip(text)" in MAP
    #: The copied-objects paste is still the one request.
    assert "/paste`, { method" in SOURCE


def test_text_pasted_on_a_map_never_falls_through_to_a_stale_board_copy():
    listener = SOURCE[SOURCE.index('document.addEventListener("paste"') :][:2200]
    assert "if (wbIsMap()) return;" in listener
    assert listener.index("if (wbIsMap()) return;") < listener.index("if (wbClipboard) {")
