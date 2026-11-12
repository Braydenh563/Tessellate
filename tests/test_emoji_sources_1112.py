"""L296: the Markdown :shortcode: table is a subset of the icon picker's emoji (no drift).

The two tables use different names (GitHub shortcodes against Unicode names), so they stay
two tables; what must never differ is the glyphs. Every glyph a shortcode types is in the
picker, so a person can pick the same emoji the colon menu offers.
"""

from __future__ import annotations

import re
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _glyphs(block: str) -> set[str]:
    text = "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', block))
    text = re.sub(r"\\u\{([0-9A-Fa-f]+)\}", lambda m: chr(int(m.group(1), 16)), text)
    out = set()
    for pair in text.split(","):
        name, eq, glyph = pair.partition("=")
        if eq and glyph:
            out.add(glyph.replace("\ufe0f", ""))
    return out


def test_every_shortcode_glyph_is_in_the_picker():
    prose = (JS / "documents-prose.js").read_text(encoding="utf-8")
    start = prose.index("const DOC_EMOJI_SOURCE")
    shortcodes = _glyphs(prose[start : prose.index("let docEmojiTable", start)])
    picker = (JS / "icon-picker.js").read_text(encoding="utf-8")
    start = picker.index("const ICON_EMOJI_SOURCE = [")
    full = _glyphs(picker[start : picker.index("\n  ];", start)])
    assert len(shortcodes) > 200
    assert shortcodes - full == set()
