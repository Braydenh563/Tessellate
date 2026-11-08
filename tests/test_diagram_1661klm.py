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
    assert 'openMenuAtPoint(KINDS.map' in bar and '"Kind of diagram"' in bar


def test_the_button_sits_in_the_title_row_behind_a_kind_label_else_first_in_the_toolbar():
    bar = _js("diagram-kindbar.js")
    assert '.closest(".dgm-dialog")?.querySelector(".dgm-titlebar")' in bar
    assert '"muted dgm-kindlabel", "Kind"' in bar and "dock?.prepend(button" in bar
    # the Title row outlives the pane, so a remount replaces the old button rather than adding a second
    assert ":scope > :is(.dgm-kindbtn, .dgm-kindlabel)" in bar and "old.remove()" in bar


def test_each_menu_row_has_its_sample_and_what_it_makes_and_a_change_says_its_cost():
    bar = _js("diagram-kindbar.js")
    assert "row.replaceChildren(sample(key), text)" in bar and '"muted dgm-kind-about"' in bar
    assert 'row.setAttribute("aria-current", "true")' in bar
    assert "A new kind starts empty. Undo brings this one back." in bar
    assert ".dgm-kindmenu .dgm-kindpic" in CSS and ".dgm-kind-about" in CSS


@needs_node
def test_every_kind_has_a_sample_and_an_about_line_short_enough_for_one_row():
    out = _kindbar("k.KINDS.map(([key,,,about])=>[key, !!k.SAMPLE[key], about.length])")
    assert [row[0] for row in out] == ["flowchart", "sequence", "mindmap", "timeline"]
    # 45 characters fit one line of the menu at 390 (measured: a 62-character line wrapped to a 73 px row)
    assert all(has and length <= 45 for _, has, length in out), out


def test_below_600_the_word_hides_and_the_button_is_44_px():
    block = CSS[CSS.index(".dgm-kindword {") - 40 :][:260]
    assert "@media (max-width: 599.98px)" in block and "display: none" in block
    assert "min-block-size: 2.75rem" in CSS[CSS.index(".dgm-kindword {") :][:200]


def test_a_source_the_blocks_cannot_draw_offers_no_kind_even_from_the_title_row():
    assert ".dgm-dialog:has(.dgm-plain) :is(.dgm-kindbtn, .dgm-kindlabel)" in CSS


# --- S2: a box just added and picked is brought into view


def test_a_new_picked_box_is_scrolled_into_view_but_not_on_the_first_picture():
    # Measured at 200% zoom, 1440: 0 of 10 Ctrl+D adds were wholly inside the picture before, 10 of 10 after; at 50% none scrolls.
    overlay = _js("diagram-overlay.js")
    draw = overlay[overlay.index("const draw = () => {") :][:1400]
    assert "born.push(b.id)" in overlay and 'sync(found, boxes, "node", "", born)' in draw
    assert "const fresh = seen && born.find((id) => ids.has(id));" in draw
    assert 'scrollIntoView({ block: "nearest", inline: "nearest" })' in draw
