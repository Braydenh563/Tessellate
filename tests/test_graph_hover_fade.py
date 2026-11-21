"""The owner, 2026-10-04: "when I hover over parts of the graph, the labels
and stuff just suddenly appear and it is very visually confronting".

Measured before with `scratchpad/ui-sweeps/graphfade.js`: a non-neighbour's
dot, a non-neighbour's link, a dimmed note's name and the hovered note's
name each went from rest to their end value in the first frame (largest
single-frame step 1.0, no frame in between). The canvas has no CSS, so each
of them now carries a lit-ness that travels per frame; these tests run the
label pass and the step under node against a recording context, and read the
source for the parts a canvas hides from the lints."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._js_scope import gc_frame, unwrapped

ROOT = Path(__file__).resolve().parent.parent
CANVAS = unwrapped((ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8"))

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _fn(name: str) -> str:
    found = re.search(rf"^function {name}\(.*?^\}}", CANVAS, re.S | re.M)
    assert found, name
    return found.group(0)


def _const(name: str) -> str:
    found = re.search(rf"^const {name} = .*?;$", CANVAS, re.M)
    assert found, name
    return found.group(0)


def _run(body: str) -> dict:
    script = "\n".join(
        [
            "const GC_DIM_ALPHA = 0.2;",
            _const("GC_FADE_MS"),
            _fn("gcSmooth"),
            _fn("gcFadeToward"),
            _fn("gcFadeStep"),
            _fn("gcDrawLabels"),
            "const gcLabelPlates = () => true;",
            "let gcTokens = { font: 'x', card: '#fff', ink: '#000' };",
            "const drawn = [];",
            "const ctx = { set globalAlpha(v) { this.a = v; }, get globalAlpha() { return this.a; },",
            "  beginPath() {}, roundRect() {}, fill() {}, save() {}, restore() {}, translate() {}, scale() {}, setTransform() {},",
            "  getTransform() { return { a: 1, b: 0, c: 0, d: 1, e: 0, f: 0 }; },",
            "  fillText(text) { drawn.push([text, +this.a.toFixed(3)]); } };",
            body,
        ]
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, timeout=30).stdout
    return json.loads(out)


@needs_node
def test_a_label_fades_in_and_out_over_frames_rather_than_appearing():
    out = _run(
        """
        const node = { id: 1, x: 0, y: 0 };
        const s = { byId: new Map([[1, node]]) };
        const item = { id: 1, x: 0, y: 20, align: "center", text: "Alpha" };
        const step = 16.7 / GC_FADE_MS;
        const inA = [], outA = [];
        for (let i = 0; i < 14; i++) { drawn.length = 0; gcDrawLabels(ctx, s, [item], step, 1); inA.push(drawn[0][1]); }
        let frames = 0;
        for (let i = 0; i < 14; i++) { drawn.length = 0; gcDrawLabels(ctx, s, [], step, 1); if (drawn.length) { outA.push(drawn[0][1]); frames++; } }
        process.stdout.write(JSON.stringify({ inA, outA, frames }));
        """
    )
    # In: starts near nothing, rises every frame, lands on full by ~180ms.
    assert out["inA"][0] < 0.1
    assert all(b >= a for a, b in zip(out["inA"], out["inA"][1:]))
    assert out["inA"][-1] == 1
    assert max(b - a for a, b in zip(out["inA"], out["inA"][1:])) < 0.25
    # Out: drawn where it was on its way out, for several frames, then gone.
    assert 8 <= out["frames"] <= 12
    assert all(b <= a for a, b in zip(out["outA"], out["outA"][1:]))


@needs_node
def test_a_label_that_changes_words_cross_fades_through_a_ghost():
    out = _run(
        """
        const node = { id: 1, x: 0, y: 0 };
        const s = { byId: new Map([[1, node]]) };
        const step = 16.7 / GC_FADE_MS;
        for (let i = 0; i < 14; i++) gcDrawLabels(ctx, s, [{ id: 1, x: 0, y: 20, align: "center", text: "Quarterly…" }], step, 1);
        drawn.length = 0;
        gcDrawLabels(ctx, s, [{ id: 1, x: 0, y: 20, align: "center", text: "Quarterly planning" }], step, 1);
        process.stdout.write(JSON.stringify({ drawn }));
        """
    )
    texts = dict(out["drawn"])
    assert texts["Quarterly…"] > 0.8  # the old words, fading out
    assert texts["Quarterly planning"] < 0.1  # the new, fading in


@needs_node
def test_reduced_motion_lands_every_fade_on_the_first_frame():
    out = _run("process.stdout.write(JSON.stringify({ step: gcFadeStep({}, true) }));")
    assert out["step"] == 1


@needs_node
def test_the_first_frame_after_idle_is_one_ordinary_frame_not_a_jump():
    out = _run("process.stdout.write(JSON.stringify({ step: gcFadeStep({ fadeLast: performance.now() - 5000 }, false) }));")
    assert out["step"] == pytest.approx(16.7 / 180)


def test_dots_lines_rings_and_pills_all_draw_from_their_lit_ness():
    draw = gc_frame(CANVAS)
    # Nodes: batched by colour only; alpha per node from its own lit-ness.
    assert "const key = node.colour;" in draw
    # Each node's alpha is its own lit-ness; FE-04's batched small dots carry
    # it in their batch key (eight steps), large ones set it directly.
    # A note new to the picture also fades in (`gcBornAlpha`, INBOX 775 round 2).
    assert "let alpha = gcLitAlpha(node._lit) * born;" in draw and "ctx.globalAlpha = alpha;" in draw
    # Edges: bucketed by an eleven-step level, not a dim flag.
    assert "edge._lit = gcFadeToward(edge._lit" in draw and "|${level}`" in draw
    assert "|${dim}`" not in draw
    # Rings follow the hover's own ease, the one being left included.
    assert "item.ringFade" in draw and "node.id === s.hoverFrom && heat > 0" in draw
    # The score pills fade, the last note's as a ghost.
    assert "s.pillGhost" in draw and "gcDrawPill(ctx, drawn, k, gcSmooth(s.pillA))" in draw
    # And the loop keeps asking for frames until every fade has landed.
    assert "if (easing || fading || gliding || s.bornPending) gcRequestDraw(s);" in draw


def test_a_line_answers_the_pointer_and_a_click_opens_its_peek():
    """The owner, 2026-10-04: "I cant click on links to see their reason in
    the graph??". Only a `link` answered a click, with a modal editor, and
    nothing showed a line could be clicked. `graphlinkpeek.js`: 20 of 20
    sampled line middles hover (pointer cursor) and open the peek."""
    assert 'const GC_PEEK_KINDS = new Set(["link", "thread", "similar", "map"]);' in CANVAS
    assert "if (!GC_PEEK_KINDS.has(edge.kind)) continue;" in CANVAS
    assert "openGraphLinkPeek(edge, event, s.nodes);" in CANVAS
    assert 's.canvas.classList.toggle("graph-edge-hover", Boolean(edge));' in CANVAS
    assert "if (gcDrawEdgeHover(ctx, s, k, fadeStep, curvedLinks)) f.fading = true;" in CANVAS
    graph = (ROOT / "frontend" / "js" / "graph.js").read_text(encoding="utf-8")
    peek = graph[graph.index("function openGraphLinkPeek") :]
    peek = peek[: peek.index("\n}\n")]
    assert 'panel.className = "help-popover graph-link-peek";' in peek
    assert "placeHelpPopover(panel, anchor);" in peek
    assert "openGraphLinkPanel(edge, nodes);" in peek and "graphRemoveLink(edge, sourceId)" in peek
    assert "reason_confidence" in peek
    css = (ROOT / "frontend" / "css" / "02-chat-graph.css").read_text(encoding="utf-8")
    assert "#graph-canvas.graph-edge-hover {\n  cursor: pointer;" in css
