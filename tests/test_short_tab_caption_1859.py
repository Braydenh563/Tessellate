"""Below 480px the Dashboard tab reads "Home" (INBOX 1859, L-world-class-83).

Measured 2026-11-14 with getBoundingClientRect on the phone dock at 390, 360
and 320 (Playwright, `.tab-label` text range): the Dashboard caption is the
only long one, 62.6px in a 78, 72 and 64px column, 1.4px of air at 320. Every
other caption is 40.4px or less. The word swaps by CSS (`data-short`), so the
text the palette, the More sheet and Settings search read stays "Dashboard",
and the aria-label and tooltip keep the full name.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")


def test_the_dashboard_caption_carries_a_short_word_and_keeps_its_name():
    button = HTML[HTML.index('id="tab-btn-dashboard"') :].split("</button>", 1)[0]
    assert '<span class="tab-label" data-short="Home">Dashboard</span>' in button
    assert 'aria-label="Dashboard" title="Dashboard (t then d)"' in button


def test_only_the_dashboard_has_a_short_word():
    assert HTML.count('class="tab-label" data-short=') == 1


def test_the_swap_is_in_both_phone_bands_and_no_new_breakpoint():
    for head in ("@media (max-width: 359.98px) {", "@media (min-width: 360px) and (max-width: 479.98px) {"):
        block = CSS[CSS.index(head) :]
        block = block[: block.index("\n}\n")]
        assert "#tab-btn-dashboard .tab-label::after" in block, head
        assert "content: attr(data-short)" in block, head
    assert "content: attr(data-short)" not in CSS.split("@media (max-width: 359.98px) {")[0]
