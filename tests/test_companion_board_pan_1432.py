"""INBOX 1432, the owner: "when I move the companion the board pans a bit with it
as well". While the companion is held, nothing pans the board, and a pan that
tries is logged with its source so the owner's next log names the path."""

from pathlib import Path

JS_DIR = Path(__file__).resolve().parents[1] / "frontend" / "js"
JS = (JS_DIR / "avatars.js").read_text(encoding="utf-8") + "\n" + (JS_DIR / "whiteboard.js").read_text(encoding="utf-8")


def _body(name: str) -> str:
    start = JS.index(f"function {name}(")
    return JS[start : JS.index("\n}\n", start)]


def test_the_press_marks_the_companion_held_and_every_way_out_clears_it():
    assert "nmb.grabbed = true;" in JS
    assert "nmb.grabbed = false" in JS[JS.index("const release = (event) => {") :][:80]
    assert 'face.addEventListener("lostpointercapture", release)' in JS


def test_the_board_zoom_and_edge_pan_refuse_while_held():
    assert _body("wbZoomFilter").splitlines()[1].strip().startswith("if (wbCompanionHeld(event")
    assert '.on("start.companion"' in JS
    edge = JS[JS.index("function wbEdgePanWanted("):]
    assert "wbCompanionHeld(null" in edge[: edge.index("\n  }\n")]


def test_a_refused_pan_is_logged_once_a_press():
    held = _body("wbCompanionHeld")
    assert 'nmb.grabbed = "logged"' in held
    assert "lagNote(" in held
