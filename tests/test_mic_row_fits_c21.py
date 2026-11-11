"""W20 C21: the Microphone row in Settings was 14 px wider than the 360 px sheet (an 83 px label and a 180 px select in a
234 px flex row), so Settings scrolled sideways. The device row is a grid whose select column shrinks. Measured in
Chromium at 360, 390 and 1280: scrollWidth equals clientWidth, the select stays on the right at 1280."""

from pathlib import Path

CSS = (Path(__file__).resolve().parents[1] / "frontend" / "css" / "meetings-lazy.css").read_text(encoding="utf-8")


def test_the_device_row_is_a_grid_with_a_shrinking_select_column() -> None:
    rule = CSS.split(".mic-controls .setting-row:has(> .select-shell) {", 1)[1].split("}", 1)[0]
    assert "display: grid" in rule
    assert "minmax(0, 1fr)" in rule  # the select's column may shrink below its text


def test_the_select_stays_on_the_right_and_within_the_row() -> None:
    rule = CSS.split(".mic-controls .setting-row > .select-shell {", 1)[1].split("}", 1)[0]
    assert "justify-self: end" in rule
    assert "max-width: 100%" in rule
