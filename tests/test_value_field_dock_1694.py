"""A value field in a dock reads as part of its control (INBOX 1694 c).

The owner, 2026-11-08: the sketch pad's size number "clashes with the slider border and it doesnt look like
it belongs in the slider". Measured: the dock's text-field rule (`.dock input:not(...)`, 0,4,1) outranked
`.value-field .value-field-input` (0,2,0), so the number drew the dock's filled box, 34 px tall in a 32 px pill,
and the slider's own track drew the same fill. The dock rules leave both alone."""

import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "frontend" / "css"


def _dock_input_selectors(name: str) -> list[str]:
    text = re.sub(r"/\*.*?\*/", "", (CSS / name).read_text(encoding="utf-8"), flags=re.S)
    return re.findall(r"\.dock input:not\([^{,]*?\)(?::not\([^{]*?\))*", text)


def test_the_dock_field_rules_skip_value_fields_and_the_fill_skips_sliders():
    found = _dock_input_selectors("07-whiteboard-misc.css")[:1] + _dock_input_selectors("08-consistency.css")
    assert len(found) == 2, found
    for sel in found:
        assert ".value-field-input" in sel, sel
    #: The fill is 08's; 07 sets only the height, which a slider in a dock keeps.
    assert '[type="range"]' in found[1], found[1]


def test_the_sketch_size_slider_rule_names_the_slider_only():
    """`.sp-size input` reached the typed number too; the slider's own track is see-through in the pill."""
    text = (CSS / "sketch-pad.css").read_text(encoding="utf-8")
    assert not re.search(r"\.sp-size input\s*\{", text)
    rule = re.search(r'\.sp-size input\[type="range"\]\s*\{([^}]*)\}', text)
    assert rule and "background: transparent" in rule.group(1)
