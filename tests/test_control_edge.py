"""The edge of anything you aim at holds 3:1 through one token (INBOX 464).

`scratchpad/ui-sweeps/contrastui.js` measures non-text contrast (WCAG 1.4.11)
on a running app: on the default look at 1440 it found 37 text fields, select
openers and date inputs whose edge was 1.2 to 2.3:1 against their card, 25
selected segments and options told apart by a tint of 1.15 to 1.25:1, two
icons dimmed by `opacity`, and a field hover that was weaker than the resting
edge. The fix is one token, `--control-edge` (a step stronger than the quiet
button's measured `--ghost-btn-border`), and these pins keep a later stylesheet from
going back to a hand-mixed near-miss. The numbers themselves are the sweep's;
this file holds the shapes it cannot hold.
"""

from __future__ import annotations

import re
from pathlib import Path
from tests._css_paths import FORMER_08

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / "frontend" / "css"


def _css(name: str) -> str:
    return re.sub(r"/\*.*?\*/", "", (CSS / name).read_text(encoding="utf-8"), flags=re.S)


def _all_css() -> dict[str, str]:
    return {p.name: _css(p.name) for p in sorted(CSS.glob("*.css"))}


def test_control_edge_is_one_token_with_a_value_per_mode() -> None:
    # Light, the dark block and the OS-dark block: three literals in the
    # tokens file, never a hand-mixed value in a rule. (Light is 0.58 ink and
    # dark 0.40 white; the sweep measures 3:1 on a card and on a grey well.)
    tokens = _css("00-tokens-shell.css")
    values = re.findall(r"--control-edge:\s*(rgba\([^)]*\));", tokens)
    assert values == [
        "rgba(31, 36, 48, 0.58)",
        "rgba(255, 255, 255, 0.4)",
        "rgba(255, 255, 255, 0.4)",
    ]
    elsewhere = [n for n, t in _all_css().items() if n != "00-tokens-shell.css" and re.search(r"--control-edge:\s*(rgba?|#|color-mix)", t)]
    assert not elsewhere


def test_high_contrast_makes_the_control_edge_ink() -> None:
    text = _css("02-chat-graph.css")
    block = re.search(r':root\[data-contrast="on"\]\s*\{([^}]*)\}', text)
    assert block and "--control-edge: var(--ink);" in block.group(1)


def test_fields_do_not_mix_their_own_edge() -> None:
    # The hand-mixed edge this replaced: `--border` 60% with ink 25%, 1.4 to
    # 2.3:1 on a card depending on the glass setting.
    for name, text in _all_css().items():
        assert "var(--border) 60%, var(--ink) 25%" not in text, name
    forms = _css("01-forms-settings.css")
    base = re.search(r"input\[type=\"datetime-local\"\]\s*\{([^}]*)\}", forms)
    assert base and "border: 1px solid var(--control-edge);" in base.group(1)


def test_a_field_hover_is_never_weaker_than_its_resting_edge() -> None:
    text = _css("07-whiteboard-misc.css")
    hover = re.search(r"textarea:hover:not\(:focus\)[^{]*\{([^}]*)\}", text)
    assert hover and "var(--control-edge)" in hover.group(1)
    opener = re.search(r"\.select-opener:hover:not\(\[disabled\]\)[^{]*\{([^}]*)\}", text)
    assert opener and "var(--control-edge)" in opener.group(1)


def test_a_selected_segment_and_a_chosen_option_carry_an_edge_not_only_a_tint() -> None:
    text = "\n".join(_css(n) for n in FORMER_08)
    flat = re.findall(r"background: color-mix\(in srgb, var\(--ink\) 11%, transparent\);[^}]*\}", text)
    assert len(flat) == 2
    assert all("inset 0 0 0 1px var(--control-edge)" in rule for rule in flat)
    assert re.search(
        r"\.check-row:has\(input\[type=\"radio\"\]:checked\)[^{]*\{[^}]*inset 0 0 0 1px var\(--accent-text\)",
        text,
    )


def test_no_icon_is_dimmed_by_opacity_where_the_sweep_caught_one() -> None:
    assert "opacity" not in re.search(r"\.ph-trail\s*\{([^}]*)\}", _css("07-whiteboard-misc.css")).group(1)
    caret = re.search(r"\.wb-shape-caret\s*\{([^}]*)\}", _css("06-timeline-dialogs.css"))
    assert caret and "opacity" not in caret.group(1)
