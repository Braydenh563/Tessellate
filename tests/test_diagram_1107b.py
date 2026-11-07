"""1107 diagram builder, round 2 (docs/roadmap/agent-remaining/diagbuild-1107.md): DD-6, DD-8a, DD-8, DD-4, DD-5, DD-10 to DD-13.

Source assertions for what the code must hold; the browser numbers (rects, key counts) are in each commit and in the remaining file.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"


def _js(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


EMBED = _js("diagram-embed.js")
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")


def _phone_css() -> str:
    start = CSS.index("/* A phone's builder is a full-screen sheet")
    return CSS[start - 120 : start + 2600]


def test_a_phone_builder_is_a_full_screen_sheet_with_the_views_on_top_and_a_one_row_foot():
    # DD-6: 390 x 844 measured before: dialog 342 wide, dock 18 px outside it, foot three rows (153 px), Source under the foot.
    assert 'const viewbar = el("div", "dgm-viewbar")' in EMBED
    assert 'matchMedia("(max-width: 599.98px)")' in EMBED and "(phone.matches ? viewbar : foot).prepend(seg)" in EMBED
    # DD-12 puts the optional title row after the head.
    assert "dialog.append(head, ...(titlebar ? [titlebar] : []), viewbar, body, foot)" in EMBED
    css = _phone_css()
    assert ".modal-overlay > .card.dgm-dialog" in css and "max-width: none" in css and "max-height: none" in css
    # Out of the notch and off the home indicator, as 10-responsive.css band 2 does for every other dialog.
    assert "env(safe-area-inset-top, 0px)" in css and "env(safe-area-inset-bottom, 0px)" in css
    assert ".dgm-dialog .space-dialog-actions" in css and "flex-wrap: nowrap" in css
    # The door's "Open an existing diagram" is its glyph on a phone, and keeps its name.
    assert ".dgm-known .ph-text" in css and 'known.setAttribute("aria-label", "Open an existing diagram")' in EMBED
    # An empty diagram's picture is a strip so the steps and the template button stay on the screen.
    assert ".dgm-picture-empty" in css[css.index("grid-template-rows: auto minmax(0, 1fr)") - 200 :]


needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _math(expr: str):
    script = (
        "const vm=require('vm');const ctx={diagramModel:{}};vm.createContext(ctx);"
        f"vm.runInContext(require('fs').readFileSync({json.dumps(str(JS / 'diagram-view.js'))},'utf8'),ctx);"
        f"const m=ctx.diagramModel.view.math;process.stdout.write(JSON.stringify({expr}));"
    )
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


MODEL = (
    "{nodes:[{id:'A',text:'Start',shape:'rect'},{id:'B',text:'Check',shape:'diamond'},{id:'C',text:'Done',shape:'rect'},{id:'D',text:'Lone',shape:'round'}],"
    "edges:[{from:'A',to:'B'},{from:'B',to:'C'}]}"
)
BOXES = "[{id:'A',x:50,y:20},{id:'B',x:50,y:100},{id:'C',x:150,y:180},{id:'D',x:-40,y:180}]"


@needs_node
def test_an_arrow_key_on_the_picture_reaches_the_nearest_box_that_way_or_the_top_left_one():
    # DD-8a: nothing picked starts at the top left; a box straight below beats one far to the side; no box that way is null.
    assert _math(f"m.reach({BOXES}, '', 0, 1).id") == "A"
    assert _math(f"m.reach({BOXES}, 'A', 0, 1).id") == "B"
    assert _math(f"m.reach({BOXES}, 'B', 0, 1).id") in ("C", "D")
    assert _math(f"m.reach({BOXES}, 'C', -1, 0).id") == "D"
    assert _math(f"m.reach({BOXES}, 'A', 0, -1)") is None
    assert _math(f"m.reach({BOXES}, 'A', 1, 0)") is None or _math(f"m.reach({BOXES}, 'A', 1, 0).id") == "C"


@needs_node
def test_the_picture_names_every_box_and_arrow_and_a_picked_box_names_its_arrows():
    # DD-8a: the alt text lists every box (a lone one too) and every arrow; the live region reads the box and its edges.
    said = _math(f"m.summary({MODEL})")
    assert said.startswith("Flowchart, 4 boxes (Start, Check, Done, Lone), 2 arrows: Start to Check, Check to Done")
    assert _math(f"m.said({MODEL}, 'B')") == "Check, decision. In from Start. Out to Done."
    assert _math(f"m.said({MODEL}, 'D')") == "Lone, pill. No arrows." or "No arrows." in _math(f"m.said({MODEL}, 'D')")
    assert _math("m.summary({nodes:[],edges:[]})") == "Flowchart, empty"


def test_the_picture_arrows_pick_and_shift_pans_and_the_description_is_on_the_figure():
    view = _js("diagram-view.js")
    assert "if (move && !event.shiftKey && choose(event.key)) return event.preventDefault();" in view
    assert 'fig.setAttribute("aria-description", (img.alt = math.summary(S.m)))' in view
    assert "diagramModel.builder.select(S, `n:${to.id}`)" in view and "tell(math.said(S.m, to.id))" in view
    # A kind's pane has no boxes, so its arrows still pan.
    assert "!S.k && S.m && S.hit?.boxes?.length" in view


def test_only_the_picked_row_keeps_tab_stops_so_the_picture_is_within_six_stops():
    # DD-8: five rows of four buttons put the first picture stop at 23 (1440, five boxes). Now the picked row's buttons only.
    builder = _js("diagram-builder.js")
    assert 'for (const c of b.querySelectorAll(":scope > .dgm-card button, :scope > .dgm-joins button"))' in builder
    assert "add.tabIndex = connect.tabIndex = -1;" in _js("diagram-steps.js")


def test_the_drawing_error_note_offers_undo_of_the_last_edit():
    # DD-4 rest: measured at 1440 (port 8871): a typed bad line gave the note [Undo the last edit, Go to line 4], image kept (418 px, stale),
    # role=alert; one press restored the source and the picture, note gone.
    picture = _js("diagram-picture.js")
    failure = picture[picture.index("function failure(") :]
    assert 'if (S.io?.undo) note.prepend(smallButton("ph:arrow-u-up-left Undo the last edit"' in failure
    assert failure.index("Undo the last edit") < failure.index("replaceChildren(note)")


def test_the_source_pane_has_line_numbers_indent_keys_whole_edit_undo_and_a_way_out():
    # DD-5. Measured before (1440, port 8871): Tab left the field (focus on a ghost button), no line numbers, a soft-wrapped 480 px field,
    # Ctrl+Z was the browser's own so a block edit could not be undone from the text, Escape closed the window.
    assert 'const srcwrap = el("div", "dgm-srcwrap")' in EMBED and 'gutter.setAttribute("aria-hidden", "true")' in EMBED
    assert 'field.setAttribute("wrap", "off")' in EMBED and "body.append(srcwrap, host)" in EMBED
    # Tab is two spaces (every selected line when it spans lines), Shift+Tab takes them back.
    assert 'event.key === "Tab" && !event.ctrlKey && !event.metaKey && !event.altKey' in EMBED
    # The text field's undo is the history's: the debounce is flushed first so an edit made a moment ago is its own step.
    assert "const flush = () =>" in EMBED and "if (event.target === field) flush()" in EMBED
    assert "event.target === field ||" not in EMBED
    # Escape in the field leaves the field (Tab now indents, so it is the way out); the next one closes the window.
    assert "if (event.target === field)" in EMBED[EMBED.index("const onKey") :]
    # The error line is marked in the gutter, set by the picture's failure note and cleared when the picture draws.
    picture = _js("diagram-picture.js")
    assert 'field.dispatchEvent(new Event("dgmerror"))' in picture
    assert 'field.addEventListener("dgmerror"' in EMBED
    assert ".dgm-gutter-bad" in CSS and ".dgm-srcwrap" in CSS


def test_the_empty_checklist_is_one_width_and_goes_at_two_boxes():
    # DD-10, measured at 1440 (pane 256 wide): step buttons 113, 133, 131 px wide, rows 43, 32, 43 tall (two-line words), the ticked
    # record left to the first arrow. After: 190 px each, rows 60, words one line (18 px), and the list and its frame gone at two boxes
    # (the foot's Connect is the next action). At 390: 160 px each, the pane 383 = 383 (no scroll).
    steps = _js("diagram-steps.js")
    assert "const lesson = m.edges.length === 0 && m.nodes.length < 2;" in steps
    assert 'S.empty.classList.toggle("hidden", !lesson)' in steps and 'S.footConnect?.classList.toggle("hidden", lesson && Boolean(S.steps))' in steps
    start = CSS.index(".dgm-step {")
    rule = CSS[start : start + 400]
    assert "display: grid" in rule and "inline-size: 100%" in rule
    assert "grid-template-columns: auto minmax(0, 1fr) 10rem" in CSS


def test_the_new_diagram_window_has_a_title_that_names_the_document_and_the_export():
    # DD-12. Before: Done made a document titled "Diagram" every time and the PNG was "Diagram builder.png".
    assert 'const titleField = named ? el("input", "dgm-title") : null' in EMBED
    assert "get name() { return titleField?.value.trim() || title; }" in EMBED
    assert 'onDone(history[at], history[at] !== first, titleField ? titleField.value.trim() : "")' in EMBED
    assert "dialog.append(head, ...(titlebar ? [titlebar] : []), viewbar, body, foot)" in EMBED
    door = _js("documents-mermaid.js")
    assert door.count("named: true") == 2 and "onDone: async (next, _changed, name)" in door
    assert "title: name || " in door and ".dgm-title" in CSS


def _look(source: str, hand: bool) -> str:
    # The pure `withLook` is lifted out of the embed file between its markers and run in node, with a front matter reader like the model's.
    start = EMBED.index("const withLook = ")
    end = EMBED.index("//: end withLook")
    program = (
        "const front=(text)=>{const m=/^---\\n[\\s\\S]*?\\n---\\n/.exec(text);return {front:m?m[0].replace(/\\n$/,'').split('\\n'):[],rest:m?text.slice(m[0].length):text};};"
        "const diagramModel={front};"
        + EMBED[start:end]
        + f"process.stdout.write(JSON.stringify(withLook({json.dumps(source)},{json.dumps(hand)})));"
    )
    return json.loads(subprocess.run(["node", "-e", program], capture_output=True, text=True, check=True).stdout)


@needs_node
def test_the_hand_drawn_look_is_front_matter_that_keeps_the_rest_and_clean_removes_it_again():
    # DD-13. Measured at 1440: the same two-box chart drew a 10,160 B SVG clean and a 59,754 B SVG with look: handDrawn (the viewBox grew 186 x 270
    # to 199 x 281). The look is two front matter lines, so the model, the document and the exports all keep it.
    plain = "flowchart TD\n  A --> B\n"
    hand = _look(plain, True)
    assert hand == "---\nconfig:\n  look: handDrawn\n---\nflowchart TD\n  A --> B\n"
    assert _look(hand, False) == plain
    # Another key in the front matter stays, and a config block already there gains the line once.
    titled = "---\ntitle: Login\n---\nflowchart TD\n  A --> B\n"
    assert _look(titled, True) == "---\ntitle: Login\nconfig:\n  look: handDrawn\n---\nflowchart TD\n  A --> B\n"
    assert _look(_look(titled, True), True) == _look(titled, True)
    assert _look(_look(titled, True), False) == titled
    themed = "---\nconfig:\n  theme: dark\n---\nflowchart TD\n  A --> B\n"
    assert _look(themed, True) == "---\nconfig:\n  look: handDrawn\n  theme: dark\n---\nflowchart TD\n  A --> B\n"
    assert _look(_look(themed, True), False) == themed
    assert 'makeMenuItem("ph:pencil-line Hand-drawn look"' in EMBED and 'makeMenuItem("ph:rectangle Clean look"' in EMBED
