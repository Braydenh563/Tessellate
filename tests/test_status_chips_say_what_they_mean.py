"""Every warning chip in the status bar says what it means on hover and on click
(L-world-class-104). The AI dot's "!" already opens its popup; the two amber
chips (Saver on, Offline) had a short title and nothing on click, and a touch
screen has no hover.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
WIRING = (ROOT / "frontend/js/wiring.js").read_text(encoding="utf-8")


def _chip(chip_id):
    return re.search(rf'<span id="{chip_id}"[^>]*>', HTML, re.S).group(0)


def test_every_warning_chip_in_the_bar_has_a_sentence_for_a_title():
    bar = HTML[HTML.index('<footer id="status-bar"'):]
    bar = bar[: bar.index("</footer>")]
    chips = re.findall(r'<span id="([\w-]+)" class="chip warning[^"]*"[^>]*', bar)
    assert set(chips) == {"power-saver-indicator", "offline-indicator"}, chips
    for chip_id in chips:
        title = re.search(r'title="([^"]*)"', _chip(chip_id), re.S).group(1)
        assert len(title.split()) >= 8 and title.endswith("."), (chip_id, title)
        assert "!" not in title


def test_power_saver_says_what_it_pauses_and_where_the_switch_is():
    title = re.search(r'title="([^"]*)"', _chip("power-saver-indicator")).group(1)
    assert "background" in title and "Settings" in title


def test_a_click_on_either_chip_says_it_too():
    block = WIRING[WIRING.index("status-chip-says"):]
    block = block[: block.index("\n\n")]
    assert "power-saver-indicator" in block and "offline-indicator" in block
    assert 'toast(chip.title, "info")' in block
