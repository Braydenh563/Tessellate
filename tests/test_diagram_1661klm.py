"""INBOX 1661 (k) (l) (m): the Kind menu, the picture you edit in place, the panels that fold (spec in
docs/roadmap/agent-remaining/diagklm-1108.md). Measured numbers are in that file and in the CHANGELOG lines."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="node is not installed")


def _js(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def _kindbar(expr: str):
    run = (
        "const vm=require('vm');const ctx={diagramModel:{}};vm.createContext(ctx);"
        f"vm.runInContext(require('fs').readFileSync({json.dumps(str(JS / 'diagram-kindbar.js'))},'utf8'),ctx);"
        f"const k=ctx.diagramModel.kindbar;process.stdout.write(JSON.stringify({expr}));"
    )
    return json.loads(subprocess.run(["node", "-e", run], capture_output=True, text=True, check=True).stdout)


# --- S1 (k): one Kind button in the Title row, a menu of drawn samples


def test_the_four_button_row_is_gone_and_one_kind_button_opens_a_menu():
    bar = _js("diagram-kindbar.js")
    assert "dgm-kinds" not in bar and ".dgm-kinds" not in CSS
    assert 'aria-haspopup", "menu"' in bar and "Kind of diagram: ${label}. Choose a kind" in bar
    assert 'openMenuAtPoint(KINDS.map' in bar and '"Kinds of diagram"' in bar


def test_the_button_sits_in_the_title_row_behind_a_kind_label_else_first_in_the_toolbar():
    bar = _js("diagram-kindbar.js")
    assert '.closest(".dgm-dialog")?.querySelector(".dgm-titlebar")' in bar
    assert '"muted dgm-kindlabel", "Kind"' in bar and "dock?.prepend(button" in bar
    # the Title row outlives the pane, so a remount replaces the old button rather than adding a second
    assert ":scope > :is(.dgm-kindbtn, .dgm-kindlabel)" in bar and "old.remove()" in bar
    # Review 1108: the Title row is a <label>, so a press on the word Kind went to the title field; it opens the menu instead.
    assert 'word.addEventListener("click", (event) => (event.preventDefault(), button.click()))' in bar


def test_each_menu_row_has_its_sample_and_what_it_makes_and_a_change_says_its_cost():
    bar = _js("diagram-kindbar.js")
    assert "row.replaceChildren(sample(key), text)" in bar and '"muted dgm-kind-about"' in bar
    assert 'row.setAttribute("aria-current", "true")' in bar
    assert "A new kind starts empty. Undo brings this one back." in bar
    assert ".dgm-kindmenu .dgm-kindpic" in CSS and ".dgm-kind-about" in CSS


@needs_node
def test_every_kind_has_a_sample_and_an_about_line_short_enough_for_one_row():
    out = _kindbar("k.KINDS.map(([key,,,about])=>[key, !!k.SAMPLE[key], about.length])")
    assert [row[0] for row in out] == ["flowchart", "sequence", "mindmap", "timeline", "gantt", "pie", "state", "class", "er"]
    # 45 characters fit one line of the menu at 390 (measured: a 62-character line wrapped to a 73 px row)
    assert all(has and length <= 45 for _, has, length in out), out


def test_below_600_the_word_hides_and_the_button_is_44_px():
    # The window rule; a narrow pane hides the word too (the @container block above it, wrapzoom 2026-11-11).
    at = CSS.index("@media (max-width: 599.98px) {\n  .dgm-kindword {")
    block = CSS[at:][:260]
    assert "display: none" in block and "min-block-size: 2.75rem" in block
    assert "@container (max-width: 599.98px) {\n  .dgm-kindword {\n    display: none;" in CSS


def test_a_source_the_blocks_cannot_draw_offers_no_kind_even_from_the_title_row():
    assert ".dgm-dialog:has(.dgm-plain) :is(.dgm-kindbtn, .dgm-kindlabel)" in CSS


# --- S2: a box just added and picked is brought into view


def test_a_new_picked_box_is_scrolled_into_view_but_not_on_the_first_picture():
    # Measured at 200% zoom, 1440: 0 of 10 Ctrl+D adds were wholly inside the picture before, 10 of 10 after; at 50% none scrolls.
    overlay = _js("diagram-overlay.js")
    draw = overlay[overlay.index("const draw = () => {") :][:1400]
    assert "born.push(b.id)" in overlay and 'sync(found, boxes, "node", "", born)' in draw
    assert "const fresh = seen && born.find((id) => ids.has(id));" in draw
    # The scroll moved to the task a frame after the draw (INBOX 1766): the draw owes it, `second` does it with the boxes laid out.
    assert "owed = boxes.get(fresh)" in draw
    assert 'owed.scrollIntoView({ block: "nearest", inline: "nearest" })' in overlay


# --- S3 (m): both side panels fold to a rail


@needs_node
def test_one_kept_fold_means_one_side_always_shows():
    run = (
        "const vm=require('vm');const ctx={diagramModel:{}};vm.createContext(ctx);"
        f"vm.runInContext(require('fs').readFileSync({json.dumps(str(JS / 'diagram-split.js'))},'utf8'),ctx);"
        "const n=ctx.diagramModel.split.fold.next;process.stdout.write(JSON.stringify([n('', 'left'), n('left', 'left'), n('right', 'left'), n('left', 'right')]));"
    )
    out = json.loads(subprocess.run(["node", "-e", run], capture_output=True, text=True, check=True).stdout)
    # folding the list while the picture is folded opens the picture: never both
    assert out == ["left", "", "left", "right"]


def test_the_folds_have_keys_a_rail_and_the_old_list_button_is_gone():
    split = _js("diagram-split.js")
    assert 'event.code === "BracketLeft"' in split and 'event.code === "BracketRight"' in split
    assert 't.closest?.("input, textarea, select")' in split and "matchMedia(PHONE).matches) return" in split
    assert 'prefs.get("diagram.outline") === "0"' in split  # the old choice is read once
    assert "The ${noun} is folded. ${key} opens it." in split
    assert "OUTLINE" not in _js("diagram-bar.js") and "dgm-no-outline" not in CSS
    # Measured at 1440: the rail 32 px, the picture 905 to 1136 px wide, the list 1136 with the picture folded; kept on reopen.
    assert "@media (min-width: 600px)" in CSS[CSS.index(".dgm-rail {") :][:120]


def test_a_kinds_list_on_a_phone_is_the_sheet_once_it_has_a_block():
    # Measured at 390: a sequence picture was 96 px tall under its stacked list; 435 with the list in the sheet.
    touch = _js("diagram-touch.js")
    assert "(S.steps || S.k) && S.pane && actions" in touch
    assert 'S.root.classList.toggle("dgm-listless", !A.blank(S.m))' in _js("diagram-kinds.js")


# --- S4 (l): a sequence diagram edited on its picture

#: Cut from Mermaid's own drawing of the login template (the tags it writes; styles and text left out).
LOGIN_SVG = (
    '<svg viewBox="-50 -10 650 623">'
    '<line id="actor2" x1="475" y1="76" x2="475" y2="496" class="actor-line 200" data-et="life-line" data-id="Server"/>'
    '<g id="root-2" data-et="participant" data-type="participant" data-id="Server"><rect x="400" y="0" width="150" height="76" class="actor actor-top"/></g>'
    '<line id="actor1" x1="275" y1="76" x2="275" y2="496" class="actor-line 200" data-et="life-line" data-id="App"/>'
    '<g id="root-1" data-et="participant" data-type="participant" data-id="App"><rect x="200" y="0" width="150" height="76" class="actor actor-top"/></g>'
    '<line id="actor0" x1="75" y1="76" x2="75" y2="496" class="actor-line 200" data-et="life-line" data-id="User"/>'
    '<g data-et="note" data-id="i7"><rect x="50" y="426" width="250" height="40" class="note"/></g>'
    '<g data-et="control-structure" data-id="i8"><line x1="40" y1="186" x2="486" y2="186" class="loopLine"/>'
    '<line x1="486" y1="186" x2="486" y2="476" class="loopLine"/><line x1="40" y1="476" x2="486" y2="476" class="loopLine"/>'
    '<line x1="40" y1="186" x2="40" y2="476" class="loopLine"/><line x1="40" y1="336" x2="486" y2="336" class="loopLine" /></g>'
    '<g class="actor-man actor-top" name="User" data-et="participant" data-type="actor" data-id="User"><line x1="75" y1="20" x2="75" y2="33"/><circle cx="75" cy="10" r="10"/></g>'
    '<line x1="76" y1="126" x2="268" y2="126" class="messageLine0" data-et="message" data-id="i0" data-from="User" data-to="App"/>'
    '<line x1="276" y1="176" x2="468" y2="176" class="messageLine0" data-et="message" data-id="i1" data-from="App" data-to="Server"/>'
    '<line x1="474" y1="271" x2="282" y2="271" class="messageLine1" data-et="message" data-id="i3" data-from="Server" data-to="App"/>'
    '<line x1="274" y1="321" x2="82" y2="321" class="messageLine1" data-et="message" data-id="i4" data-from="App" data-to="User"/>'
    '<line x1="474" y1="416" x2="282" y2="416" class="messageLine1" data-et="message" data-id="i6" data-from="Server" data-to="App"/>'
    "</svg>"
)
LOGIN = (
    "sequenceDiagram\n  actor User\n  participant App\n  participant Server\n  User->>App: Enter password\n  App->>Server: Check login\n"
    "  alt Correct\n    Server-->>App: Token\n    App-->>User: Welcome\n  else Wrong\n    Server-->>App: Refused\n"
    "    Note over User,App: Try again\n  end\n"
)


def _seq(expr: str, **values):
    run = (
        "const vm=require('vm');const ctx={diagramModel:{decode:(t)=>t,statements:(t)=>t.split('\\n').map((l)=>l.trim()).filter(Boolean),"
        "front:(t)=>({front:[],rest:t})}};vm.createContext(ctx);"
        f"vm.runInContext(require('fs').readFileSync({json.dumps(str(JS / 'diagram-kinds.js'))},'utf8'),ctx);"
        f"vm.runInContext(require('fs').readFileSync({json.dumps(str(JS / 'diagram-seq-canvas.js'))},'utf8'),ctx);"
        "const K=ctx.diagramModel.kinds,C=ctx.diagramModel.seqCanvas,V=" + json.dumps(values) + ";"
        f"process.stdout.write(JSON.stringify({expr}));"
    )
    return json.loads(subprocess.run(["node", "-e", run], capture_output=True, text=True, check=True).stdout)


@needs_node
def test_every_part_mermaid_tags_becomes_a_box_under_its_rows_key():
    # Measured in the app: 11 of 11 rows of the login template picked by a press at their box's centre, at 1440 and 390.
    out = _seq(
        "(()=>{const m=K.sequence.parse(V.src);const hit=C.boxes(V.svg,m,K.ops.key);"
        "const rows=[];K.ops.walk(K.sequence,m,(n)=>n.type!=='k'&&rows.push(K.ops.key(n)));"
        "return {rows:rows.length,boxes:hit.boxes.length,missing:rows.filter((k)=>!hit.boxes.some((b)=>b.id===k)),"
        "kinds:hit.boxes.map((b)=>b.et),first:hit.boxes[0],vb:hit.vb}})()",
        src=LOGIN, svg=LOGIN_SVG,
    )
    assert out["rows"] == 11 and out["boxes"] == 11 and out["missing"] == []
    assert out["kinds"].count("participant") == 3 and out["kinds"].count("message") == 5
    assert out["kinds"][-2:] == ["frame", "divider"]  # frames last, so a press finds a step before its box
    assert out["vb"] == [-50, -10, 650, 623]
    assert out["first"]["x"] == 475 and out["first"]["w"] == 150 and out["first"]["h"] == 76


@needs_node
def test_mermaids_statement_ids_count_box_ends_dividers_and_activations():
    src = (
        "sequenceDiagram\n  A->>+B: one\n  activate A\n  alt yes\n    loop again\n      B->>A: two\n    end\n"
        "  else no\n    %% a comment is no statement\n    A->>B: three\n  end\n"
    )
    out = _seq(
        "(()=>{const m=K.sequence.parse(V.src);const map=C.order(m,K.ops.key);"
        "const name=(k)=>{const f=K.ops.find(K.sequence,m,k)?.node;return f?(f.text||f.kw||f.label):k};"
        "return [...map.entries()].filter(([id])=>id.startsWith('i')).map(([id,k])=>[id,name(k)])})()",
        src=src,
    )
    # i0 one, i1 its +activation, i2 activate A, i3 alt start, i4 loop start, i5 two, i6 loop end, i7 else, i8 three, i9 alt end
    assert out == [["i0", "one"], ["i5", "two"], ["i6", "again"], ["i8", "three"], ["i9", "yes"], ["i9/0", "no"]]


def test_the_picture_takes_a_press_a_rename_and_the_lists_keys():
    canvas = _js("diagram-seq-canvas.js")
    for needle in ('fig.addEventListener("dblclick"', "F2: () => rename(key)", "Delete: () => act.remove(S, key)", "ArrowUp: () => act.step(S, key, -1)", 'input.className = "dgm-rename"'):
        assert needle in canvas, needle
    assert "(fig.onpaint ||= []).unshift(" in canvas  # before the overlay's own paint
    builder = _js("diagram-builder.js")
    # dgpic-1109: the overlay takes any kind whose picture names its parts (`S.hitAt`), a mind map and a timeline too.
    assert 'lazyScript("/js/diagram-seq-canvas.js")' in builder and "(!S.k || S.hitAt)" in builder
    assert "(S.k && !S.hitAt)" in _js("diagram-overlay.js")
    assert "const act = {" in _js("diagram-kinds.js") and "ghostSpec, act }" in _js("diagram-kinds.js")


# --- S4 (l) part 2: reorder a head, draw a message between lifelines, the "+" in a gap


@needs_node
def test_a_head_dragged_past_the_last_one_gives_user_server_app():
    # Measured in the app: App dragged past Server gives User, Server, App.
    out = _seq(
        "(()=>{const m=K.sequence.parse(V.src);const hit=C.boxes(V.svg,m,K.ops.key);"
        "const app=hit.boxes.find((b)=>b.et==='participant'&&b.who==='App');"
        "const g=C.headGap(hit,520,app.id);const ok=K.ops.move(K.sequence,m,app.id,null,g.key);"
        "return {ok,key:g.key,names:m.participants.map((p)=>p.label),line:g.x>550}})()",
        src=LOGIN, svg=LOGIN_SVG,
    )
    assert out["ok"] and out["key"] is None and out["names"] == ["User", "Server", "App"] and out["line"]


@needs_node
def test_the_gap_under_the_pointer_names_the_row_it_goes_before_and_the_lifeline_pair():
    # A message from User to Server between messages 1 and 2 inserts at index 1; a pointer past the last row appends.
    out = _seq(
        "(()=>{const m=K.sequence.parse(V.src);const hit=C.boxes(V.svg,m,K.ops.key);"
        "const g=C.gap(hit,150);const p=C.pair(hit,75);const f=K.ops.find(K.sequence,m,g.key);"
        "const node=K.ops.add(K.sequence,m,'m',{parent:f.parent,before:f.node,fields:{from:'User',to:'Server',text:'New'}});"
        "const end=C.gap(hit,600);const last=C.pair(hit,475);"
        "return {at:m.steps.indexOf(node),text:m.steps.map((s)=>s.text),before:g.key===K.ops.key(m.steps[0])?'first':'second',"
        "pair:[p.from,p.to],end:end.key,last:[last.from,last.to],mid:g.y>126&&g.y<176-38+1}})()",
        src=LOGIN, svg=LOGIN_SVG,
    )
    assert out["at"] == 1 and out["text"][:3] == ["Enter password", "New", "Check login"]
    assert out["pair"] == ["User", "App"] and out["last"] == ["App", "Server"] and out["end"] is None


def test_the_picture_takes_the_drags_the_plus_and_the_shelf_drop():
    canvas = _js("diagram-seq-canvas.js")
    for needle in ('fig.addEventListener("pointerdown"', "stopImmediatePropagation()", "act.shift(S, ", "dgm-gap-plus", "seqOpen", "over, clear"):
        assert needle in canvas, needle
    assert "dgm-seqmark" in CSS and ".dgm-gap-plus" in CSS and "min-block-size: 24px" in CSS
    assert "shift(S, key, before)" in _js("diagram-kinds.js")


# --- S5: the shelf


@needs_node
def test_a_message_dropped_at_apps_x_between_messages_one_and_two_goes_app_to_server_at_index_one():
    out = _seq(
        "(()=>{const m=K.sequence.parse(V.src);const hit=C.boxes(V.svg,m,K.ops.key);"
        "const app=hit.boxes.find((b)=>b.et==='participant'&&b.who==='App');"
        "const x=app.x+app.w/2;const p=C.pair(hit,x);const g=C.gap(hit,150);const f=K.ops.find(K.sequence,m,g.key);"
        "const node=K.ops.add(K.sequence,m,'m',{parent:f.parent,before:f.node,fields:{from:p.from,to:p.to,text:'Message'}});"
        "return {at:m.steps.indexOf(node),pair:[p.from,p.to]}})()",
        src=LOGIN, svg=LOGIN_SVG,
    )
    assert out["at"] == 1 and out["pair"] == ["App", "Server"]


def test_the_shelf_is_a_dock_of_six_grip_tiles_and_a_caret_shown_on_touch_too():
    lib = _js("diagram-library.js")
    for needle in ("function tileOf(t)", "dataset.objGrip", "dock dgm-shelf", "dgm-shelf-more", 'aria-haspopup", "menu"', "openMenuAtPoint("):
        assert needle in lib, needle
    for kind in ('"Box", "Rounded", "Decision", "Pill", "Note", "Group"', '"participant", "message", "reply", "note", "loop", "alt"'):
        assert kind in lib
    assert "diagramModel.library.shelf(S, { ...helpers, glyph: shapeGlyph, groupGlyph })" in _js("diagram-builder.js")
    block = CSS[CSS.index(".dgm-shelf {") :][:700]
    assert "position: absolute" in block and "var(--space-3)" in block
    # The shelf stays on a phone and a touch screen (dgpolish-1109: a finger holds a tile, then drags it); it scrolls sideways there.
    assert CSS.count("@media (pointer: coarse), (max-width: 599.98px) {") == 1
    coarse = CSS[CSS.index("@media (pointer: coarse), (max-width: 599.98px) {") :].split("\n}\n", 1)[0]
    assert ".dgm-shelf {\n    display: none;" not in coarse
    assert "overflow-x: auto" in coarse[coarse.index(".dgm-shelf {") :][:300]
