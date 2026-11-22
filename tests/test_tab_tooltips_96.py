"""Tab labels hold down to 820px and every tab's tooltip names its chord
(22.1.3, L-world-class-96).

Measured 2026-11-14 with getBoundingClientRect on `.tab-label` at 1024, 1100
and 1280 (and 900): every label has width above 0 (Dashboard 63px, Reminders
61px at 1024). Under 820 an inactive tab is an icon, so its tooltip is the
only name a pointer gets. The titles are markup (no boot-script bytes: the
gzip ratchet), and this test holds them to `TAB_JUMP_KEYS`.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WIRING = (ROOT / "frontend" / "js" / "settings-wiring.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
CSS = "\n".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "frontend" / "css").glob("*.css")))


def test_every_tab_title_names_its_jump_key():
    table = WIRING[WIRING.index("const TAB_JUMP_KEYS = {"):]
    pairs = re.findall(r'(\w): "(\w+)"', table[: table.index("};")])
    assert len(pairs) == 7
    for key, tab in pairs:
        name = tab.capitalize()
        assert f'id="tab-btn-{tab}"' in HTML
        assert f'aria-label="{name}" title="{name} (t then {key})"' in HTML, tab


def test_no_label_is_hidden_between_820_and_1100():
    """The captions go only in the bands below 820 (the 1717 zoom pass)."""
    for m in re.finditer(r"@media \(([^)]*)\)[^{]*\{", CSS):
        low = re.search(r"min-width:\s*(\d+)", m.group(1))
        if low and int(low.group(1)) >= 820:
            body = CSS[m.end(): m.end() + 400]
            assert "#tab-bar button:not(.active) .tab-label {\n    display: none" not in body
