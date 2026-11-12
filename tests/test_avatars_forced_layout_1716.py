"""The companion's poke and its drawing step do not restyle the page more than they must (INBOX 1716).

A browser cannot run in pytest, so these are static. The measured sweep (4x CPU throttle, 2560x1504 at
device scale 2, the Library Images tab with 240 tiles, about 20,000 nodes) is in the CHANGELOG line: a cold
face drawn with its measuring host inside `<body>` took a median 140ms and 65ms under `<html>`, and a poke
no longer reads layout in its own task (`poke` 229/176, 245/217 and 108/101ms of script/forced layout
before; 31/9 at best after, where what remains is the figure swap's and the blend's own reads).
"""

from __future__ import annotations

from pathlib import Path
from tests._js_scope import unwrapped

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _src() -> str:
    return unwrapped((JS / "avatars.js").read_text(encoding="utf-8"))


def _body(src: str, head: str) -> str:
    start = src.index(head)
    return src[start : src.index("\n}\n", start) + 2]


def test_the_measuring_host_is_outside_the_body() -> None:
    body = _body(_src(), "function nameMarkRasterise(")
    assert "document.documentElement.appendChild(nameMarkMeasureHost)" in body
    assert "document.body.appendChild(nameMarkMeasureHost)" not in body, "a node added inside body restyles every :has() subject in it"


def test_a_poke_hop_restarts_with_a_layout_read_only_when_one_is_playing() -> None:
    body = _body(_src(), "function nameMarkReact(")
    assert body.index('if (svg.classList.contains("nm-react"))') < body.index("getBoundingClientRect"), "the read is inside the restart branch"
    assert body.count("getBoundingClientRect") == 1


def test_a_speech_bubble_is_measured_a_frame_on_not_in_the_poke_task() -> None:
    body = _body(_src(), "function nameMarkSay(")
    assert body.index("afterFrames(") < body.index("getBoundingClientRect"), "the edge shift is read before the frame is drawn, not in the caller's task"
    assert "requestAnimationFrame" not in body, "the file's own frame helper, not a new wake source (test_frontend_wake_sources.py)"
    assert "}, 1);" in body, "one frame: the first, which runs before it paints"
    assert "if (!bubble.isConnected) return;" in body, "a bubble already replaced or removed is not measured"
    assert body.count("getBoundingClientRect") == 1
