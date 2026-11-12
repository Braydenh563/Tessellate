"""The iPhone sweep's fixes (safe areas, field size, dialogs), held at the source.

`scratchpad/ui-sweeps/iphone1011.js` measures them in a browser with an
iPhone's user agent, touch and the notch set through DevTools; these say the
rules it found missing stay written.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._css_paths import FORMER_10, sheets

ROOT = Path(__file__).resolve().parents[1]
FRONT = ROOT / "frontend"


def _css(name: str) -> str:
    return re.sub(r"/\*.*?\*/", "", (FRONT / "css" / name).read_text(encoding="utf-8"), flags=re.S)


def test_viewport_lets_ios_report_the_safe_areas():
    """Without `viewport-fit=cover` iOS reports every `env(safe-area-inset-*)`
    as 0, so none of the app's inset rules ever applied on an iPhone."""
    html = (FRONT / "index.html").read_text(encoding="utf-8")
    meta = re.search(r'<meta name="viewport" content="([^"]*)"', html)
    assert meta and "viewport-fit=cover" in meta.group(1)


def test_field_text_is_the_body_size_under_a_finger():
    """iOS zooms into a field under 16px on focus; 16 fields measured 13.6px."""
    css = sheets(*FORMER_10)
    block = re.search(r"@media \(pointer: coarse\) \{\s*:is\(input, textarea, select\) \{([^}]*)\}", css)
    assert block, "the coarse-pointer field token block is missing"
    for token in ("--text-xs", "--text-sm", "--text-base", "--text-md"):
        assert f"{token}: var(--text-body)" in block.group(1)


def test_a_dialog_keeps_out_of_the_notch_and_the_home_indicator():
    css = sheets(*FORMER_10)
    rule = re.search(r"\.modal-overlay:not\(\.sheet-overlay\) \{([^}]*)\}", css)
    assert rule
    for edge in ("top", "right", "bottom", "left"):
        assert f"padding-{edge}: max(var(--space-8), env(safe-area-inset-{edge}, 0px))" in rule.group(1)
    assert "max-height: min(96dvh, 100%)" in css


def test_the_note_page_head_clears_the_notch():
    css = sheets(*FORMER_10)
    assert re.search(r"\.sheet-card-page \{\s*padding-top: calc\(var\(--card-pad-y\) \+ env\(safe-area-inset-top, 0px\)\);", css)


def test_the_sweep_is_kept():
    sweep = (ROOT / "scratchpad" / "ui-sweeps" / "iphone1011.js").read_text(encoding="utf-8")
    for needle in ("setSafeAreaInsetsOverride", "synthesizeScrollGesture", "viewport-fit=cover", "430x932"):
        assert needle in sweep
