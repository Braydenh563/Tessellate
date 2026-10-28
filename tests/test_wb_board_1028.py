"""Board audit 1028: B8, B16 (see test_wb_edge_pan), B21, B5 and the UX rows U1 to U3, U5."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
WB = (JS / "whiteboard.js").read_text(encoding="utf-8")
MAP = (JS / "whiteboard-map.js").read_text(encoding="utf-8")
LAZY = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
MISC = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")


def _function(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    return source[start : source.index("\n}\n", start) + 3]


def _node(script: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip())


# B8 -------------------------------------------------------------------------


def test_every_failed_delete_goes_through_one_toasting_restore():
    for kind in ("sketches", "nodes", "objects"):
        at = WB.index(f"/whiteboard/{kind}/${{d.id}}`, {{ method: \"DELETE\" }}")
        tail = WB[at : at + 2200]
        catch = tail[tail.index("} catch (e) {") : tail.index("} finally {")]
        assert "wbDeleteFailed(entry, redoBefore, e, () => delete" in catch
        assert "console.error" not in catch
        assert "const redoBefore = wbRedoStack;" in WB[at - 400 : at]


def test_a_failed_delete_drops_the_entry_keeps_redo_and_tells_the_person():
    body = _function(WB, "wbDeleteFailed")
    assert "wbDropUndoEntry(entry)" in body
    assert "wbRedoStack = redoBefore" in body
    assert "toast(" in body and 'action: ["Try again", retry]' in body


def test_a_failed_delete_behaves_as_if_nothing_happened():
    script = (
        "let wbUndoStack=[], wbRedoStack=['r1'], toasts=[];"
        "const toast=(m,e)=>toasts.push([m,e]); const voiceLine=(k,o)=>`failed ${o.what}`;"
        "const wbUpdateUndoRedoButtons=()=>{}; console.error=()=>{};"
        + _function(WB, "wbDropUndoEntry")
        + _function(WB, "wbDeleteFailed")
        + "const before=wbRedoStack; const entry={a:1}; wbUndoStack.push(entry); wbRedoStack=[];"
        "wbDeleteFailed(entry, before, new Error('x'), () => 0);"
        "console.log(JSON.stringify({u:wbUndoStack.length,r:wbRedoStack,t:toasts}));"
    )
    assert _node(script) == {"u": 0, "r": ["r1"], "t": [["failed delete that", True]]}


# B21 ------------------------------------------------------------------------


def test_the_eraser_hit_tests_the_whole_pointer_path_not_only_enter_events():
    start = WB.index('containerEl.addEventListener("pointermove", (e) => {\n    if (window.currentTool !== "eraser"')
    body = WB[start : start + 600]
    body += WB[WB.index("  function wbEraseAt(") : start]
    # Every sample the browser coalesced, so a fast touch or pen stroke skips nothing.
    assert "getCoalescedEvents" in body
    assert "document.elementFromPoint" in body
    assert "mouseenter" not in body


# B5 -------------------------------------------------------------------------


def test_the_unthrottled_container_pointermoves_share_one_frame_gate():
    assert "function wbOnFrame(" in WB
    gate = _function(WB, "wbOnFrame")
    assert "requestAnimationFrame" in gate
    for marker in ('containerEl.addEventListener("pointermove", wbOnFrame(', ):
        assert marker in WB


def test_the_frame_gate_runs_once_per_frame_with_the_latest_event():
    script = (
        "let frames=[]; const requestAnimationFrame=(f)=>frames.push(f);"
        + _function(WB, "wbOnFrame")
        + "const seen=[]; const h=wbOnFrame((e)=>seen.push(e.x)); h({x:1}); h({x:2}); h({x:3});"
        "const before=seen.length; frames.shift()(); h({x:4}); frames.shift()();"
        "console.log(JSON.stringify({before, seen}));"
    )
    assert _node(script) == {"before": 0, "seen": [3, 4]}


# U1, U2 ---------------------------------------------------------------------


def _ratio(a: str, b: str) -> float:
    def lum(h: str) -> float:
        h = h.lstrip("#")
        c = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
        c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _ink(ink: str, bg: str):
    script = (
        'const WB_CORE_INK_DARK="#000000", WB_CORE_INK_LIGHT="#ffffff";'
        + _function(MAP, "wbColourChannels")
        + _function(MAP, "wbRelativeLuminance")
        + _function(MAP, "wbCoreInkFor")
        + _function(MAP, "wbReadableInk")
        + f"console.log(JSON.stringify(wbReadableInk({json.dumps(ink)}, {json.dumps(bg)})));"
    )
    return _node(script)


@pytest.mark.parametrize(
    ("ink", "bg"),
    [("#000000", "#1e1e1c"), ("#ffffff", "#fff4a3"), ("#ffffff", "rgb(255, 244, 163)"), ("#000000", "#101820")],
)
def test_an_ink_that_cannot_be_read_is_swapped_for_one_that_can(ink, bg):
    out = _ink(ink, bg)
    hexbg = "#1e1e1c" if bg == "#1e1e1c" else "#fff4a3" if "244" in bg or bg == "#fff4a3" else bg
    assert _ratio(out, hexbg) >= 4.5


def test_a_readable_ink_is_left_alone():
    assert _ink("#2a2a1f", "#fff4a3") == "#2a2a1f"
    assert _ink("#ff8800", "#000000") == "#ff8800"
    assert _ink("#ffffff", "not a colour") == "#ffffff"


def test_default_ink_is_remapped_at_render_for_strokes_and_text():
    assert "wbDefaultInk(parsed.color)" in WB
    assert "wbReadableInk(d.data.color, d.data.bg || wbBoardBg())" in WB
    body = _function(WB, "wbDefaultInk")
    assert '"#000000"' in body and '"#ffffff"' in body and "wbBoardBg()" in body


# U3 -------------------------------------------------------------------------


def test_insert_sticky_from_the_keyboard_places_one_in_view():
    start = WB.index('document.getElementById("wb-insert-menu")?.addEventListener("click"')
    body = WB[start : start + 900]
    assert 'what === "sticky" && e.detail === 0' in body
    assert "wbCreateSticky(...wbViewCentre())" in body


# U5 -------------------------------------------------------------------------


def test_the_fold_chevron_and_count_keep_a_24px_floor_and_44_on_touch():
    rule = LAZY[LAZY.index("\n.wb-map-collapse {") :][:900]
    assert "scale(clamp(calc(24 / 28 * var(--wb-inv-zoom)), 1, var(--wb-inv-zoom)))" in rule
    assert "translate: 0 -50%" in rule
    coarse = LAZY[LAZY.index("@media (pointer: coarse) {\n  .wb-map-collapse") :][:400]
    assert "scale(var(--wb-inv-zoom))" in coarse
    count = LAZY[LAZY.index("\n.wb-map-count {") :][:1800]
    assert "scale(max(1, var(--wb-inv-zoom)))" in count and "min-width: 1.5rem" in count
    down = MISC[MISC.index(".wb-map-down .wb-map-collapse {") :][:200]
    assert "transform" not in down and "translate: 50% 0" in down
    listed = WB[WB.index("const WB_INV_ZOOM_GRIPS") :][:900]
    assert '".wb-map-collapse"' in listed and '".wb-map-count"' in listed


def test_the_node_action_buttons_floor_is_24_not_20():
    rule = LAZY[LAZY.index("\n.wb-map-actions {\n  transform: scale(") :][:200]
    assert "24 / 28" in rule
    coarse = LAZY[LAZY.index("@media (pointer: coarse) {\n  .wb-map-actions") :][:200]
    assert "scale(var(--wb-inv-zoom))" in coarse
