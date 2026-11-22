"""Function lengths in lines across the app's scripts, for the JS size ratchet (L-whiteboard-78)."""

from __future__ import annotations

from pathlib import Path

from tests._js_functions import function_spans
from tests._js_scope import is_wrapped

ROOT = Path(__file__).resolve().parents[1]
CAP = 150  # lines; a body longer than this is seeded and may only shrink


def sizes() -> dict[str, int]:
    """`file::name` to the longest such body over CAP; the file's own wrapper closure is not a function."""
    out: dict[str, int] = {}
    for path in sorted((ROOT / "frontend" / "js").glob("*.js")) + [ROOT / "frontend" / "sw.js"]:
        text = path.read_text(encoding="utf-8")
        spans = function_spans(text)
        if is_wrapped(text) and spans:
            spans.remove(max(spans, key=lambda s: s[1] - s[0]))
        for start, end, name in spans:
            lines = text.count("\n", start, end) + 1
            key = f"{path.name}::{name}"
            if lines > CAP and lines > out.get(key, 0):
                out[key] = lines
    return out
