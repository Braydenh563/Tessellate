"""Batch BG1 (diagram rows of OPEN.md): the foot says what the bare arrow on a row does, and the picture's connect
handle and end dots clear 3:1 against their own disc in the default light and dark themes."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STEPS = (ROOT / "frontend" / "js" / "diagram-steps.js").read_text(encoding="utf-8")
TOKENS = (ROOT / "frontend" / "css" / "00-tokens-shell.css").read_text(encoding="utf-8")


def _lum(rgb):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = (ch(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _ratio(a, b):
    hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _hex(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def test_tight_list_foot_names_the_row_arrow():
    # D1.3: the words of Connect to… are hidden in a list under 19rem (a 224 px list at 1440), so the foot says what the arrow does.
    assert "The arrow on a block, or Connect, draws an arrow from it." in STEPS


def test_connect_handle_and_end_dots_clear_three_to_one():
    # 1661 f: the ring and glyph are --accent on --modal-bg (diagram-lazy.css .dgm-handle, .dgm-end); default light and dark.
    assert _ratio(_hex("#4664f0"), (252, 253, 255)) >= 3  # light: --modal-bg rgba(252, 253, 255, .96)
    assert _ratio(_hex("#8b9df8"), (24, 27, 37)) >= 3  # dark: --modal-bg rgba(24, 27, 37, .97)
    assert "--accent: #4664f0;" in TOKENS and "--accent: #8b9df8;" in TOKENS
