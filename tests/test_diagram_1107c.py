"""1107 diagram builder, round 2 review (docs/roadmap/agent-remaining/diagbuild-1107.md): the reviewer's and the UX auditor's findings.

Source assertions for what the code must hold; the browser numbers are in each commit and in the remaining file.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _js(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


EMBED = _js("diagram-embed.js")
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")


def _lift(start: str, end: str, call: str):
    program = (
        "const front=(text)=>{const m=/^---\\n[\\s\\S]*?\\n---\\n/.exec(text);return {front:m?m[0].replace(/\\n$/,'').split('\\n'):[],rest:m?text.slice(m[0].length):text};};"
        "const diagramModel={front};" + EMBED[EMBED.index(start) : EMBED.index(end)] + f"process.stdout.write(JSON.stringify({call}));"
    )
    return json.loads(subprocess.run(["node", "-e", program], capture_output=True, text=True, check=True).stdout)


def _look(source: str, hand: bool):
    return _lift("const withLook = ", "//: end withLook", f"withLook({json.dumps(source)},{json.dumps(hand)})")


@needs_node
def test_a_look_joins_a_config_written_on_one_line_and_leaves_one_it_cannot_edit():
    # Review 3: `config: {theme: dark}` made the old code append a second `config:` key (invalid YAML).
    body = "flowchart TD\n  A --> B\n"
    flow = f"---\nconfig: {{theme: dark}}\n---\n{body}"
    hand = _look(flow, True)
    assert hand == f"---\nconfig: {{look: handDrawn, theme: dark}}\n---\n{body}"
    assert hand.count("config:") == 1
    assert _look(hand, True) == hand
    assert _look(hand, False) == flow
    only = f"---\nconfig: {{look: handDrawn}}\n---\n{body}"
    assert _look(only, False) == body
    assert _look(f"---\nconfig: {{}}\n---\n{body}", True) == only
    # A look in the middle of the braces comes out cleanly.
    assert _look(f"---\nconfig: {{a: 1, look: handDrawn, b: 2}}\n---\n{body}", False) == f"---\nconfig: {{a: 1, b: 2}}\n---\n{body}"
    # A value the menu cannot read is not touched: null, and the caller says so.
    assert _look(f"---\nconfig: ~\n---\n{body}", True) is None
    assert 'if (next === null) return toast("The front matter has a config line the menu cannot edit. Change it in Source.", "info")' in EMBED


@needs_node
def test_a_title_has_no_link_syntax_and_is_never_a_name_another_document_has():
    # Review 1: links resolve `![[Title]]` to the first document of that title, `|` and `]]` end or split the reference, `#` starts a block reference.
    assert _lift("const cleanTitle", "//: end freshTitle", "cleanTitle('  A [[b]] | c #d  ')") == "A b c d"
    assert _lift("const cleanTitle", "//: end freshTitle", "cleanTitle('')") == ""
    taken = "new Set(['login flow','login flow 2'])"
    assert _lift("const cleanTitle", "//: end freshTitle", f"freshTitle('Login flow',{taken})") == "Login flow 3"
    assert _lift("const cleanTitle", "//: end freshTitle", f"freshTitle('Plan',{taken})") == "Plan"
    # The name comes from the server's whole list (the page's list may be stale), after the dialog has gone, so Done is still once.
    assert 'apiPagedList("/documents", 200)' in EMBED and "onDone(next, changed, titleField ? await documentName(typed) : \"\")" in EMBED
    assert "titleField.value.replace(/[\\[\\]|#]+/g, \"\")" in EMBED


def test_a_typed_title_alone_is_a_change_the_discard_guard_asks_about():
    # Review 2: Escape, Cancel and the backdrop dropped a title with no question.
    assert "(history[at] === first && !titleField?.value.trim()) || (await confirmDialog(" in EMBED


def test_the_error_notes_undo_is_offered_only_where_there_is_an_earlier_step_and_returns_focus():
    # Review 4 and UX 2: at the first step Undo had nowhere to go; the note left with the press and focus fell to the body.
    assert "get canUndo() { return at > 0; }" in EMBED
    picture = _js("diagram-picture.js")
    assert "if (S.io?.undo && S.io.canUndo !== false)" in picture
    assert picture.index("(S.fig?.isConnected ? S.fig : field)?.focus") < picture.index("S.io.undo();")


def test_the_arrow_key_pick_starts_from_a_box_not_from_a_picked_arrow():
    # Review 5: `S.sel` is a key (`n:id`, or an arrow's); `slice(2)` of an arrow's key is no box, so the nearest-box search fell back to the top left.
    view = _js("diagram-view.js")
    assert 'S.sel?.startsWith("n:") ? S.sel.slice(2) : ""' in view
    # Review 7: one pending announcement.
    assert "clearTimeout(told);" in view and "told = setTimeout(" in view


def test_the_palette_twins_stay_out_of_the_tab_order_because_the_keys_and_the_bar_reach_them():
    # Review 6, rejected as a change: Add is the bar's first button (one roving stop), the foot's Connect is a Tab stop, and N and C are
    # documented in the Keys sheet and the dialog's help; the twins were 4 of the 23 stops before the picture.
    steps = _js("diagram-steps.js")
    assert "add.tabIndex = connect.tabIndex = -1;" in steps
    style = _js("diagram-style.js")
    assert "Connect the selected block to another" in style and "Left, Right in the bar" in style


def test_a_phone_opens_its_blocks_from_the_blocks_view_and_focus_starts_in_the_window():
    # UX 1: the pressed Blocks segment showed the same picture (the tree is a sheet there); UX 3: focus began on the body.
    assert 'name === "blocks" && phone.matches ? pane?.root?.querySelector(".dgm-listbtn") : null' in EMBED
    assert "sheet ? sheet.click() : view(name);" in EMBED
    assert "if (!dialog.contains(document.activeElement)) (host.querySelector(\".dgm-picture\") || dialog).focus" in EMBED
    assert "dialog.tabIndex = -1;" in EMBED


def test_the_look_menu_offers_the_look_that_is_not_on():
    # UX 5: both rows were offered with nothing to say which was on. `kebabMenu` rows carry no checked state, so the row is the other look.
    assert "get menu() {" in EMBED and "lookRow()," in EMBED
    assert 'makeMenuItem("ph:rectangle Clean look"' in EMBED and 'makeMenuItem("ph:pencil-line Hand-drawn look"' in EMBED
    assert "const hand = diagramModel.front(history[at]).front.some(" in EMBED


def test_touch_hit_areas_reach_44_and_the_phone_source_takes_the_room():
    # UX 4: the edge handle drew 24 wide (half a small block) with a 40 px hit area; the divider was the 13 px gap. UX 6: Source was 144 px under a 418 px host.
    coarse = CSS[CSS.index("@media (pointer: coarse) {\n  .dgm-handle {") :]
    coarse = coarse[: coarse.index("\n}\n") + 3]
    assert ".dgm-handle::after" in coarse and "inset: -12px;" in coarse
    assert ".dgm-split-handle.sidebar-resize::after" in coarse and "calc((var(--space-5) - 44px) / 2)" in coarse
    assert '.dgm-dialog[data-view="source"] .dgm-srcwrap {\n    flex: 1 1 9rem;' in CSS
    assert '.dgm-dialog[data-view="source"] .dgm-host {\n    flex: 0 0 auto;' in CSS


def test_enter_on_a_picked_box_names_it_where_it_stands_and_the_keys_say_so():
    # UX 8 and 7.
    assert "S.renameNode = renameNode;" in _js("diagram-edges.js")
    view = _js("diagram-view.js")
    assert 'event.key === "Enter" || event.key === "F2"' in view and "S.renameNode?.(S.sel.slice(2))" in view
    assert "Name the selected block, in the list or on the picture" in _js("diagram-style.js")
